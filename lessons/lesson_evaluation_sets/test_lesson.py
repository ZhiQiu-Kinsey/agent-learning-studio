"""Behavior tests for evaluation-sets: deterministic model data; the tools, the verifier and the comparison really run in Python."""
import json
import re
import unittest
from datetime import datetime
from unittest import mock

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_evaluation_sets import runtime, verifier
from lessons.lesson_evaluation_sets.cases import CASES, JUDGE_SAMPLES, fingerprint
from lessons.lesson_evaluation_sets.fixtures import create_completion
from lessons.lesson_evaluation_sets.locales import texts_for
from server.selectors import resolve_path

LOCALES = ("zh-CN", "en")
CJK = re.compile(r"[　-〿一-鿿＀-￯]")
CASE = {case.id: case for case in CASES}
ALLOWED = {"add_numbers", "get_current_time", "divide_numbers"}

# The real clock tool still runs, on a pinned time: version A guesses 12 + 30 and 12 / 2, and at a
# time such as 02:40 or 12:xx a guess would happen to be right, turning the failure cases into passes.
# Naive on purpose: the tool calls astimezone(), which reads a naive time as local, so every machine
# sees 09:05 whatever its time zone.
FIXED_NOW = datetime(2026, 10, 21, 9, 5)
_clock = mock.patch("lessons.lesson_01_tool_selection.tools.datetime", wraps=datetime)


def setUpModule():
    _clock.start().now.return_value = FIXED_NOW


def tearDownModule():
    _clock.stop()


def run_case(exercise_id, inputs, completion=None, budget=80, cancelled=lambda: False, locale="zh-CN", question=""):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="evaluation-sets", exercise_id=exercise_id, question=question, mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def verdicts(events, version):
    return {data["case"]: data["verdict"] for data in of(events, "lesson.case_result") if data["version"] == version}


def metric(report, metric_id):
    return resolve_path({"data": report}, f"data.metrics[id={metric_id}]")["value"]


def trajectory(calls=(), content=None, ended=True):
    return {"calls": [{"step": step, "name": name, "arguments": json.dumps(arguments), "result": result}
                      for step, name, arguments, result in calls],
            "content": content, "ended": ended, "model_calls": 1}


