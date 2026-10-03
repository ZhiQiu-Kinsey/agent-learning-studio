"""“执行工具与回传结果”的工具边界测试：真实执行 add_numbers，不请求模型。"""
import unittest

from course.runner import execute_tool
from lessons.lesson_01_tool_selection.tools import AVAILABLE_TOOLS


def add_call(arguments):
    return {"id": "c1", "type": "function", "function": {"name": "add_numbers", "arguments": arguments}}


class AddNumbersTests(unittest.TestCase):
    def test_finite_numbers_are_added(self):
        self.assertEqual(execute_tool(add_call('{"a": 19, "b": 23}'), AVAILABLE_TOOLS), {"ok": True, "result": 42})

    def test_unusable_numbers_become_structured_errors(self):
        # 1e400 解析成 inf；401 位的整数解析成 int，转浮点数时溢出。都应返回 ok=false，不让运行崩溃。
        huge = "1" + "0" * 400
        for arguments in ('{"a": 1e400, "b": 1}', '{"a": NaN, "b": 1}', '{"a": %s, "b": 1}' % huge,
                          '{"a": 1, "b": -%s}' % huge):
            with self.subTest(arguments=arguments[:24]):
                result = execute_tool(add_call(arguments), AVAILABLE_TOOLS)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error_type"], "ValueError")

    def test_overflowing_sum_becomes_structured_error(self):
        # 两个参数各自有限，和却溢出：浮点数相加得到 inf，大整数相加超出浮点数范围。
        # 若返回 ok=true，发布 tool_result 时 allow_nan=False 会报错，tool_call 就没有配对的结果。
        big = "1" + "0" * 308
        for arguments in ('{"a": 1e308, "b": 1e308}', '{"a": -1e308, "b": -1e308}', '{"a": %s, "b": %s}' % (big, big)):
            with self.subTest(arguments=arguments[:24]):
                result = execute_tool(add_call(arguments), AVAILABLE_TOOLS)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error_type"], "ValueError")
                self.assertIn("两数之和", result["error"])


if __name__ == "__main__":
    unittest.main()
