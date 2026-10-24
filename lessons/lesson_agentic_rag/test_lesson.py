"""Behavior tests for agentic-rag: deterministic model data; every search runs the real BM25 index in Python."""
import json
import re
import unittest
from unittest import mock

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled, execute_tool
from lessons.lesson_agentic_rag import runtime
from lessons.lesson_agentic_rag.fixtures import create_completion
from lessons.lesson_agentic_rag.locales import texts_for
from lessons.lesson_agentic_rag.search_tool import Handbook, InvalidQuery, SearchBudgetExhausted
from server.offline import tool_call
from server.selectors import resolve_path

LOCALES = ("zh-CN", "en")
DEFAULTS = {"mode": "agentic", "question_id": "q11", "max_searches": 4, "max_model_calls": 5,
            "time_budget_s": 60, "top_k": 3}
PRESETS = {
    "static": {"mode": "static", "question_id": "q11"},
    "agentic": {"mode": "agentic", "question_id": "q11", "max_searches": 4, "max_model_calls": 5},
    "no-answer": {"mode": "agentic", "question_id": "q07", "max_searches": 3, "max_model_calls": 5},
    "one-search": {"mode": "agentic", "question_id": "q11", "max_searches": 1, "max_model_calls": 5},
}
CJK = re.compile("[　-〿㐀-䶿一-鿿＀-￯]")


def run_case(exercise_id, overrides=None, completion=None, locale="zh-CN", cancelled=lambda: False):
    events = []
    values = validate_inputs(runtime, {**DEFAULTS, **PRESETS.get(exercise_id, {}), **(overrides or {})})
    context = RunContext(
        lesson_id="agentic-rag", exercise_id=exercise_id, question="", mode="offline", model="fixture-model",
        representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=8,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)), locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def report(events):
    return of(events, "lesson.report")[-1]


def metric(events, metric_id):
    return resolve_path({"data": report(events)}, f"data.metrics[id={metric_id}]")["value"]


def check(events, check_id):
    return resolve_path({"data": report(events)}, f"data.checks[id={check_id}]")["passed"]


def reply(content=None, calls=None, usage=None):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    body = {"choices": [{"message": message}]}
    if usage is not None:
        body["usage"] = usage
    return body


def final(status="answered", citations=(), answer="a"):
    return json.dumps({"status": status, "answer": answer, "citations": list(citations), "missing": ""})


class SearchToolTests(unittest.TestCase):
    def handbook(self, locale="zh-CN", max_searches=3):
        return Handbook(texts_for(locale), locale, max_searches=max_searches, default_top_k=3)

    def test_result_carries_ids_sources_scores_and_trust(self):
        book = self.handbook()
        result = book.search("三楼研究区几点关闭")
        self.assertEqual(result["search"], 1)
        self.assertEqual([r["chunk_id"] for r in result["results"]],
                         ["hours-2025:15-21", "hours-2025:21-27", "hours:18-26"])
        first = result["results"][0]
        self.assertEqual(set(first), {"chunk_id", "doc_id", "title", "version", "supersedes", "sections", "score",
                                      "trust", "text"})
        self.assertEqual(first["trust"], "untrusted_data")
        self.assertEqual(result["results"][2]["supersedes"], ["hours-2025"])
        self.assertGreater(first["score"], result["results"][2]["score"])

    def test_contract_errors_are_structured_and_spend_no_search(self):
        for locale in LOCALES:
            t = texts_for(locale)
            book = self.handbook(locale, max_searches=1)
            cases = [({"query": ""}, t.query_not_text), ({"query": 42}, t.query_not_text),
                     ({"query": "x" * 201}, t.query_too_long.format(limit=200)),
                     ({"query": "？！"}, t.query_no_terms),
                     ({"query": "B2", "top_k": True}, t.top_k_invalid.format(limit=5)),
                     ({"query": "B2", "top_k": 6}, t.top_k_invalid.format(limit=5))]
            for arguments, message in cases:
                with self.subTest(locale=locale, arguments=arguments):
                    result = execute_tool(tool_call("search_handbook", arguments, 1), {"search_handbook": book.search}, locale)
                    self.assertEqual(result, {"ok": False, "error_type": "InvalidQuery", "error": message})
            extra = execute_tool(tool_call("search_handbook", {"query": "B2", "k": 1}, 1), {"search_handbook": book.search})
            self.assertEqual(extra["error_type"], "TypeError")
            self.assertEqual(book.attempts, [], "a call that breaks the contract is not a search")
            book.search("B2")
            with self.assertRaises(SearchBudgetExhausted) as caught:
                book.search("R-305")
            self.assertEqual(str(caught.exception), t.search_budget_exhausted.format(limit=1))

    def test_repeats_are_the_same_term_set_with_no_larger_top_k(self):
        book = self.handbook(max_searches=5)
        book.search("研讨室 B2")
        book.search("B2 研讨室")
        book.search("B2 研讨室", top_k=5)
        book.search("B2 研讨室", top_k=2)
        self.assertEqual([a.duplicate_of for a in book.attempts], [None, 1, None, 1])
        self.assertEqual(book.attempts[1].new, (), "a repeat brings nothing new")
        self.assertEqual(len(book.attempts[2].new), 2, "a larger top_k may look deeper")

    def test_empty_result_is_a_search_too(self):
        book = self.handbook()
        self.assertEqual(book.search("停车场")["results"], [])
        self.assertEqual(len(book.attempts), 1)


