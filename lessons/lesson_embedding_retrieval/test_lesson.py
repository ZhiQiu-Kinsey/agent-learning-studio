"""Behavior tests for embedding-retrieval: offline test vectors from the fixture; batching, saving, staleness checks, cosine search and BM25 really run in Python."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from course.execution import EmbeddingNotConfigured, RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_document_loading.chunking import default_chunks
from lessons.lesson_document_loading.loader import corpus_version, load_corpus
from lessons.lesson_embedding_retrieval import runtime
from lessons.lesson_embedding_retrieval.fixtures import concept_vector, create_embedding
from lessons.lesson_embedding_retrieval.locales import texts_for
from lessons.lesson_embedding_retrieval.vector_index import VectorIndex
from lessons.lesson_keyword_retrieval.query_set import judge, load_queries

LOCALES = ("zh-CN", "en")
CJK = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")
PRESETS = json.loads((Path(runtime.__file__).parent / "lesson.json").read_text(encoding="utf-8"))
QUERY = PRESETS["input_defaults"]["query"]
SUNDAY = PRESETS["exercises"][2]["inputs"]["query"]


def run_case(inputs, locale="zh-CN", *, embedding=None, budget=12, cancelled=lambda: False,
             model="offline-embedding", mode="offline"):
    events = []
    values = validate_inputs(runtime, {"query": QUERY[locale], **inputs})
    context = RunContext(
        lesson_id="embedding-retrieval", exercise_id="test", question="", mode=mode, model="chat-model",
        representation="sdk_standardized", inputs=values, api_key="", completion=None,
        emit_event=lambda kind, data, number: events.append((kind, data, number)),
        cancelled=cancelled, max_model_calls=budget, locale=locale,
        embedding=embedding or create_embedding("test", values, locale), embedding_model=model,
        embedding_batch_limit=10,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def reports(events, title_field, locale):
    title = getattr(texts_for(locale), title_field)
    return [data for data in of(events, "lesson.report") if data["title"] == title]


def metrics(report):
    return {item["id"]: item["value"] for item in report["metrics"]}


def checks(report):
    return {item["id"]: item["passed"] for item in report["checks"]}


class SavedIndexCase(unittest.TestCase):
    """Runs share one index folder, as live runs share .runtime/."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        previous = runtime.OFFLINE_INDEX_DIR
        runtime.OFFLINE_INDEX_DIR = self.folder
        self.addCleanup(setattr, runtime, "OFFLINE_INDEX_DIR", previous)

    def saved(self, locale="zh-CN", size=256):
        return VectorIndex.load(self.folder / ".runtime" / "rag-index" / locale / f"offline-embedding-{size}.json")


