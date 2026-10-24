"""Behavior tests for rag-citations: deterministic model data, real BM25 retrieval, real citation checks.

The fixture stands in for the model only; retrieval, judging against the annotation and every
citation check run as real Python. Errors the fixture writes on purpose are marked as such.
"""
import json
import re
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_document_loading.chunking import default_chunks
from lessons.lesson_keyword_retrieval.bm25 import BM25Index
from lessons.lesson_keyword_retrieval.query_set import load_queries
from lessons.lesson_rag_citations import citations, runtime
from lessons.lesson_rag_citations.citations import Citation, Claim, Conflict, GroundedAnswer
from lessons.lesson_rag_citations.fixtures import INVENTED_ID, create_completion
from lessons.lesson_rag_citations.locales import texts_for

CJK = re.compile(r"[　-〿㐀-䶿一-鿿豈-﫿＀-￯]")
CHUNKS = {locale: {c.chunk_id: c for c in default_chunks(locale)} for locale in ("zh-CN", "en")}
EXERCISES = {"grounded": "q03", "no-answer": "q07", "conflict": "q13", "triage": "triage"}


def run_case(exercise_id, inputs=None, locale="zh-CN", completion=None, budget=3, cancelled=lambda: False):
    inputs = inputs or {"query": EXERCISES[exercise_id]}
    events = []
    context = RunContext(
        lesson_id="rag-citations", exercise_id=exercise_id, question="note", mode="offline", model="fixture-model",
        representation="sdk_standardized", inputs=validate_inputs(runtime, inputs), api_key="fixture-key",
        completion=completion or create_completion(exercise_id, inputs, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, round_number: events.append((kind, data, round_number)),
        locale=locale)
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event_kind, data, _ in events if event_kind == kind]


def answer_of(claims, insufficient=False, missing="", conflicts=()):
    return GroundedAnswer(claims=list(claims), insufficient_evidence=insufficient, missing=missing,
                          conflicts=list(conflicts))


def claim(text, chunk_id, quote):
    return Claim(text=text, citations=[Citation(chunk_id=chunk_id, quote=quote)])


