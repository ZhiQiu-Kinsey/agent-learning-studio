"""Behavior tests for langchain-vs-native: deterministic model data; the tools, the framework parsing and the loops really run."""
import json
import re
import unittest

from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.frameworks import FRAMEWORK_CALLBACK_EVENT, FRAMEWORK_INPUT_EVENT, FRAMEWORK_OUTPUT_EVENT
from course.locales import texts_for as platform_texts
from course.runner import RunCancelled
from lessons.lesson_langchain_vs_native import runtime
from lessons.lesson_langchain_vs_native.fixtures import create_completion
from lessons.lesson_langchain_vs_native.locales import texts_for
from lessons.lesson_langchain_vs_native.tools import add_numbers_tool, clock_tool
from server.selectors import resolve_path

LOCALES = ("zh-CN", "en")
CJK = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")
QUESTIONS = {"sum": {"zh-CN": "帮我计算 19 加 23，并说明结果。", "en": "Add 19 and 23 for me and explain the result."},
             "divide-zero": {"zh-CN": "12 除以 0 等于多少？", "en": "What is 12 divided by 0?"}}


def run_case(exercise_id, completion=None, locale="zh-CN", cancelled=lambda: False, budget=6):
    events = []
    needs_model = exercise_id in runtime.TASKS
    context = RunContext(
        lesson_id="langchain-vs-native", exercise_id=exercise_id,
        question=QUESTIONS.get(exercise_id, {}).get(locale, ""), mode="offline", model="fixture-model",
        representation="sdk_standardized", inputs={}, api_key="",
        completion=(completion or create_completion(exercise_id, {}, locale)) if needs_model else None,
        emit_event=lambda kind, data, number: events.append((kind, data, number)),
        cancelled=cancelled, max_model_calls=budget, locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def report(events, title_field, locale="zh-CN", key=None):
    title = getattr(texts_for(locale), title_field)
    title = title[key] if key else title
    return next(data for data in of(events, "lesson.report") if data["title"] == title)


def check(data, check_id):
    return resolve_path({"data": data}, f"data.checks[id={check_id}]")["passed"]


def metric(data, metric_id):
    return resolve_path({"data": data}, f"data.metrics[id={metric_id}]")["value"]


def reply(message):
    return {"model": "fixture-model", "choices": [{"index": 0, "finish_reason": "stop",
                                                   "message": {"role": "assistant", "content": None, **message}}]}


class PairedRunTests(unittest.TestCase):
    def test_sum_runs_both_sides_on_separate_rounds(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_case("sum", locale=locale)
                requests = [(data, number) for kind, data, number in events if kind == "request"]
                self.assertEqual([number for _, number in requests], [1, 2, 3, 4])
                # Framework events wrap only the LangChain side's calls.
                self.assertEqual([number for kind, _, number in events if kind == FRAMEWORK_INPUT_EVENT], [3, 4])
                self.assertEqual(len(of(events, FRAMEWORK_OUTPUT_EVENT)), 2)
                # Same system prompt and question on both sides; both sides really ran add_numbers.
                self.assertEqual(requests[0][0]["body"]["messages"], requests[2][0]["body"]["messages"])
                self.assertEqual([item["result"] for item in of(events, "tool_result")],
                                 [{"ok": True, "result": 42}, {"ok": True, "result": 42.0}])
                paired = report(events, "report_task_title", locale, "sum")
                for check_id in ("native_accepted", "langchain_accepted", "same_tools"):
                    self.assertTrue(check(paired, check_id), check_id)
                self.assertEqual(metric(paired, "native_rounds"), "1–2")
                self.assertEqual(metric(paired, "langchain_rounds"), "3–4")
                self.assertEqual(metric(paired, "framework_version"), runtime.framework_versions()["langchain-core"])
                t = texts_for(locale)
                self.assertTrue(answer.startswith(t.answer_task.split("{native}")[0]))

    def test_request_diff_shows_schema_tool_choice_and_reserialized_arguments(self):
        _, events = run_case("sum")
        diff = report(events, "report_diff_title")
        fields = {(row[0], row[1]): (row[2], row[3]) for row in diff["table"]["rows"]}
        t = texts_for("zh-CN")
        first, second = t.request_pair.format(n=1), t.request_pair.format(n=2)
        self.assertEqual(fields[(first, "tool_choice")], ("auto", t.absent))
        self.assertEqual(fields[(first, "tools[0].function.parameters.properties.a.description")], ("第一个数字", t.absent))
        self.assertEqual(fields[(first, "tools[0].function.parameters.additionalProperties")], ("false", t.absent))
        # The native loop sends the provider's arguments text back; the framework re-serializes the parsed dict.
        self.assertEqual(fields[(second, "messages[2].tool_calls[0].function.arguments")],
                         ('{"a":19,"b":23}', '{"a": 19, "b": 23}'))
        self.assertEqual(fields[(second, "messages[3].content")],
                         ('{"ok": true, "result": 42}', '{"ok": true, "result": 42.0}'))
        # Tool definitions are listed once, under the first pair.
        self.assertFalse(any(row[0] == second and row[1].startswith("tools") for row in diff["table"]["rows"]))
        self.assertEqual(metric(diff, "diff_1"), 6)

    def test_reconstructed_framework_body_matches_the_recorded_request(self):
        # The diff compares request_body(); this proves it is the body the adapter actually sent.
        captured = []
        original = runtime.request_body

        def spy(model, history):
            body = original(model, history)
            captured.append(json.loads(json.dumps(body, ensure_ascii=False)))
            return body

        runtime.request_body = spy
        try:
            _, events = run_case("sum", locale="en")
        finally:
            runtime.request_body = original
        recorded = [data["body"] for data, number in
                    [(data, number) for kind, data, number in events if kind == "request"] if number >= 3]
        self.assertEqual([{k: v for k, v in body.items() if k != "model"} for body in recorded], captured)

    def test_failure_task_is_not_masked_on_either_side(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                _, events = run_case("divide-zero", locale=locale)
                results = of(events, "tool_result")
                self.assertEqual([item["result"]["ok"] for item in results], [False, False])
                self.assertEqual({item["result"]["error_type"] for item in results}, {"ValueError"})
                # The tool's own error text, the same function on both sides.
                self.assertEqual(results[0]["result"]["error"], results[1]["result"]["error"])
                paired = report(events, "report_task_title", locale, "divide")
                self.assertTrue(check(paired, "native_accepted"))
                self.assertTrue(check(paired, "langchain_accepted"))
                callbacks = [item["callback"] for item in of(events, FRAMEWORK_CALLBACK_EVENT)]
                self.assertIn("on_tool_error", callbacks)
                self.assertEqual(callbacks[0], "on_chat_model_start")

    def test_round_limit_is_the_lessons_own_stop_condition(self):
        def always_call(body, api_key):
            return reply({"tool_calls": [{"id": "c", "type": "function",
                                          "function": {"name": "add_numbers", "arguments": '{"a": 1, "b": 2}'}}]})
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("sum", always_call, locale=locale)
                self.assertEqual(len(of(events, "request")), 2 * runtime.MAX_TOOL_ROUNDS)
                paired = report(events, "report_task_title", locale, "sum")
                self.assertFalse(check(paired, "native_accepted"))
                self.assertFalse(check(paired, "langchain_accepted"))
                self.assertEqual(answer, t.answer_task.format(native=t.stop_reasons["rounds"],
                                                              langchain=t.stop_reasons["rounds"]))

    def test_model_budget_error_is_not_mistaken_for_the_round_limit(self):
        def always_call(body, api_key):
            return reply({"tool_calls": [{"id": "c", "type": "function",
                                          "function": {"name": "add_numbers", "arguments": '{"a": 1, "b": 2}'}}]})
        with self.assertRaises(RuntimeError) as caught:
            run_case("sum", always_call, budget=2)
        self.assertEqual(str(caught.exception), platform_texts("zh-CN").model_budget_exceeded.format(limit=2))

    def test_acceptance_reads_the_answer_against_the_tool_result(self):
        def wrong_answer(body, api_key):
            if any(message["role"] == "tool" for message in body["messages"]):
                return reply({"content": "The answer is 41."})
            return reply({"tool_calls": [{"id": "c1", "type": "function",
                                          "function": {"name": "add_numbers", "arguments": '{"a": 19, "b": 23}'}}]})
        _, events = run_case("sum", wrong_answer, locale="en")
        paired = report(events, "report_task_title", "en", "sum")
        self.assertFalse(check(paired, "native_accepted"))
        self.assertFalse(check(paired, "langchain_accepted"))

    def test_broken_and_id_less_proposals_in_a_real_loop(self):
        def broken_then_answer(body, api_key):
            if any(message["role"] == "tool" for message in body["messages"]):
                return reply({"content": "done"})
            return reply({"tool_calls": [{"type": "function", "function": {"name": "add_numbers",
                                                                          "arguments": '{"a": 19, "b": 23}'}},
                                         {"id": "bad", "type": "function",
                                          "function": {"name": "add_numbers", "arguments": "{oops"}}]})
        _, events = run_case("sum", broken_then_answer, locale="en")
        calls = of(events, "tool_call")
        # Native: the platform fills the missing id; LangChain: the adapter does, and says so in framework_output.
        self.assertEqual(calls[0]["id"], "synthesized_call_1_1")
        self.assertTrue(calls[0]["id_synthesized"])
        self.assertEqual(of(events, FRAMEWORK_OUTPUT_EVENT)[0]["synthesized_call_ids"], ["framework_call_1_1"])
        self.assertEqual(of(events, FRAMEWORK_OUTPUT_EVENT)[0]["message"]["invalid_tool_calls"][0]["id"], "bad")
        errors = [item["result"]["error_type"] for item in of(events, "tool_result") if not item["result"]["ok"]]
        self.assertEqual(errors, ["JSONDecodeError", "JSONDecodeError"])
        rows = report(events, "report_task_title", "en", "sum")["table"]["rows"]
        t = texts_for("en")
        self.assertEqual(rows[2][2], t.cell_langchain_parsing.format(valid=1, invalid=1))


class LocalExerciseTests(unittest.TestCase):
    def test_default_tool_coerces_what_the_native_tool_rejects(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("arguments", locale=locale)
                self.assertEqual(of(events, "request"), [], "no model call")
                results = {item["tool_call_id"]: item["result"] for item in of(events, "tool_result")}
                self.assertEqual(results["native-valid"], {"ok": True, "result": 42})
                self.assertEqual(results["default-valid"], {"ok": True, "result": 42.0})
                self.assertEqual(results["default-string"], {"ok": True, "result": 42.0})
                self.assertEqual(results["default-boolean"], {"ok": True, "result": 24.0})
                self.assertEqual(results["native-extra"]["error_type"], "TypeError")
                for case in ("string", "boolean", "extra"):
                    self.assertEqual(results[f"strict-{case}"]["error_type"], "ValidationError")
                self.assertTrue(all(item.get("origin") == "course_program" for item in of(events, "tool_call")))
                data = report(events, "report_arguments_title", locale)
                self.assertFalse(check(data, "default_agrees"))
                self.assertTrue(check(data, "strict_agrees"))
                self.assertEqual(metric(data, "masked"), 3)
                self.assertEqual(answer, t.answer_arguments.format(masked=3, total=4, strict=4))

    def test_parsing_fills_ids_keeps_invalid_calls_and_reorders(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                _, events = run_case("parsing", locale=locale)
                self.assertEqual(of(events, "request"), [])
                self.assertEqual(of(events, "lesson.sample_response")[0]["origin"], "course_program")
                parsed = of(events, "lesson.parse_result")[0]
                self.assertEqual(parsed["synthesized_call_ids"], ["framework_call_1_3"])
                self.assertEqual([item["id"] for item in parsed["message"]["invalid_tool_calls"]],
                                 ["call_cut", "call_list"])
                # The native loop sends the provider message back unchanged, raw arguments and all.
                self.assertNotIn("id", parsed["native_next_message"]["tool_calls"][2])
                self.assertEqual([call["id"] for call in parsed["framework_next_message"]["tool_calls"]],
                                 ["framework_call_1_3", "call_cut", "call_list"])
                self.assertEqual(parsed["framework_next_message"]["tool_calls"][0]["function"]["arguments"],
                                 '{"a": 19, "b": 23}')
                results = {item["tool_call_id"]: item["result"] for item in of(events, "tool_result")}
                self.assertEqual(results["framework_call_1_3"], {"ok": True, "result": 42.0})
                self.assertEqual(results["call_cut"]["error_type"], "JSONDecodeError")
                self.assertEqual(results["call_list"]["error"], platform_texts(locale).tool_arguments_not_object)
                data = report(events, "report_parsing_title", locale)
                self.assertTrue(check(data, "all_answered"))
                self.assertFalse(check(data, "same_order"))
                self.assertEqual(metric(data, "invalid"), 2)


class FrameworkContractTests(unittest.TestCase):
    def test_generated_schema_is_pinned_for_upgrades(self):
        # If a langchain-core upgrade changes what @tool generates, this fails and the comparison must be rerun.
        self.assertEqual(convert_to_openai_tool(add_numbers_tool("en")), {"type": "function", "function": {
            "name": "add_numbers", "description": "Add two numbers. Call it when you need the sum of two numbers.",
            "parameters": {"properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                           "required": ["a", "b"], "type": "object"}}})
        self.assertEqual(convert_to_openai_tool(clock_tool("en"))["function"]["parameters"],
                         {"properties": {}, "type": "object"})

    def test_english_runs_have_no_chinese(self):
        for exercise in ("sum", "divide-zero", "arguments", "parsing"):
            with self.subTest(exercise=exercise):
                answer, events = run_case(exercise, locale="en")
                self.assertIsNone(CJK.search(json.dumps(events, ensure_ascii=False) + answer))

    def test_stop_between_the_two_sides_leaves_no_framework_events(self):
        # Cancelling after the native side's last request must stop before LangChain asks anything.
        seen = []

        def cancelled():
            return len(seen) >= 2

        script = create_completion("sum", {}, "en")
        events = []
        with self.assertRaises(RunCancelled):
            context = RunContext(
                lesson_id="langchain-vs-native", exercise_id="sum", question=QUESTIONS["sum"]["en"], mode="offline",
                model="fixture-model", representation="sdk_standardized", inputs={}, api_key="",
                completion=lambda body, api_key: (seen.append(body), script(body, api_key))[1],
                emit_event=lambda kind, data, number: events.append((kind, data, number)),
                cancelled=cancelled, max_model_calls=6, locale="en")
            execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
        self.assertEqual(of(events, FRAMEWORK_INPUT_EVENT), [])
        self.assertLessEqual(len(seen), 2)

    def test_inputs_cancel_and_unknown_exercise(self):
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {"task": "sum"})
        with self.assertRaises(RunCancelled):
            run_case("sum", cancelled=lambda: True)
        with self.assertRaises(ValueError):
            run_case("nope")


if __name__ == "__main__":
    unittest.main()