class InputTests(unittest.TestCase):
    def test_inputs_are_validated(self):
        good = {"query": "q"}
        self.assertEqual(validate_inputs(runtime, good)["dimensions"], 256)
        for bad in ({}, {"query": ""}, {"query": "q", "top_k": 0}, {"query": "q", "top_k": 11},
                    {"query": "q", "dimensions": 300}, {"query": "q", "doc_filter": "unknown"},
                    {"query": "q", "task": "stale", "change": "dimensions", "dimensions": 512, "new_dimensions": 512},
                    {"query": "q", "extra": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)

    def test_corpus_version_matches_the_loader(self):
        for locale in LOCALES:
            documents, _ = load_corpus(locale)
            self.assertEqual(runtime.corpus_version_of(documents), corpus_version(locale))


class FixtureTests(unittest.TestCase):
    def test_synonyms_share_a_dimension_and_codes_have_none(self):
        late, overdue = concept_vector("滞纳金", "zh-CN"), concept_vector("逾期费用", "zh-CN")
        self.assertEqual(late, overdue)
        self.assertEqual(concept_vector("late fee", "en"), concept_vector("overdue charge", "en"))
        self.assertEqual(concept_vector("R-305", "en"), concept_vector("B2", "en"))
        self.assertEqual(len(concept_vector("x", "en", 128)), 128)
        with self.assertRaises(ValueError):
            concept_vector("x", "en", 4)

    def test_response_has_one_vector_per_input_at_the_requested_size(self):
        reply = create_embedding("test", {}, "en")({"model": "m", "input": ["a", "b"], "dimensions": 128}, "")
        self.assertEqual([len(item["embedding"]) for item in reply["data"]], [128, 128])
        self.assertEqual([item["index"] for item in reply["data"]], [0, 1])


class SearchTests(SavedIndexCase):
    def test_first_run_embeds_chunks_in_batches_then_the_query(self):
        for locale, sizes in (("zh-CN", [10, 10, 10, 8, 1]), ("en", [10, 10, 10, 6, 1])):
            with self.subTest(locale=locale):
                answer, events = run_case({"task": "search"}, locale)
                requests = of(events, "request")
                self.assertEqual([len(request["body"]["input"]) for request in requests], sizes)
                self.assertTrue(all(request["endpoint"] == "embeddings" for request in requests))
                self.assertTrue(all(request["body"]["dimensions"] == 256 for request in requests))
                self.assertEqual([number for kind, _, number in events if kind == "request"], [1, 2, 3, 4, 5])
                index = metrics(reports(events, "index_title", locale)[0])
                self.assertEqual(index["index_status"], texts_for(locale).status_built)
                self.assertEqual((index["embedding_model"], index["dimensions"], index["corpus_version"]),
                                 ("offline-embedding", 256, corpus_version(locale)))
                self.assertEqual(index["vector_source"], texts_for(locale).source_test)
                result = reports(events, "search_title", locale)[0]
                # The paraphrased late-fee query finds the overdue section by meaning.
                self.assertTrue(result["table"]["rows"][0][1].startswith("fees:"))
                self.assertIn("fees#overdue", result["table"]["rows"][0][3])
                self.assertIn(result["table"]["rows"][0][1], answer)
                saved = self.saved(locale)
                self.assertEqual(saved.chunk_ids, [chunk.chunk_id for chunk in default_chunks(locale)])

    def test_anchor_marks_never_reach_the_embedding_requests(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                _, events = run_case({"task": "search"}, locale)
                texts = [text for request in of(events, "request") for text in request["body"]["input"]]
                self.assertEqual(len(texts), len(default_chunks(locale)) + 1)
                self.assertFalse([text for text in texts if "{#" in text])
                self.assertTrue(all("{#" in chunk.text for chunk in default_chunks(locale)[:3]))

    def test_second_run_reuses_the_saved_index(self):
        run_case({"task": "search"})
        _, events = run_case({"task": "search"})
        self.assertEqual(len(of(events, "request")), 1)
        index = metrics(reports(events, "index_title", "zh-CN")[0])
        self.assertEqual((index["index_status"], index["index_calls"]), (texts_for("zh-CN").status_reused, 0))
        self.assertIn(".runtime/rag-index/zh-CN/offline-embedding-256.json", index["index_file"])
        self.assertNotIn(str(self.folder), json.dumps(events, ensure_ascii=False))

    def test_index_from_another_model_or_a_damaged_file_is_rebuilt(self):
        run_case({"task": "search"})
        _, events = run_case({"task": "search"}, model="another-model")
        self.assertEqual(len(of(events, "request")), 5)  # another model means another file
        path = self.folder / ".runtime" / "rag-index" / "zh-CN" / "offline-embedding-256.json"
        old = self.saved()
        VectorIndex("another-model", 256, old.corpus_version, old.chunk_ids, old.vectors).save(path)
        _, events = run_case({"task": "search"})
        index = metrics(reports(events, "index_title", "zh-CN")[0])
        self.assertEqual(index["index_status"], texts_for("zh-CN").status_rebuilt)
        self.assertIn("model", index["stale_reasons"])
        self.assertEqual(self.saved().model, "offline-embedding")
        path.write_text("{not json", encoding="utf-8")
        _, events = run_case({"task": "search"}, "en")  # another language, another file: still built
        _, events = run_case({"task": "search"})
        index = metrics(reports(events, "index_title", "zh-CN")[0])
        self.assertIn("JSONDecodeError", index["stale_reasons"])

    def test_same_corpus_with_other_chunks_is_stale(self):
        t = texts_for("en")
        index = VectorIndex("m", 2, "v1", ["a:1-2", "a:3-4"], [[1.0, 0.0], [0.0, 1.0]])
        self.assertEqual(runtime.stale_reasons(t, index, model="m", dimensions=2, version="v1",
                                               chunk_ids=["a:1-2", "a:3-4"]), [])
        reasons = runtime.stale_reasons(t, index, model="m", dimensions=2, version="v1", chunk_ids=["a:1-4"])
        self.assertEqual(reasons, [t.reason_chunks.format(removed=2, added=1)])

    def test_metadata_filter_applies_before_ranking(self):
        _, events = run_case({"task": "search", "doc_filter": "rooms", "top_k": 3})
        rows = reports(events, "search_title", "zh-CN")[0]["table"]["rows"]
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row[1].startswith("rooms:") for row in rows))