class CitationCheckTests(unittest.TestCase):
    """citations.py on its own: existence and support are separate verdicts."""

    def setUp(self):
        self.zh = CHUNKS["zh-CN"]
        self.fees = [self.zh["fees:7-13"], self.zh["reader-notes:17-23"]]

    def test_existence_is_checked_before_support(self):
        check = citations.check_answer(answer_of([claim("最高 20 元", "fees:13-21", "累计最高 20 元")]), self.fees)
        cited = check.claims[0].citations[0]
        # fees:13-21 is a real chunk of the handbook, but it was not provided in this request.
        self.assertIn("fees:13-21", self.zh)
        self.assertEqual((cited.exists, cited.quote_found, cited.reason), (False, None, "not_provided"))
        self.assertEqual(check.unprovided, ["fees:13-21"])
        self.assertFalse(check.claims[0].numbers_checked)

    def test_a_provided_id_with_a_quote_that_is_not_there_is_not_support(self):
        check = citations.check_answer(answer_of([claim("最高 30 元", "fees:7-13", "累计最高 30 元")]), self.fees)
        cited = check.claims[0].citations[0]
        self.assertEqual((cited.exists, cited.quote_found, cited.reason), (True, False, "quote_not_found"))
        self.assertFalse(check.claims[0].supported)

    def test_quote_matching_ignores_spacing_width_and_dash_style(self):
        hours = [self.zh["hours:8-18"]]
        for quote in ("周六、周日 9:00-18:00 开放", "周六、周日9:00–18:00开放。", "周六、周日 ９:００–18:00 开放"):
            with self.subTest(quote=quote):
                check = citations.check_answer(answer_of([claim("周日 18:00 闭馆", "hours:8-18", quote)]), hours)
                self.assertTrue(check.claims[0].supported, check.to_dict())
        english = citations.check_answer(answer_of([claim("Capped at 20 yuan.", "fees:7-17",
                                                          "the OVERDUE charge for any single item is capped at 20 yuan")]),
                                         [CHUNKS["en"]["fees:7-17"]])
        self.assertTrue(english.claims[0].supported)

    def test_short_quotes_prove_nothing(self):
        check = citations.check_answer(answer_of([claim("20 元", "fees:7-13", "20 元")]), self.fees)
        self.assertEqual(check.claims[0].citations[0].reason, "quote_too_short")

    def test_a_number_in_the_claim_must_be_in_its_quote(self):
        found_quote = "每册每天收取 0.5 元逾期费用"
        wrong = citations.check_answer(answer_of([claim("每天 5 元，最高 20 元", "fees:7-13", found_quote)]), self.fees)
        self.assertEqual(wrong.claims[0].unmatched_numbers, ("5", "20"))
        self.assertFalse(wrong.claims[0].supported)
        right = citations.check_answer(answer_of([claim("每天 0.5 元", "fees:7-13", found_quote)]), self.fees)
        self.assertTrue(right.claims[0].supported)
        # "21" may be written for "21:00"; "B2" is a name, not the number 2.
        self.assertEqual(citations.numbers("B2 研究证 R-305 8:30–21:00"), ["305", "8:30", "21:00"])
        self.assertEqual(citations.numbers("up to 15 items"), ["15"])

    def test_versions_are_read_from_metadata_not_from_the_model(self):
        both = [self.zh["hours:8-18"], self.zh["hours-2025:7-15"]]
        old = citations.check_answer(answer_of([claim("周日 17:00 闭馆", "hours-2025:7-15", "周日 10:00–17:00 开放")]),
                                     both)
        self.assertEqual(old.claims[0].citations[0].superseded_by, "hours")
        self.assertTrue(old.claims[0].stale)
        self.assertEqual(old.version_pairs, (("hours", "hours-2025"),))
        self.assertIs(old.conflict_disclosed, False)
        self.assertEqual(citations.classify(old, hit=True, complete=True)[0], "misused")
        conflict = Conflict(topic="周日", resolution="以 2025 版为准",
                            sources=[Citation(chunk_id="hours:8-18", quote="周六、周日 9:00–18:00 开放"),
                                     Citation(chunk_id="hours-2025:7-15", quote="周日 10:00–17:00 开放")])
        new = citations.check_answer(answer_of([claim("周日 18:00 闭馆", "hours:8-18", "周六、周日 9:00–18:00 开放")],
                                               conflicts=[conflict]), both)
        # The model wrote the wrong resolution; the program still names the current version from supersedes.
        self.assertEqual(new.conflicts[0].current, "hours")
        self.assertTrue(new.conflict_disclosed)
        self.assertEqual(citations.classify(new, hit=True, complete=True), ("ok", ()))
        # With only the old edition provided, nothing in this request says it was replaced.
        alone = citations.check_answer(answer_of([claim("周日 17:00 闭馆", "hours-2025:7-15", "周日 10:00–17:00 开放")]),
                                       [self.zh["hours-2025:7-15"]])
        self.assertFalse(alone.claims[0].stale)
        self.assertIsNone(alone.conflict_disclosed)

    def test_classify_names_the_first_broken_link(self):
        good = citations.check_answer(answer_of([claim("最高 20 元", "fees:7-13", "累计最高 20 元")]), self.fees)
        declined = citations.check_answer(answer_of([], insufficient=True, missing="没有"), self.fees)
        invented = citations.check_answer(answer_of([claim("最高 20 元", "fees:1-2", "累计最高 20 元")]), self.fees)
        cases = [
            (None, True, True, "invalid_output"),
            (invented, True, True, "cited_unprovided"),
            (good, False, False, "retrieval_miss"),
            (good, None, None, "answered_without_evidence"),
            (declined, None, None, "declined_ok"),
            (declined, True, True, "misused"),
            (declined, True, False, "retrieval_partial"),
            (good, True, False, "retrieval_partial"),
            (good, True, True, "ok"),
        ]
        for check, hit, complete, expected in cases:
            with self.subTest(expected=expected, hit=hit, complete=complete):
                self.assertEqual(citations.classify(check, hit=hit, complete=complete)[0], expected)
        self.assertEqual(citations.classify(declined, hit=True, complete=True)[1], ("declined_with_evidence",))
        self.assertEqual(set(texts_for("zh-CN").categories), set(citations.CATEGORIES))

    def test_parse_answer_reports_json_and_schema_layers(self):
        self.assertEqual(citations.parse_answer("no json here")[1], ["json: no object"])
        self.assertTrue(citations.parse_answer('{"claims": [')[1][0].startswith("json: "))
        _, problems = citations.parse_answer('{"claims": [], "insufficient_evidence": true}')
        self.assertTrue(problems and problems[0].startswith("schema: "))
        _, problems = citations.parse_answer('{"claims": [{"text": "x", "citations": []}], "insufficient_evidence": false}')
        self.assertIn("claims.0.citations", problems[0])
        fenced = '```json\n{"claims": [], "insufficient_evidence": true, "missing": "x"}\n```'
        answer, problems = citations.parse_answer(fenced)
        self.assertEqual((answer.insufficient_evidence, problems), (True, []))
        with self.assertRaises(ValidationError):
            GroundedAnswer(claims=[], insufficient_evidence=False, extra=1)


