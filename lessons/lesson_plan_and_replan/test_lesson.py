"""Behavior tests for plan-and-replan: deterministic model data; the tools (including the always-failing primary source) really run in Python."""
import json
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_plan_and_replan import runtime
from lessons.lesson_plan_and_replan.fixtures import create_completion
from lessons.lesson_plan_and_replan.locales import texts_for
from server.selectors import resolve_path

ZH, EN = texts_for("zh-CN"), texts_for("en")


def run_case(exercise_id, inputs, completion=None, budget=8, cancelled=lambda: False, locale="zh-CN"):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="plan-and-replan", exercise_id=exercise_id, question="", mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def report(events):
    return of(events, "lesson.report")[-1]


def metrics(events, locale="zh-CN"):
    """Report metrics keyed by catalog field name, so one assertion covers both languages."""
    t = texts_for(locale)
    names = {getattr(t, field): field for field in vars(t) if field.startswith("label_")}
    return {names[item["label"]]: item["value"] for item in report(events)["metrics"]}


def plan_reply(plan):
    return {"choices": [{"message": {"content": json.dumps(plan)}}]}


class ToolAndParserTests(unittest.TestCase):
    def test_primary_source_always_fails_and_backup_works(self):
        with self.assertRaises(ValueError):
            runtime.fetch_quiz_scores(ZH, "lin", "primary")
        self.assertEqual(runtime.fetch_quiz_scores(ZH, "lin", "backup")["scores"]["application-state"], 67)
        with self.assertRaises(ValueError):
            runtime.fetch_progress(ZH, "someone")

    def test_tool_errors_follow_the_run_language(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                tools = runtime.available_tools(locale)
                with self.assertRaises(ValueError) as caught:
                    tools["fetch_quiz_scores"](learner="lin", source="primary")
                self.assertEqual(str(caught.exception), texts_for(locale).primary_unavailable)
                with self.assertRaises(TypeError):
                    tools["fetch_progress"](t="x", learner="lin")
        self.assertIn("可以改用 source=backup", ZH.primary_unavailable)
        self.assertIn("source=backup", EN.primary_unavailable)

    def test_parse_plan_accepts_fences_but_rejects_bad_plans(self):
        plan = runtime.parse_plan('计划如下：\n```json\n{"steps": [{"id": "s1", "tool": "fetch_progress", "arguments": {"learner": "lin"}}]}\n```', ZH)
        self.assertEqual(plan["steps"][0]["id"], "s1")
        for bad, message in (("没有计划", "没有 JSON"), ('{"steps": []}', "非空"),
                             ('{"steps": [{"id": "s1", "tool": "rm_rf", "arguments": {}}]}', "未登记"),
                             ('{"steps": [{"id": "s1", "tool": "fetch_progress", "arguments": "lin"}]}', "JSON 对象"),
                             ('{"steps": [{"id": "s1", "tool": "fetch_progress", "arguments": {}}, '
                              '{"id": "s1", "tool": "fetch_progress", "arguments": {}}]}', "唯一")):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, message):
                runtime.parse_plan(bad, ZH)
        with self.assertRaisesRegex(ValueError, "unregistered tool: rm_rf"):
            runtime.parse_plan('{"steps": [{"id": "s1", "tool": "rm_rf", "arguments": {}}]}', EN)

    def test_parse_plan_rejects_ids_used_by_earlier_versions(self):
        plan = '{"steps": [{"id": "s2", "tool": "fetch_quiz_scores", "arguments": {"learner": "lin"}}]}'
        self.assertEqual(runtime.parse_plan(plan, ZH, {"s1"})["steps"][0]["id"], "s2")
        for locale in ("zh-CN", "en"):
            t = texts_for(locale)
            with self.subTest(locale=locale), self.assertRaises(ValueError) as caught:
                runtime.parse_plan(plan, t, {"s1", "s2"})
            self.assertEqual(str(caught.exception), t.plan_reused_id.format(step_id="s2"))

    def test_verify_uses_tool_results_and_report_numbers(self):
        results = {"fetch_progress": runtime.PROGRESS, "fetch_quiz_scores": runtime.SCORES}
        self.assertTrue(all(c["passed"] for c in runtime.verify(results, "82 67 91", ZH)))
        self.assertFalse(runtime.verify(results, "82 67", ZH)[2]["passed"])
        self.assertEqual([c["passed"] for c in runtime.verify({"fetch_progress": runtime.PROGRESS}, "82 67 91", ZH)],
                         [True, False, False])
        self.assertEqual(runtime.verify(results, "82 67 91", ZH)[2]["detail"], "周报包含 82、67、91")
        self.assertEqual(runtime.verify(results, "82 67 91", EN)[2]["detail"], "The report contains 82, 67, 91")


