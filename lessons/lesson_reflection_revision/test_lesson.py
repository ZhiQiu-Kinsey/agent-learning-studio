"""第 16 课行为测试：确定性模型数据，正则测试在 Python 中真实执行。"""
import json
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_reflection_revision import runtime
from lessons.lesson_reflection_revision.fixtures import FIRST, FIXED, create_completion


def run_case(exercise_id, inputs, completion=None, budget=8, cancelled=lambda: False):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="reflection-revision", exercise_id=exercise_id, question="", mode="offline",
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


def reply(content, total=None):
    response = {"choices": [{"message": {"content": content}}]}
    if total is not None:
        response["usage"] = {"total_tokens": total}
    return response


class TestRunnerTests(unittest.TestCase):
    def test_cases_run_for_real(self):
        self.assertEqual(runtime.run_tests(FIXED)["failed"], 0)
        first = runtime.run_tests(FIRST)
        self.assertEqual(first["failed"], 1)
        self.assertEqual(runtime.failures_of(first), ["s-0420 应该不匹配，实际匹配"])
        broken = runtime.run_tests("s-[")
        self.assertFalse(broken["compiled"])
        self.assertEqual(broken["failed"], len(runtime.CASES))
        self.assertFalse(runtime.run_tests("a" * 201)["compiled"])

    def test_extract_json(self):
        self.assertEqual(runtime.extract_json('说明\n```json\n{"regex": "x"}\n```')["regex"], "x")
        for bad in ("没有", "[1, 2]"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                runtime.extract_json(bad)


class LoopTests(unittest.TestCase):
    def test_self_review_passes_a_draft_that_fails_real_tests(self):
        answer, events = run_case("self-review", {"reviewer": "self", "max_iters": 3})
        reviews = of(events, "lesson.review")
        self.assertEqual([(r["source"], r["verdict"]) for r in reviews], [("model", "pass")])
        self.assertEqual(metric(events, "停止原因"), "评审通过")
        final = of(events, "lesson.tests")[-1]
        self.assertEqual((final["version"], final["failed"]), ("final", 1))
        self.assertIn("未通过", answer)

    def test_test_review_revises_with_real_failures(self):
        answer, events = run_case("test-review", {"reviewer": "tests", "max_iters": 3})
        reviews = of(events, "lesson.review")
        self.assertEqual([(r["source"], r["verdict"]) for r in reviews], [("tests", "revise"), ("tests", "pass")])
        self.assertIn("s-0420", reviews[0]["issues"][0])
        revision_request = of(events, "request")[1]["body"]["messages"][1]["content"]
        self.assertIn("s-0420 应该不匹配", revision_request)
        drafts = of(events, "lesson.draft")
        self.assertEqual([d["regex"] for d in drafts], [FIRST, FIXED])
        self.assertEqual(drafts[1]["previous"], FIRST)
        self.assertEqual(metric(events, "停止原因"), "评审通过")
        self.assertEqual(metric(events, "累计 total_tokens"), 120)
        self.assertIn("通过（9/9）", answer)

    def test_limit_of_one_stops_without_revision(self):
        answer, events = run_case("test-review-once", {"reviewer": "tests", "max_iters": 1})
        self.assertEqual(len(of(events, "request")), 1)
        self.assertEqual(metric(events, "停止原因"), "达到迭代上限")
        self.assertIn("未通过", answer)

    def test_unchanged_revision_and_invalid_review_stop_the_loop(self):
        def stuck(body, key):
            return reply(json.dumps({"regex": FIRST}))
        _, events = run_case("test-review", {"reviewer": "tests", "max_iters": 3}, stuck)
        self.assertEqual(metric(events, "停止原因"), "修订后没有变化")
        self.assertTrue(of(events, "lesson.draft")[-1]["unchanged"])

        def rambling(body, key):
            if body["messages"][0]["content"].startswith("你是评审"):
                return reply("看起来不错。")
            return reply(json.dumps({"regex": FIRST}))
        _, events = run_case("self-review", {"reviewer": "self"}, rambling)
        self.assertEqual(metric(events, "停止原因"), "评审输出不合格式")

    def test_usage_is_not_invented(self):
        def partial(body, key):
            if "评审意见" in body["messages"][1]["content"]:
                return reply(json.dumps({"regex": FIXED}))
            return reply(json.dumps({"regex": FIRST}), total=40)
        _, events = run_case("test-review", {"reviewer": "tests"}, partial)
        self.assertEqual(metric(events, "累计 total_tokens"), "40（1 次未报告）")

    def test_inputs_and_cancel(self):
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {"reviewer": "tests", "max_iters": 9})
        with self.assertRaises(RunCancelled):
            run_case("test-review", {"reviewer": "tests"}, cancelled=lambda: True)


if __name__ == "__main__":
    unittest.main()
