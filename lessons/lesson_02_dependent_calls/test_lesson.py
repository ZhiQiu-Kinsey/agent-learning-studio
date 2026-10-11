"""Behavior tests for dependent-calls: deterministic model data, real tools; the dependent call must use this run's clock."""
import json
import re
import unittest

from course.execution import RunContext
from lessons.lesson_01_tool_selection.tools import tool_definitions
from lessons.lesson_02_dependent_calls import main
from lessons.lesson_02_dependent_calls.fixtures import create_completion
from lessons.lesson_02_dependent_calls.locales import texts_for

CJK = re.compile(r"[　-〿一-鿿＀-￯]")


def run_case(exercise_id, locale="zh-CN"):
    events = []
    context = RunContext(
        lesson_id="dependent-calls", exercise_id=exercise_id, question="q", mode="offline", model="offline-script",
        representation="local", inputs={}, api_key="", completion=create_completion(exercise_id, locale=locale),
        emit_event=lambda kind, data, number: events.append((kind, data)), max_model_calls=3, locale=locale,
    )
    context.run_native(main, 3, publish_answer=True)
    return events


def of(events, kind):
    return [data for event, data in events if event == kind]


class SetupTests(unittest.TestCase):
    def test_setup_follows_the_locale_and_keeps_the_shared_tools(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                setup = main.setup(locale)
                self.assertEqual(setup.system_prompt, texts_for(locale).system_prompt)
                self.assertEqual(setup.tools, tool_definitions(locale))
                self.assertEqual(set(setup.available_tools), {"add_numbers", "get_current_time"})
        self.assertFalse(CJK.search(main.setup("en").system_prompt))
        self.assertIn("get_current_time", main.setup("en").system_prompt)


class ChainTests(unittest.TestCase):
    def test_dependent_call_uses_the_real_clock_in_both_languages(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                events = run_case("chain", locale)
                calls = of(events, "tool_call")
                clock = of(events, "tool_result")[0]["result"]["result"]
                self.assertEqual([call["function"]["name"] for call in calls], ["get_current_time", "add_numbers"])
                self.assertEqual(json.loads(calls[1]["function"]["arguments"]),
                                 {"a": clock["hour"], "b": clock["minute"]})
                self.assertEqual(of(events, "request")[0]["body"]["messages"][0]["content"],
                                 texts_for(locale).system_prompt)
                answer = of(events, "answer")[-1]["content"]
                self.assertIn(str(clock["hour"] + clock["minute"]), answer)

    def test_english_run_has_no_chinese(self):
        for exercise_id in ("chain", "both"):
            with self.subTest(exercise=exercise_id):
                events = run_case(exercise_id, "en")
                self.assertFalse(CJK.search(json.dumps(events, ensure_ascii=False)))


if __name__ == "__main__":
    unittest.main()
