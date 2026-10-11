"""Show a tool success, an argument error and an unknown tool locally; reads no key and never connects to Bailian.

Run it with --locale en for English output.
"""

import json

from course.i18n import cli_locale
from course.runner import execute_tool
from lessons.lesson_03_fail_safely.locales import texts_for
from lessons.lesson_03_fail_safely.tools import available_tools

# Case -> the call to check: the same shape a model proposal has.
CASES = {
    "valid": {"function": {"name": "divide_numbers", "arguments": '{"a": 12, "b": 3}'}},
    "zero": {"function": {"name": "divide_numbers", "arguments": '{"a": 12, "b": 0}'}},
    "unknown": {"function": {"name": "delete_files", "arguments": "{}"}},
    "malformed": {"function": {"name": "divide_numbers", "arguments": "{bad json"}},
}


def show_case(title, tool_call, locale):
    print("\n=== {} ===".format(title))
    result = execute_tool(tool_call, available_tools(locale), locale)
    print(texts_for(locale).demo_result.format(result=json.dumps(result, ensure_ascii=False)))


def main(locale=None):
    locale = locale or cli_locale()
    t = texts_for(locale)
    print(t.demo_intro)
    for case, tool_call in CASES.items():
        show_case(t.demo_cases[case], tool_call, locale)


if __name__ == "__main__":
    main()