class StrategyTests(unittest.TestCase):
    def test_static_plan_keeps_going_and_fails_acceptance(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                answer, events = run_case("static", {"strategy": "static"}, locale=locale)
                plans = of(events, "lesson.plan")
                self.assertEqual({p["version"] for p in plans}, {1})
                self.assertEqual([s["status"] for s in plans[-1]["steps"]], ["done", "failed"])
                self.assertTrue(answer.startswith(texts_for(locale).verdict_failed))
                self.assertEqual(len(of(events, "request")), 2)
                self.assertEqual(of(events, "request")[0]["body"]["messages"][0]["content"],
                                 texts_for(locale).planner_system)
        answer, _ = run_case("static", {"strategy": "static"})
        self.assertIn("没有拿到", answer)

    def test_replan_revises_with_reason_and_diff_after_a_real_failure(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("replan", {"strategy": "replan"}, locale=locale)
                plans = of(events, "lesson.plan")
                revised = [p for p in plans if p["event"] == "revised"]
                self.assertEqual(len(revised), 1)
                self.assertEqual(revised[0]["diff"], {"removed": [], "added": ["s3"], "failed_step": "s2"})
                self.assertEqual([s["status"] for s in plans[-1]["steps"]], ["done", "failed", "done"])
                planner_retry = of(events, "request")[1]["body"]["messages"][-1]["content"]
                self.assertIn(t.primary_unavailable, planner_retry, "the revision is based on the real error")
                failed = [d for d in of(events, "tool_result") if not d["result"]["ok"]]
                self.assertEqual(len(failed), 1)
                self.assertTrue(answer.startswith(t.verdict_passed))
                self.assertEqual(metrics(events, locale)["label_revisions"], 1)
        _, events = run_case("replan", {"strategy": "replan"})
        revised = [p for p in of(events, "lesson.plan") if p["event"] == "revised"]
        self.assertIn("备份", revised[0]["reason"])
        self.assertTrue(of(events, "request")[1]["body"]["messages"][-1]["content"].startswith("执行情况："))

    def test_model_call_metric_is_found_by_id_in_both_languages(self):
        # The lab's cost observation point selects data.metrics[id=model_calls], not a position.
        for locale in ("zh-CN", "en"):
            for strategy in ("static", "replan", "react"):
                with self.subTest(locale=locale, strategy=strategy):
                    _, events = run_case(strategy, {"strategy": strategy}, locale=locale)
                    entry = resolve_path({"data": report(events)}, "data.metrics[id=model_calls]")
                    self.assertEqual(entry["label"], texts_for(locale).label_model_calls)
                    self.assertEqual(entry["value"], len(of(events, "request")))

    def test_react_baseline_recovers_without_a_plan(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                answer, events = run_case("react", {"strategy": "react"}, locale=locale)
                self.assertEqual(of(events, "lesson.plan"), [])
                self.assertEqual(of(events, "request")[0]["body"]["tools"], runtime.tool_definitions(locale))
                sources = [json.loads(c["function"]["arguments"]).get("source") for c in of(events, "tool_call")]
                self.assertEqual(sources, [None, "primary", "backup"])
                self.assertTrue(answer.startswith(texts_for(locale).verdict_passed))

    def test_revisions_are_bounded(self):
        def stubborn(body, key):
            messages = body["messages"]
            if messages[0]["content"] == ZH.planner_system:
                attempt = sum(1 for m in messages if m["role"] == "assistant")
                return plan_reply({"reason": "再试主数据源", "steps": [{"id": f"p{attempt}", "tool": "fetch_quiz_scores",
                                   "arguments": {"learner": "lin", "source": "primary"}}]})
            return {"choices": [{"message": {"content": "没有成绩。"}}]}
        answer, events = run_case("replan", {"strategy": "replan"}, stubborn)
        self.assertEqual(metrics(events)["label_revisions"], runtime.MAX_REVISIONS)
        self.assertEqual(len([d for d in of(events, "tool_result") if not d["result"]["ok"]]), runtime.MAX_REVISIONS + 1)
        self.assertTrue(answer.startswith("验收未通过"))

    def test_a_revision_that_reuses_a_step_id_is_rejected(self):
        def reuse(body, key):
            messages = body["messages"]
            if messages[0]["content"] == EN.planner_system:
                revising = any(m["role"] == "assistant" for m in messages)
                # The revision reuses s2, the id of the step that just failed.
                steps = ([{"id": "s2", "tool": "fetch_quiz_scores", "arguments": {"learner": "lin", "source": "backup"}}]
                         if revising else
                         [{"id": "s1", "tool": "fetch_progress", "arguments": {"learner": "lin"}},
                          {"id": "s2", "tool": "fetch_quiz_scores", "arguments": {"learner": "lin", "source": "primary"}}])
                return plan_reply({"reason": "r", "steps": steps})
            return {"choices": [{"message": {"content": "No scores."}}]}
        answer, events = run_case("replan", {"strategy": "replan"}, reuse, locale="en")
        errors = of(events, "lesson.plan_error")
        self.assertEqual([e["error"] for e in errors], [EN.plan_reused_id.format(step_id="s2")])
        self.assertEqual([p["event"] for p in of(events, "lesson.plan") if p["event"] != "progress"], ["created"])
        self.assertEqual(len(of(events, "tool_call")), 2, "the rejected revision runs no tool")
        self.assertTrue(answer.startswith(EN.verdict_failed))

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