class RunTests(unittest.TestCase):
    def test_static_baseline_searches_once_and_misses_the_second_hop(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_case("static", locale=locale)
                calls = of(events, "tool_call")
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0]["origin"], "course_program")
                self.assertEqual(len(of(events, "request")), 1)
                self.assertNotIn("tools", of(events, "request")[0]["body"])
                self.assertEqual(of(events, "lesson.stop")[0]["reason"], "static")
                self.assertTrue(check(events, "citations_from_results"))
                self.assertFalse(check(events, "citations_cover_gold"))
                self.assertFalse(check(events, "evidence_cover_gold"))
                self.assertEqual(metric(events, "model_calls"), 1)
                self.assertIn(texts_for(locale).answer_statuses["partial"], answer)

    def test_agentic_loop_rewrites_and_fetches_the_second_hop(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("agentic", locale=locale)
                requests = of(events, "request")
                self.assertEqual(len(requests), 3)
                self.assertEqual(requests[0]["body"]["tools"][0]["function"]["name"], "search_handbook")
                attempts = of(events, "lesson.attempt")
                self.assertEqual([a["n"] for a in attempts], [1, 2])
                self.assertNotEqual(attempts[0]["query"], requests[0]["body"]["messages"][1]["content"],
                                    "the model searched a sub-question, not the whole question")
                self.assertEqual(attempts[1]["gold_covered"], ["rooms#room-list", "hours#floor-hours"])
                # Round 2 sees the attempt log the runner inserted after round 1.
                note = requests[1]["body"]["messages"][-1]
                self.assertEqual(note["role"], "user")
                self.assertTrue(note["content"].startswith(t.progress_header.format(
                    searches=1, max_searches=4, calls=1, max_calls=5)))
                self.assertEqual(of(events, "lesson.stop")[0]["reason"], "answered")
                self.assertTrue(check(events, "citations_cover_gold"))
                self.assertTrue(check(events, "within_limits"))
                self.assertEqual(metric(events, "searches"), 2)
                self.assertEqual(metric(events, "total_tokens"), 480 + 740 + 1000)
                self.assertTrue(answer.endswith(t.stop_reasons["answered"]))

    def test_no_answer_question_stops_at_the_search_limit_and_says_why(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("no-answer", locale=locale)
                attempts = of(events, "lesson.attempt")
                self.assertEqual([a.get("duplicate_of") for a in attempts], [None, 1, None])
                self.assertEqual(attempts[0]["returned"], [])
                injected = of(events, "lesson.harness_injected")
                self.assertNotIn("repeats", injected[0])
                self.assertEqual(injected[1]["repeats"], [2])
                self.assertIn(t.duplicate_line.format(n=2, first=1), injected[1]["text"])
                requests = of(events, "request")
                self.assertEqual(len(requests), 4)
                self.assertEqual(requests[-1]["body"]["tool_choice"], "none")
                self.assertIn(t.final_instruction.format(reason=t.stop_reasons["search_limit"]),
                              requests[-1]["body"]["messages"][-1]["content"])
                self.assertEqual(of(events, "lesson.stop")[0]["reason"], "search_limit")
                self.assertTrue(check(events, "declined"))
                self.assertEqual(metric(events, "repeats"), 1)
                self.assertEqual(metric(events, "answer_status"), t.answer_statuses["insufficient"])
                self.assertIn(t.stop_reasons["search_limit"], answer)

    def test_one_search_budget_stops_honestly_with_a_partial_answer(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                _, events = run_case("one-search", locale=locale)
                self.assertEqual(len(of(events, "lesson.attempt")), 1)
                self.assertEqual(of(events, "lesson.harness_injected"), [], "no progress note once a limit is reached")
                self.assertEqual(of(events, "lesson.stop")[0]["reason"], "search_limit")
                self.assertEqual(metric(events, "model_calls"), 2)
                self.assertFalse(check(events, "citations_cover_gold"))
                self.assertTrue(check(events, "citations_from_results"))

    def test_call_limit_keeps_the_last_call_for_the_answer(self):
        _, events = run_case("agentic", {"max_model_calls": 2})
        self.assertEqual(of(events, "lesson.stop")[0]["reason"], "call_limit")
        self.assertEqual(len(of(events, "request")), 2)
        self.assertEqual(of(events, "request")[-1]["body"]["tool_choice"], "none")

    def test_time_limit_stops_without_another_request(self):
        ticks = iter([0.0, 0.0, 30.0, 61.0, 61.0, 61.0])
        with mock.patch.object(runtime, "clock", lambda: next(ticks)):
            answer, events = run_case("agentic")
        t = texts_for("zh-CN")
        self.assertEqual(of(events, "lesson.stop")[0]["reason"], "time_limit")
        self.assertEqual(len(of(events, "request")), 1)
        self.assertEqual(metric(events, "answer_status"), t.answer_statuses["unfinished"])
        self.assertNotIn("citations_from_results", [c["id"] for c in report(events)["checks"]])
        self.assertTrue(answer.startswith(t.unfinished_answer.split("：")[0]))

    def test_proposals_past_the_limit_are_refused_as_structured_errors(self):
        def greedy(body, key):
            if body.get("tool_choice") == "none":
                return reply(final("partial", ["rooms:7-11"]))
            return reply(calls=[tool_call("search_handbook", {"query": "B2 研讨室"}, 1),
                                tool_call("search_handbook", {"query": "三楼 关闭"}, 2)])
        _, events = run_case("agentic", {"max_searches": 1}, greedy)
        results = of(events, "tool_result")
        self.assertTrue(results[0]["result"]["ok"])
        self.assertEqual(results[1]["result"]["error_type"], "SearchBudgetExhausted")
        self.assertEqual(metric(events, "refused"), 1)
        self.assertEqual(metric(events, "searches"), 1)

    def test_citation_checks_catch_unreturned_ids_and_bad_format(self):
        def cites_unseen(body, key):
            if body.get("tools") and not any(m["role"] == "tool" for m in body["messages"]):
                return reply(calls=[tool_call("search_handbook", {"query": "B2 研讨室"}, 1)])
            return reply(final("answered", ["rooms:7-11", "hours:18-26"]))
        _, events = run_case("agentic", completion=cites_unseen)
        self.assertFalse(check(events, "citations_from_results"))
        self.assertFalse(check(events, "citations_cover_gold"), "an id never returned cannot count as coverage")

        _, events = run_case("agentic", completion=lambda body, key: reply("```json\n{\"status\": \"maybe\"}\n```"))
        self.assertEqual(metric(events, "answer_status"), texts_for("zh-CN").answer_statuses["invalid"])
        self.assertEqual(metric(events, "searches"), 0)

    def test_parse_final_reads_the_agreed_shape_only(self):
        self.assertEqual(runtime.parse_final('前言 {"status": "partial", "answer": "x", "citations": ["a", "a"]}'),
                         {"status": "partial", "answer": "x", "citations": ["a"], "missing": ""})
        self.assertEqual(runtime.parse_final(None)["status"], "invalid")
        self.assertEqual(runtime.parse_final('{"status": "answered", "answer": "x", "citations": [1]}')["status"],
                         "invalid")

    def test_usage_not_reported_is_written_as_such(self):
        _, events = run_case("static", completion=lambda body, key: reply(final("partial", ["rooms:7-11"])))
        self.assertEqual(metric(events, "total_tokens"), "未报告")
        calls = iter([{"total_tokens": 100}, None])

        def mixed(body, key):
            usage = next(calls)
            if body.get("tool_choice") == "none":
                return reply(final("partial", ["rooms:7-11"]), usage=usage)
            return reply(calls=[tool_call("search_handbook", {"query": "B2"}, 1)], usage=usage)
        _, events = run_case("one-search", completion=mixed, locale="en")
        self.assertEqual(metric(events, "total_tokens"), "100 (1 more calls not reported)")

    def test_english_runs_carry_no_chinese(self):
        for exercise in PRESETS:
            with self.subTest(exercise=exercise):
                answer, events = run_case(exercise, locale="en")
                self.assertIsNone(CJK.search(json.dumps([data for _, data, _ in events], ensure_ascii=False)))
                self.assertIsNone(CJK.search(answer))

    def test_hop_queries_return_the_chunks_the_lesson_text_names(self):
        # The content walks through these exact queries by hand; if the corpus or BM25 changes, the text is stale.
        expected = {
            "zh-CN": [["floors:17-23", "rooms:7-11", "rooms:11-19"], ["hours-2025:15-21", "hours-2025:21-27", "hours:18-26"]],
            "en": [["floors:17-23", "rooms:7-11", "rooms:11-19"], ["hours-2025:21-27", "hours-2025:7-21", "hours:26-32"]],
        }
        for locale in LOCALES:
            with self.subTest(locale=locale):
                _, events = run_case("agentic", locale=locale)
                self.assertEqual([a["returned"] for a in of(events, "lesson.attempt")], expected[locale])

    def test_identical_proposals_in_one_round_are_counted_and_the_second_is_a_repeat(self):
        def twice(body, key):
            if body.get("tool_choice") == "none":
                return reply(final("partial", ["rooms:7-11"]))
            return reply(calls=[tool_call("search_handbook", {"query": "B2 研讨室"}, 1),
                                tool_call("search_handbook", {"query": "研讨室 B2"}, 2)])
        _, events = run_case("agentic", {"max_searches": 2}, twice)
        attempts = of(events, "lesson.attempt")
        self.assertEqual([a.get("duplicate_of") for a in attempts], [None, 1])
        self.assertEqual(attempts[1]["new"], [])
        self.assertEqual(of(events, "lesson.stop")[0]["reason"], "search_limit")
        self.assertEqual(metric(events, "repeats"), 1)

    def test_broken_proposals_come_back_as_errors_and_cost_no_search(self):
        broken = [
            {"id": "c1", "type": "function", "function": {"name": "search_handbook", "arguments": "{not json"}},
            {"id": "c2", "type": "function", "function": {"name": "delete_everything", "arguments": "{}"}},
            {"id": "c3", "type": "function", "function": {"name": "search_handbook", "arguments": "[1]"}},
        ]
        sent = []

        def model(body, key):
            sent.append(body)
            if len(sent) == 1:
                return reply(calls=broken)
            return reply(final("insufficient"))
        _, events = run_case("agentic", completion=model)
        errors = [r["result"]["error_type"] for r in of(events, "tool_result")]
        self.assertEqual(errors, ["JSONDecodeError", "ValueError", "ValueError"])
        self.assertEqual(metric(events, "refused"), 3)
        self.assertEqual(metric(events, "searches"), 0)
        self.assertEqual(of(events, "lesson.attempt"), [])
        self.assertEqual(of(events, "lesson.stop")[0]["reason"], "answered")
        # The errors are in the history the model sees next, so it can correct itself.
        self.assertEqual([m["role"] for m in sent[1]["messages"][-5:]], ["assistant", "tool", "tool", "tool", "user"])

    def test_a_model_that_never_stops_searching_is_ended_by_the_limits(self):
        words = iter("alpha bravo charlie delta echo foxtrot golf hotel".split())

        def endless(body, key):
            if body.get("tool_choice") == "none":
                return reply(final("partial"))
            return reply(calls=[tool_call("search_handbook", {"query": "B2 " + next(words)}, 1)])
        for limits, reason in (({"max_searches": 6, "max_model_calls": 3}, "call_limit"),
                               ({"max_searches": 2, "max_model_calls": 8}, "search_limit")):
            with self.subTest(limits=limits):
                _, events = run_case("agentic", limits, endless)
                self.assertEqual(of(events, "lesson.stop")[0]["reason"], reason)
                self.assertLessEqual(len(of(events, "request")), limits["max_model_calls"])
                self.assertLessEqual(len(of(events, "lesson.attempt")), limits["max_searches"])
                self.assertTrue(check(events, "within_limits"))
                self.assertEqual(of(events, "request")[-1]["body"]["tool_choice"], "none")

    def test_cancel_stops_the_loop_between_rounds_and_before_the_first_search(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                requests = []
                model = create_completion("agentic", None, locale)

                def counted(body, key):
                    requests.append(body)
                    return model(body, key)
                # Cancelled once the first real search has finished: round 2 must not send a request.
                state = {"searched": False}
                original = Handbook.search

                def search_then_cancel(self, *args, **kwargs):
                    try:
                        return original(self, *args, **kwargs)
                    finally:
                        state["searched"] = True
                with mock.patch.object(Handbook, "search", search_then_cancel), self.assertRaises(RunCancelled):
                    run_case("agentic", completion=counted, locale=locale, cancelled=lambda: state["searched"])
                self.assertEqual(len(requests), 1)
        # Cancelled while the model is being asked: the proposal it returns is never executed.
        proposed = []

        def cancel_after_request(body, key):
            proposed.append(body)
            return create_completion("agentic", None, "zh-CN")(body, key)
        with self.assertRaises(RunCancelled):
            run_case("agentic", completion=cancel_after_request, cancelled=lambda: bool(proposed))

    def test_static_mode_on_a_no_answer_question_can_decline(self):
        def decline(body, key):
            return reply(final("insufficient", answer="not in the handbook"))
        for question in ("q07", "q08"):
            with self.subTest(question=question):
                _, events = run_case("static", {"question_id": question}, decline)
                self.assertTrue(check(events, "declined"))
                self.assertEqual(metric(events, "searches"), 1)
                self.assertEqual(metric(events, "model_calls"), 1)
                self.assertNotIn("evidence_cover_gold", [c["id"] for c in report(events)["checks"]])

    def test_a_confident_answer_to_a_no_answer_question_fails_the_declined_check(self):
        def invents(body, key):
            return reply(final("answered", ["membership:7-15"], answer="Yes, level 1."))
        _, events = run_case("static", {"question_id": "q07"}, invents)
        self.assertFalse(check(events, "declined"))
        self.assertTrue(check(events, "citations_from_results"), "the chunk was returned; the answer is still wrong")

    def test_time_limit_in_english_carries_no_chinese(self):
        ticks = iter([0.0, 0.0, 30.0, 61.0, 61.0, 61.0])
        with mock.patch.object(runtime, "clock", lambda: next(ticks)):
            answer, events = run_case("agentic", locale="en")
        self.assertEqual(of(events, "lesson.stop")[0]["reason"], "time_limit")
        self.assertIsNone(CJK.search(json.dumps([data for _, data, _ in events], ensure_ascii=False) + answer))

    def test_report_table_has_one_row_per_search_and_matches_its_columns(self):
        for locale in LOCALES:
            for exercise in ("static", "agentic", "no-answer", "one-search"):
                with self.subTest(locale=locale, exercise=exercise):
                    _, events = run_case(exercise, locale=locale)
                    table = report(events)["table"]
                    self.assertEqual(len(table["rows"]), len(of(events, "lesson.attempt")))
                    self.assertTrue(all(len(row) == len(table["columns"]) for row in table["rows"]))

    def test_every_search_in_a_run_is_a_recorded_tool_call_with_a_result(self):
        for exercise in ("static", "agentic", "no-answer", "one-search"):
            with self.subTest(exercise=exercise):
                _, events = run_case(exercise)
                calls, results = of(events, "tool_call"), of(events, "tool_result")
                self.assertEqual([c["id"] for c in calls], [r["tool_call_id"] for r in results])
                self.assertEqual(len(calls), len(of(events, "lesson.attempt")))

    def test_inputs_and_cancel(self):
        for bad in ({"max_model_calls": 1}, {"question_id": "q99"}, {"mode": "hybrid"}, {"max_searches": 0},
                    {"top_k": 6}, {"label": "x"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, {**DEFAULTS, **bad})
        with self.assertRaises(RunCancelled):
            run_case("agentic", cancelled=lambda: True)


if __name__ == "__main__":
    unittest.main()
