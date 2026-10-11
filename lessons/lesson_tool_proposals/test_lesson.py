"""Behavior tests for tool-proposals: deterministic model data; the lesson only records proposals and never executes a tool."""
import json
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_01_tool_selection import tools
from lessons.lesson_tool_proposals import runtime
from lessons.lesson_tool_proposals.fixtures import create_completion
from lessons.lesson_tool_proposals.locales import texts_for


def run_case(exercise_id, completion=None, question="帮我计算 19 加 23。", cancelled=lambda: False, locale="zh-CN"):
    events = []
    context = RunContext(
        lesson_id="tool-proposals", exercise_id=exercise_id, question=question, mode="offline",
        model="fixture-model", representation="http_body", inputs=validate_inputs(runtime, {}), api_key="",
        completion=completion or create_completion(exercise_id, locale=locale), max_model_calls=1,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def reply(message, finish_reason):
    return lambda body, key: {"choices": [{"message": {"role": "assistant", **message}, "finish_reason": finish_reason}]}


class ProposalTests(unittest.TestCase):
    def test_request_carries_the_tool_definitions(self):
        _, events = run_case("sum")
        body = of(events, "request")[0]["body"]
        self.assertEqual(body["tools"], tools.tool_definitions("zh-CN"))
        self.assertEqual(body["tool_choice"], "auto")
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "user"])

    def test_sum_proposal_is_recorded_but_never_executed(self):
        # Replace the allowlisted functions: if anything executed a tool by name, the test would fail.
        never = lambda *_, **__: self.fail("no tool may be executed")
        with patch.object(tools, "add_numbers", never), patch.object(tools, "get_current_time", never):
            answer, events = run_case("sum")
        self.assertEqual(of(events, "tool_call"), [])
        self.assertEqual(of(events, "tool_result"), [])
        report = of(events, "lesson.report")[-1]
        self.assertEqual(report["table"]["rows"], [["offline_call_1", "add_numbers", json.dumps({"a": 19, "b": 23}), True]])
        metrics = {item["label"]: item["value"] for item in report["metrics"]}
        self.assertEqual(metrics["finish_reason"], "tool_calls")
        self.assertEqual(metrics["调用提议数"], 1)
        self.assertIn("add_numbers", answer)
        self.assertIn("本课不执行工具", answer)

    def test_time_proposal(self):
        answer, events = run_case("time", question="现在本地时间是几点？")
        self.assertEqual(of(events, "lesson.report")[-1]["table"]["rows"][0][1], "get_current_time")
        self.assertEqual(of(events, "tool_result"), [])
        self.assertIn("get_current_time({})", answer)

    def test_chat_answers_directly_without_proposals(self):
        answer, events = run_case("chat", question="你好，用一句话介绍一下你自己。")
        report = of(events, "lesson.report")[-1]
        self.assertEqual(report["table"]["rows"], [])
        self.assertEqual({item["label"]: item["value"] for item in report["metrics"]}["finish_reason"], "stop")
        self.assertEqual(answer, of(events, "response")[0]["body"]["choices"][0]["message"]["content"])

    def test_invalid_json_arguments_are_shown_not_repaired(self):
        call = {"id": "c1", "type": "function", "function": {"name": "add_numbers", "arguments": "{a: 19}"}}
        answer, events = run_case("sum", reply({"content": None, "tool_calls": [call]}, "tool_calls"))
        row = of(events, "lesson.report")[-1]["table"]["rows"][0]
        self.assertEqual(row[2:], ["{a: 19}", False])
        self.assertIn("{a: 19}", answer)

    def test_unknown_tool_name_is_only_listed(self):
        call = {"id": "c2", "type": "function", "function": {"name": "delete_files", "arguments": "{}"}}
        _, events = run_case("sum", reply({"content": None, "tool_calls": [call]}, "tool_calls"))
        self.assertEqual(of(events, "lesson.report")[-1]["table"]["rows"][0][1], "delete_files")
        self.assertEqual(of(events, "tool_call"), [])

    def test_two_proposals_in_one_response(self):
        calls = [{"id": "a", "type": "function", "function": {"name": "add_numbers", "arguments": "{\"a\":1,\"b\":2}"}},
                 {"id": "b", "type": "function", "function": {"name": "get_current_time", "arguments": "{}"}}]
        answer, events = run_case("sum", reply({"content": None, "tool_calls": calls}, "tool_calls"))
        self.assertEqual(len(of(events, "lesson.report")[-1]["table"]["rows"]), 2)
        self.assertIn("2 个调用", answer)


class EnglishRunTests(unittest.TestCase):
    def test_english_run_sends_and_reports_in_english(self):
        t = texts_for("en")
        answer, events = run_case("sum", question="Add 19 and 23 for me.", locale="en")
        body = of(events, "request")[0]["body"]
        self.assertEqual(body["messages"][0]["content"], t.system_prompt)
        self.assertEqual(body["tools"], tools.tool_definitions("en"))
        report = of(events, "lesson.report")[-1]
        self.assertEqual(report["title"], t.report_title)
        self.assertEqual(report["table"]["columns"], list(t.columns))
        metrics = {item["label"]: item["value"] for item in report["metrics"]}
        self.assertEqual(metrics[t.label_proposal_count], 1)
        self.assertEqual(answer, t.proposals_answer.format(count=1, calls='add_numbers({"a": 19, "b": 23})'))

    def test_english_defaults_and_errors(self):
        t = texts_for("en")
        _, events = run_case("sum", question="  ", locale="en")
        self.assertEqual(of(events, "request")[0]["body"]["messages"][1]["content"], t.default_question)
        answer, _ = run_case("sum", reply({"content": None}, "stop"), locale="en")
        self.assertEqual(answer, t.empty_content)
        with self.assertRaisesRegex(ValueError, "choices"):
            run_case("sum", lambda body, key: {"choices": []}, locale="en")
        _, events = run_case("chat", question="Hello", locale="en")
        self.assertTrue(of(events, "response")[0]["body"]["choices"][0]["message"]["content"]
                        .startswith("[Offline script answer]"))


class BoundaryTests(unittest.TestCase):
    def test_no_inputs_are_accepted(self):
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {"execute": True})

    def test_malformed_response_and_cancel(self):
        with self.assertRaisesRegex(ValueError, "choices"):
            run_case("sum", lambda body, key: {"choices": []})
        with self.assertRaises(RunCancelled):
            run_case("sum", cancelled=lambda: True)


if __name__ == "__main__":
    unittest.main()
