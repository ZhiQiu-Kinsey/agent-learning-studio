"""协议辅助层（course/protocols.py）的测试：真实启动本地 MCP stdio 服务和 A2A 服务进程。

证明：发现与调用来自真实协议交互，每条 JSON-RPC 消息都记成 lesson.mcp_message；停止运行会取消
挂起的调用并回收子进程；子进程拿不到父进程环境里的密钥；A2A 被委派方的任务状态能逐条读到。
"""
import asyncio
import json
import os
import time
import unittest
from unittest import mock

import httpx
from google.protobuf.json_format import MessageToDict
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest
from mcp import Client

from course.execution import RunContext
from course.protocols import (
    MCP_MESSAGE_EVENT,
    python_module_server,
    recording_stdio,
    run_until_cancelled,
    safe_child_environment,
    spawn_local_service,
)
from course.runner import RunCancelled

MCP_SERVER = "tests.fixtures.mcp_demo_server"
A2A_WORKER = "tests.fixtures.a2a_demo_worker"


def make_context(events, cancelled=lambda: False, locale="en"):
    return RunContext(
        lesson_id="protocol-test", exercise_id="mcp", question="", mode="offline", model="fixture-model",
        representation="sdk_standardized", inputs={}, api_key="", completion=None,
        emit_event=lambda kind, data, number: events.append((kind, data, number)), cancelled=cancelled,
        locale=locale,
    )


def process_gone(pid, wait_seconds=5.0):
    """子进程已退出并被回收：pid 不再存在。"""
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


