"""English-run tests for messages-context; the Chinese behaviour tests are in tests/test_lessons_context_state.py.

Deterministic model data; lookup_score really runs in Python.
"""
import json
import re
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from lessons.lesson_07_messages_context import runtime
from lessons.lesson_07_messages_context.fixtures import create_completion
from lessons.lesson_07_messages_context.locales import texts_for
from lessons.lesson_07_messages_context.locales.protocol import texts_for as protocol_texts

CJK = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")


def run_case(inputs=None, locale="en"):
    events = []
    values = validate_inputs(runtime, inputs or {})
    context = RunContext(
        lesson_id="messages-context", exercise_id="ablate", question="", mode="offline",
        model="fixture-model", representation="offline", inputs=values, api_key="",
        completion=create_completion("ablate", values, locale), max_model_calls=4,
        emit_event=lambda kind, data, number: events.append((kind, data, number)), locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


class EnglishRunTests(unittest.TestCase):
    def test_english_run_has_no_chinese_anywhere(self):
        answer, events = run_case()
        self.assertIsNone(CJK.search(json.dumps([answer, events], ensure_ascii=False)))

    def test_english_messages_and_variant_names(self):
        t = texts_for("en")
        answer, events = run_case({"free_day": "sat"})
        full = of(events, "request")[0]["body"]["messages"]
        self.assertEqual(full[0]["content"], t.system_prompt)
        self.assertEqual(full[1]["content"],
                         "This week I can only review on Saturday evening. First, look up the latest exercise for s-1042.")
        self.assertEqual(full[4]["content"], t.question)
        variants = [data["variant"] for data in of(events, "lesson.context") if "variant" in data]
        self.assertEqual(variants, [t.variant_names[code] for code in runtime.VARIANTS])
        self.assertEqual(answer, t.final_answer.format(sent=4, blocked=1))

    def test_blocked_variant_reason_is_in_the_run_language(self):
        _, events = run_case()
        blocked = next(data for data in of(events, "lesson.context") if "rejected" in data)
        self.assertEqual(blocked["rejected"], protocol_texts("en").result_expected)
        report = of(events, "lesson.report")[0]
        self.assertTrue(all(check["passed"] for check in report["checks"]))
        rows = {row[0]: row for row in report["table"]["rows"]}
        t = texts_for("en")
        # The keyword screen looks for the English day and the English basis word.
        self.assertEqual(rows[t.variant_names["full"]][4:], [True, True, True])
        self.assertEqual(rows[t.variant_names["no_conversation"]][5], False)
        self.assertEqual(rows[t.variant_names["no_system"]][6], False)
        self.assertEqual(rows[t.variant_names["no_tool_result"]][2:4],
                         [t.protocol_rejected.format(error=protocol_texts("en").result_expected), t.outcome_not_sent])
        self.assertEqual(report["table"]["columns"], list(t.columns))

    def test_zh_run_keeps_the_chinese_text(self):
        _, events = run_case(locale="zh-CN")
        full = of(events, "request")[0]["body"]["messages"]
        self.assertEqual(full[1]["content"], "这周我只有周四晚上能复习。先帮我查一下 s-1042 最近一次练习。")
        self.assertEqual(of(events, "lesson.report")[0]["title"], "一次只拿掉一部分")

    def test_weekday_is_a_code_and_tool_errors_follow_the_language(self):
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {"free_day": "周四"})
        with self.assertRaisesRegex(ValueError, "No record for student ID s-9999"):
            runtime.lookup_score(texts_for("en"), "s-9999")
        with self.assertRaisesRegex(ValueError, "Orphaned"):
            runtime.validate_tool_history([{"role": "tool", "tool_call_id": "x", "content": "3"}], "en")

    def test_catalogs_cover_every_variant_and_day(self):
        for locale in ("zh-CN", "en"):
            t = texts_for(locale)
            self.assertEqual(set(t.variant_names), set(runtime.VARIANTS))
            self.assertEqual(set(t.weekdays), set(runtime.Inputs.model_fields["free_day"].annotation.__args__))


if __name__ == "__main__":
    unittest.main()
