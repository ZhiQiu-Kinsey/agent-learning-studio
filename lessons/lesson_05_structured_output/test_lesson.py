"""Behavior tests for structured-output: deterministic model data; they check the three layers, the bounded repair and the report."""
import json
import re
import unittest

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_05_structured_output import runtime as structured
from lessons.lesson_05_structured_output.fixtures import create_completion
from lessons.lesson_05_structured_output.locales import texts_for

CJK = re.compile(r"[　-〿一-鿿＀-￯]")
ZH = texts_for("zh-CN")


def run_case(exercise_id, inputs, completion, budget=2, cancelled=lambda: False, question="fixed task",
             locale="zh-CN"):
    events = []
    context = RunContext(
        lesson_id="structured-output", exercise_id=exercise_id, question=question, mode="offline",
        model="fixture-model", representation="sdk_standardized",
        inputs=validate_inputs(structured, inputs), api_key="fixture-key",
        completion=completion, max_model_calls=budget, cancelled=cancelled,
        emit_event=lambda kind, data, round_number: events.append((kind, data, round_number)),
        locale=locale,
    )
    result = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, structured, context)
    return result, events


def reports(events):
    return [data for kind, data, _ in events if kind == "lesson.report"]


def report(events):
    return reports(events)[-1]


class StructuredOutputTests(unittest.TestCase):
    def test_layers_distinguish_format_schema_and_fact(self):
        cases = [('{bad', [False]), ('{"lesson_id":"task-contract"}', [True, False]),
                 ('NaN', [False]), ('Infinity', [False]), ('-Infinity', [False]),
                 ('{"lesson_id":"task-contract","lesson_title":"任务目标与验收","prerequisite":"dependent-calls","exercise":"解释验收流程与证据"}',
                  [True, True, False])]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                _, checks = structured.inspect_output(raw, ZH)
                self.assertEqual([c["passed"] for c in checks], expected)
        _, checks = structured.inspect_output("NaN", ZH)
        self.assertEqual(checks[0]["detail"], "非标准 JSON 常量：NaN")
        _, checks = structured.inspect_output("NaN", texts_for("en"))
        self.assertEqual(checks[0]["detail"], "non-standard JSON constant: NaN")

    def test_title_fact_follows_the_run_language(self):
        card = {"lesson_id": "task-contract", "lesson_title": "任务目标与验收", "prerequisite": "fail-safely",
                "exercise": "explain acceptance"}
        self.assertTrue(all(c["passed"] for c in structured.inspect_output(json.dumps(card), ZH)[1]))
        english = structured.inspect_output(json.dumps(card), texts_for("en"))[1]
        self.assertEqual([c["passed"] for c in english], [True, True, False])
        self.assertIn("lesson_title", english[2]["detail"])

    def test_normal_and_one_bounded_repair(self):
        for locale in ("zh-CN", "en"):
            for scenario, calls in (("normal", 1), ("missing_field", 2), ("wrong_fact", 2)):
                with self.subTest(locale=locale, scenario=scenario):
                    completion = create_completion(scenario, {"scenario": scenario}, locale)
                    _, events = run_case(scenario, {"scenario": scenario}, completion, locale=locale)
                    self.assertTrue(all(c["passed"] for c in report(events)["checks"]))
                    self.assertEqual(len([e for e in events if e[0] == "request"]), calls)
                    self.assertEqual(len(reports(events)), calls)
                    # Each report is recorded on the round of its draft, so the guided tour can point at the first draft's report.
                    self.assertEqual([number for kind, _, number in events if kind == "lesson.report"],
                                     list(range(1, calls + 1)))
                    if scenario == "missing_field":
                        self.assertEqual([c["passed"] for c in reports(events)[0]["checks"]], [True, False])
                    elif scenario == "wrong_fact":
                        self.assertEqual([c["passed"] for c in reports(events)[0]["checks"]], [True, True, False])
                    label = texts_for(locale).label_note
                    self.assertIn({"label": label, "value": "fixed task"}, report(events)["metrics"])

    def test_repair_request_carries_the_failure_reason(self):
        _, events = run_case("missing-field", {"scenario": "missing_field"},
                             create_completion("missing-field", {"scenario": "missing_field"}))
        repair = [data["body"] for kind, data, _ in events if kind == "request"][1]["messages"][-1]["content"]
        self.assertEqual(repair, "上一版未通过：prerequisite: missing。只按原始可信事实输出完整 JSON 对象。")
        self.assertEqual(reports(events)[0]["title"], "初稿：结构化输出三层校验")
        self.assertEqual(reports(events)[1]["summary"], "修复稿通过已执行的全部检查")

    def test_failed_repair_does_not_become_success_or_exceed_budget(self):
        calls = []

        def invalid(body, key):
            calls.append(body)
            return {"choices": [{"message": {"content": "not JSON"}}]}
        result, events = run_case("normal", {}, invalid, budget=1)
        self.assertIn("未通过", result)
        self.assertEqual(len(calls), 1)
        self.assertFalse(report(events)["checks"][0]["passed"])
        self.assertEqual(report(events)["metrics"][0]["value"], 1)

    def test_disabling_repair_preserves_first_schema_failure(self):
        result, events = run_case("missing-field", {"scenario": "missing_field", "repair": False},
                                  create_completion("missing-field"))
        self.assertIn("未通过", result)
        self.assertEqual(len([e for e in events if e[0] == "request"]), 1)
        self.assertEqual([check["passed"] for check in report(events)["checks"]], [True, False])

    def test_cancel_after_first_model_call_prevents_repair(self):
        calls = []

        def first_invalid(body, key):
            calls.append(body)
            return {"choices": [{"message": {"content": "not JSON"}}]}
        with self.assertRaises(RunCancelled):
            run_case("normal", {}, first_invalid, cancelled=lambda: bool(calls))
        self.assertEqual(len(calls), 1)

    def test_unreadable_response_raises_in_the_run_language(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale), self.assertRaisesRegex(ValueError, "message.content"):
                run_case("normal", {}, lambda body, key: {"error": "x"}, locale=locale)


class EnglishRunTests(unittest.TestCase):
    def test_english_run_sends_and_reports_english(self):
        t = texts_for("en")
        result, events = run_case("wrong-fact", {"scenario": "wrong_fact"},
                                  create_completion("wrong-fact", {"scenario": "wrong_fact"}, "en"),
                                  question="note", locale="en")
        bodies = [data["body"] for kind, data, _ in events if kind == "request"]
        self.assertEqual(bodies[0]["messages"][0]["content"], t.system_prompt)
        self.assertIn('"lesson_title": "Task goals and acceptance"', bodies[0]["messages"][1]["content"])
        self.assertTrue(bodies[0]["messages"][1]["content"].endswith(t.inject_wrong_fact.format(wrong="dependent-calls")))
        self.assertEqual(bodies[1]["messages"][-1]["content"], t.repair_prompt.format(
            reasons="does not match the given facts: prerequisite"))
        self.assertEqual(reports(events)[0]["title"], "First draft: three-layer check of structured output")
        self.assertTrue(result.startswith("Accepted: "))
        self.assertIsNone(CJK.search(json.dumps([result, *[data for _, data, _ in events]], ensure_ascii=False)))


if __name__ == "__main__":
    unittest.main()
