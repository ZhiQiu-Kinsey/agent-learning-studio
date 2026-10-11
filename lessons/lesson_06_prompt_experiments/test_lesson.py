"""Behavior tests for prompt-experiments: deterministic model data; real Python runs the proposals of the matrix."""
import json
import re
import unittest

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_06_prompt_experiments import runtime as prompts
from lessons.lesson_06_prompt_experiments.fixtures import create_completion
from lessons.lesson_06_prompt_experiments.locales import texts_for

CJK = re.compile(r"[　-〿一-鿿＀-￯]")
ZH = texts_for("zh-CN")
EN = texts_for("en")
SAMPLES = {"zh-CN": "配对样本", "en": "paired sample"}


def run_case(exercise_id, inputs, completion=None, budget=2, cancelled=lambda: False, question="fixed task",
             locale="zh-CN"):
    events = []
    context = RunContext(
        lesson_id="prompt-experiments", exercise_id=exercise_id, question=question, mode="offline",
        model="fixture-model", representation="sdk_standardized",
        inputs=validate_inputs(prompts, {"sample_label": SAMPLES[locale], **inputs}), api_key="fixture-key",
        completion=completion, max_model_calls=budget, cancelled=cancelled,
        emit_event=lambda kind, data, round_number: events.append((kind, data, round_number)),
        locale=locale,
    )
    result = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, prompts, context)
    return result, events


def report(events):
    return [data for kind, data, _ in events if kind == "lesson.report"][-1]


class PromptExperimentTests(unittest.TestCase):
    def test_pair_uses_same_task_model_and_temperature_and_records_both(self):
        for locale in ("zh-CN", "en"):
            for scenario in prompts.PAIR_SCENARIOS:
                with self.subTest(locale=locale, scenario=scenario):
                    result, events = run_case(scenario, {"scenario": scenario},
                                              create_completion(scenario, {"scenario": scenario}, locale),
                                              locale=locale)
                    self.assertFalse(any(kind == "tool_call" for kind, _, _ in events),
                                     "the paired experiment records proposals without executing them")
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
                    self.assertEqual(result, texts_for(locale).pair_answer)
                    self.assertIn({"label": texts_for(locale).label_note, "value": "fixed task"},
                                  report(events)["metrics"])
        result, _ = run_case("flow-rule", {"scenario": "flow_rule"}, create_completion("flow-rule"))
        self.assertIn("单次", result)

    def test_rewrite_screens_hit_in_both_languages(self):
        for locale in ("zh-CN", "en"):
            for scenario in prompts.PAIR_SCENARIOS:
                with self.subTest(locale=locale, scenario=scenario):
                    _, events = run_case(scenario, {"scenario": scenario},
                                         create_completion(scenario, {"scenario": scenario}, locale), locale=locale)
                    self.assertEqual([check["passed"] for check in report(events)["checks"]], [False, True])

    def test_description_matrix_changes_only_the_description_and_runs_proposals(self):
        result, events = run_case("tool-matrix", {"scenario": "tool_matrix"},
                                  create_completion("tool-matrix", {"scenario": "tool_matrix"}), budget=6)
        requests = [data["body"] for kind, data, _ in events if kind == "request"]
        self.assertEqual(len(requests), 6)
        functions = [body["tools"][0]["function"] for body in requests]
        self.assertNotIn("description", functions[0])
        self.assertEqual([f.get("description") for f in functions[::2]],
                         [ZH.descriptions.get(group) for group in prompts.MATRIX_GROUPS])
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

    def test_matrix_records_the_models_own_proposal(self):
        # The model proposed these calls: the events carry the model's call id and no origin=course_program.
        _, events = run_case("tool-matrix", {"scenario": "tool_matrix"},
                             create_completion("tool-matrix", {"scenario": "tool_matrix"}), budget=6)
        responses = {number: data["body"] for kind, data, number in events if kind == "response"}
        calls = [(data, number) for kind, data, number in events if kind == "tool_call"]
        self.assertEqual([number for _, number in calls], [1, 3, 6])
        for call, number in calls:
            self.assertNotIn("origin", call)
            self.assertEqual(call, responses[number]["choices"][0]["message"]["tool_calls"][0])
        results = [data for kind, data, _ in events if kind == "tool_result"]
        self.assertEqual([result["tool_call_id"] for result in results], [call["id"] for call, _ in calls])
        self.assertTrue(all("origin" not in result for result in results))

    def test_matrix_needs_full_budget_and_judges_cells_strictly(self):
        with self.assertRaises(RuntimeError):
            run_case("tool-matrix", {"scenario": "tool_matrix"},
                     create_completion("tool-matrix", {"scenario": "tool_matrix"}), budget=5)
        expected = {"a": 19, "b": 23}
        self.assertTrue(prompts.judge_cell(expected, {"name": "add_numbers", "arguments": expected}, ZH)[0])
        self.assertFalse(prompts.judge_cell(expected, {"name": "add_numbers", "arguments": {"a": 19}}, ZH)[0])
        self.assertFalse(prompts.judge_cell(expected, None, ZH)[0])
        self.assertFalse(prompts.judge_cell(None, {"name": "add_numbers", "arguments": expected}, ZH)[0])
        self.assertTrue(prompts.judge_cell(None, None, ZH)[0])
        bad_json = {"choices": [{"message": {"tool_calls": [{"function": {"name": "add_numbers", "arguments": "{"}}]}}]}
        proposal = prompts.proposed_call(bad_json)
        self.assertEqual((proposal["name"], proposal["arguments"]), ("add_numbers", None))

    def test_matrix_tool_rejects_non_integer_arguments_instead_of_concatenating(self):
        # The schema says integers: strings or floats must come back as an error, not 1923 and not inf.
        self.assertEqual(prompts.add_numbers(ZH, 19, 23), 42)
        for a, b in (("19", "23"), (1e308, 1e308), (True, 1)):
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                prompts.add_numbers(ZH, a, b)
        with self.assertRaisesRegex(ValueError, "must be integers"):
            prompts.add_numbers(EN, "19", "23")

    def test_matrix_tool_error_reaches_the_table(self):
        def string_arguments(body, key):
            return {"choices": [{"message": {"content": None, "tool_calls": [{"id": "call_s", "type": "function",
                    "function": {"name": "add_numbers", "arguments": '{"a":"19","b":"23"}'}}]}}]}
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                _, events = run_case("tool-matrix", {"scenario": "tool_matrix"}, string_arguments, budget=6,
                                     locale=locale)
                result = next(data for kind, data, _ in events if kind == "tool_result")["result"]
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"], texts_for(locale).not_integers)
                self.assertIn(texts_for(locale).not_integers, report(events)["table"]["rows"][0][1])

    def test_heuristic_rejects_known_false_positives(self):
        self.assertFalse(prompts.evaluate("flow_rule", "不是42而是43", ZH)[0])
        self.assertFalse(prompts.evaluate("missing_input", "需要计算1+1=2", ZH)[0])
        self.assertIn("人工复核", prompts.evaluate("flow_rule", "19+23=42", ZH)[1])
        self.assertFalse(prompts.evaluate("flow_rule", "It is not 42 but 43", EN)[0])
        self.assertFalse(prompts.evaluate("flow_rule", "The sum isn't 42.", EN)[0])
        self.assertTrue(prompts.evaluate("flow_rule", "19 + 23 = 42.", EN)[0])
        self.assertFalse(prompts.evaluate("missing_input", "Compute 1+1=2", EN)[0])
        self.assertTrue(prompts.evaluate("missing_input", "Which two numbers should I add?", EN)[0])

    def test_budget_and_cancel_stop_second_call(self):
        calls = []

        def provider(body, key):
            calls.append(body)
            return {"choices": [{"message": {"content": "42"}}]}
        with self.assertRaises(RuntimeError):
            run_case("flow-rule", {}, provider, budget=1)
        self.assertEqual(calls, [])
        with self.assertRaises(RunCancelled):
            run_case("flow-rule", {}, provider, cancelled=lambda: bool(calls))
        self.assertEqual(len(calls), 1)

    def test_bad_tool_proposal_is_reported_as_failure_without_execution(self):
        def wrong_call(body, key):
            return {"choices": [{"message": {"content": None, "tool_calls": [{"id": "x", "type": "function",
                "function": {"name": "delete_file", "arguments": '{"path":"secret"}'}}]}}]}
        _, events = run_case("tool-description", {}, wrong_call)
        self.assertEqual(len([e for e in events if e[0] == "tool_result"]), 0)
        self.assertTrue(all(not check["passed"] for check in report(events)["checks"]))


