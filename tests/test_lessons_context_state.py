"""第 7–8 课的离线行为回归。"""
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_07_messages_context import fixtures as context_fixtures
from lessons.lesson_07_messages_context import runtime as context_runtime
from lessons.lesson_08_application_state import runtime as state_runtime


def make_context(lesson_id, exercise_id, inputs, completion=None, cancelled=lambda: False):
    events = []
    context = RunContext(
        lesson_id=lesson_id, exercise_id=exercise_id, question="", mode="offline",
        model="test-model", representation="offline", inputs=inputs,
        api_key="", completion=completion,
        emit_event=lambda kind, data, round_number: events.append((kind, data, round_number)),
        cancelled=cancelled, max_model_calls=3,
    )
    return context, events


class MessagesContextTests(unittest.TestCase):
    def test_full_vs_omitted_history_uses_three_real_completion_calls(self):
        values = validate_inputs(context_runtime, {})
        context, events = make_context("7", "compare", values, context_fixtures.create_completion("compare", values))
        result = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, context_runtime, context)
        requests = [data["body"] for kind, data, _ in events if kind == "request"]
        self.assertEqual(len(requests), 3)
        self.assertEqual(len(requests[1]["messages"]), 4)
        self.assertEqual(len(requests[2]["messages"]), 2)
        self.assertNotIn(values["fact"], str(requests[2]))
        self.assertEqual([kind for kind, _, _ in events].count("response"), 3)
        self.assertIn("已保存", result)

    def test_full_only_respects_two_call_budget(self):
        values = validate_inputs(context_runtime, {"comparison": "full_only"})
        context, events = make_context("7", "full", values, context_fixtures.create_completion("full", values))
        context.max_model_calls = 2
        context_runtime.run(context)
        self.assertEqual([kind for kind, _, _ in events].count("request"), 2)
        report = next(data for kind, data, _ in events if kind == "lesson.report")
        self.assertFalse(any("消融" in check["label"] for check in report["checks"]))

    def test_question_override_and_multiline_fact_visibility(self):
        values = validate_inputs(context_runtime, {"fact": "代号是\nQH-\"731\"。"})
        context, events = make_context("7", "compare", values, context_fixtures.create_completion("compare", values))
        context.question = "请回答当前自定义追问"
        context_runtime.run(context)
        requests = [data["body"]["messages"] for kind, data, _ in events if kind == "request"]
        self.assertEqual(requests[1][-1]["content"], "请回答当前自定义追问")
        self.assertEqual(requests[2][-1]["content"], "请回答当前自定义追问")
        report = next(data for kind, data, _ in events if kind == "lesson.report")
        self.assertTrue(all(check["passed"] for check in report["checks"]))

    def test_protocol_rejects_orphan_tool_result_and_unfinished_call(self):
        with self.assertRaises(ValueError):
            context_runtime.validate_tool_history([{"role": "tool", "tool_call_id": "x", "content": "3"}])
        with self.assertRaises(ValueError):
            context_runtime.validate_tool_history([{"role": "assistant", "tool_calls": [{"id": "x"}]}])
        context_runtime.validate_tool_history([{"role": "assistant", "tool_calls": [{"id": "x"}]},
                                               {"role": "tool", "tool_call_id": "x", "content": "3"}])

    def test_input_contract(self):
        with self.assertRaises(ValidationError):
            validate_inputs(context_runtime, {"fact": "x"})
        with self.assertRaises(ValidationError):
            validate_inputs(context_runtime, {"unexpected": "value"})


class ApplicationStateTests(unittest.TestCase):
    def test_success_has_evidence_and_distinct_messages(self):
        values = validate_inputs(state_runtime, {})
        context, events = make_context("8", "success", values)
        answer = state_runtime.run(context)
        states = [data["state"] for kind, data, _ in events if kind == "lesson.state"]
        self.assertEqual(states[-1]["status"], "completed")
        self.assertEqual(len(states[-1]["evidence"]), 1)
        metrics = next(data for kind, data, _ in events if kind == "lesson.report")["metrics"]
        self.assertEqual(next(item["value"] for item in metrics if item["label"] == "消息数"), 1)
        self.assertEqual(next(item["value"] for item in metrics if item["label"] == "已执行步骤"), 3)
        self.assertIn("lesson-07", answer)

    def test_missing_and_budget_are_distinct_failures(self):
        for scenario in ("missing", "budget"):
            values = validate_inputs(state_runtime, {"scenario": scenario, "step_budget": 2 if scenario == "budget" else 3})
            context, events = make_context("8", scenario, values)
            state_runtime.run(context)
            states = [data["state"] for kind, data, _ in events if kind == "lesson.state"]
            self.assertEqual(states[-1]["status"], "failed")
            self.assertTrue(states[-1]["terminal_reason"])
            self.assertEqual(len(states[-1]["evidence"]), 0 if scenario == "missing" else 1)
            self.assertEqual(states[-1]["used_steps"], 1 if scenario == "missing" else 2)
            self.assertEqual("waiting" in [s["status"] for s in states], scenario == "missing")

    def test_invalid_transition_and_cancel(self):
        state = state_runtime.TaskState(run_id="one", goal="可检查的目标")
        with self.assertRaises(ValueError):
            state.transition("completed", "未经执行")
        state.transition("running")
        with self.assertRaises(ValueError):
            state.transition("completed", "没有证据")
        state.evidence.append({"source": "x"})
        with self.assertRaises(ValueError):
            state.transition("completed", "没有产物")
        state.transition("cancelled", "用户停止")
        with self.assertRaises(ValueError):
            state.transition("running")
        values = validate_inputs(state_runtime, {})
        context, _ = make_context("8", "success", values, cancelled=lambda: True)
        with self.assertRaises(RunCancelled):
            state_runtime.run(context)

    def test_input_contract(self):
        for invalid in ({"step_budget": 0}, {"source_key": "../../private"}, {"scenario": "unknown"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                validate_inputs(state_runtime, invalid)


if __name__ == "__main__":
    unittest.main()