class VerifierTests(unittest.TestCase):
    """The verifier on hand-built trajectories: each check decides on its own."""

    def setUp(self):
        self.t = texts_for("zh-CN")

    def check(self, outcome, check_id):
        return next(item["status"] for item in outcome["checks"] if item["id"] == check_id)

    def test_parse_answer_reads_the_last_tag(self):
        self.assertEqual(verifier.parse_answer("x <answer>1</answer> <answer>42, 105</answer>"),
                         {"kind": "numbers", "numbers": [42.0, 105.0]})
        self.assertEqual(verifier.parse_answer("<answer> none </answer>")["kind"], "none")
        self.assertEqual(verifier.parse_answer("42")["kind"], "missing")
        self.assertEqual(verifier.parse_answer(None)["kind"], "missing")

    def test_correct_simple_case_passes_every_check(self):
        outcome = verifier.verify(CASE["add-basic"], trajectory(
            [(1, "add_numbers", {"a": 23, "b": 19.0}, {"ok": True, "result": 42})], "<answer>42</answer>"),
            "19 加 23 等于多少？", ALLOWED, self.t)
        # Swapped arguments of a commutative tool and 19.0 for 19 are not errors.
        self.assertEqual(outcome["verdict"], "passed")

    def test_right_number_without_a_call_has_no_evidence(self):
        outcome = verifier.verify(CASE["add-basic"], trajectory([], "<answer>42</answer>"),
                                  "19 加 23 等于多少？", ALLOWED, self.t)
        self.assertEqual(self.check(outcome, "correct"), "pass")
        self.assertEqual(self.check(outcome, "evidence"), "fail")
        self.assertEqual(self.check(outcome, "calls"), "fail")
        self.assertEqual(outcome["verdict"], "failed")

    def test_dependency_without_its_source_is_unassessable_and_guessed(self):
        outcome = verifier.verify(CASE["clock-sum"], trajectory(
            [(1, "add_numbers", {"a": 12, "b": 30}, {"ok": True, "result": 42})], "<answer>42</answer>"),
            "把现在的小时数和分钟数相加，结果是多少？", ALLOWED, self.t)
        self.assertEqual(self.check(outcome, "correct"), "unassessable")
        self.assertEqual([v["id"] for v in outcome["violations"]], ["guessed_dependency"])
        self.assertEqual(outcome["verdict"], "failed")

    def test_dependency_in_a_later_step_is_checked_against_the_clock(self):
        clock = {"ok": True, "result": {"local_datetime": "2026-10-20T09:15:00+08:00", "timezone": "UTC+08:00",
                                        "hour": 9, "minute": 15}}
        good = trajectory([(1, "get_current_time", {}, clock),
                           (2, "add_numbers", {"a": 9, "b": 15}, {"ok": True, "result": 24})], "<answer>24</answer>")
        self.assertEqual(verifier.verify(CASE["clock-sum"], good, "", ALLOWED, self.t)["verdict"], "passed")
        same_step = trajectory([(1, "get_current_time", {}, clock),
                                (1, "add_numbers", {"a": 9, "b": 15}, {"ok": True, "result": 24})], "<answer>24</answer>")
        outcome = verifier.verify(CASE["clock-sum"], same_step, "", ALLOWED, self.t)
        # A lucky guess: right arguments and answer, but sent before the clock result existed.
        self.assertEqual(self.check(outcome, "correct"), "pass")
        self.assertEqual(outcome["verdict"], "failed")

    def test_number_after_a_tool_error_is_a_violation_even_when_grounded(self):
        error = {"ok": False, "error_type": "ValueError", "error": "x"}
        outcome = verifier.verify(CASE["divide-zero"], trajectory(
            [(1, "divide_numbers", {"a": 100, "b": 0}, error)], "<answer>0</answer>"), "100 除以 0 等于多少？",
            ALLOWED, self.t)
        # 0 is in the question, so the evidence check lets it through; the violation check does not.
        self.assertEqual(self.check(outcome, "evidence"), "pass")
        self.assertEqual([v["id"] for v in outcome["violations"]], ["number_after_failure"])
        untried = verifier.verify(CASE["divide-zero"], trajectory([], "<answer>NONE</answer>"), "", ALLOWED, self.t)
        self.assertEqual(self.check(untried, "evidence"), "fail")

    def test_open_answer_is_unassessable_not_passed(self):
        outcome = verifier.verify(CASE["greeting"], trajectory([], "hello"), "", ALLOWED, self.t)
        self.assertEqual(outcome["verdict"], "unassessable")
        called = verifier.verify(CASE["greeting"], trajectory(
            [(1, "get_current_time", {}, {"ok": True, "result": {"hour": 1, "minute": 2}})], "hello"), "", ALLOWED, self.t)
        self.assertEqual(called["verdict"], "failed")

    def test_unordered_mode_and_unregistered_tools(self):
        calls = [(1, "add_numbers", {"a": 100, "b": 5}, {"ok": True, "result": 105}),
                 (1, "add_numbers", {"a": 19, "b": 23}, {"ok": True, "result": 42})]
        outcome = verifier.verify(CASE["two-sums"], trajectory(calls, "<answer>42, 105</answer>"), "", ALLOWED, self.t)
        self.assertEqual(outcome["verdict"], "passed")
        duplicate = [calls[0], calls[0]]
        self.assertEqual(self.check(verifier.verify(CASE["two-sums"], trajectory(duplicate, "<answer>105</answer>"),
                                                    "", ALLOWED, self.t), "calls"), "fail")
        rogue = verifier.verify(CASE["greeting"], trajectory(
            [(1, "delete_files", {}, {"ok": False, "error_type": "ValueError", "error": "x"})], "hi"), "", ALLOWED, self.t)
        self.assertIn("unregistered_tool", [v["id"] for v in rogue["violations"]])

    def test_run_that_did_not_end_fails_without_judging_the_answer(self):
        outcome = verifier.verify(CASE["add-basic"], trajectory(ended=False), "", ALLOWED, self.t)
        self.assertEqual(self.check(outcome, "ended"), "fail")
        self.assertEqual(self.check(outcome, "correct"), "fail")
        self.assertEqual(self.check(outcome, "evidence"), "na")


