"""course/runner.py 的工具分发与命令行入口；不联网、不调模型。"""
import io
import json
import sys
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from course import runner


def call(arguments, name="add"):
    function = {"name": name}
    if arguments is not ...:
        function["arguments"] = arguments
    return {"id": "call_1", "type": "function", "function": function}


TOOLS = {"add": lambda a=0, b=0: a + b, "ping": lambda: "pong"}


class ExecuteToolTests(unittest.TestCase):
    def test_empty_arguments_mean_no_arguments(self):
        # 无参数调用有的服务商给空串或 null：按没有参数执行，而不是报解析错误。
        for arguments in (..., "", None, "{}"):
            with self.subTest(arguments=arguments):
                self.assertEqual(runner.execute_tool(call(arguments, "ping"), TOOLS), {"ok": True, "result": "pong"})

    def test_broken_or_non_object_arguments_return_structured_errors(self):
        cases = {'{"a": 1': "JSONDecodeError", "[1, 2]": "ValueError", '{"c": 1}': "TypeError"}
        for arguments, error_type in cases.items():
            with self.subTest(arguments=arguments):
                result = runner.execute_tool(call(arguments), TOOLS)
                self.assertEqual((result["ok"], result["error_type"]), (False, error_type))

    def test_unknown_names_are_never_executed(self):
        result = runner.execute_tool(call("{}", "delete_files"), TOOLS)
        self.assertEqual((result["ok"], result["error_type"]), (False, "ValueError"))


class RunCliTests(unittest.TestCase):
    def test_cli_prints_requests_and_tool_results_but_never_the_key(self):
        responses = iter([
            {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "add", "arguments": '{"a": 19, "b": 23}'}}]}}]},
            {"choices": [{"message": {"role": "assistant", "content": "结果是 42。"}}]},
        ])
        sent = []

        def fake_send(request, api_key, timeout_seconds=60, *, locale="zh-CN"):
            sent.append((json.loads(json.dumps(request)), api_key))
            return next(responses)

        out, err = io.StringIO(), io.StringIO()
        config = types.SimpleNamespace(MODEL="test-model")
        with patch.dict(sys.modules, {"local_config": config}), \
                patch.object(runner, "send_bailian", fake_send), \
                patch("builtins.input", return_value="19 加 23"), \
                patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-secret-value"}), \
                redirect_stdout(out), redirect_stderr(err):
            runner.run_cli(runner.AgentSetup("系统提示", [], TOOLS), title="标题", examples=[], max_tool_rounds=3)
        printed = out.getvalue() + err.getvalue()
        self.assertEqual(len(sent), 2)
        self.assertTrue(all(request["model"] == "test-model" for request, _ in sent))
        self.assertTrue(all(key == "sk-secret-value" for _, key in sent))
        # 第二轮请求带着工具结果；命令行打印每轮请求、工具结果和回答，但不打印密钥。
        self.assertEqual(sent[1][0]["messages"][-1]["tool_call_id"], "call_1")
        self.assertIn("结果是 42。", printed)
        self.assertIn('"result": 42', printed)
        self.assertNotIn("sk-secret-value", printed)


if __name__ == "__main__":
    unittest.main()
