"""Behavior tests for hybrid-retrieval: deterministic embeddings and chat replies from fixtures.py;
BM25, cosine search, fusion, filtering, file changes and index reloads really run in Python."""
import hashlib
import json
import re
import tempfile
import typing
import unittest
from pathlib import Path

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_document_loading.chunking import default_chunks
from lessons.lesson_document_loading.loader import CORPUS_DIR, ROOT
from lessons.lesson_embedding_retrieval.vector_index import VectorIndex
from lessons.lesson_hybrid_retrieval import index_update, runtime
from lessons.lesson_hybrid_retrieval.fixtures import concept_vector, create_completion, create_embedding
from lessons.lesson_hybrid_retrieval.fusion import apply_filter, rrf
from lessons.lesson_hybrid_retrieval.locales import texts_for
from lessons.lesson_hybrid_retrieval.rerank import build_request, parse_order
from lessons.lesson_hybrid_retrieval.retrieval import embed_texts, keyword_search, vector_search
from lessons.lesson_keyword_retrieval.bm25 import BM25Index, Hit
from lessons.lesson_keyword_retrieval.query_set import load_queries
from server.content_schema import LessonContent, Predict, TraceHunt
from server.selectors import count_events, select_events

LOCALES = ("zh-CN", "en")
SPEC = json.loads((Path(__file__).resolve().parent / "lesson.json").read_text(encoding="utf-8"))
CJK = re.compile("[㐀-鿿　-〿＀-￯]")


def exercise_inputs(exercise_id):
    exercise = next(item for item in SPEC["exercises"] if item["id"] == exercise_id)
    return {**SPEC["input_defaults"], **exercise["inputs"]}


def run_case(exercise_id, locale="zh-CN", inputs=None, completion=None, embedding=None, budget=8,
             cancelled=lambda: False, batch_limit=10):
    events = []
    values = validate_inputs(runtime, inputs or exercise_inputs(exercise_id))
    context = RunContext(
        lesson_id="hybrid-retrieval", exercise_id=exercise_id, question="", mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale),
        embedding=embedding or create_embedding(exercise_id, values, locale), embedding_model="fixture-embedding",
        embedding_batch_limit=batch_limit, max_model_calls=budget, cancelled=cancelled,
        emit_event=lambda kind, data, number: events.append((kind, data, number)), locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def report(events, title_field, locale="zh-CN", **fmt):
    title = getattr(texts_for(locale), title_field)
    title = title.format(**fmt) if fmt else title
    return next(data for data in of(events, "lesson.report") if data["title"] == title)


def by_id(items, key):
    return {item["id"]: item for item in items}[key]


class WorkspaceTestCase(unittest.TestCase):
    """Points the working copy at a temporary folder under .runtime/, removed after each test."""

    def setUp(self):
        (ROOT / ".runtime").mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".runtime")
        self.saved_workspace = index_update.WORKSPACE
        index_update.WORKSPACE = Path(self.tmp.name)

    def tearDown(self):
        index_update.WORKSPACE = self.saved_workspace
        self.tmp.cleanup()


class FusionTests(unittest.TestCase):
    def test_rrf_by_hand(self):
        keyword = [Hit("a", 9.0, 1, {}), Hit("b", 5.0, 2, {})]
        vector = [Hit("c", 0.9, 1, {}), Hit("a", 0.8, 2, {})]
        fused = rrf({"keyword": keyword, "vector": vector}, k=60, top_k=3)
        self.assertEqual([hit.chunk_id for hit in fused], ["a", "c", "b"])
        self.assertAlmostEqual(fused[0].score, round(1 / 61 + 1 / 62, 6))
        self.assertEqual(fused[0].detail["ranks"], {"keyword": 1, "vector": 2})
        self.assertEqual(fused[1].detail["ranks"], {"keyword": None, "vector": 1})
        self.assertEqual(fused[1].detail["contributions"], {"vector": round(1 / 61, 6)})

    def test_rrf_uses_positions_not_scores(self):
        # A huge BM25 score and a tiny cosine weigh the same at the same position.
        fused = rrf({"keyword": [Hit("a", 1000.0, 7, {})], "vector": [Hit("b", 0.01, 3, {})]}, k=60, top_k=2)
        self.assertEqual(fused[0].score, fused[1].score)
        self.assertEqual([hit.chunk_id for hit in fused], ["a", "b"])  # tie: best rank, then chunk_id

    def test_rrf_rejects_bad_parameters(self):
        with self.assertRaises(ValueError):
            rrf({}, k=-1)
        with self.assertRaises(ValueError):
            rrf({}, top_k=0)

    def test_newest_only_removes_superseded_version_with_a_record(self):
        chunks = default_chunks("zh-CN")
        kept, removed = apply_filter(chunks, newest_only=True)
        self.assertTrue(removed)
        self.assertTrue(all(r["doc_id"] == "hours-2025" and r["reason"] == "superseded" and r["by"] == "hours"
                            for r in removed))
        self.assertEqual(len(kept) + len(removed), len(chunks))
        # Without the newer version in the candidates, the old one stays.
        without_new = [c for c in chunks if c.doc_id != "hours"]
        self.assertEqual(apply_filter(without_new, newest_only=True)[1], [])


