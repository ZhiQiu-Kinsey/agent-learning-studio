"""Behavior tests for reflection-revision: deterministic model data; the regex tests really run in Python."""
import json
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_reflection_revision import runtime
from lessons.lesson_reflection_revision.fixtures import FIRST, FIXED, create_completion
from lessons.lesson_reflection_revision.locales import texts_for

LOCALES = ("zh-CN", "en")


def run_case(exercise_id, inputs, completion=None, budget=8, cancelled=lambda: False, locale="zh-CN"):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="reflection-revision", exercise_id=exercise_id, question="", mode="offline",
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


def reply(content, total=None):
    response = {"choices": [{"message": {"content": content}}]}
    if total is not None:
        response["usage"] = {"total_tokens": total}
    return response


class TestRunnerTests(unittest.TestCase):
    def test_cases_run_for_real(self):
        zh, en = texts_for("zh-CN"), texts_for("en")
        self.assertEqual(runtime.run_tests(zh, FIXED)["failed"], 0)
        first = runtime.run_tests(zh, FIRST)
        self.assertEqual(first["failed"], 1)
        self.assertEqual(runtime.failures_of(zh, first), ["s-0420 应该不匹配，实际匹配"])
        self.assertEqual(runtime.failures_of(en, runtime.run_tests(en, FIRST)),
                         ["s-0420 should not match, but it matched"])
        broken = runtime.run_tests(zh, "s-[")
        self.assertFalse(broken["compiled"])
        self.assertEqual(broken["failed"], len(runtime.CASES))
        self.assertTrue(runtime.run_tests(en, "s-[")["error"].startswith("The regex does not compile: "))
        self.assertFalse(runtime.run_tests(zh, "a" * 201)["compiled"])

    def test_extract_json(self):
        for locale in LOCALES:
            t = texts_for(locale)
            self.assertEqual(runtime.extract_json(t, '说明\n```json\n{"regex": "x"}\n```')["regex"], "x")
            for bad, message in (("没有", t.no_json_object), ("[1, 2]", t.no_json_object)):
                with self.subTest(locale=locale, bad=bad), self.assertRaises(ValueError) as caught:
                    runtime.extract_json(t, bad)
                self.assertEqual(str(caught.exception), message)


class LoopTests(unittest.TestCase):
    def test_self_review_passes_a_draft_that_fails_real_tests(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("self-review", {"reviewer": "self", "max_iters": 3}, locale=locale)
                reviews = of(events, "lesson.review")
                self.assertEqual([(r["source"], r["verdict"]) for r in reviews], [("model", "pass")])
                self.assertEqual(metric(events, "label_stop_reason", locale), t.stop_reasons["passed"])
                final = of(events, "lesson.tests")[-1]
                self.assertEqual((final["version"], final["failed"]), ("final", 1))
                self.assertEqual(answer, t.answer_failed.format(reason=t.stop_reasons["passed"], pattern=FIRST,
                                                                passed=8, total=9))
        answer, events = run_case("self-review", {"reviewer": "self", "max_iters": 3})
        self.assertEqual(metric(events, "label_stop_reason"), "评审通过")
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
        self.assertEqual(metric(events, "label_stop_reason"), "评审通过")
        self.assertEqual(metric(events, "label_total_tokens"), 120)
        self.assertIn("通过（9/9）", answer)

    def test_english_run_sends_and_reports_english(self):
        t = texts_for("en")
        answer, events = run_case("test-review", {"reviewer": "tests", "max_iters": 3}, locale="en")
        requests = [data["body"]["messages"] for data in of(events, "request")]
        self.assertEqual(requests[0][0]["content"], t.writer_system)
        self.assertEqual(requests[0][1]["content"], "Requirement: " + t.spec)
        self.assertIn("Previous regex: " + FIRST, requests[1][1]["content"])
        self.assertIn("s-0420 should not match, but it matched", requests[1][1]["content"])
        report = of(events, "lesson.report")[-1]
        self.assertEqual(report["title"], "Test results drive revision")
        self.assertEqual(report["checks"][0]["detail"], "9/9 passed")
        self.assertEqual(report["table"]["columns"], list(t.table_columns))
        self.assertEqual(report["table"]["rows"][0][2], "tests")
        self.assertEqual(answer, "Stop reason: review passed. The final regex s-[1-9]\\d{3} passed the real test cases (9/9).")

    def test_limit_of_one_stops_without_revision(self):
        answer, events = run_case("test-review-once", {"reviewer": "tests", "max_iters": 1})
        self.assertEqual(len(of(events, "request")), 1)
        self.assertEqual(metric(events, "label_stop_reason"), "达到迭代上限")
        self.assertIn("未通过", answer)

    def test_unchanged_revision_and_invalid_review_stop_the_loop(self):
        def stuck(body, key):
            return reply(json.dumps({"regex": FIRST}))

        def rambling(body, key):
            if body["messages"][0]["content"] in (texts_for(l).self_review_system for l in LOCALES):
                return reply("看起来不错。")
            return reply(json.dumps({"regex": FIRST}))

        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                _, events = run_case("test-review", {"reviewer": "tests", "max_iters": 3}, stuck, locale=locale)
                self.assertEqual(metric(events, "label_stop_reason", locale), t.stop_reasons["unchanged"])
                self.assertTrue(of(events, "lesson.draft")[-1]["unchanged"])
                _, events = run_case("self-review", {"reviewer": "self"}, rambling, locale=locale)
                self.assertEqual(metric(events, "label_stop_reason", locale), t.stop_reasons["invalid"])
        _, events = run_case("test-review", {"reviewer": "tests", "max_iters": 3}, stuck)
        self.assertEqual(metric(events, "label_stop_reason"), "修订后没有变化")

    def test_missing_regex_is_recorded_not_repaired(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                _, events = run_case("test-review-once", {"reviewer": "tests", "max_iters": 1},
                                     lambda body, key: reply('{"pattern": "s-\\\\d{4}"}'), locale=locale)
                draft = of(events, "lesson.draft")[0]
                self.assertEqual((draft["regex"], draft["parse_error"]), ("", texts_for(locale).missing_regex))

    def test_usage_is_not_invented(self):
        def partial(body, key):
            if body["messages"][1]["content"] not in (texts_for(l).draft_request.format(spec=texts_for(l).spec)
                                                      for l in LOCALES):
                return reply(json.dumps({"regex": FIXED}))
            return reply(json.dumps({"regex": FIRST}), total=40)
        _, events = run_case("test-review", {"reviewer": "tests"}, partial)
        self.assertEqual(metric(events, "label_total_tokens"), "40（1 次未报告）")
        _, events = run_case("test-review", {"reviewer": "tests"}, partial, locale="en")
        self.assertEqual(metric(events, "label_total_tokens", "en"), "40 (1 not reported)")
        _, events = run_case("test-review", {"reviewer": "tests"}, lambda body, key: reply(json.dumps({"regex": FIXED})),
                             locale="en")
        self.assertEqual(metric(events, "label_total_tokens", "en"), "not reported")

    def test_inputs_and_cancel(self):
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {"reviewer": "tests", "max_iters": 9})
        with self.assertRaises(RunCancelled):
            run_case("test-review", {"reviewer": "tests"}, cancelled=lambda: True)


if __name__ == "__main__":
    unittest.main()
