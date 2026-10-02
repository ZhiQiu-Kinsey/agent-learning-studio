"""“多轮对话：程序重发历史”的行为测试：确定性模型数据，检查每轮实际发出的消息与报告。"""
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_multi_turn_history import runtime
from lessons.lesson_multi_turn_history.fixtures import create_completion


def run_case(exercise_id, inputs, completion=None, budget=3, cancelled=lambda: False):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="multi-turn-history", exercise_id=exercise_id, question="", mode="offline",
        model="fixture-model", representation="http_body", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def requests(events):
    return [(data["body"]["messages"], number) for kind, data, number in events if kind == "request"]


def report(events):
    return [data for kind, data, _ in events if kind == "lesson.report"][-1]


class HistoryTests(unittest.TestCase):
    def test_with_history_resends_the_first_turn(self):
        answer, events = run_case("with-history", {"history": "full", "turns": 2})
        sent = requests(events)
        self.assertEqual([number for _, number in sent], [1, 2])
        first, second = sent[0][0], sent[1][0]
        self.assertEqual([m["role"] for m in first], ["system", "user"])
        self.assertEqual([m["role"] for m in second], ["system", "user", "assistant", "user"])
        # 第一轮的回答原样放回第二轮请求。
        first_reply = [d for k, d, _ in events if k == "response"][0]["body"]["choices"][0]["message"]["content"]
        self.assertEqual(second[2]["content"], first_reply)
        self.assertIn("团子", answer)
        checks = {check["label"]: check["passed"] for check in report(events)["checks"]}
        self.assertTrue(checks["第二轮请求里有第一轮说的事实"])
        self.assertTrue(checks["第二轮回答提到了这个事实"])

    def test_without_history_only_sends_the_latest_question(self):
        answer, events = run_case("without-history", {"history": "latest_only", "turns": 2})
        sent = requests(events)
        # 第一轮两组完全相同，差别只在第二轮发什么。
        self.assertEqual(sent[0][0], requests(run_case("with-history", {"history": "full", "turns": 2})[1])[0][0])
        self.assertEqual([m["role"] for m in sent[1][0]], ["system", "user"])
        self.assertEqual(sent[1][0][1]["content"], runtime.TURNS[1])
        self.assertNotIn("团子", answer)
        checks = {check["label"]: check["passed"] for check in report(events)["checks"]}
        self.assertFalse(checks["第二轮请求里有第一轮说的事实"])

    def test_three_turns_grow_and_report_each_prompt(self):
        answer, events = run_case("three-turns", {"history": "full", "turns": 3})
        sent = requests(events)
        self.assertEqual([len(messages) for messages, _ in sent], [2, 4, 6])
        rows = report(events)["table"]["rows"]
        prompts = [row[3] for row in rows]
        self.assertEqual(len(rows), 3)
        # 报告里的消息数必须等于实际发出的条数（之后追加的回答不能算进去）。
        self.assertEqual([row[1] for row in rows], [2, 4, 6])
        metrics = {item["label"]: item["value"] for item in report(events)["metrics"]}
        self.assertEqual(metrics["最后一轮发出的消息数"], 6)
        self.assertTrue(prompts[0] < prompts[1] < prompts[2])
        usage = [d["body"]["usage"]["prompt_tokens"] for k, d, _ in events if k == "response"]
        self.assertEqual(prompts, usage)
        self.assertIn("三岁", answer)

    def test_recorded_requests_are_snapshots(self):
        # 之后往 history 里追加消息，不会改动已经记录的请求。
        _, events = run_case("three-turns", {"history": "full", "turns": 3})
        self.assertEqual(len(requests(events)[0][0]), 2)

    def test_missing_usage_is_unreported(self):
        def provider(body, key):
            return {"choices": [{"message": {"role": "assistant", "content": "好"}, "finish_reason": "stop"}]}
        _, events = run_case("with-history", {"history": "full", "turns": 2}, provider)
        data = report(events)
        self.assertEqual(data["table"]["rows"][0][3], "未报告")
        metrics = {item["label"]: item["value"] for item in data["metrics"]}
        self.assertEqual(metrics["提示 Token 从第一轮到最后一轮"], "未报告")


class BoundaryTests(unittest.TestCase):
    def test_inputs_are_bounded(self):
        for bad in ({"turns": 1}, {"turns": 4}, {"history": "summary"}, {"extra": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)

    def test_budget_and_cancel(self):
        with self.assertRaisesRegex(RuntimeError, "超过 2 次"):
            run_case("three-turns", {"history": "full", "turns": 3}, budget=2)
        with self.assertRaises(RunCancelled):
            run_case("with-history", {}, cancelled=lambda: True)

    def test_malformed_response_raises(self):
        with self.assertRaisesRegex(ValueError, "choices"):
            run_case("with-history", {}, lambda body, key: {})


if __name__ == "__main__":
    unittest.main()
