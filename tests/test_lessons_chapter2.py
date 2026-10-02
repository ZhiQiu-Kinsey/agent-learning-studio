"""Behavior checks for chapter 2 custom runtimes, with no paid calls."""
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_04_task_contract import runtime as task
from lessons.lesson_05_structured_output import runtime as structured
from lessons.lesson_05_structured_output.fixtures import create_completion as structured_fixture
from lessons.lesson_06_prompt_experiments import runtime as prompts
from lessons.lesson_06_prompt_experiments.fixtures import create_completion as prompt_fixture


def run_case(module, lesson_id, exercise_id, inputs, completion=None, budget=2,
             cancelled=lambda: False, question="fixed task"):
    events = []
    context = RunContext(
        lesson_id=lesson_id, exercise_id=exercise_id, question=question, mode="offline",
        model="fixture-model", representation="sdk_standardized",
        inputs=validate_inputs(module, inputs), api_key="fixture-key",
        completion=completion, max_model_calls=budget, cancelled=cancelled,
        emit_event=lambda kind, data, round_number: events.append((kind, data, round_number)),
    )
    result = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, module, context)
    return result, events


def report(events):
    return reports(events)[-1]


def reports(events):
    return [data for kind, data, _ in events if kind == "lesson.report"]


class TaskContractTests(unittest.TestCase):
    def test_same_acceptance_rule_distinguishes_end_from_success(self):
        for scenario, expected in (("normal", True), ("missing_evidence", False), ("wrong_result", False)):
            with self.subTest(scenario=scenario):
                result, events = run_case(task, "4", scenario, {"scenario": scenario})
                checks = report(events)["checks"]
                self.assertTrue(checks[0]["passed"])
                self.assertEqual(all(check["passed"] for check in checks[1:]), expected)
                self.assertEqual("验收通过" in result, expected)
                self.assertEqual(len([kind for kind, _, _ in events if kind == "tool_result"]),
                                 0 if scenario == "missing_evidence" else 1)

    def test_claim_does_not_overrule_evidence_and_inputs_are_bounded(self):
        _, events = run_case(task, "4", "missing-evidence", {"scenario": "missing_evidence", "claim": "全部通过"})
        self.assertFalse(report(events)["checks"][1]["passed"])
        claim = next(data for kind, data, _ in events if kind == "lesson.completion_claim")
        self.assertEqual((claim["answer"], claim["evidence_ref"], claim["summary"]), (42, None, "全部通过"))
        with self.assertRaises(ValidationError):
            validate_inputs(task, {"scenario": "normal", "path": "secrets.py"})
        with self.assertRaises(ValidationError):
            validate_inputs(task, {"scenario": "goal_loop", "max_attempts": 4})
        with self.assertRaises(RunCancelled):
            run_case(task, "4", "normal", {}, cancelled=lambda: True)

    def test_verifier_reads_referenced_evidence_not_the_claimed_answer(self):
        _, events = run_case(task, "4", "claim-mismatch", {"scenario": "claim_mismatch"})
        claim = next(data for kind, data, _ in events if kind == "lesson.completion_claim")
        result = next(data for kind, data, _ in events if kind == "tool_result")
        self.assertEqual(claim["answer"], 42)
        self.assertEqual(claim["evidence_ref"], result["tool_call_id"])
        self.assertEqual(result["result"]["result"], 41)
        checks = report(events)["checks"]
        self.assertEqual([check["passed"] for check in checks], [True, True, True, False, False])
        self.assertFalse(task.accepted(checks))

    def test_verify_rejects_references_to_evidence_from_elsewhere(self):
        claim = {"answer": 42, "evidence_ref": "forged"}
        evidence = {"real": {"result": {"ok": True, "result": 42}}}
        self.assertFalse(task.accepted(task.verify(claim, evidence)))
        self.assertTrue(task.accepted(task.verify({**claim, "evidence_ref": "real"}, evidence)))
        failed = {"real": {"result": {"ok": False, "error": "boom"}}}
        self.assertFalse(task.accepted(task.verify({**claim, "evidence_ref": "real"}, failed)))

    def test_goal_loop_retries_with_reasons_and_stops_at_pass_or_limit(self):
        result, events = run_case(task, "4", "goal-loop", {"scenario": "goal_loop", "max_attempts": 3})
        goal_checks = [(data, round_number) for kind, data, round_number in events if kind == "lesson.goal_check"]
        self.assertEqual([(data["passed"], data["next"], round_number) for data, round_number in goal_checks],
                         [(False, "retry", 1), (True, "stop", 2)])
        self.assertTrue(any("41" in reason for reason in goal_checks[0][0]["reasons"]))
        self.assertEqual(len([kind for kind, _, _ in events if kind == "tool_result"]), 2)
        self.assertIn("第 2 次", result)
        card = next(data for kind, data, _ in events if kind == "lesson.task_card")
        self.assertIn("3 次", card["stop"])
        self.assertIn({"label": "停止原因", "value": "验收通过"}, report(events)["metrics"])

        result, events = run_case(task, "4", "goal-loop-once", {"scenario": "goal_loop", "max_attempts": 1})
        goal_checks = [data for kind, data, _ in events if kind == "lesson.goal_check"]
        self.assertEqual([(data["passed"], data["next"]) for data in goal_checks], [(False, "stop")])
        self.assertIn("未通过", result)
        self.assertIn({"label": "停止原因", "value": "达到尝试上限"}, report(events)["metrics"])

    def test_single_attempt_scenarios_ignore_attempt_limit(self):
        _, events = run_case(task, "4", "normal", {"scenario": "normal", "max_attempts": 3})
        self.assertEqual(len([kind for kind, _, _ in events if kind == "tool_call"]), 1)
        self.assertFalse(any(kind == "lesson.goal_check" for kind, _, _ in events))

    def test_question_is_report_note_not_task_override(self):
        _, events = run_case(task, "4", "normal", {}, question="改做别的算术")
        self.assertIn({"label": "学习者备注", "value": "改做别的算术"}, report(events)["metrics"])
        self.assertTrue(report(events)["checks"][-1]["passed"])


