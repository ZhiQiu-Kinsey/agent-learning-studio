"""Behavior tests for keyword-retrieval. The lesson calls no model: BM25 really indexes and scores the handbook chunks."""
import dataclasses
import json
import math
import re
import string
import typing
import unittest
from pathlib import Path

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_document_loading.chunking import default_chunks
from lessons.lesson_document_loading.loader import corpus_version
from lessons.lesson_keyword_retrieval import runtime
from lessons.lesson_keyword_retrieval.bm25 import BM25Index
from lessons.lesson_keyword_retrieval.locales import Texts, texts_for
from lessons.lesson_keyword_retrieval.query_set import load_queries, query_set_version
from server.selectors import count_events, select_events

LOCALES = ("zh-CN", "en")
CJK = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")
HERE = Path(__file__).parent
MANIFEST = json.loads((HERE / "lesson.json").read_text(encoding="utf-8"))
PRESETS = {item["id"]: item["inputs"] for item in MANIFEST["exercises"]}


def run_case(inputs, locale="zh-CN", question="", cancelled=lambda: False):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="keyword-retrieval", exercise_id=values["scenario"], question=question, mode="offline",
        model="local-python", representation="local", inputs=values, api_key="", completion=None,
        emit_event=lambda kind, data, number: events.append((kind, data, number)), cancelled=cancelled,
        max_model_calls=1, locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def report(events):
    return of(events, "lesson.report")[-1]


def metric(events, metric_id):
    return next(item["value"] for item in report(events)["metrics"] if item.get("id") == metric_id)


def check(events, check_id):
    return next(item for item in report(events)["checks"] if item.get("id") == check_id)


class InputTests(unittest.TestCase):
    def test_query_id_literal_matches_the_query_file(self):
        self.assertEqual(list(typing.get_args(runtime.QueryId)), [query.id for query in load_queries("zh-CN")])

    def test_presets_validate(self):
        for exercise_id, inputs in PRESETS.items():
            with self.subTest(exercise=exercise_id):
                runtime.Inputs.model_validate(inputs)

    def test_rejects_out_of_range_and_unknown_inputs(self):
        for bad in ({"top_k": 0}, {"top_k": 11}, {"k1": -0.1}, {"k1": 3.5}, {"b": 1.2}, {"b": -0.5},
                    {"scenario": "rerank"}, {"query_id": "q99"}, {"query": ""}, {"chunk_id": ""}, {"label": "x"}):
            with self.subTest(inputs=bad), self.assertRaises(ValidationError):
                runtime.Inputs.model_validate(bad)

    def test_natural_language_field_has_no_default_text(self):
        self.assertIsNone(runtime.Inputs().query)
        schema = json.dumps(runtime.Inputs.model_json_schema(), ensure_ascii=False)
        self.assertIsNone(CJK.search(schema))


