"""English-run tests for application-state; the Chinese behaviour tests are in tests/test_lessons_context_state.py.

This lesson calls no model: the state machine really runs in Python.
"""
import json
import re
import unittest

from pydantic import ValidationError

from course.execution import RunContext, validate_inputs
from lessons.lesson_08_application_state import runtime
from lessons.lesson_08_application_state.locales import texts_for
from server.selectors import resolve_path

CJK = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")
GOALS = {"zh-CN": "说明消息与应用状态的区别", "en": "Explain the difference between messages and application state"}
PRESETS = {"success": {"source_key": "messages-context"}, "missing": {"source_key": "missing"},
           "budget": {"source_key": "application-state", "step_budget": 2}}


def run_case(exercise_id, locale="en"):
    events = []
    values = validate_inputs(runtime, {"goal": GOALS[locale], **PRESETS[exercise_id]})
    context = RunContext(
        lesson_id="application-state", exercise_id=exercise_id, question="", mode="offline",
        model="local-python", representation="local", inputs=values, api_key="", completion=None,
        emit_event=lambda kind, data, number: events.append((kind, data, number)), locale=locale,
    )
    return runtime.run(context), events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


class EnglishRunTests(unittest.TestCase):
    def test_english_runs_have_no_chinese_and_the_same_outcomes(self):
        for exercise, status in (("success", "completed"), ("missing", "failed"), ("budget", "failed")):
            with self.subTest(exercise=exercise):
                answers = {locale: run_case(exercise, locale) for locale in ("zh-CN", "en")}
                answer, events = answers["en"]
                self.assertIsNone(CJK.search(json.dumps([answer, events], ensure_ascii=False)))
                for locale, (_, run_events) in answers.items():
                    states = [data["state"] for data in of(run_events, "lesson.state")]
                    self.assertEqual(states[-1]["status"], status)
                    # The lab selects the terminal-reason check by id, the same in both languages.
                    reason = resolve_path({"data": of(run_events, "lesson.report")[0]}, "data.checks[id=terminal_reason]")
                    self.assertEqual(reason["detail"], states[-1]["terminal_reason"])
                # Both languages walk the same states with the same number of steps.
                self.assertEqual([[data["state"]["status"], data["state"]["used_steps"]] for data in of(events, "lesson.state")],
                                 [[data["state"]["status"], data["state"]["used_steps"]]
                                  for data in of(answers["zh-CN"][1], "lesson.state")])

    def test_english_snapshot_and_report(self):
        t = texts_for("en")
        answer, events = run_case("success")
        final = of(events, "lesson.state")[-1]["state"]
        self.assertEqual(final["steps"], [t.step_read_index, t.step_check_source, t.step_summarize])
        self.assertEqual(final["evidence"][0]["excerpt"], t.source_excerpts["messages-context"])
        self.assertNotIn("locale", final)
        self.assertEqual(answer, t.answer_completed.format(result=final["result"], goal=GOALS["en"]))
        report = of(events, "lesson.report")[0]
        self.assertEqual([check["label"] for check in report["checks"]], [t.check_reason, t.check_success, t.check_separate])
        self.assertEqual(report["table"]["columns"], list(t.columns))

    def test_success_answer_has_no_doubled_punctuation(self):
        # result is a full sentence (the excerpt ends with its own full stop), so the answer template must not
        # append another separator after it ("。；" / ".;").
        expected = {"zh-CN": "课内资料归纳流程已完成。资料 {key} 的要点：{excerpt}自由目标“{goal}”未被单独验收。",
                    "en": "The lesson-material summary flow finished. Key points of material {key}: {excerpt} "
                          "The free-form goal \"{goal}\" was not checked separately."}
        for locale in ("zh-CN", "en"):
            t = texts_for(locale)
            for key, excerpt in t.source_excerpts.items():
                with self.subTest(locale=locale, source_key=key):
                    self.assertTrue(excerpt.endswith("。" if locale == "zh-CN" else "."), excerpt)
                    events = []
                    values = validate_inputs(runtime, {"goal": GOALS[locale], "source_key": key})
                    context = RunContext(
                        lesson_id="application-state", exercise_id="success", question="", mode="offline",
                        model="local-python", representation="local", inputs=values, api_key="", completion=None,
                        emit_event=lambda kind, data, number: events.append((kind, data, number)), locale=locale,
                    )
                    answer = runtime.run(context)
                    self.assertEqual(answer, expected[locale].format(key=key, excerpt=excerpt, goal=GOALS[locale]))
                    self.assertIsNone(re.search(r"[。.][；;，,。]", answer.replace("...", "")), answer)

    def test_state_machine_errors_follow_the_language(self):
        state = runtime.TaskState(run_id="one", goal="a checkable goal", locale="en")
        with self.assertRaisesRegex(ValueError, "Illegal state transition: ready → completed"):
            state.transition("completed", "not run")
        state.transition("running")
        with self.assertRaisesRegex(ValueError, "cannot be marked completed"):
            state.transition("completed", "no evidence")

    def test_goal_has_no_hidden_default(self):
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {})


if __name__ == "__main__":
    unittest.main()
