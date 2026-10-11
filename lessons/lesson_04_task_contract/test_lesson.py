"""Behavior tests for task-contract: no model; the tool really runs and the same acceptance rule judges every scenario."""
import json
import re
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_04_task_contract import runtime as task
from lessons.lesson_04_task_contract.locales import texts_for

CJK = re.compile(r"[　-〿一-鿿＀-￯]")
CLAIMS = {"zh-CN": "已完成学习助教的加法任务", "en": "The addition task for the study assistant is done"}


def run_case(exercise_id, inputs, cancelled=lambda: False, question="fixed task", locale="zh-CN"):
    events = []
    context = RunContext(
        lesson_id="task-contract", exercise_id=exercise_id, question=question, mode="offline",
        model="fixture-model", representation="sdk_standardized",
        inputs=validate_inputs(task, {"claim": CLAIMS[locale], **inputs}), api_key="fixture-key",
        completion=None, max_model_calls=1, cancelled=cancelled,
        emit_event=lambda kind, data, round_number: events.append((kind, data, round_number)),
        locale=locale,
    )
    result = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, task, context)
    return result, events


def report(events):
    return [data for kind, data, _ in events if kind == "lesson.report"][-1]


def metric(events, field, locale="zh-CN"):
    label = getattr(texts_for(locale), field)
    return next(item["value"] for item in report(events)["metrics"] if item["label"] == label)


class TaskContractTests(unittest.TestCase):
    def test_same_acceptance_rule_distinguishes_end_from_success(self):
        for scenario, expected in (("normal", True), ("missing_evidence", False), ("wrong_result", False)):
            with self.subTest(scenario=scenario):
                result, events = run_case(scenario, {"scenario": scenario})
                checks = report(events)["checks"]
                self.assertTrue(checks[0]["passed"])
                self.assertEqual(all(check["passed"] for check in checks[1:]), expected)
                self.assertEqual("验收通过" in result, expected)
                self.assertEqual(len([kind for kind, _, _ in events if kind == "tool_result"]),
                                 0 if scenario == "missing_evidence" else 1)

    def test_wrong_result_fails_on_arguments_and_value(self):
        _, events = run_case("wrong-result", {"scenario": "wrong_result"})
        checks = report(events)["checks"]
        self.assertEqual([check["passed"] for check in checks], [True, True, True, False, False, True])
        self.assertEqual(checks[3]["detail"], "期望 a=19、b=23；证据中为 a=19、b=22")
        self.assertEqual(checks[4]["detail"], "期望 42；证据中为 41")

    def test_claim_does_not_overrule_evidence_and_inputs_are_bounded(self):
        _, events = run_case("missing-evidence", {"scenario": "missing_evidence", "claim": "全部通过"})
        self.assertFalse(report(events)["checks"][1]["passed"])
        claim = next(data for kind, data, _ in events if kind == "lesson.completion_claim")
        self.assertEqual((claim["answer"], claim["evidence_ref"], claim["summary"]), (42, None, "全部通过"))
        with self.assertRaises(ValidationError):
            validate_inputs(task, {"scenario": "normal", "claim": "x", "path": "secrets.py"})
        with self.assertRaises(ValidationError):
            validate_inputs(task, {"scenario": "goal_loop", "claim": "x", "max_attempts": 4})
        with self.assertRaises(RunCancelled):
            run_case("normal", {}, cancelled=lambda: True)

    def test_claim_has_no_hidden_default(self):
        # The preset in lesson.json supplies it in the run's language; an omitted claim is an input error.
        with self.assertRaises(ValidationError):
            validate_inputs(task, {"scenario": "normal"})

    def test_verifier_reads_referenced_evidence_not_the_claimed_answer(self):
        _, events = run_case("claim-mismatch", {"scenario": "claim_mismatch"})
        claim = next(data for kind, data, _ in events if kind == "lesson.completion_claim")
        result = next(data for kind, data, _ in events if kind == "tool_result")
        self.assertEqual(claim["answer"], 42)
        self.assertEqual(claim["evidence_ref"], result["tool_call_id"])
        self.assertEqual(result["result"]["result"], 41)
        checks = report(events)["checks"]
        self.assertEqual([check["passed"] for check in checks], [True, True, True, False, False, False])
        self.assertFalse(task.accepted(checks))

    def test_verify_checks_the_recorded_arguments(self):
        t = texts_for("zh-CN")
        claim = {"answer": 42, "evidence_ref": "real"}
        right = {"real": {"arguments": {"a": 19, "b": 23}, "result": {"ok": True, "result": 42}}}
        self.assertTrue(task.accepted(task.verify(claim, right, t)))
        # 20 + 22 is also 42, but input_scope allows only 19 and 23.
        out_of_scope = {"real": {"arguments": {"a": 20, "b": 22}, "result": {"ok": True, "result": 42}}}
        checks = task.verify(claim, out_of_scope, t)
        self.assertFalse(task.accepted(checks))
        self.assertEqual([check["passed"] for check in checks], [True, True, True, False, True, True])
        # A record without arguments proves nothing about the inputs.
        no_arguments = {"real": {"result": {"ok": True, "result": 42}}}
        self.assertFalse(task.accepted(task.verify(claim, no_arguments, t)))

    def test_verify_rejects_references_to_evidence_from_elsewhere(self):
        t = texts_for("zh-CN")
        claim = {"answer": 42, "evidence_ref": "forged"}
        evidence = {"real": {"arguments": {"a": 19, "b": 23}, "result": {"ok": True, "result": 42}}}
        self.assertFalse(task.accepted(task.verify(claim, evidence, t)))
        self.assertTrue(task.accepted(task.verify({**claim, "evidence_ref": "real"}, evidence, t)))
        failed = {"real": {"arguments": {"a": 19, "b": 23}, "result": {"ok": False, "error": "boom"}}}
        self.assertFalse(task.accepted(task.verify({**claim, "evidence_ref": "real"}, failed, t)))

    def test_goal_loop_retries_with_reasons_and_stops_at_pass_or_limit(self):
        result, events = run_case("goal-loop", {"scenario": "goal_loop", "max_attempts": 3})
        goal_checks = [(data, round_number) for kind, data, round_number in events if kind == "lesson.goal_check"]
        self.assertEqual([(data["passed"], data["next"], round_number) for data, round_number in goal_checks],
                         [(False, "retry", 1), (True, "stop", 2)])
        self.assertTrue(any("41" in reason for reason in goal_checks[0][0]["reasons"]))
        self.assertTrue(any("b=22" in reason for reason in goal_checks[0][0]["reasons"]))
        self.assertEqual(len([kind for kind, _, _ in events if kind == "tool_result"]), 2)
        self.assertIn("第 2 次", result)
        card = next(data for kind, data, _ in events if kind == "lesson.task_card")
        self.assertIn("3 次", card["stop"])
        self.assertIn({"id": "stop_reason", "label": "停止原因", "value": "验收通过"}, report(events)["metrics"])

        result, events = run_case("goal-loop-once", {"scenario": "goal_loop", "max_attempts": 1})
        goal_checks = [data for kind, data, _ in events if kind == "lesson.goal_check"]
        self.assertEqual([(data["passed"], data["next"]) for data in goal_checks], [(False, "stop")])
        self.assertIn("未通过", result)
        self.assertIn({"id": "stop_reason", "label": "停止原因", "value": "达到尝试上限"}, report(events)["metrics"])

    def test_observed_report_entries_are_found_by_id_in_both_languages(self):
        # The lab's observation points select these entries by id, so adding a check does not shift them.
        from server.selectors import resolve_path
        expected = {"checks[id=run_ended]": "check_ended", "checks[id=arguments_match]": "check_arguments",
                    "checks[id=value_matches]": "check_value", "checks[id=claim_consistent]": "check_consistent",
                    "metrics[id=stop_reason]": "label_stop_reason"}
        for locale in ("zh-CN", "en"):
            _, events = run_case("goal-loop", {"scenario": "goal_loop", "max_attempts": 3}, locale=locale)
            for path, field in expected.items():
                with self.subTest(locale=locale, path=path):
                    entry = resolve_path({"data": report(events)}, f"data.{path}")
                    self.assertEqual(entry["label"], getattr(texts_for(locale), field))

    def test_single_attempt_scenarios_ignore_attempt_limit(self):
        _, events = run_case("normal", {"scenario": "normal", "max_attempts": 3})
        self.assertEqual(len([kind for kind, _, _ in events if kind == "tool_call"]), 1)
        self.assertFalse(any(kind == "lesson.goal_check" for kind, _, _ in events))

    def test_question_is_report_note_not_task_override(self):
        _, events = run_case("normal", {}, question="改做别的算术")
        self.assertIn({"label": "学习者备注", "value": "改做别的算术"}, report(events)["metrics"])
        self.assertTrue(report(events)["checks"][-1]["passed"])