class RetrievalTests(unittest.TestCase):
    def test_keyword_filter_applies_before_the_cut(self):
        chunks = default_chunks("zh-CN")
        bm25 = BM25Index(chunks, "zh-CN")
        allowed = {c.chunk_id for c in chunks if c.doc_id != "hours-2025"}
        hits = keyword_search(bm25, "周日几点闭馆？", depth=5, allowed=allowed)
        self.assertTrue(hits)
        self.assertEqual([hit.rank for hit in hits], list(range(1, len(hits) + 1)))
        self.assertFalse(any(hit.chunk_id.startswith("hours-2025:") for hit in hits))
        self.assertTrue(any(hit.chunk_id.startswith("hours-2025:") for hit in keyword_search(bm25, "周日几点闭馆？", 5)))

    def test_vector_filter_and_fixture_synonyms(self):
        chunks = default_chunks("en")
        index = VectorIndex("m", len(concept_vector("x", "en")), "v", [c.chunk_id for c in chunks],
                            [concept_vector(c.text, "en") for c in chunks])
        late_fee = vector_search(index, concept_vector("How much is the late fee?", "en"), depth=3)
        self.assertTrue(late_fee[0].chunk_id.startswith("fees:"))
        only_rooms = vector_search(index, concept_vector("late fee", "en"), depth=3,
                                   allowed={c.chunk_id for c in chunks if c.doc_id == "rooms"})
        self.assertTrue(all(hit.chunk_id.startswith("rooms:") for hit in only_rooms))

    def test_embed_texts_batches_and_reorders_by_index(self):
        sent = []

        class Context:
            embedding_batch_limit = 3

            def check_cancelled(self):
                pass

            def embed(self, texts, round_number):
                sent.append((list(texts), round_number))
                data = [{"index": i, "embedding": [float(len(text)), 1.0]} for i, text in enumerate(texts)]
                return {"data": list(reversed(data))}

        vectors, next_round = embed_texts(Context(), ["a", "bb", "ccc", "dddd"], 4)
        self.assertEqual([batch for batch, _ in sent], [["a", "bb", "ccc"], ["dddd"]])
        self.assertEqual([number for _, number in sent], [4, 5])
        self.assertEqual(next_round, 6)
        self.assertEqual([v[0] for v in vectors], [1.0, 2.0, 3.0, 4.0])

    def test_bad_vector_is_rejected(self):
        class Context:
            embedding_batch_limit = 10

            def check_cancelled(self):
                pass

            def embed(self, texts, round_number):
                return {"data": [{"index": 0, "embedding": ["x"]}]}

        with self.assertRaises(ValueError):
            embed_texts(Context(), ["a"], 1)


class RerankTests(unittest.TestCase):
    def setUp(self):
        self.chunks = default_chunks("zh-CN")[:3]
        self.body, self.labels = build_request("system", "q", self.chunks)

    def test_request_uses_labels_and_marks_text_as_data(self):
        payload = json.loads(self.body["messages"][1]["content"])
        self.assertEqual([item["id"] for item in payload["candidates"]], ["c1", "c2", "c3"])
        self.assertEqual(self.labels["c2"], self.chunks[1].chunk_id)
        for locale in LOCALES:
            self.assertIn('"order"', texts_for(locale).rerank_system)

    def test_parse_keeps_known_labels_and_fills_gaps(self):
        parsed = parse_order('Here: {"order": ["c3", "c9", "c3", "c1"]}', self.labels)
        self.assertTrue(parsed["valid"])
        self.assertEqual(parsed["order"], ["c3", "c1", "c2"])
        self.assertEqual((parsed["unknown"], parsed["duplicates"], parsed["missing"]), (["c9"], ["c3"], ["c2"]))

    def test_unusable_reply_keeps_fused_order(self):
        for content, error in (("no json", "no_order"), ('{"order": []}', "no_order"), ('{"order": ["x"]}', "no_known_label"),
                               ('{"order": "c1"}', "no_order"), ("{broken", "no_order")):
            parsed = parse_order(content, self.labels)
            self.assertFalse(parsed["valid"], content)
            self.assertEqual(parsed["error"], error)
            self.assertEqual(parsed["order"], ["c1", "c2", "c3"])


