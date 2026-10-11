"""Behavior tests for orchestrator-evaluator: deterministic model data; format checks, parallel workers and the revision loop really run in Python."""
import json
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_orchestrator_evaluator import runtime
from lessons.lesson_orchestrator_evaluator.fixtures import create_completion
from lessons.lesson_orchestrator_evaluator.locales import texts_for
from server.envelope import SpanTracker

LOCALES = ("zh-CN", "en")


def run_case(exercise_id, inputs, completion=None, budget=8, cancelled=lambda: False, locale="zh-CN"):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="orchestrator-evaluator", exercise_id=exercise_id, question="", mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def metric(events, field, locale="zh-CN"):
    """A report metric by catalog field name, so one assertion covers both languages."""
    label = getattr(texts_for(locale), field)
    return next(item["value"] for item in of(events, "lesson.report")[-1]["metrics"] if item["label"] == label)


def content(text):
    return {"choices": [{"message": {"content": text}}]}


class CheckTests(unittest.TestCase):
    def test_question_format(self):
        good = {"question": "q", "options": ["a", "b", "c", "d"], "answer": 2, "explanation": "e"}
        for locale in LOCALES:
            t = texts_for(locale)
            with self.subTest(locale=locale):
                self.assertEqual(runtime.check_question(t, good), [])
                self.assertIn(t.options_duplicate, runtime.check_question(t, {**good, "options": ["a", "a", "c", "d"]}))
                self.assertIn(t.answer_invalid, runtime.check_question(t, {**good, "answer": True}))
                self.assertIn(t.answer_invalid, runtime.check_question(t, {**good, "answer": 4}))
                self.assertEqual(runtime.check_question(t, []), [t.not_an_object])
        zh = texts_for("zh-CN")
        self.assertIn("四个选项不能重复", runtime.check_question(zh, {**good, "options": ["a", "a", "c", "d"]}))
        self.assertIn("answer 必须是 0 到 3 的整数", runtime.check_question(zh, {**good, "answer": True}))

    def test_extract_json_reads_objects_and_arrays(self):
        t = texts_for("en")
        self.assertEqual(runtime.extract_json(t, '结果：[1, 2]'), [1, 2])
        self.assertEqual(runtime.extract_json(t, '```json\n{"a": 1}\n```'), {"a": 1})
        for locale in LOCALES:
            with self.assertRaises(ValueError) as caught:
                runtime.extract_json(texts_for(locale), "没有")
            self.assertEqual(str(caught.exception), texts_for(locale).no_json_found)