class StructuredOutputTests(unittest.TestCase):
    def test_layers_distinguish_format_schema_and_fact(self):
        cases = [('{bad', [False]), ('{"lesson_id":"task-contract"}', [True, False]),
                 ('NaN', [False]), ('Infinity', [False]), ('-Infinity', [False]),
                 ('{"lesson_id":"task-contract","lesson_title":"任务目标与验收","prerequisite":"dependent-calls","exercise":"解释验收流程与证据"}',
                  [True, True, False])]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                _, checks = structured.inspect_output(raw)
                self.assertEqual([c["passed"] for c in checks], expected)

    def test_normal_and_one_bounded_repair(self):
        for scenario, calls in (("normal", 1), ("missing_field", 2), ("wrong_fact", 2)):
            with self.subTest(scenario=scenario):
                completion = structured_fixture(scenario, {"scenario": scenario})
                _, events = run_case(structured, "5", scenario, {"scenario": scenario}, completion)
                self.assertTrue(all(c["passed"] for c in report(events)["checks"]))
                self.assertEqual(len([e for e in events if e[0] == "request"]), calls)
                self.assertEqual(len(reports(events)), calls)
                if scenario == "missing_field":
                    self.assertEqual([c["passed"] for c in reports(events)[0]["checks"]], [True, False])
                elif scenario == "wrong_fact":
                    self.assertEqual([c["passed"] for c in reports(events)[0]["checks"]], [True, True, False])
                self.assertIn({"label": "学习者备注", "value": "fixed task"}, report(events)["metrics"])

    def test_failed_repair_does_not_become_success_or_exceed_budget(self):
        calls = []
        def invalid(body, key):
            calls.append(body)
            return {"choices": [{"message": {"content": "not JSON"}}]}
        result, events = run_case(structured, "5", "normal", {}, invalid, budget=1)
        self.assertIn("未通过", result)
        self.assertEqual(len(calls), 1)
        self.assertFalse(report(events)["checks"][0]["passed"])
        self.assertEqual(report(events)["metrics"][0]["value"], 1)

    def test_disabling_repair_preserves_first_schema_failure(self):
        result, events = run_case(structured, "5", "missing-field",
                                  {"scenario": "missing_field", "repair": False},
                                  structured_fixture("missing-field"))
        self.assertIn("未通过", result)
        self.assertEqual(len([e for e in events if e[0] == "request"]), 1)
        self.assertEqual([check["passed"] for check in report(events)["checks"]], [True, False])

    def test_cancel_after_first_model_call_prevents_repair(self):
        calls = []
        def first_invalid(body, key):
            calls.append(body)
            return {"choices": [{"message": {"content": "not JSON"}}]}
        with self.assertRaises(RunCancelled):
            run_case(structured, "5", "normal", {}, first_invalid, cancelled=lambda: bool(calls))
        self.assertEqual(len(calls), 1)


