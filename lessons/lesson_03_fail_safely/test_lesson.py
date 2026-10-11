"""Behavior tests for fail-safely: divide_numbers really runs; the model side is deterministic or absent."""
import io
import json
import re
import unittest
from contextlib import redirect_stdout

from course.execution import RunContext, execute_lesson
from course.runner import execute_tool
from lessons.lesson_03_fail_safely import main, offline_demo, runtime
from lessons.lesson_03_fail_safely.fixtures import create_completion
from lessons.lesson_03_fail_safely.locales import texts_for
from lessons.lesson_03_fail_safely.tools import available_tools, tool_definitions

CJK = re.compile(r"[　-〿一-鿿＀-￯]")
SPEC = {"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}


def divide(arguments, locale="zh-CN"):
    call = {"id": "c1", "type": "function", "function": {"name": "divide_numbers", "arguments": arguments}}
    return execute_tool(call, available_tools(locale), locale)


def run_case(exercise_id, locale="zh-CN"):
    events = []
    needs_model = exercise_id in ("divide", "zero")
    context = RunContext(
        lesson_id="fail-safely", exercise_id=exercise_id, question="q", mode="offline", model="offline-script",
        representation="local", inputs={}, api_key="",
        completion=create_completion(exercise_id, locale=locale) if needs_model else None,
        emit_event=lambda kind, data, number: events.append((kind, data)), max_model_calls=2, locale=locale,
    )
    execute_lesson(SPEC, runtime, context)
    return events


def of(events, kind):
    return [data for event, data in events if event == kind]


class DivideTests(unittest.TestCase):
    def test_valid_division(self):
        self.assertEqual(divide('{"a": 12, "b": 3}'), {"ok": True, "result": {"quotient": 4.0}})

    def test_errors_follow_the_run_language(self):
        cases = {'{"a": 12, "b": 0}': "zero_divisor", '{"a": 1e400, "b": 1}': "not_finite",
                 '{"a": 1e308, "b": 1e-308}': "out_of_range"}
        for locale in ("zh-CN", "en"):
            t = texts_for(locale)
            for arguments, field in cases.items():
                with self.subTest(locale=locale, arguments=arguments):
                    self.assertEqual(divide(arguments, locale),
                                     {"ok": False, "error_type": "ValueError", "error": getattr(t, field)})
            self.assertEqual(divide('{"a": "12", "b": 3}', locale)["error"], t.not_a_number.format(name="a"))

    def test_huge_integer_counts_as_not_finite(self):
        # Converting a 401-digit integer to a float raises OverflowError inside math.isfinite;
        # the tool reports it as a non-finite input instead of crashing.
        result = divide('{"a": 1%s, "b": 3}' % ("0" * 400), "en")
        self.assertEqual(result["error"], texts_for("en").not_finite)

    def test_model_arguments_cannot_replace_the_message_catalog(self):
        for arguments in ('{"a": 1, "b": 2, "t": "x"}', '{"a": 1, "b": 2, "c": 3}'):
            with self.subTest(arguments=arguments):
                self.assertEqual(divide(arguments, "en")["error_type"], "TypeError")

    def test_definitions_keep_names_and_translate_descriptions(self):
        zh, en = tool_definitions("zh-CN")[0]["function"], tool_definitions("en")[0]["function"]
        self.assertEqual((zh["name"], sorted(zh["parameters"]["properties"])),
                         (en["name"], sorted(en["parameters"]["properties"])))
        self.assertFalse(CJK.search(json.dumps(en, ensure_ascii=False)))
        self.assertEqual(main.setup("en").system_prompt, texts_for("en").system_prompt)


class RunTests(unittest.TestCase):
    def test_zero_divisor_goes_back_to_the_model(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                events = run_case("zero", locale)
                results = of(events, "tool_result")
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["result"]["error"], texts_for(locale).zero_divisor)
                second = of(events, "request")[1]["body"]["messages"]
                self.assertEqual(second[-1]["role"], "tool")

    def test_fault_injections_answer_in_the_run_language(self):
        for case, error_type in (("unknown", "ValueError"), ("malformed", "JSONDecodeError")):
            for locale in ("zh-CN", "en"):
                with self.subTest(case=case, locale=locale):
                    events = run_case(case, locale)
                    self.assertEqual(of(events, "request"), [])
                    result = of(events, "tool_result")[0]["result"]
                    self.assertEqual(result["error_type"], error_type)
                    answer = of(events, "answer")[-1]["content"]
                    name, arguments = runtime.FAULTS[case]
                    self.assertEqual(answer, texts_for(locale).fault_answer.format(
                        name=name, arguments=arguments, error_type=error_type, error=result["error"]))

    def test_english_runs_have_no_chinese(self):
        for case in ("divide", "zero", "unknown", "malformed"):
            with self.subTest(case=case):
                self.assertFalse(CJK.search(json.dumps(run_case(case, "en"), ensure_ascii=False)))


class OfflineDemoTests(unittest.TestCase):
    def test_demo_prints_four_cases_in_the_chosen_language(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                output = io.StringIO()
                with redirect_stdout(output):
                    offline_demo.main(locale)
                text = output.getvalue()
                self.assertEqual(text.count("==="), 8)
                for title in texts_for(locale).demo_cases.values():
                    self.assertIn(title, text)
        self.assertFalse(CJK.search(text))


if __name__ == "__main__":
    unittest.main()
