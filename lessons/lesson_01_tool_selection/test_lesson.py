"""Tool boundary tests for tool-selection: they really run add_numbers and never call a model."""
import unittest

from course.runner import execute_tool
from lessons.lesson_01_tool_selection import main
from lessons.lesson_01_tool_selection.tools import available_tools, tool_definitions


def add_call(arguments):
    return {"id": "c1", "type": "function", "function": {"name": "add_numbers", "arguments": arguments}}


class AddNumbersTests(unittest.TestCase):
    def test_finite_numbers_are_added(self):
        self.assertEqual(execute_tool(add_call('{"a": 19, "b": 23}'), available_tools("zh-CN")),
                         {"ok": True, "result": 42})

    def test_unusable_numbers_become_structured_errors(self):
        # 1e400 parses as inf; a 401-digit integer parses as int and overflows when turned into a float.
        # Both must come back as ok=false instead of crashing the run.
        huge = "1" + "0" * 400
        for arguments in ('{"a": 1e400, "b": 1}', '{"a": NaN, "b": 1}', '{"a": %s, "b": 1}' % huge,
                          '{"a": 1, "b": -%s}' % huge):
            with self.subTest(arguments=arguments[:24]):
                result = execute_tool(add_call(arguments), available_tools("zh-CN"))
                self.assertFalse(result["ok"])
                self.assertEqual(result["error_type"], "ValueError")

    def test_overflowing_sum_becomes_structured_error(self):
        # Each argument is finite but the sum overflows: floats add up to inf, big integers leave the float range.
        # Returning ok=true would make publishing the tool_result fail (allow_nan=False), leaving the call unpaired.
        big = "1" + "0" * 308
        for arguments in ('{"a": 1e308, "b": 1e308}', '{"a": -1e308, "b": -1e308}', '{"a": %s, "b": %s}' % (big, big)):
            with self.subTest(arguments=arguments[:24]):
                result = execute_tool(add_call(arguments), available_tools("zh-CN"))
                self.assertFalse(result["ok"])
                self.assertEqual(result["error_type"], "ValueError")
                self.assertIn("两数之和", result["error"])

    def test_errors_come_in_the_run_language(self):
        result = execute_tool(add_call('{"a": "19", "b": 23}'), available_tools("en"), "en")
        self.assertEqual(result, {"ok": False, "error_type": "ValueError", "error": "Argument a must be a number."})
        unknown = execute_tool({"id": "c2", "type": "function", "function": {"name": "delete_files"}},
                               available_tools("en"), "en")
        self.assertEqual(unknown["error"], "Unknown tool: delete_files")

    def test_model_arguments_cannot_replace_the_message_catalog(self):
        # t is positional-only: an argument named t (or anything else extra) is a TypeError, not a new catalog.
        for arguments in ('{"a": 1, "b": 2, "t": "x"}', '{"a": 1, "b": 2, "c": 3}'):
            with self.subTest(arguments=arguments):
                result = execute_tool(add_call(arguments), available_tools("en"), "en")
                self.assertEqual(result["error_type"], "TypeError")
                self.assertIn("add_numbers()", result["error"])


class SetupTests(unittest.TestCase):
    def test_names_stay_code_and_descriptions_follow_the_locale(self):
        zh, en = tool_definitions("zh-CN"), tool_definitions("en")
        self.assertEqual([tool["function"]["name"] for tool in zh], [tool["function"]["name"] for tool in en])
        self.assertEqual([sorted(tool["function"]["parameters"]["properties"]) for tool in zh],
                         [sorted(tool["function"]["parameters"]["properties"]) for tool in en])
        self.assertNotEqual(zh[0]["function"]["description"], en[0]["function"]["description"])
        self.assertEqual(main.setup("en").system_prompt.split()[0], "You")
        self.assertEqual(set(main.setup("zh-CN").available_tools), {"add_numbers", "get_current_time"})


if __name__ == "__main__":
    unittest.main()