class StatisticsTests(unittest.TestCase):
    def test_sign_test_and_wilson(self):
        self.assertEqual(runtime.sign_test(0, 0), 1.0)
        self.assertAlmostEqual(runtime.sign_test(5, 0), 0.0625)
        self.assertAlmostEqual(runtime.sign_test(6, 0), 0.03125)
        self.assertAlmostEqual(runtime.sign_test(3, 0), 0.25)
        self.assertEqual(runtime.sign_test(2, 1), 1.0)
        low, high = runtime.wilson(5, 6)
        self.assertTrue(0.4 < low < 0.45 and 0.96 < high < 0.98)
        self.assertEqual(runtime.wilson(0, 0), (0.0, 1.0))

    def test_kappa(self):
        rows = [{"human": h, "judge": j} for h, j in
                (("pass", "pass"), ("fail", "fail"), ("fail", "fail"), ("pass", "pass"), ("pass", "pass"), ("fail", "pass"))]
        # observed 5/6, chance (3/6)(4/6) + (3/6)(2/6) = 0.5, kappa = (5/6 - 0.5) / 0.5 = 2/3
        self.assertAlmostEqual(runtime.kappa(rows), 2 / 3)
        self.assertIsNone(runtime.kappa([{"human": "pass", "judge": "pass"}]))

    def test_fingerprint_changes_with_a_case(self):
        dev = [case for case in CASES if case.split == "dev"]
        self.assertEqual(fingerprint(dev), fingerprint(list(dev)))
        self.assertNotEqual(fingerprint(dev), fingerprint(dev[:-1]))


class ComparisonTests(unittest.TestCase):
    def test_dev_compare_keeps_every_case_and_pairs_them(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("dev-compare", {"split": "dev", "versions": "both"}, locale=locale)
                results = of(events, "lesson.case_result")
                self.assertEqual(len(results), 12, "6 cases x 2 versions, failures included")
                self.assertEqual(verdicts(events, "A"), {
                    "add-basic": "passed", "clock-sum": "failed", "divide-zero": "failed", "greeting": "unassessable",
                    "two-sums": "passed", "unknown-balance": "failed"})
                self.assertEqual(verdicts(events, "B"), {
                    "add-basic": "passed", "clock-sum": "passed", "divide-zero": "passed", "greeting": "unassessable",
                    "two-sums": "passed", "unknown-balance": "passed"})
                reports = of(events, "lesson.report")
                self.assertEqual(len(reports), 3, "one per version, then the comparison")
                # Every run ended, yet only some passed: finishing is not accepting.
                self.assertEqual(metric(reports[0], "ended"), "6/6")
                self.assertEqual(metric(reports[0], "passed"), "2/6")
                self.assertEqual(metric(reports[0], "unassessable"), 1)
                compare = reports[-1]
                self.assertEqual(metric(compare, "improved"), 3)
                self.assertEqual(metric(compare, "regressed"), 0)
                self.assertEqual(metric(compare, "p_value"), 0.25)
                self.assertEqual(compare["summary"], t.too_few_pairs.format(n=3, minimum=6))
                self.assertTrue(answer.endswith(compare["summary"]))
                card = of(events, "lesson.task_card")[0]
                self.assertIn(fingerprint([c for c in CASES if c.split == "dev"]), card["input_scope"])

    def test_case_result_lists_failures_violations_and_unassessable(self):
        _, events = run_case("dev-compare", {"split": "dev", "versions": "both"})
        by_case = {(d["version"], d["case"]): d for d in of(events, "lesson.case_result")}
        guessed = by_case[("A", "clock-sum")]
        self.assertEqual([v["id"] for v in guessed["violations"]], ["guessed_dependency"])
        self.assertIn("答案正确", guessed["failures"])
        fabricated = by_case[("A", "unknown-balance")]
        self.assertEqual(next(c for c in fabricated["checks"] if c["id"] == "evidence")["status"], "fail")
        self.assertEqual(by_case[("A", "greeting")]["unassessable"], ["答案正确"])
        self.assertEqual(by_case[("B", "clock-sum")]["violations"], [])
        # The tools really ran: the clock case of version B used this machine's time.
        clock = next(d["result"] for k, d, _ in events if k == "tool_result" and d["name"] == "get_current_time")
        self.assertTrue(clock["ok"])
        self.assertIn("hour", clock["result"])

    def test_holdout_shows_a_regression(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                _, events = run_case("holdout-compare", {"split": "holdout", "versions": "both"}, locale=locale)
                self.assertEqual(verdicts(events, "A"), {"add-holdout": "passed", "divide-zero-holdout": "failed",
                                                         "given-distance": "passed", "clock-half": "failed"})
                self.assertEqual(verdicts(events, "B")["given-distance"], "failed")
                compare = of(events, "lesson.report")[-1]
                self.assertEqual(metric(compare, "regressed"), 1)
                self.assertFalse(compare["checks"][0]["passed"])
                self.assertEqual(compare["checks"][0]["detail"], "given-distance")
                self.assertEqual(metric(compare, "p_value"), 1.0)

    def test_repeats_report_stability(self):
        answer, events = run_case("repeat-b", {"split": "dev", "versions": "B", "repeats": 2})
        self.assertEqual(len(of(events, "lesson.case_result")), 12)
        reports = of(events, "lesson.report")
        self.assertEqual(len(reports), 1, "one version: no paired comparison")
        self.assertEqual(metric(reports[0], "pass_all"), "5/6")
        self.assertEqual(metric(reports[0], "unstable"), 0)
        self.assertEqual(reports[0]["table"]["columns"], list(texts_for("zh-CN").columns_repeats))
        self.assertIn("10/12", answer)

    def test_only_version_b_differs_in_the_prompt(self):
        _, events = run_case("dev-compare", {"split": "dev", "versions": "both"}, locale="en")
        t = texts_for("en")
        systems = {d["body"]["messages"][0]["content"] for d in of(events, "request")}
        self.assertEqual(systems, {t.base_prompt + t.answer_format, t.base_prompt + t.rules_b + t.answer_format})
        names = {tool["function"]["name"] for tool in of(events, "request")[0]["body"]["tools"]}
        self.assertEqual(names, ALLOWED)

    def test_round_limit_is_recorded_not_raised(self):
        def stubborn(body, key):
            call = {"id": "c1", "type": "function", "function": {"name": "add_numbers", "arguments": '{"a": 1, "b": 2}'}}
            return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [call]}}]}
        _, events = run_case("dev-compare", {"split": "dev", "versions": "A"}, stubborn)
        first = of(events, "lesson.case_result")[0]
        self.assertEqual(first["model_calls"], 3)
        self.assertIn("流程结束", first["failures"])
        self.assertEqual(len(of(events, "lesson.case_result")), 6, "the suite goes on after a case runs out")

    def test_english_events_have_no_chinese(self):
        for exercise, inputs in (("dev-compare", {"split": "dev"}), ("holdout-compare", {"split": "holdout"}),
                                 ("judge-calibration", {"task": "judge"})):
            with self.subTest(exercise=exercise):
                answer, events = run_case(exercise, inputs, locale="en")
                self.assertIsNone(CJK.search(json.dumps([d for _, d, _ in events], ensure_ascii=False)))
                self.assertIsNone(CJK.search(answer))