class CompareTests(unittest.TestCase):
    def test_both_retrievers_answer_the_same_query_set(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_case({"task": "compare"}, locale)
                self.assertEqual([len(r["body"]["input"]) for r in of(events, "request")][-2:], [10, 4])
                report = reports(events, "compare_title", locale)[0]
                values = metrics(report)
                self.assertEqual((values["bm25_hits"], values["vector_hits"]), ("9/12", "11/12"))
                self.assertEqual((values["only_bm25"], values["only_vector"]), (1, 3))
                self.assertEqual(values["no_answer_returned"], "q07: 5, q08: 5")
                self.assertEqual(checks(report), {"same_queries": True, "same_chunks": True})
                verdicts = {row[0]: row[5] for row in report["table"]["rows"]}
                t = texts_for(locale)
                self.assertEqual(verdicts["q02"], t.verdicts["10"])  # a room number: keywords win
                for query in ("q04", "q05", "q06"):  # paraphrases: vectors win
                    self.assertEqual(verdicts[query], t.verdicts["01"])
                self.assertEqual(verdicts["q07"], t.verdict_no_gold)
                self.assertIn("9", answer)


class LessonTextClaimTests(unittest.TestCase):
    """Facts the lesson text quotes about the offline run (content.json section-4, the quiz and the misconception).

    The fixture vectors are by construction, so these numbers are stable; if one changes, the text must change too."""

    def search(self, locale, query_id):
        chunks = default_chunks(locale)
        index = VectorIndex("test", 256, "v", [chunk.chunk_id for chunk in chunks],
                            [concept_vector(runtime.embedding_text(chunk), locale, 256) for chunk in chunks])
        query = next(query for query in load_queries(locale) if query.id == query_id)
        hits = index.search(concept_vector(query.text, locale, 256), 5)
        by_id = {chunk.chunk_id: chunk for chunk in chunks}
        return query, hits, [by_id[hit.chunk_id] for hit in hits]

    def test_sunday_query_ranks_the_wish_in_the_top_three_and_the_rule_fifth(self):
        reader_note_rank = {"zh-CN": 1, "en": 3}
        for locale in LOCALES:
            with self.subTest(locale=locale):
                query, hits, found = self.search(locale, "q13")
                ranks = [rank for rank, chunk in enumerate(found, start=1)
                         if chunk.doc_id == "reader-notes" and any(a.endswith("#note-hours") for a in chunk.anchors)]
                self.assertEqual(ranks[0], reader_note_rank[locale])
                verdict = judge(found, query)
                self.assertEqual((verdict["hit"], verdict["first_rank"], verdict["complete"]), (True, 5, False))

    def test_no_answer_queries_still_get_a_high_score(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                for query_id in ("q07", "q08"):
                    query, hits, _ = self.search(locale, query_id)
                    self.assertEqual(len(hits), 5)
                    self.assertGreaterEqual(hits[0].score, 0.75)


class StaleTests(SavedIndexCase):
    def test_new_dimensions_refuse_the_old_index_and_get_their_own_file(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_case({"task": "stale", "change": "dimensions", "query": SUNDAY[locale]}, locale)
                sizes = [request["body"]["dimensions"] for request in of(events, "request")]
                self.assertEqual(sizes, [256] * 4 + [512] * 5)
                report = reports(events, "stale_title", locale)[0]
                self.assertEqual(checks(report), {"stale_detected": True, "size_guard": True,
                                                  "separate_files": True, "new_results_clean": True})
                self.assertEqual(self.saved(locale, 512).dimensions, 512)
                self.assertEqual(self.saved(locale, 256).dimensions, 256)
                self.assertIn("256", answer)

    def test_retired_document_makes_the_old_index_stale_without_overwriting_it(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                _, events = run_case({"task": "stale", "change": "corpus", "query": SUNDAY[locale]}, locale)
                self.assertEqual(len(of(events, "request")), 9)
                report = reports(events, "stale_title", locale)[0]
                self.assertEqual(checks(report), {"stale_detected": True, "orphans": True,
                                                  "old_results_leak": True, "new_results_clean": True})
                old_column = [row[1] for row in report["table"]["rows"]]
                new_column = [row[2] for row in report["table"]["rows"]]
                self.assertTrue(any(cell.startswith("hours-2025:") for cell in old_column))
                self.assertFalse(any(cell.startswith("hours-2025:") for cell in new_column))
                new_index = metrics(reports(events, "index_title", locale)[1])
                self.assertEqual(new_index["index_file"], texts_for(locale).location_memory)
                # The saved index still describes the real corpus.
                self.assertEqual(self.saved(locale).corpus_version, corpus_version(locale))


class FailureTests(unittest.TestCase):
    def test_wrong_vector_size_stops_the_run(self):
        def embedding(body, api_key):
            return {"data": [{"index": i, "embedding": [1.0] * 1024} for i, _ in enumerate(body["input"])]}
        for locale in LOCALES:
            with self.assertRaises(ValueError) as caught:
                run_case({"task": "search"}, locale, embedding=embedding)
            self.assertEqual(str(caught.exception), texts_for(locale).size_mismatch.format(asked=256, got=1024))

    def test_usage_the_provider_does_not_report_stays_not_reported(self):
        plain = create_embedding("test", {}, "en")

        def embedding(body, api_key):
            reply = plain(body, api_key)
            del reply["usage"]
            return reply
        _, events = run_case({"task": "search"}, "en", embedding=embedding)
        self.assertEqual(metrics(reports(events, "search_title", "en")[0])["embedding_usage"], "not reported")

    def test_embedding_requests_count_against_the_call_budget(self):
        with self.assertRaises(RuntimeError):
            run_case({"task": "search"}, budget=4)

    def test_cancelled_run_sends_nothing(self):
        with self.assertRaises(RunCancelled):
            run_case({"task": "search"}, cancelled=lambda: True)

    def test_missing_embedding_model_is_the_platform_error(self):
        with self.assertRaises(EmbeddingNotConfigured) as caught:
            run_case({"task": "search"}, model=None, mode="live")
        self.assertEqual(caught.exception.code, "embedding_model_missing")


class LocaleTests(unittest.TestCase):
    def test_english_runs_contain_no_chinese(self):
        for inputs in ({"task": "search"}, {"task": "compare"},
                       {"task": "stale", "change": "dimensions", "query": SUNDAY["en"]},
                       {"task": "stale", "change": "corpus", "query": SUNDAY["en"]}):
            with self.subTest(inputs=inputs):
                answer, events = run_case(inputs, "en")
                self.assertIsNone(CJK.search(json.dumps([answer, events], ensure_ascii=False)))


if __name__ == "__main__":
    unittest.main()