class QueryTableTests(unittest.TestCase):
    def test_every_query_is_searched_and_judged_in_both_languages(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_case(PRESETS["query-table"], locale)
                searches = of(events, "lesson.search")
                self.assertEqual([item["query_id"] for item in searches], [q.id for q in load_queries(locale)])
                self.assertEqual(metric(events, "hit_count"), "9/12")
                self.assertEqual(metric(events, "hit_rate"), 0.75)
                self.assertEqual(metric(events, "mrr"), 0.75)
                self.assertEqual(metric(events, "model_calls"), 0)
                self.assertTrue(all(item["passed"] for item in report(events)["checks"]), report(events)["checks"])
                missed = [item["query_id"] for item in searches if item["judge"]["hit"] is False]
                self.assertEqual(missed, ["q04", "q05", "q06"])
                self.assertEqual(of(events, "request"), [])
                self.assertEqual(len(report(events)["table"]["rows"]), 14)
                self.assertIn("q04", answer)

    def test_exact_queries_rank_their_section_first_and_hits_trace_to_lines(self):
        _, events = run_case(PRESETS["query-table"])
        chunks = {chunk.chunk_id: chunk for chunk in default_chunks("zh-CN")}
        for item in of(events, "lesson.search"):
            if item["kind"] == "exact":
                self.assertEqual(item["judge"]["first_rank"], 1, item["query_id"])
            for hit in item["hits"]:
                chunk = chunks[hit["chunk_id"]]
                self.assertEqual((hit["path"], hit["start_line"], hit["end_line"]),
                                 (chunk.path, chunk.start_line, chunk.end_line))
                self.assertAlmostEqual(sum(hit["terms"].values()), hit["score"], places=3)

    def test_versions_are_recorded_for_a_rerun(self):
        _, events = run_case(PRESETS["query-table"], "en")
        index = of(events, "lesson.index")[0]
        self.assertEqual(index["corpus_version"], corpus_version("en"))
        self.assertEqual(index["query_set_version"], query_set_version())
        self.assertEqual((index["k1"], index["b"], index["chunks"]), (1.5, 0.75, len(default_chunks("en"))))
        self.assertEqual(metric(events, "query_set_version"), query_set_version())

    def test_top_k_changes_completeness_not_hits(self):
        _, five = run_case(PRESETS["query-table"])
        _, one = run_case({**PRESETS["query-table"], "top_k": 1})
        self.assertEqual(metric(one, "hit_count"), metric(five, "hit_count"))
        self.assertLess(metric(one, "complete_rate"), metric(five, "complete_rate"))
        self.assertTrue(all(len(item["hits"]) <= 1 for item in of(one, "lesson.search")))

    def test_no_answer_queries_have_nothing_to_judge(self):
        _, events = run_case(PRESETS["query-table"])
        for item in of(events, "lesson.search"):
            if item["kind"] == "no_answer":
                self.assertIsNone(item["judge"]["hit"])
                self.assertGreater(len(item["hits"]), 0)

    def test_runs_are_deterministic(self):
        first = run_case(PRESETS["query-table"], "en")
        second = run_case(PRESETS["query-table"], "en")
        self.assertEqual(first, second)


class ExplainTests(unittest.TestCase):
    def test_contributions_add_up_and_follow_the_formula(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                _, events = run_case(PRESETS["explain-score"], locale)
                score = of(events, "lesson.score")[0]
                self.assertTrue(score["ok"])
                self.assertEqual(score["query_id"], "q03")
                self.assertEqual(score["rank"], 1)
                self.assertAlmostEqual(sum(term["contribution"] for term in score["terms"]), score["score"], places=3)
                norm = 1 - score["b"] + score["b"] * score["length"] / score["avg_length"]
                self.assertAlmostEqual(norm, score["length_norm"], places=3)
                for term in score["terms"]:
                    expected = math.log((score["chunks"] - term["df"] + 0.5) / (term["df"] + 0.5))
                    self.assertAlmostEqual(term["raw_idf"], expected, places=3)
                    self.assertAlmostEqual(term["idf"] * term["tf_part"], term["contribution"], places=3)
                    if not term["tf"]:
                        self.assertEqual(term["contribution"], 0.0)
                self.assertTrue(check(events, "sum_matches")["passed"])

    def test_documented_numbers_of_the_chinese_run(self):
        _, events = run_case(PRESETS["explain-score"])
        score = of(events, "lesson.score")[0]
        terms = {term["term"]: term for term in score["terms"]}
        self.assertEqual(score["chunk_id"], "fees:7-13")
        self.assertEqual((score["length"], score["avg_length"], score["length_norm"]), (41, 57.92, 0.7809))
        self.assertEqual((terms["最高"]["df"], terms["最高"]["idf"], terms["最高"]["contribution"]), (1, 3.2189, 3.7061))
        self.assertEqual(score["score"], 15.8188)

    def test_b_zero_turns_length_normalization_off(self):
        _, events = run_case({**PRESETS["explain-score"], "b": 0.0})
        score = of(events, "lesson.score")[0]
        self.assertEqual(score["length_norm"], 1.0)
        self.assertEqual(score["score"], 14.4831)
        self.assertEqual(metric(events, "baseline_score"), 15.8188)

    def test_k1_zero_counts_presence_only(self):
        _, events = run_case({**PRESETS["explain-score"], "k1": 0.0})
        for term in of(events, "lesson.score")[0]["terms"]:
            self.assertEqual(term["tf_part"], 1.0 if term["tf"] else 0.0)

    def test_a_chosen_chunk_and_a_custom_query(self):
        _, events = run_case({**PRESETS["explain-score"], "chunk_id": "fees:13-21"})
        score = of(events, "lesson.score")[0]
        self.assertEqual((score["chunk_id"], score["rank"]), ("fees:13-21", 3))
        _, events = run_case({"scenario": "explain", "query": "B2", "top_k": 5})
        score = of(events, "lesson.score")[0]
        self.assertIsNone(score["query_id"])
        self.assertEqual(score["terms"][0]["term"], "b2")
        self.assertIsNone(of(events, "lesson.index")[0]["query_set_version"])

    def test_no_match_and_unknown_chunk_are_structured_errors(self):
        for inputs, error_type in (({"scenario": "explain", "query": "zzz qqq"}, "no_match"),
                                   ({"scenario": "explain", "chunk_id": "nope:1-2"}, "unknown_chunk")):
            for locale in LOCALES:
                with self.subTest(error_type=error_type, locale=locale):
                    answer, events = run_case(inputs, locale)
                    score = of(events, "lesson.score")[0]
                    self.assertEqual((score["ok"], score["error_type"]), (False, error_type))
                    self.assertTrue(score["error"])
                    self.assertFalse(check(events, "chunk_found")["passed"])
                    self.assertIn(score["error"], answer)

    def test_chinese_single_character_query_matches_nothing(self):
        _, events = run_case({"scenario": "explain", "query_id": "q05"})
        score = of(events, "lesson.score")[0]
        self.assertEqual(score["error_type"], "no_match")
        self.assertIn("书", score["terms"])


class MissTests(unittest.TestCase):
    def test_reworded_queries_miss_for_a_reason_and_rewrites_hit(self):
        expected = {"zh-CN": {"q04": "no_shared_terms", "q05": "no_shared_terms", "q06": "no_shared_terms"},
                    "en": {"q04": "no_shared_terms", "q05": "no_shared_terms", "q06": "outranked"}}
        for locale in LOCALES:
            with self.subTest(locale=locale):
                _, events = run_case(PRESETS["misses"], locale)
                misses = of(events, "lesson.miss")
                self.assertEqual({item["query_id"]: item["reason"] for item in misses}, expected[locale])
                for item in misses:
                    self.assertFalse(item["hit"])
                    self.assertEqual(item["rewrite"]["first_rank"], 1)
                    if item["reason"] == "no_shared_terms":
                        self.assertTrue(all(not chunk["shared_terms"] for chunk in item["gold_chunks"]))
                self.assertTrue(all(c["passed"] for c in report(events)["checks"]), report(events)["checks"])

    def test_outranked_chunk_reports_its_rank_and_a_larger_top_k_recovers_it(self):
        _, events = run_case(PRESETS["misses"], "en")
        q06 = next(item for item in of(events, "lesson.miss") if item["query_id"] == "q06")
        self.assertEqual([(chunk["shared_terms"], chunk["rank"]) for chunk in q06["gold_chunks"]], [(["after"], 9)])
        _, events = run_case({**PRESETS["misses"], "top_k": 10}, "en")
        q06 = next(item for item in of(events, "lesson.miss") if item["query_id"] == "q06")
        self.assertEqual((q06["hit"], q06["reason"]), (True, None))

    def test_unanswerable_queries_still_return_chunks(self):
        for locale in LOCALES:
            _, events = run_case(PRESETS["misses"], locale)
            unanswerable = of(events, "lesson.no_answer")
            self.assertEqual([item["query_id"] for item in unanswerable], ["q07", "q08"])
            for item in unanswerable:
                self.assertEqual(item["returned"], 5)
                self.assertGreater(item["top_score"], 0)

    def test_rewrites_match_the_handbook_wording(self):
        # The rewrites must use words the gold chunks contain, otherwise the exercise proves nothing.
        for locale in LOCALES:
            index = BM25Index(default_chunks(locale), locale)
            queries = {q.id: q for q in load_queries(locale)}
            for query_id, text in texts_for(locale).rewrites.items():
                gold = [c.chunk_id for c in index.chunks if set(c.anchors) & set(queries[query_id].gold)]
                shared = [t["term"] for c in gold for t in index.explain(text, c)["terms"] if t["tf"]]
                self.assertTrue(shared, (locale, query_id))


class RuntimeTests(unittest.TestCase):
    def test_english_runs_have_no_chinese(self):
        for exercise_id, inputs in PRESETS.items():
            with self.subTest(exercise=exercise_id):
                answer, events = run_case(inputs, "en")
                dumped = json.dumps([data for _, data, _ in events], ensure_ascii=False) + answer
                self.assertIsNone(CJK.search(dumped))

    def test_chinese_runs_use_chinese_text(self):
        answer, events = run_case(PRESETS["misses"])
        self.assertIn("同义改写", answer)
        self.assertEqual(report(events)["title"], texts_for("zh-CN").misses_title)

    def test_learner_note_goes_to_the_report_only(self):
        _, events = run_case(PRESETS["query-table"], question="只是备注")
        self.assertEqual(metric(events, "note"), "只是备注")
        others = [data for kind, data, _ in events if kind != "lesson.report"]
        self.assertNotIn("只是备注", json.dumps(others, ensure_ascii=False))

    def test_cancel_before_the_first_search(self):
        with self.assertRaises(RunCancelled):
            run_case(PRESETS["query-table"], cancelled=lambda: True)

    def test_cancel_stops_the_query_loop(self):
        seen = []

        def cancelled():
            seen.append(1)
            return len(seen) > 6

        with self.assertRaises(RunCancelled):
            run_case(PRESETS["query-table"], cancelled=cancelled)

    def test_locale_catalogs_match_field_by_field(self):
        zh, en = texts_for("zh-CN"), texts_for("en")
        formatter = string.Formatter()

        def leaves(value, path):
            if isinstance(value, dict):
                for key in value:
                    yield from leaves(value[key], f"{path}.{key}")
            elif isinstance(value, tuple):
                for position, item in enumerate(value):
                    yield from leaves(item, f"{path}[{position}]")
            else:
                yield path, value

        for field in dataclasses.fields(Texts):
            a, b = dict(leaves(getattr(zh, field.name), field.name)), dict(leaves(getattr(en, field.name), field.name))
            self.assertEqual(a.keys(), b.keys(), field.name)
            for path in a:
                names = lambda text: sorted(name for _, name, _, _ in formatter.parse(text) if name)
                self.assertEqual(names(a[path]), names(b[path]), path)
                self.assertIsNone(CJK.search(b[path]), path)
        self.assertEqual(set(zh.kinds), {q.kind for q in load_queries("zh-CN")})
        self.assertEqual(set(zh.rewrites), {q.id for q in load_queries("zh-CN") if q.kind == "synonym"})


class ExperimentTests(unittest.TestCase):
    """While the lesson is planned the shared experiment test skips it; this checks the same things offline."""

    def test_observe_points_hit_and_predict_counts_real_events(self):
        content = json.loads((HERE / "content.json").read_text(encoding="utf-8"))
        for locale in LOCALES:
            for experiment in content["scenes"]["lab"]["experiments"]:
                runs = {}
                for arm in experiment["arms"]:
                    _, raw = run_case(arm.get("inputs") or PRESETS[arm["exercise"]], locale)
                    runs[arm["id"]] = [{"type": kind, "round": number, "data": data} for kind, data, number in raw]
                for point in experiment["observe"]:
                    with self.subTest(locale=locale, experiment=experiment["id"], observe=point["id"]):
                        self.assertTrue(any(select_events(point["selector"], events) for events in runs.values()))
                self.assertEqual({step["observe"] for step in experiment["guide"] if step.get("observe")},
                                 {point["id"] for point in experiment["observe"]})
            predict = next(block for block in content["scenes"]["understand"]["blocks"] if block["type"] == "predict")
            experiment = next(item for item in content["scenes"]["lab"]["experiments"]
                              if item["id"] == predict["experiment"])
            arm = next(item for item in experiment["arms"] if item["id"] == predict["arm"])
            _, raw = run_case(arm.get("inputs") or PRESETS[arm["exercise"]], locale)
            events = [{"type": kind, "round": number, "data": data} for kind, data, number in raw]
            self.assertEqual(count_events(predict["rule"], events), 14)

    def test_every_exercise_is_used_by_an_experiment(self):
        content = json.loads((HERE / "content.json").read_text(encoding="utf-8"))
        used = {arm["exercise"] for experiment in content["scenes"]["lab"]["experiments"] for arm in experiment["arms"]}
        self.assertEqual(used, set(PRESETS))
        names = {item["name"] for item in content["scenes"]["lab"]["inputs"]}
        self.assertEqual(names, set(runtime.Inputs.model_fields))

    def test_arms_use_preset_inputs_only(self):
        # The offline mode rejects inputs that differ from the exercise preset, so an arm may not carry its own.
        content = json.loads((HERE / "content.json").read_text(encoding="utf-8"))
        for experiment in content["scenes"]["lab"]["experiments"]:
            for arm in experiment["arms"]:
                with self.subTest(arm=arm["id"]):
                    self.assertNotIn("inputs", arm)

    def test_query_id_options_show_the_query_text_of_each_language(self):
        content = json.loads((HERE / "content.json").read_text(encoding="utf-8"))
        layer = json.loads((HERE / "content.en.json").read_text(encoding="utf-8"))["texts"]
        field = next(item for item in content["scenes"]["lab"]["inputs"] if item["name"] == "query_id")
        zh = {item.id: item.text for item in load_queries("zh-CN")}
        en = {item.id: item.text for item in load_queries("en")}
        self.assertEqual([option["value"] for option in field["options"]], list(typing.get_args(runtime.QueryId)))
        for option in field["options"]:
            query_id = option["value"]
            self.assertEqual(option["label"], f"{query_id} · {zh[query_id]}")
            self.assertEqual(layer[f"inputs.query_id.options.{query_id}.label"]["text"], f"{query_id} · {en[query_id]}")


if __name__ == "__main__":
    unittest.main()