class JudgeTests(unittest.TestCase):
    def test_judge_is_compared_with_human_labels(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_case("judge-calibration", {"task": "judge"}, locale=locale)
                judgements = of(events, "lesson.judgement")
                self.assertEqual([j["human"] for j in judgements], [label for _, label in JUDGE_SAMPLES])
                self.assertEqual([j["sample"] for j in judgements if not j["agree"]], ["j6"])
                report = of(events, "lesson.report")[-1]
                self.assertEqual(metric(report, "agreement"), "5/6")
                self.assertEqual(metric(report, "false_pass"), 1)
                self.assertEqual(metric(report, "kappa"), 0.67)
                self.assertEqual(len(of(events, "request")), 6)
                self.assertEqual(answer, texts_for(locale).answer_judge.format(agree=5, total=6))

    def test_malformed_judge_reply_is_invalid(self):
        self.assertEqual(runtime.parse_judgement("not json")[0], "invalid")
        self.assertEqual(runtime.parse_judgement('{"verdict": "maybe"}')[0], "invalid")
        self.assertEqual(runtime.parse_judgement('ok {"verdict": "fail", "reason": "r"}'), ("fail", "r"))

        def chatty(body, key):
            return {"choices": [{"message": {"content": "looks fine to me"}}]}
        _, events = run_case("judge-calibration", {"task": "judge"}, chatty)
        report = of(events, "lesson.report")[-1]
        self.assertEqual(metric(report, "invalid"), 6)
        self.assertEqual(metric(report, "agreement"), "0/6")


class InputTests(unittest.TestCase):
    def test_inputs_budget_and_cancel(self):
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {"repeats": 3})
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {"split": "test"})
        with self.assertRaises(ValueError) as caught:
            run_case("dev-compare", {"split": "dev", "versions": "both"}, budget=10)
        self.assertIn("36", str(caught.exception))
        with self.assertRaises(RunCancelled):
            run_case("dev-compare", {"split": "dev"}, cancelled=lambda: True)

    def test_worst_case_fits_the_declared_limit(self):
        # dev, both versions, two repeats: 6 x 2 x 2 x 3 model calls at most.
        self.assertLessEqual(6 * 2 * 2 * 3, 80)

    def test_learner_note_goes_to_the_report_only(self):
        _, events = run_case("dev-compare", {"split": "dev"}, question="备注")
        self.assertNotIn("备注", json.dumps([d["body"] for d in of(events, "request")], ensure_ascii=False))
        note = texts_for("zh-CN").label_note
        self.assertIn({"label": note, "value": "备注"}, of(events, "lesson.report")[-1]["metrics"])


if __name__ == "__main__":
    unittest.main()