class McpOverStdio(unittest.TestCase):
    def test_discovery_calls_and_errors_are_real_protocol_messages(self):
        events = []
        context = make_context(events)

        async def session():
            async with Client(recording_stdio(context, python_module_server(MCP_SERVER), server="notes"),
                              mode="legacy", read_timeout_seconds=20) as client:
                tools = await client.list_tools()
                found = await client.call_tool("search_notes", {"query": "loop"})
                empty = await client.call_tool("search_notes", {"query": "nothing-matches"})
                refused = await client.call_tool("search_notes", {"query": " "})
                invalid = await client.call_tool("search_notes", {"query": 3})
                info = await client.call_tool("process_info", {})
                return tools, found, empty, refused, invalid, json.loads(info.content[0].text)

        with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test-must-not-reach-children"}):
            tools, found, empty, refused, invalid, info = asyncio.run(run_until_cancelled(context, session))

        self.assertEqual([tool.name for tool in tools.tools], ["search_notes", "slow", "process_info"])
        self.assertEqual(tools.tools[0].input_schema["required"], ["query"])
        self.assertEqual((found.is_error, found.structured_content), (False, {"hits": ["agent-loop"], "count": 1}))
        # 业务无结果是正常结果，预期错误与参数校验失败是 is_error=True 的工具结果，三者分开。
        self.assertEqual((empty.is_error, empty.structured_content), (False, {"hits": [], "count": 0}))
        self.assertTrue(refused.is_error)
        self.assertIn("query must not be empty", refused.content[0].text)
        self.assertTrue(invalid.is_error)
        # 子进程只拿到 SDK 的安全变量列表，父进程里的密钥不会传过去。
        self.assertNotIn("DASHSCOPE_API_KEY", info["env_keys"])
        self.assertTrue(process_gone(info["pid"]), "关闭连接后服务进程应退出")

        messages = [data for kind, data, _ in events if kind == MCP_MESSAGE_EVENT]
        self.assertEqual({data["captured"] for data in messages}, {"sdk_session_message"})
        self.assertEqual({data["server"] for data in messages}, {"notes"})
        sent = [data["message"].get("method") for data in messages if data["direction"] == "client_to_server"]
        self.assertEqual(sent[:3], ["initialize", "notifications/initialized", "tools/list"])
        self.assertEqual(sent.count("tools/call"), 5)
        replies = [data["message"] for data in messages if data["direction"] == "server_to_client"]
        self.assertTrue(all(reply["jsonrpc"] == "2.0" for reply in replies))
        self.assertEqual(replies[1]["result"]["tools"][0]["name"], "search_notes")

    def test_stop_cancels_a_pending_call_and_reaps_the_server(self):
        events, state = [], {"cancelled": False, "pid": None}
        context = make_context(events, cancelled=lambda: state["cancelled"])

        async def session():
            async with Client(recording_stdio(context, python_module_server(MCP_SERVER), server="notes"),
                              mode="legacy") as client:
                info = await client.call_tool("process_info", {})
                state["pid"] = json.loads(info.content[0].text)["pid"]
                state["cancelled"] = True  # 用户在调用挂起时点了停止
                await client.call_tool("slow", {"seconds": 60})

        started = time.monotonic()
        with self.assertRaises(RunCancelled):
            asyncio.run(run_until_cancelled(context, session, poll_interval=0.05))
        # SDK 先关 stdin，宽限期后终止进程树；不会等满 60 秒。
        self.assertLess(time.monotonic() - started, 20)
        self.assertTrue(process_gone(state["pid"]))

    def test_only_lesson_or_test_modules_can_be_servers(self):
        for module in ("os", "lessons", "lessons/../x", "lessons.lesson_x;rm", "-c"):
            with self.assertRaises(ValueError, msg=module):
                python_module_server(module)
        params = python_module_server("lessons.lesson_demo.server", "--flag")
        self.assertEqual(params.args, ["-m", "lessons.lesson_demo.server", "--flag"])
        self.assertEqual(params.env, {})

    def test_child_environment_keeps_only_safe_names(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-x", "PATH": "/usr/bin"}):
            environment = safe_child_environment({"COURSE_FLAG": "1"})
        self.assertNotIn("OPENAI_API_KEY", environment)
        self.assertEqual(environment["COURSE_FLAG"], "1")
        self.assertEqual(environment["PATH"], "/usr/bin")


class A2aBetweenTwoProcesses(unittest.TestCase):
    def test_card_discovery_and_task_states(self):
        async def delegate(base_url):
            async with httpx.AsyncClient(timeout=10) as http:
                card = await A2ACardResolver(httpx_client=http, base_url=base_url).get_agent_card()
                client = await create_client(agent=card, client_config=ClientConfig(streaming=True, httpx_client=http))
                runs = {}
                for text in ("summarize these words for me please", "fail on purpose"):
                    states, artifacts = [], []
                    request = SendMessageRequest(message=new_text_message(text, role=Role.ROLE_USER))
                    async for item in client.send_message(request):
                        data = MessageToDict(item)
                        status = (data.get("task") or data.get("statusUpdate") or {}).get("status")
                        if status:
                            states.append(status["state"])
                        if "artifactUpdate" in data:
                            artifacts.append(data["artifactUpdate"]["artifact"]["parts"][0]["text"])
                    runs[text.split()[0]] = (states, artifacts)
                await client.close()
                return MessageToDict(card), runs

        with spawn_local_service(A2A_WORKER) as service:
            card, runs = asyncio.run(delegate(service.base_url))
            pid = service.pid
        self.assertEqual(card["skills"][0]["id"], "first-words")
        self.assertEqual(card["supportedInterfaces"][0]["url"], service.base_url)
        self.assertEqual(runs["summarize"], (["TASK_STATE_SUBMITTED", "TASK_STATE_WORKING", "TASK_STATE_COMPLETED"],
                                             ["summarize these words"]))
        self.assertEqual(runs["fail"][0][-1], "TASK_STATE_FAILED")
        self.assertTrue(process_gone(pid), "离开 with 后被委派方进程应退出")

    def test_service_that_never_reports_a_port_is_stopped(self):
        # MCP stdio 服务读到 stdin 结束就退出，不会打印端口：启动失败要报错，而不是一直等。
        with self.assertRaises(RuntimeError):
            with spawn_local_service(MCP_SERVER, startup_timeout=20):
                pass


if __name__ == "__main__":
    unittest.main()