class IndexUpdateTests(WorkspaceTestCase):
    def test_plan_update_sorts_chunks_into_four_groups(self):
        plan = index_update.plan_update({"a": "1", "b": "2", "c": "3"}, {"a": "1", "b": "9", "d": "4"})
        self.assertEqual(plan, {"added": ["d"], "changed": ["b"], "removed": ["c"], "unchanged": ["a"]})

    def test_apply_update_refuses_mixed_dimensions(self):
        chunk = default_chunks("zh-CN")[0]
        index = VectorIndex("m", 2, "v1", [chunk.chunk_id], [[1.0, 0.0]])
        with self.assertRaises(ValueError):
            index_update.apply_update(index, [chunk], {chunk.chunk_id: [1.0, 0.0, 0.0]}, "v2")

    def test_changes_touch_only_the_working_copy(self):
        repo_before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (CORPUS_DIR / "zh-CN").glob("*.md")}
        folder = index_update.reset_working_copy("zh-CN")
        self.assertTrue(folder.resolve().is_relative_to(Path(self.tmp.name).resolve()))
        records = index_update.apply_changes(folder)
        self.assertEqual([r["action"] for r in records], ["edit", "delete"])
        self.assertFalse((folder / index_update.DELETED_FILE).exists())
        edited = (folder / index_update.EDITED_FILE).read_text(encoding="utf-8")
        self.assertIn(index_update.NEW_VALUE, edited)
        self.assertIn(f"version: {index_update.NEW_VERSION}", edited)
        repo_after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (CORPUS_DIR / "zh-CN").glob("*.md")}
        self.assertEqual(repo_before, repo_after)
        # A second reset brings the clean files back.
        folder = index_update.reset_working_copy("zh-CN")
        self.assertTrue((folder / index_update.DELETED_FILE).exists())

    def test_saved_files_must_agree(self):
        store = index_update.working_folder("en") / "index"
        index = VectorIndex("m", 2, "v1", ["a:1-2"], [[1.0, 0.0]])
        index_update.save(index, {"a:1-2": "f"}, store)
        loaded, prints = index_update.load(store)
        self.assertEqual((loaded.corpus_version, prints), ("v1", {"a:1-2": "f"}))
        manifest = json.loads((store / "manifest.json").read_text(encoding="utf-8"))
        manifest["corpus_version"] = "other"
        (store / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValueError):
            index_update.load(store)

    def test_stale_hits_name_the_reason(self):
        hits = [Hit("gone:1-2", 0.9, 1, {}), Hit("edited:1-2", 0.8, 2, {}), Hit("same:1-2", 0.7, 3, {})]
        saved = {"gone:1-2": "a", "edited:1-2": "b", "same:1-2": "c"}
        current = {"edited:1-2": "B", "same:1-2": "c"}
        self.assertEqual(index_update.stale_hits(hits, saved, current),
                         [{"chunk_id": "gone:1-2", "reason": "source_missing"},
                          {"chunk_id": "edited:1-2", "reason": "text_changed"}])


class InputTests(unittest.TestCase):
    def test_query_ids_match_the_shared_query_set(self):
        allowed = typing.get_args(runtime.QueryId)
        self.assertEqual(list(allowed), [query.id for query in load_queries("zh-CN")])

    def test_invalid_inputs_are_rejected(self):
        for values in ({"top_k": 0}, {"top_k": 9}, {"rrf_k": -1}, {"candidates": 11}, {"query_id": "q99"},
                       {"task": "delete"}, {"label": "x"},
                       {"task": "rerank", "top_k": 5, "candidates": 3}):
            with self.assertRaises(ValidationError, msg=values):
                runtime.Inputs.model_validate(values)

    def test_every_exercise_preset_is_valid(self):
        for exercise in SPEC["exercises"]:
            runtime.Inputs.model_validate(exercise_inputs(exercise["id"]))