class PromptExperimentTests(unittest.TestCase):
    def test_pair_uses_same_task_model_and_temperature_and_records_both(self):
        for scenario in prompts.TASKS:
            with self.subTest(scenario=scenario):
                result, events = run_case(prompts, "6", scenario, {"scenario": scenario},
                                          prompt_fixture(scenario, {"scenario": scenario}))
                self.assertFalse(any(kind == "tool_call" for kind, _, _ in events), "配对实验只记录提议，不执行")
                requests = [data["body"] for kind, data, _ in events if kind == "request"]
                self.assertEqual(len(requests), 2)
                self.assertEqual(requests[0]["model"], requests[1]["model"])
                self.assertEqual(requests[0]["temperature"], requests[1]["temperature"])
                self.assertEqual(requests[0]["messages"][1], requests[1]["messages"][1])
                if scenario == "tool_description":
                    self.assertEqual(requests[0]["messages"], requests[1]["messages"])
                    self.assertNotEqual(requests[0]["tools"][0]["function"]["description"],
                                        requests[1]["tools"][0]["function"]["description"])
                    self.assertEqual(requests[0]["tools"][0]["function"]["parameters"],
                                     requests[1]["tools"][0]["function"]["parameters"])
                else:
                    self.assertNotEqual(requests[0]["messages"][0], requests[1]["messages"][0])
                self.assertEqual(len(report(events)["table"]["rows"]), 2)
                self.assertIn("单次", result)
                self.assertIn({"label": "学习者备注", "value": "fixed task"}, report(events)["metrics"])

    def test_description_matrix_changes_only_the_description_and_runs_proposals(self):
        result, events = run_case(prompts, "6", "tool-matrix", {"scenario": "tool_matrix"},
                                  prompt_fixture("tool-matrix", {"scenario": "tool_matrix"}), budget=6)
        requests = [data["body"] for kind, data, _ in events if kind == "request"]
        self.assertEqual(len(requests), 6)
        functions = [body["tools"][0]["function"] for body in requests]
        self.assertNotIn("description", functions[0])
        self.assertEqual([f.get("description") for f in functions[::2]], list(prompts.DESCRIPTIONS.values()))
        self.assertTrue(all(f["parameters"] == functions[0]["parameters"] for f in functions))
        self.assertTrue(all(body["messages"][0] == requests[0]["messages"][0] for body in requests))
        self.assertTrue(all(body["temperature"] == 0 for body in requests))
        # Proposals are executed by real Python; the misleading "concatenate" call still returns a sum.
        results = [(round_number, data["result"]) for kind, data, round_number in events if kind == "tool_result"]
        self.assertEqual(results, [(1, {"ok": True, "result": 42}), (3, {"ok": True, "result": 42}),
                                   (6, {"ok": True, "result": 42})])
        checks = report(events)["checks"]
        self.assertEqual([check["passed"] for check in checks], [True, True, True, True, False, False])
        self.assertIn("实际返回 42", report(events)["table"]["rows"][2][2])
        self.assertIn("单次", result)

    def test_matrix_needs_full_budget_and_judges_cells_strictly(self):
        with self.assertRaises(RuntimeError):
            run_case(prompts, "6", "tool-matrix", {"scenario": "tool_matrix"},
                     prompt_fixture("tool-matrix", {"scenario": "tool_matrix"}), budget=5)
        expected = {"a": 19, "b": 23}
        self.assertTrue(prompts.judge_cell(expected, {"name": "add_numbers", "arguments": expected})[0])
        self.assertFalse(prompts.judge_cell(expected, {"name": "add_numbers", "arguments": {"a": 19}})[0])
        self.assertFalse(prompts.judge_cell(expected, None)[0])
        self.assertFalse(prompts.judge_cell(None, {"name": "add_numbers", "arguments": expected})[0])
        self.assertTrue(prompts.judge_cell(None, None)[0])
        bad_json = {"choices": [{"message": {"tool_calls": [{"function": {"name": "add_numbers", "arguments": "{"}}]}}]}
        self.assertEqual(prompts.proposed_call(bad_json), {"name": "add_numbers", "arguments": None})

    def test_heuristic_rejects_known_false_positives(self):
        self.assertFalse(prompts.evaluate("flow_rule", "不是42而是43")[0])
        self.assertFalse(prompts.evaluate("missing_input", "需要计算1+1=2")[0])
        self.assertIn("人工复核", prompts.evaluate("flow_rule", "19+23=42")[1])

    def test_budget_and_cancel_stop_second_call(self):
        calls = []
        def provider(body, key):
            calls.append(body)
            return {"choices": [{"message": {"content": "42"}}]}
        with self.assertRaises(RuntimeError):
            run_case(prompts, "6", "flow-rule", {}, provider, budget=1)
        self.assertEqual(calls, [])
        with self.assertRaises(RunCancelled):
            run_case(prompts, "6", "flow-rule", {}, provider, cancelled=lambda: bool(calls))
        self.assertEqual(len(calls), 1)

    def test_bad_tool_proposal_is_reported_as_failure_without_execution(self):
        def wrong_call(body, key):
            return {"choices": [{"message": {"content": None, "tool_calls": [{"id": "x", "type": "function",
                "function": {"name": "delete_file", "arguments": '{"path":"secret"}'}}]}}]}
        _, events = run_case(prompts, "6", "tool-description", {}, wrong_call)
        self.assertEqual(len([e for e in events if e[0] == "tool_result"]), 0)
        self.assertTrue(all(not check["passed"] for check in report(events)["checks"]))


if __name__ == "__main__":
    unittest.main()