class EnglishRunTests(unittest.TestCase):
    def test_every_scenario_runs_in_english_without_chinese(self):
        for scenario in ("normal", "missing_evidence", "wrong_result", "claim_mismatch", "goal_loop"):
            with self.subTest(scenario=scenario):
                result, events = run_case(scenario, {"scenario": scenario}, question="note", locale="en")
                self.assertIsNone(CJK.search(json.dumps([result, *[data for _, data, _ in events]],
                                                        ensure_ascii=False)))

    def test_english_run_judges_the_same_way(self):
        t = texts_for("en")
        result, events = run_case("goal-loop", {"scenario": "goal_loop", "max_attempts": 3}, locale="en")
        self.assertEqual(result, t.answer_passed.format(attempts=2))
        self.assertEqual(metric(events, "label_stop_reason", "en"), t.stop_passed)
        card = next(data for kind, data, _ in events if kind == "lesson.task_card")
        self.assertEqual(card["stop"], "Stop when the acceptance check passes or after 3 attempts")
        reasons = next(data for kind, data, _ in events if kind == "lesson.goal_check")["reasons"]
        self.assertIn("The call arguments match the task card: expected a=19, b=23; the evidence has a=19, b=22",
                      reasons)
        _, events = run_case("claim-mismatch", {"scenario": "claim_mismatch"}, locale="en")
        self.assertEqual(report(events)["checks"][5]["detail"], "the claim says 42; the evidence has 41")
        self.assertEqual(report(events)["table"]["columns"], list(t.columns))


if __name__ == "__main__":
    unittest.main()