class EnglishRunTests(unittest.TestCase):
    def test_english_matrix_sends_and_reports_english(self):
        result, events = run_case("tool-matrix", {"scenario": "tool_matrix"},
                                  create_completion("tool-matrix", {"scenario": "tool_matrix"}, "en"), budget=6,
                                  question="note", locale="en")
        requests = [data["body"] for kind, data, _ in events if kind == "request"]
        self.assertEqual(requests[4]["tools"][0]["function"]["description"], EN.descriptions["misleading"])
        self.assertEqual(requests[0]["messages"][1]["content"], "What is 19 plus 23?")
        table = report(events)["table"]
        self.assertEqual(table["columns"][1], "Sum: What is 19 plus 23?")
        self.assertEqual(table["rows"][0][0], "Blank (no description)")
        self.assertIn("actually returned 42", table["rows"][2][2])
        self.assertEqual(result, EN.matrix_answer.format(calls=6))
        self.assertIsNone(CJK.search(json.dumps([result, *[data for _, data, _ in events]], ensure_ascii=False)))

    def test_english_pairs_have_no_chinese(self):
        for scenario in prompts.PAIR_SCENARIOS:
            with self.subTest(scenario=scenario):
                result, events = run_case(scenario, {"scenario": scenario},
                                          create_completion(scenario, {"scenario": scenario}, "en"),
                                          question="note", locale="en")
                self.assertIsNone(CJK.search(json.dumps([result, *[data for _, data, _ in events]],
                                                        ensure_ascii=False)))


if __name__ == "__main__":
    unittest.main()