class CompareRunTests(unittest.TestCase):
    def test_three_strategies_on_one_query_set(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_case("compare", locale)
                requests = of(events, "request")
                self.assertEqual(len(requests), 6, "4 chunk batches + 2 query batches")
                self.assertTrue(all(r["endpoint"] == "embeddings" for r in requests))
                self.assertTrue(all(len(r["body"]["input"]) <= 10 for r in requests))
                self.assertEqual(len(of(events, "lesson.report")), 5)
                compare = report(events, "compare_title", locale)
                self.assertTrue(by_id(compare["checks"], "same-source")["passed"])
                self.assertEqual(by_id(compare["metrics"], "hits-keyword")["value"], "9/12")
                self.assertEqual(by_id(compare["metrics"], "hits-hybrid")["value"], "12/12")
                self.assertEqual(by_id(compare["metrics"], "keyword-only")["value"], "q02")
                t = texts_for(locale)
                self.assertEqual(by_id(compare["metrics"], "vector-only")["value"], t.separator.join(["q04", "q05", "q06"]))
                self.assertEqual(len(compare["table"]["rows"]), 14)
                self.assertEqual(answer, t.compare_answer.format(total=12, keyword=9, vector=11, hybrid=12))

    def test_strategy_reports_keep_their_own_scores(self):
        _, events = run_case("compare")
        t = texts_for("zh-CN")
        for name in ("keyword", "vector", "hybrid"):
            data = next(d for d in of(events, "lesson.report") if d["title"] == t.strategy_titles[name])
            self.assertEqual(data["table"]["columns"][2], t.list_columns[name])
            self.assertEqual(by_id(data["metrics"], f"{name}-noise")["value"], 10)
        rrf_report = report(events, "rrf_title", query="q04")
        first = rrf_report["table"]["rows"][0]
        self.assertAlmostEqual(first[5], round(first[3] + first[4], 6), places=5)

    def test_budget_stops_the_run(self):
        with self.assertRaises(RuntimeError):
            run_case("compare", budget=5)

    def test_cancellation_stops_before_more_requests(self):
        calls = []

        def cancelled():
            return len(calls) >= 2

        base = create_embedding("compare", None, "zh-CN")

        def embedding(body, key):
            calls.append(1)
            return base(body, key)

        with self.assertRaises(RunCancelled):
            run_case("compare", embedding=embedding, cancelled=cancelled)
        self.assertEqual(len(calls), 2)

    def test_smaller_batch_limit_means_more_requests(self):
        _, events = run_case("compare", batch_limit=6, budget=10)
        self.assertEqual(len(of(events, "request")), 7 + 3)


class RerankRunTests(unittest.TestCase):
    def test_rerank_is_one_chat_request_after_the_embeddings(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_case("rerank-synonym", locale)
                requests = of(events, "request")
                self.assertEqual([r.get("endpoint") for r in requests], ["embeddings"] * 5 + [None])
                chat = requests[-1]["body"]
                self.assertEqual(chat["messages"][0]["content"], texts_for(locale).rerank_system)
                self.assertEqual(len(json.loads(chat["messages"][1]["content"])["candidates"]), 8)
                data = report(events, "rerank_title", locale, query="q06")
                t = texts_for(locale)
                self.assertTrue(by_id(data["checks"], "reply-valid")["passed"])
                self.assertTrue(by_id(data["checks"], "pool-covers")["passed"])
                # zh: the gold chunk sits 4th before reranking; en: 3rd. Either way it moves to 1st.
                before = {"zh-CN": t.verdict_miss, "en": t.verdict_complete.format(rank=3)}[locale]
                self.assertEqual(by_id(data["metrics"], "before")["value"], before)
                self.assertEqual(by_id(data["metrics"], "after")["value"], t.verdict_complete.format(rank=1))
                self.assertEqual(by_id(data["metrics"], "rerank-tokens")["value"], 400 + 60 * 8)
                self.assertEqual(len(data["table"]["rows"]), 8)
                self.assertIn(t.verdict_complete.format(rank=1), answer)

    def test_unusable_reply_keeps_the_fused_order_and_says_so(self):
        def broken(body, key):
            return {"choices": [{"message": {"content": "I think c1 is best."}}]}

        answer, events = run_case("rerank-synonym", completion=broken)
        data = report(events, "rerank_title", query="q06")
        t = texts_for("zh-CN")
        check = by_id(data["checks"], "reply-valid")
        self.assertFalse(check["passed"])
        self.assertEqual(check["detail"], t.reply_errors["no_order"])
        self.assertEqual(by_id(data["metrics"], "before")["value"], by_id(data["metrics"], "after")["value"])
        self.assertEqual(by_id(data["metrics"], "rerank-tokens")["value"], t.value_not_reported)
        self.assertTrue(all(row[1] == row[2] for row in data["table"]["rows"]))
        self.assertIn(t.value_not_reported, answer)

    def test_exact_query_preset(self):
        _, events = run_case("rerank-exact")
        data = report(events, "rerank_title", query="q02")
        self.assertIn("R-305", json.loads(of(events, "request")[-1]["body"]["messages"][1]["content"])["query"])
        self.assertTrue(by_id(data["checks"], "pool-covers")["passed"])


class UpdateRunTests(WorkspaceTestCase):
    def test_filter_change_update_and_reload(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_case("update", locale)
                requests = of(events, "request")
                self.assertEqual(len(requests), 6, "4 chunk batches + 1 query batch + 1 update batch")
                self.assertEqual(requests[-1]["body"]["input"][0].count(index_update.NEW_VALUE), 1)
                filtered = report(events, "filter_title", locale)
                self.assertGreater(by_id(filtered["metrics"], "filtered-out")["value"], 0)
                self.assertGreater(by_id(filtered["metrics"], "old-version-hits")["value"], 0)
                changed = report(events, "change_title", locale)
                self.assertTrue(by_id(changed["checks"], "index-stale")["passed"])
                stale = by_id(changed["metrics"], "stale-hits")["value"]
                self.assertIn("fees:", stale)
                self.assertIn("hours-2025:", stale)
                updated = report(events, "update_title", locale)
                self.assertTrue(all(check["passed"] for check in updated["checks"]), updated["checks"])
                self.assertEqual(by_id(updated["metrics"], "plan-changed")["value"], 1)
                self.assertEqual(by_id(updated["metrics"], "embedded")["value"], 1)
                self.assertEqual(by_id(updated["metrics"], "filter-after-delete")["value"], 0)
                self.assertIn("5/5", answer)
                # The reloaded index on disk lists exactly the working copy's current chunks.
                loaded, _ = index_update.load(index_update.working_folder(locale) / "index")
                self.assertFalse(any(cid.startswith("hours-2025:") for cid in loaded.chunk_ids))

    def test_events_hold_no_absolute_path(self):
        _, events = run_case("update")
        dumped = json.dumps([data for _, data, _ in events], ensure_ascii=False)
        self.assertNotIn(str(ROOT), dumped)


class ContentEvidenceTests(WorkspaceTestCase):
    """The platform's experiment tests skip planned lessons; this checks the same evidence here."""

    @staticmethod
    def envelope(events):
        return [{"type": kind, "round": number, "data": data} for kind, data, number in events]

    def test_observe_points_predict_and_trace_hunt_hit_in_both_languages(self):
        model = LessonContent.model_validate(json.loads((Path(__file__).resolve().parent / "content.json")
                                                        .read_text(encoding="utf-8")))
        blocks = model.scenes.understand.blocks + model.scenes.check.blocks
        predict = next(block for block in blocks if isinstance(block, Predict))
        hunt = next(block for block in blocks if isinstance(block, TraceHunt))
        for locale in LOCALES:
            runs = {}
            for experiment in model.scenes.lab.experiments:
                for arm in experiment.arms:
                    runs[arm.exercise] = self.envelope(run_case(arm.exercise, locale)[1])
                for point in experiment.observe:
                    with self.subTest(locale=locale, observe=point.id):
                        self.assertTrue(any(select_events(point.selector, runs[arm.exercise])
                                            for arm in experiment.arms))
            self.assertEqual(count_events(predict.rule, runs["compare"]), 6)
            self.assertTrue(select_events(hunt.target, runs["update"]))


class LocaleTests(WorkspaceTestCase):
    def test_english_runs_have_no_chinese(self):
        for exercise in SPEC["exercises"]:
            with self.subTest(exercise=exercise["id"]):
                answer, events = run_case(exercise["id"], "en")
                dumped = json.dumps([data for _, data, _ in events], ensure_ascii=False) + answer
                self.assertIsNone(CJK.search(dumped), CJK.search(dumped) and dumped[CJK.search(dumped).start() - 80:][:160])

    def test_chinese_runs_stay_chinese(self):
        answer, events = run_case("compare", "zh-CN")
        self.assertIn("命中", answer)
        self.assertIn("借阅", of(events, "request")[0]["body"]["input"][0])


if __name__ == "__main__":
    unittest.main()
