"""“工具定义与调用提议”的行为测试：确定性模型数据；本课只记录提议，任何情况下都不执行工具。"""
import json
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_01_tool_selection import tools
from lessons.lesson_tool_proposals import runtime
from lessons.lesson_tool_proposals.fixtures import create_completion


def run_case(exercise_id, completion=None, question="帮我计算 19 加 23。", cancelled=lambda: False):
    events = []
    context = RunContext(
        lesson_id="tool-proposals", exercise_id=exercise_id, question=question, mode="offline",
        model="fixture-model", representation="http_body", inputs=validate_inputs(runtime, {}), api_key="",
        completion=completion or create_completion(exercise_id), max_model_calls=1,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
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
        self.assertEqual(body["tools"], tools.TOOLS)
        self.assertEqual(body["tool_choice"], "auto")
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "user"])

    def test_sum_proposal_is_recorded_but_never_executed(self):
        # 换掉白名单字典里的函数：真有地方按名字执行工具，测试就会失败。
        never = lambda **_: self.fail("不应执行工具")
        with patch.dict(tools.AVAILABLE_TOOLS, {"add_numbers": never, "get_current_time": never}):
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
