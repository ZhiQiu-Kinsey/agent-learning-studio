"""编排与评估课行为测试：确定性模型数据；格式检查、并行工人与评估循环在 Python 中真实执行。"""
import json
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_orchestrator_evaluator import runtime
from lessons.lesson_orchestrator_evaluator.fixtures import create_completion
from server.envelope import SpanTracker


def run_case(exercise_id, inputs, completion=None, budget=8, cancelled=lambda: False):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="orchestrator-evaluator", exercise_id=exercise_id, question="", mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def metric(events, label):
    return next(item["value"] for item in of(events, "lesson.report")[-1]["metrics"] if item["label"] == label)


class CheckTests(unittest.TestCase):
    def test_question_format(self):
        good = {"question": "q", "options": ["a", "b", "c", "d"], "answer": 2, "explanation": "e"}
        self.assertEqual(runtime.check_question(good), [])
        self.assertIn("四个选项不能重复", runtime.check_question({**good, "options": ["a", "a", "c", "d"]}))
        self.assertIn("answer 必须是 0 到 3 的整数", runtime.check_question({**good, "answer": True}))
        self.assertIn("answer 必须是 0 到 3 的整数", runtime.check_question({**good, "answer": 4}))
        self.assertEqual(runtime.check_question([]), ["不是 JSON 对象"])

    def test_extract_json_reads_objects_and_arrays(self):
        self.assertEqual(runtime.extract_json('结果：[1, 2]'), [1, 2])
        self.assertEqual(runtime.extract_json('```json\n{"a": 1}\n```'), {"a": 1})
        with self.assertRaises(ValueError):
            runtime.extract_json("没有")


class PatternTests(unittest.TestCase):
    def test_single_call_is_the_baseline(self):
        answer, events = run_case("single", {"pattern": "single"})
        self.assertEqual(len(of(events, "request")), 1)
        self.assertEqual(metric(events, "累计 total_tokens"), 300)
        self.assertIn("3/3", answer)

    def test_orchestrator_costs_n_plus_one_and_runs_workers_in_parallel(self):
        answer, events = run_case("orchestrator", {"pattern": "orchestrator"})
        requests = of(events, "request")
        self.assertEqual(len(requests), 4, "1 次编排 + 3 个工人")
        self.assertEqual({r.get("branch") for r in requests[1:]}, {"w1", "w2", "w3"})
        self.assertEqual(metric(events, "累计 total_tokens"), 80 + 3 * 120)
        self.assertEqual(metric(events, "各角色调用"), "编排者 1、工人 3")
        plans = of(events, "lesson.plan")
        self.assertEqual([s["status"] for s in plans[0]["steps"]], ["in_progress"] * 3)
        self.assertEqual([s["status"] for s in plans[-1]["steps"]], ["done"] * 3)
        tracker, opened, closed = SpanTracker(), {}, {}
        for kind, data, number in events:
            span = tracker.place(kind, data, number)[0]
            if kind in ("request", "response") and data.get("branch"):
                (opened if kind == "request" else closed)[data["branch"]] = span
        self.assertEqual(opened, closed)
        self.assertIn("3/3", answer)

    def test_bad_orchestrator_plan_dispatches_no_workers(self):
        def bad(body, key):
            return {"choices": [{"message": {"content": json.dumps({"subtasks": [{"id": "x", "lesson": "12"}]})}}]}
        answer, events = run_case("orchestrator", {"pattern": "orchestrator"}, bad)
        self.assertEqual(len(of(events, "request")), 1)
        self.assertEqual(len(of(events, "lesson.plan_error")), 1)
        self.assertIn("0/3", answer)

    def test_evaluator_loop_revises_then_passes_within_limit(self):
        answer, events = run_case("evaluator", {"pattern": "evaluator", "max_iters": 3})
        reviews = of(events, "lesson.review")
        self.assertEqual([(r["source"], r["verdict"]) for r in reviews], [("evaluator", "revise"), ("evaluator", "pass")])
        drafts = of(events, "lesson.draft")
        self.assertIn("修订版", drafts[1]["question"]["question"])
        self.assertIsNotNone(drafts[1]["previous"])
        self.assertEqual(metric(events, "停止原因"), "评审通过")
        self.assertEqual(len(of(events, "request")), 4)
        self.assertIn("停止原因：评审通过", answer)

    def test_evaluator_limit_and_format_gate(self):
        _, events = run_case("evaluator-once", {"pattern": "evaluator", "max_iters": 1})
        self.assertEqual(metric(events, "停止原因"), "达到迭代上限")
        self.assertEqual(len(of(events, "request")), 2)

        def broken(body, key):
            return {"choices": [{"message": {"content": '{"question": "q", "options": ["a"], "answer": 0, "explanation": "e"}'}}]}
        _, events = run_case("evaluator", {"pattern": "evaluator", "max_iters": 2}, broken)
        reviews = of(events, "lesson.review")
        self.assertEqual({r["source"] for r in reviews}, {"format-check"}, "格式不对时不必请评估者")
        self.assertEqual(len(of(events, "request")), 2)
        self.assertEqual(metric(events, "累计 total_tokens"), "未报告")

    def test_inputs_and_cancel(self):
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {"pattern": "evaluator", "max_iters": 0})
        with self.assertRaises(RunCancelled):
            run_case("orchestrator", {"pattern": "orchestrator"}, cancelled=lambda: True)


if __name__ == "__main__":
    unittest.main()