class PatternTests(unittest.TestCase):
    def test_single_call_is_the_baseline(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_case("single", {"pattern": "single"}, locale=locale)
                self.assertEqual(len(of(events, "request")), 1)
                self.assertEqual(metric(events, "label_total_tokens", locale), 300)
                self.assertIn("3/3", answer)
        _, events = run_case("single", {"pattern": "single"}, locale="en")
        user = of(events, "request")[0]["body"]["messages"][1]["content"]
        self.assertTrue(user.startswith(texts_for("en").task + "\nKey points: "))

    def test_orchestrator_costs_n_plus_one_and_runs_workers_in_parallel(self):
        answer, events = run_case("orchestrator", {"pattern": "orchestrator"})
        requests = of(events, "request")
        self.assertEqual(len(requests), 4, "1 orchestrator call + 3 workers")
        self.assertEqual({r.get("branch") for r in requests[1:]}, {"w1", "w2", "w3"})
        self.assertEqual(metric(events, "label_total_tokens"), 80 + 3 * 120)
        self.assertEqual(metric(events, "label_role_calls"), "编排者 1、工人 3")
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

    def test_english_orchestrator_run(self):
        t = texts_for("en")
        answer, events = run_case("orchestrator", {"pattern": "orchestrator"}, locale="en")
        requests = of(events, "request")
        self.assertEqual(requests[0]["body"]["messages"][0]["content"], t.orchestrator_system)
        self.assertEqual(requests[1]["body"]["messages"][0]["content"], t.worker_system)
        self.assertEqual(metric(events, "label_role_calls", "en"), "orchestrator 1, worker 3")
        self.assertEqual([row["role"] for row in of(events, "lesson.cost")[0]["calls"]],
                         ["orchestrator", "worker", "worker", "worker"])
        self.assertEqual(of(events, "lesson.report")[-1]["title"], "Orchestrator-workers")
        self.assertEqual(answer, "Model calls: 4. Questions that passed the format check: 3/3.")

    def test_bad_orchestrator_plan_dispatches_no_workers(self):
        def bad(body, key):
            return content(json.dumps({"subtasks": [{"id": "x", "lesson": "12"}]}))
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_case("orchestrator", {"pattern": "orchestrator"}, bad, locale=locale)
                self.assertEqual(len(of(events, "request")), 1)
                self.assertEqual(of(events, "lesson.plan_error")[0]["error"], texts_for(locale).plan_error)
                self.assertIn("0/3", answer)

    def test_evaluator_loop_revises_then_passes_within_limit(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("evaluator", {"pattern": "evaluator", "max_iters": 3}, locale=locale)
                reviews = of(events, "lesson.review")
                self.assertEqual([(r["source"], r["verdict"]) for r in reviews],
                                 [("evaluator", "revise"), ("evaluator", "pass")])
                drafts = of(events, "lesson.draft")
                self.assertIsNotNone(drafts[1]["previous"])
                self.assertEqual([d["unchanged"] for d in drafts], [False, False])
                # Only a revision carries revises, the version it revises; the first version has no such field.
                self.assertNotIn("revises", drafts[0])
                self.assertEqual(drafts[1]["revises"], drafts[0]["version"])
                self.assertEqual(metric(events, "label_stop_reason", locale), t.stop_reasons["passed"])
                self.assertEqual(len(of(events, "request")), 4)
                self.assertEqual(answer, t.answer_with_stop.format(calls=4, ok=1, total=1, reason=t.stop_reasons["passed"]))
        _, events = run_case("evaluator", {"pattern": "evaluator", "max_iters": 3})
        self.assertIn("修订版", of(events, "lesson.draft")[1]["question"]["question"])
        revision = of(events, "request")[2]["body"]["messages"][1]["content"]
        self.assertIn("\n评审意见：[\"干扰项太容易排除\"]\n请修订。", revision)
        _, events = run_case("evaluator", {"pattern": "evaluator", "max_iters": 3}, locale="en")
        self.assertIn("(revised)", of(events, "lesson.draft")[1]["question"]["question"])

    def test_evaluator_limit_and_format_gate(self):
        _, events = run_case("evaluator-once", {"pattern": "evaluator", "max_iters": 1})
        self.assertEqual(metric(events, "label_stop_reason"), "达到迭代上限")
        self.assertEqual(len(of(events, "request")), 2)

        outputs = iter(['{"question": "q", "options": ["a"], "answer": 0, "explanation": "e"}',
                        '{"question": "q2", "options": ["a"], "answer": 0, "explanation": "e"}'])

        def broken(body, key):
            return content(next(outputs))
        _, events = run_case("evaluator", {"pattern": "evaluator", "max_iters": 2}, broken)
        reviews = of(events, "lesson.review")
        self.assertEqual({r["source"] for r in reviews}, {"format-check"}, "no evaluator call for a format problem")
        self.assertEqual(len(of(events, "request")), 2)
        self.assertEqual(metric(events, "label_total_tokens"), "未报告")
        self.assertEqual(metric(events, "label_stop_reason"), "达到迭代上限")
        # The first version did not reach the evaluator, so the revision lands in round 2, not 3; revises is still only on the revision.
        drafts = [(number, "revises" in data) for kind, data, number in events if kind == "lesson.draft"]
        self.assertEqual(drafts, [(1, False), (2, True)])

    def test_unchanged_revision_stops_before_another_review(self):
        def stuck(body, key):
            if body["messages"][0]["content"] in (texts_for(l).evaluator_system for l in LOCALES):
                return content(json.dumps({"verdict": "revise", "feedback": ["x"]}))
            return content('{"question": "q", "options": ["a", "b", "c", "d"], "answer": 0, "explanation": "e"}')
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("evaluator", {"pattern": "evaluator", "max_iters": 3}, stuck, locale=locale)
                # Generator, evaluator, generator: the unchanged revision is not sent to the evaluator again.
                self.assertEqual(len(of(events, "request")), 3)
                self.assertEqual(len(of(events, "lesson.review")), 1)
                self.assertEqual([d["unchanged"] for d in of(events, "lesson.draft")], [False, True])
                self.assertEqual(metric(events, "label_stop_reason", locale), t.stop_reasons["unchanged"])
                self.assertTrue(answer.endswith(t.answer_with_stop.format(calls=3, ok=1, total=1,
                                                                          reason=t.stop_reasons["unchanged"])))
        _, events = run_case("evaluator", {"pattern": "evaluator", "max_iters": 3}, stuck)
        self.assertEqual(metric(events, "label_stop_reason"), "修订后没有变化")

        def same_broken(body, key):
            return content("not JSON at all")
        _, events = run_case("evaluator", {"pattern": "evaluator", "max_iters": 3}, same_broken)
        # Unparseable output is compared as raw text: the same text again also counts as unchanged.
        self.assertEqual(len(of(events, "request")), 2)
        self.assertEqual(metric(events, "label_stop_reason"), "修订后没有变化")

    def test_inputs_and_cancel(self):
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {"pattern": "evaluator", "max_iters": 0})
        with self.assertRaises(RunCancelled):
            run_case("orchestrator", {"pattern": "orchestrator"}, cancelled=lambda: True)


if __name__ == "__main__":
    unittest.main()
