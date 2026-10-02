"""先规划后执行课行为测试：确定性模型数据，工具（含固定失败的主数据源）在 Python 中真实执行。"""
import json
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_plan_and_replan import runtime
from lessons.lesson_plan_and_replan.fixtures import create_completion


def run_case(exercise_id, inputs, completion=None, budget=8, cancelled=lambda: False):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="plan-and-replan", exercise_id=exercise_id, question="", mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def report(events):
    return of(events, "lesson.report")[-1]


def metric(events, label):
    return next(item["value"] for item in report(events)["metrics"] if item["label"] == label)


class ToolAndParserTests(unittest.TestCase):
    def test_primary_source_always_fails_and_backup_works(self):
        with self.assertRaises(ValueError):
            runtime.fetch_quiz_scores("lin", "primary")
        self.assertEqual(runtime.fetch_quiz_scores("lin", "backup")["scores"]["application-state"], 67)
        with self.assertRaises(ValueError):
            runtime.fetch_progress("someone")

    def test_parse_plan_accepts_fences_but_rejects_bad_plans(self):
        plan = runtime.parse_plan('计划如下：\n```json\n{"steps": [{"id": "s1", "tool": "fetch_progress", "arguments": {"learner": "lin"}}]}\n```')
        self.assertEqual(plan["steps"][0]["id"], "s1")
        for bad, message in (("没有计划", "没有 JSON"), ('{"steps": []}', "非空"),
                             ('{"steps": [{"id": "s1", "tool": "rm_rf", "arguments": {}}]}', "未登记"),
                             ('{"steps": [{"id": "s1", "tool": "fetch_progress", "arguments": "lin"}]}', "JSON 对象"),
                             ('{"steps": [{"id": "s1", "tool": "fetch_progress", "arguments": {}}, '
                              '{"id": "s1", "tool": "fetch_progress", "arguments": {}}]}', "唯一")):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, message):
                runtime.parse_plan(bad)

    def test_verify_uses_tool_results_and_report_numbers(self):
        results = {"fetch_progress": runtime.PROGRESS, "fetch_quiz_scores": runtime.SCORES}
        self.assertTrue(all(c["passed"] for c in runtime.verify(results, "82 67 91")))
        self.assertFalse(runtime.verify(results, "82 67")[2]["passed"])
        self.assertEqual([c["passed"] for c in runtime.verify({"fetch_progress": runtime.PROGRESS}, "82 67 91")],
                         [True, False, False])


class StrategyTests(unittest.TestCase):
    def test_static_plan_keeps_going_and_fails_acceptance(self):
        answer, events = run_case("static", {"strategy": "static"})
        plans = of(events, "lesson.plan")
        self.assertEqual({p["version"] for p in plans}, {1})
        self.assertEqual([s["status"] for s in plans[-1]["steps"]], ["done", "failed"])
        self.assertTrue(answer.startswith("验收未通过"))
        self.assertIn("没有拿到", answer)
        self.assertEqual(len(of(events, "request")), 2)

    def test_replan_revises_with_reason_and_diff_after_a_real_failure(self):
        answer, events = run_case("replan", {"strategy": "replan"})
        plans = of(events, "lesson.plan")
        revised = [p for p in plans if p["event"] == "revised"]
        self.assertEqual(len(revised), 1)
        self.assertIn("备份", revised[0]["reason"])
        self.assertEqual(revised[0]["diff"], {"removed": [], "added": ["s3"], "failed_step": "s2"})
        self.assertEqual([s["status"] for s in plans[-1]["steps"]], ["done", "failed", "done"])
        planner_retry = of(events, "request")[1]["body"]["messages"][-1]["content"]
        self.assertIn("成绩主数据源暂时不可用", planner_retry, "修订依据是真实错误信息")
        failed = [d for d in of(events, "tool_result") if not d["result"]["ok"]]
        self.assertEqual(len(failed), 1)
        self.assertTrue(answer.startswith("验收通过"))
        self.assertEqual(metric(events, "修订次数"), 1)

    def test_react_baseline_recovers_without_a_plan(self):
        answer, events = run_case("react", {"strategy": "react"})
        self.assertEqual(of(events, "lesson.plan"), [])
        sources = [json.loads(c["function"]["arguments"]).get("source") for c in of(events, "tool_call")]
        self.assertEqual(sources, [None, "primary", "backup"])
        self.assertTrue(answer.startswith("验收通过"))

    def test_revisions_are_bounded(self):
        def stubborn(body, key):
            messages = body["messages"]
            if messages[0]["content"].startswith("你是规划器"):
                attempt = sum(1 for m in messages if m["role"] == "assistant")
                plan = {"reason": "再试主数据源", "steps": [{"id": f"p{attempt}", "tool": "fetch_quiz_scores",
                        "arguments": {"learner": "lin", "source": "primary"}}]}
                return {"choices": [{"message": {"content": json.dumps(plan)}}]}
            return {"choices": [{"message": {"content": "没有成绩。"}}]}
        answer, events = run_case("replan", {"strategy": "replan"}, stubborn)
        self.assertEqual(metric(events, "修订次数"), runtime.MAX_REVISIONS)
        self.assertEqual(len([d for d in of(events, "tool_result") if not d["result"]["ok"]]), runtime.MAX_REVISIONS + 1)
        self.assertTrue(answer.startswith("验收未通过"))

    def test_bad_plan_is_recorded_not_repaired(self):
        def chatty(body, key):
            return {"choices": [{"message": {"content": "我会先查进度再查成绩。"}}]}
        answer, events = run_case("replan", {"strategy": "replan"}, chatty)
        self.assertEqual(len(of(events, "lesson.plan_error")), 1)
        self.assertEqual(of(events, "tool_call"), [])
        self.assertTrue(answer.startswith("验收未通过"))

    def test_inputs_and_cancel(self):
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {"strategy": "random"})
        with self.assertRaises(RunCancelled):
            run_case("replan", {"strategy": "replan"}, cancelled=lambda: True)


if __name__ == "__main__":
    unittest.main()