class RunnerTests(unittest.TestCase):
    """The runner end to end with the offline fixture, in both run languages."""

    def test_retrieval_is_a_real_bm25_call_and_its_chunks_are_what_the_model_sees(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                _, events = run_case("grounded", locale=locale)
                query = next(q for q in load_queries(locale) if q.id == "q03")
                expected = [h.chunk_id for h in BM25Index(list(CHUNKS[locale].values()), locale).search(query.text, 5)]
                call = of(events, "tool_call")[0]
                self.assertEqual((call["function"]["name"], call["origin"]), ("search_handbook", "course_program"))
                hits = of(events, "tool_result")[0]["result"]["result"]["hits"]
                self.assertEqual([h["chunk_id"] for h in hits], expected)
                user = of(events, "request")[0]["body"]["messages"][1]["content"]
                self.assertEqual(re.findall(r'<source id="([^"]+)"', user), expected)
                # Sources come before the question, each tagged as untrusted data.
                self.assertLess(user.index("<sources>"), user.index(query.text))
                self.assertEqual(user.count('trust="untrusted_data"'), len(expected))
                # The planted instruction in reader comments reaches the model as data, inside a source tag.
                self.assertIn("reader-notes:17-23", expected)

    def test_each_exercise_classifies_as_designed(self):
        expected = {"grounded": ["ok"], "no-answer": ["declined_ok"], "conflict": ["ok"],
                    "triage": ["retrieval_miss", "cited_unprovided", "misused"]}
        for locale in ("zh-CN", "en"):
            for exercise_id, categories in expected.items():
                with self.subTest(locale=locale, exercise=exercise_id):
                    answer, events = run_case(exercise_id, locale=locale)
                    self.assertEqual([d["category"] for d in of(events, "lesson.citation_check")], categories)
                    self.assertEqual(len(of(events, "request")), len(categories))
                    self.assertEqual(len(of(events, "lesson.report")), 2)
                    self.assertIn(texts_for(locale).categories[categories[-1]], answer)

    def test_grounded_and_conflict_reports(self):
        _, events = run_case("conflict")
        report = of(events, "lesson.report")[0]
        checks = {c["id"]: c["passed"] for c in report["checks"]}
        self.assertEqual(checks, {"format": True, "provided": True, "quotes": True, "numbers": True, "conflict": True})
        check = of(events, "lesson.citation_check")[0]
        self.assertEqual(check["conflicts"][0]["current"], "hours")
        self.assertEqual(check["conflicts"][0]["doc_ids"], ["hours", "hours-2025"])
        metrics = {m.get("id"): m["value"] for m in report["metrics"]}
        self.assertEqual(metrics["usage"], "未报告")
        self.assertEqual(metrics["model_calls"], 1)

    def test_no_answer_declines_and_reports_the_declined_check(self):
        answer, events = run_case("no-answer")
        judge = of(events, "lesson.retrieval_judge")[0]
        self.assertIsNone(judge["hit"])
        # Retrieval still returned five chunks; only the answer step can refuse to use them.
        self.assertEqual(len(judge["provided"]), 5)
        check = of(events, "lesson.citation_check")[0]
        self.assertEqual((check["insufficient_evidence"], check["claims"]), (True, []))
        report = of(events, "lesson.report")[0]
        self.assertEqual([c["id"] for c in report["checks"]], ["format", "declined"])
        self.assertTrue(all(c["passed"] for c in report["checks"]))

    def test_triage_errors_are_marked_as_written_by_the_fixture(self):
        _, events = run_case("triage")
        responses = [d["body"] for d in of(events, "response")]
        self.assertNotIn("x_offline_fixture", responses[0])
        self.assertEqual([r["x_offline_fixture"]["scripted_error"] for r in responses[1:]],
                         ["invented_chunk_id", "quote_not_in_chunk"])
        checks = of(events, "lesson.citation_check")
        self.assertEqual({c["answer_source"] for c in checks}, {"offline_fixture"})
        self.assertEqual(checks[1]["unprovided"], [INVENTED_ID])
        self.assertNotIn(INVENTED_ID, CHUNKS["zh-CN"])
        self.assertEqual(checks[2]["claims"][0]["citations"][0]["reason"], "quote_not_found")
        judges = of(events, "lesson.retrieval_judge")
        self.assertEqual([j["hit"] for j in judges], [False, True, True])
        triage = of(events, "lesson.report")[1]
        metrics = {m["id"]: m["value"] for m in triage["metrics"]}
        self.assertEqual(metrics, {"retrieval_failures": 1, "generation_failures": 2, "passed": 0})
        # Events carry the round of their question, so the guide can pin each one.
        self.assertEqual([r for k, _, r in events if k == "lesson.citation_check"], [1, 2, 3])

    def test_fewer_chunks_turn_the_conflict_into_a_retrieval_problem(self):
        # zh: BM25's top 3 for q13 are all 2025 chunks, so top_k=3 hands the model no 2026 document at all.
        _, events = run_case("conflict", {"query": "q13", "top_k": 3})
        judge = of(events, "lesson.retrieval_judge")[0]
        self.assertTrue(all(chunk_id.startswith("hours-2025:") for chunk_id in judge["provided"]))
        self.assertEqual((judge["hit"], judge["complete"]), (True, False))
        self.assertEqual(of(events, "lesson.citation_check")[0]["category"], "retrieval_partial")

    def test_an_old_answer_is_retrieval_partial_at_three_chunks_and_stale_at_four(self):
        old = json.dumps({"claims": [{"text": "周日 17:00 闭馆。", "citations": [
            {"chunk_id": "hours-2025:7-15", "quote": "周日 10:00–17:00 开放"}]}],
            "insufficient_evidence": False, "missing": "", "conflicts": []}, ensure_ascii=False)

        def answers_from_2025(body, api_key):
            return {"choices": [{"message": {"role": "assistant", "content": old}}]}

        _, three = run_case("conflict", {"query": "q13", "top_k": 3}, completion=answers_from_2025)
        check = of(three, "lesson.citation_check")[0]
        # Every citation is real and nothing in the request says 2025 was replaced.
        self.assertEqual((check["category"], check["claims"][0]["supported"]), ("retrieval_partial", True))
        _, four = run_case("conflict", {"query": "q13", "top_k": 4}, completion=answers_from_2025)
        judge, check = of(four, "lesson.retrieval_judge")[0], of(four, "lesson.citation_check")[0]
        # The fourth chunk is the 2026 holidays chunk: no Sunday hours, but its supersedes exposes the old edition.
        self.assertIn("hours:26-32", judge["provided"])
        self.assertNotIn("hours:8-18", judge["provided"])
        self.assertEqual(check["claims"][0]["citations"][0]["superseded_by"], "hours")
        self.assertEqual((check["category"], check["reasons"]), ("misused", ["stale_version", "conflict_not_disclosed"]))

    def test_empty_retrieval_sends_no_request(self):
        # zh q05 shares no term with any chunk.
        answer, events = run_case("grounded", {"query": "q05"})
        self.assertEqual(of(events, "tool_result")[0]["result"]["result"]["hits"], [])
        self.assertEqual(of(events, "request"), [])
        check = of(events, "lesson.citation_check")[0]
        self.assertEqual((check["answer_source"], check["category"]), ("program", "retrieval_miss"))
        self.assertEqual(of(events, "lesson.report")[0]["checks"], [])
        self.assertIn(texts_for("zh-CN").no_hits, answer)

    def test_malformed_output_is_classified_not_repaired(self):
        def broken(body, api_key):
            return {"choices": [{"message": {"role": "assistant", "content": "the fee is 20 yuan"}}],
                    "usage": {"total_tokens": 42}}

        answer, events = run_case("grounded", completion=broken)
        check = of(events, "lesson.citation_check")[0]
        self.assertEqual((check["category"], check["format_problems"]), ("invalid_output", ["json: no object"]))
        report = of(events, "lesson.report")[0]
        self.assertEqual(report["checks"][0], {"id": "format", "label": texts_for("zh-CN").check_format,
                                               "passed": False, "detail": "0/1"})
        self.assertEqual({m.get("id"): m["value"] for m in report["metrics"]}["usage"], 42)
        self.assertIn(texts_for("zh-CN").answer_invalid, answer)

    def test_model_call_budget_stops_the_triage_run(self):
        with self.assertRaises(RuntimeError):
            run_case("triage", budget=2)

    def test_cancellation_stops_before_the_next_question(self):
        calls = {"n": 0}

        def cancelled():
            calls["n"] += 1
            return calls["n"] > 3

        with self.assertRaises(RunCancelled):
            run_case("triage", cancelled=cancelled)

    def test_inputs_are_validated(self):
        for bad in ({"query": "q99"}, {"query": "q03", "top_k": 0}, {"query": "q03", "top_k": 9},
                    {"query": "q03", "extra": 1}):
            with self.subTest(inputs=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)
        self.assertEqual(validate_inputs(runtime, {}), {"query": "q03", "top_k": 5})

    def test_search_tool_rejects_bad_arguments_as_structured_errors(self):
        from course.runner import execute_tool
        tools = runtime.make_tools(list(CHUNKS["en"].values()), "en")
        for arguments in ({"query": " "}, {"query": "fee", "top_k": 0}, {"query": "fee", "top_k": "5"}):
            call = {"id": "c1", "type": "function", "function": {"name": "search_handbook",
                                                                  "arguments": json.dumps(arguments)}}
            result = execute_tool(call, tools, "en")
            self.assertEqual((result["ok"], result["error_type"]), (False, "ValueError"))

    def test_english_runs_have_no_chinese(self):
        for exercise_id in EXERCISES:
            with self.subTest(exercise=exercise_id):
                answer, events = run_case(exercise_id, locale="en")
                leaks = [kind for kind, data, _ in events if CJK.search(json.dumps(data, ensure_ascii=False))]
                self.assertEqual(leaks, [])
                self.assertIsNone(CJK.search(answer))


if __name__ == "__main__":
    unittest.main()
