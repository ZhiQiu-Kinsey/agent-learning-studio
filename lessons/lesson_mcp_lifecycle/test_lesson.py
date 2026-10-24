"""mcp-lifecycle 的行为测试：两个真实的 MCP stdio 服务进程、真实的断连、重启故障与进程回收。

只有模型的选择来自夹具（fixtures.py）；握手、发现、调用、杀进程、重连和关闭都是真实发生的。
"""
import asyncio
import json
import os
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from pydantic import ValidationError

from course.execution import RunContext
from course.runner import RunCancelled
from lessons.lesson_mcp_lifecycle import fixtures, runtime
from lessons.lesson_mcp_lifecycle.processes import pid_alive
from server.offline import offline_marker

SPEC = json.loads((Path(__file__).parent / "lesson.json").read_text(encoding="utf-8"))
CJK = re.compile(r"[一-鿿　-〿＀-￯]")
SERVER_MODULES = ("lessons.lesson_mcp_lifecycle.catalog_server", "lessons.lesson_mcp_lifecycle.loans_server")


def lesson_children() -> list[int]:
    """本进程下仍在运行的本课服务进程（只在有 /proc 的系统上能查）。"""
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
            cmdline = (entry / "cmdline").read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        fields = stat.rsplit(")", 1)[1].split()
        state, parent = fields[0], int(fields[1])
        if parent == os.getpid() and state != "Z" and any(module in cmdline for module in SERVER_MODULES):
            found.append(int(entry.name))
    return found


def run_exercise(exercise_id, locale="zh-CN", overrides=None, cancelled=lambda events: False, completion=True):
    exercise = next(item for item in SPEC["exercises"] if item["id"] == exercise_id)
    defaults = {key: (value[locale] if isinstance(value, dict) else value) for key, value in SPEC["input_defaults"].items()}
    inputs = runtime.INPUT_MODEL(**{**defaults, **exercise["inputs"], **(overrides or {})}).model_dump()
    events = []
    uses_model = exercise.get("requires_model", True) and completion
    context = RunContext(
        lesson_id="mcp-lifecycle", exercise_id=exercise_id, question=exercise["question"][locale], mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=inputs, api_key="",
        completion=fixtures.create_completion(exercise_id, inputs, locale) if uses_model else None,
        emit_event=lambda kind, data, number: events.append((kind, data, number)),
        cancelled=lambda: cancelled(events), max_model_calls=SPEC["runtime"]["max_rounds"], locale=locale)
    answer = asyncio.run(runtime.run(context))
    return answer, events


def of_kind(events, kind):
    return [data for event_kind, data, _ in events if event_kind == kind]


def report(events):
    reports = of_kind(events, "lesson.report")
    return {check["id"]: check for check in reports[-1]["checks"]}, {m["id"]: m["value"] for m in reports[-1]["metrics"]}


def results_by_tool(events, name):
    return [data["result"] for data in of_kind(events, "tool_result") if data["name"] == name]


def sent_methods(events, server):
    return [data["message"].get("method") for data in of_kind(events, "lesson.mcp_message")
            if data["server"] == server and data["direction"] == "client_to_server"]


class LifecycleTests(unittest.TestCase):
    def tearDown(self):
        if Path("/proc").is_dir():
            self.assertEqual(lesson_children(), [], "运行结束后不能留下本课的服务进程")

    def test_two_handshakes_namespaces_and_permissions(self):
        answer, events = run_exercise("lifecycle")
        checks, metrics = report(events)
        self.assertTrue(all(check["passed"] for check in checks.values()), checks)
        # 每个服务一条连接，legacy 模式下第一条消息都是 initialize，随后是 initialized 和 tools/list。
        for server in ("catalog", "loans"):
            self.assertEqual(sent_methods(events, server)[:3], ["initialize", "notifications/initialized", "tools/list"])
        connected = [data for data in of_kind(events, "lesson.service_state") if data["state"] == "connected"]
        self.assertEqual([(data["service"], data["protocol_version"]) for data in connected],
                         [("catalog", "2025-11-25"), ("loans", "2025-11-25")])
        self.assertEqual(connected[1]["capabilities"]["tools"], {"listChanged": False})
        # 两个服务都有 search：宿主各给一个带前缀的名字；裸名、未登记、写操作都被拒绝。
        self.assertTrue(results_by_tool(events, "catalog__search")[0]["ok"])
        self.assertTrue(results_by_tool(events, "loans__search")[0]["ok"])
        for name in ("search", "loans__purge_loans", "loans__register_loan"):
            self.assertFalse(results_by_tool(events, name)[0]["ok"], name)
        # 被拒绝的调用一条 tools/call 也没有发给服务端。
        calls = [data["message"]["params"]["name"] for data in of_kind(events, "lesson.mcp_message")
                 if data["message"].get("method") == "tools/call"]
        self.assertNotIn("purge_loans", calls)
        self.assertNotIn("register_loan", calls)
        self.assertEqual(metrics["routes"], 4)
        self.assertEqual(metrics["processes_left"], 0)
        self.assertIn("0", answer)

    def test_allowing_writes_lets_the_registered_write_through(self):
        _, events = run_exercise("lifecycle", overrides={"allow_writes": True})
        checks, _ = report(events)
        self.assertTrue(checks["write_gate"]["passed"])
        written = results_by_tool(events, "loans__register_loan")[0]
        self.assertTrue(written["ok"])
        self.assertEqual(written["result"]["loan_id"], "L-0001")
        # 写入放开了，未登记的危险写操作仍然被拒绝。
        self.assertFalse(results_by_tool(events, "loans__purge_loans")[0]["ok"])

    def test_server_processes_get_no_secrets(self):
        with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test-never-in-a-child", "OPENAI_API_KEY": "sk-x"}):
            _, events = run_exercise("lifecycle")
        for data in of_kind(events, "lesson.service_state"):
            if data["state"] == "connected":
                self.assertEqual(data["secret_like_env"], [])
        self.assertNotIn("sk-test-never-in-a-child", json.dumps([data for _, data, _ in events], ensure_ascii=False))


class CrashTests(unittest.TestCase):
    def tearDown(self):
        if Path("/proc").is_dir():
            self.assertEqual(lesson_children(), [])

    def test_crash_reconnect_state_loss_and_no_replay(self):
        answer, events = run_exercise("crash-recover")
        checks, metrics = report(events)
        self.assertTrue(all(check.get("passed", True) for check in checks.values()), checks)
        writes = results_by_tool(events, "loans__register_loan")
        self.assertTrue(writes[0]["ok"])
        # 进程被杀后的写入：MCPError -32000，记成连接失败，不是成功。
        self.assertEqual(writes[1]["error_type"], "ConnectionLost")
        self.assertIn("-32000", writes[1]["error"])
        states = [(data["state"], data.get("attempt"), data.get("error_code")) for data in of_kind(events, "lesson.service_state")
                  if data["service"] == "loans"]
        self.assertEqual(states, [("connected", 0, None), ("stopped", None, None), ("lost", None, -32000),
                                  ("reconnecting", 1, None), ("failed", 1, -32000), ("reconnecting", 2, None),
                                  ("connected", 2, None)])
        # 新进程的内存是空的：确认过的借阅查不到了。
        after = results_by_tool(events, "loans__search")[-1]
        self.assertEqual(after["result"]["count"], 0)
        # 恢复后两笔写入都没有重发：一笔已确认，一笔结果未知。
        self.assertEqual([result["error_type"] for result in writes[2:]], ["WriteNotRepeated", "WriteNotRepeated"])
        loans_calls = [data["message"]["params"]["name"] for data in of_kind(events, "lesson.mcp_message")
                       if data["server"] == "loans" and data["message"].get("method") == "tools/call"]
        self.assertEqual(loans_calls.count("register_loan"), 2, "只有断连前那笔和断连时那笔真正发出")
        self.assertEqual(metrics["reconnect_attempts"], 2)
        pids = [data["pid"] for data in of_kind(events, "lesson.service_state") if data["state"] == "connected"]
        self.assertEqual(len(set(pids)), 3)
        self.assertFalse(any(pid_alive(pid) for pid in pids))
        self.assertTrue(answer)

    def test_timeout_then_changed_definition_is_held_back(self):
        _, events = run_exercise("crash-changed")
        failed = [data for data in of_kind(events, "lesson.service_state") if data["state"] == "failed"]
        self.assertEqual([data["error_code"] for data in failed], [-32001])
        reconnected = [data for data in of_kind(events, "lesson.service_state") if "recheck" in data][0]
        self.assertEqual(reconnected["recheck"]["changed"], ["register_loan"])
        self.assertEqual(reconnected["recheck"]["added"], ["renew_loan"])
        self.assertEqual(reconnected["recheck"]["quarantined"], ["register_loan"])
        resumed = results_by_tool(events, "loans__register_loan")[2:]
        self.assertEqual({result["error_type"] for result in resumed}, {"ToolChanged"})
        checks, _ = report(events)
        self.assertTrue(checks["no_replay"]["passed"])
        self.assertTrue(checks["reaped"]["passed"])

    def test_reconnects_stop_at_the_limit_and_the_service_degrades(self):
        _, events = run_exercise("crash-giveup")
        loans = [data for data in of_kind(events, "lesson.service_state") if data["service"] == "loans"]
        self.assertEqual([data["state"] for data in loans][-1], "gave_up")
        self.assertEqual(sum(data["state"] == "reconnecting" for data in loans), 2)
        # 放弃之后，借阅服务的工具一个也不发出；状态检查没有执行，所以不给 passed。
        after = results_by_tool(events, "loans__search")[-1]
        self.assertEqual(after["error_type"], "ServiceUnavailable")
        checks, metrics = report(events)
        self.assertNotIn("passed", checks["state_lost"])
        self.assertTrue(checks["bounded"]["passed"])
        self.assertEqual(metrics["reconnect_attempts"], 2)

    def test_zero_reconnects_gives_up_at_once(self):
        _, events = run_exercise("crash-recover", overrides={"max_reconnects": 0})
        states = [data["state"] for data in of_kind(events, "lesson.service_state") if data["service"] == "loans"]
        self.assertNotIn("reconnecting", states)
        self.assertEqual(states[-1], "gave_up")


class AgentTests(unittest.TestCase):
    def tearDown(self):
        if Path("/proc").is_dir():
            self.assertEqual(lesson_children(), [])

    def test_model_works_through_two_services_and_a_disconnect(self):
        answer, events = run_exercise("agent")
        requests = of_kind(events, "request")
        self.assertEqual(len(requests), 4)
        offered = [tool["function"]["name"] for tool in requests[0]["body"]["tools"]]
        self.assertEqual(offered, ["catalog__search", "catalog__get_book", "loans__search", "loans__register_loan"])
        # 模型提议用带前缀的名字；工具经 MCP 执行，结果事件与调用 id 配对。
        calls = of_kind(events, "tool_call")
        results = of_kind(events, "tool_result")
        self.assertEqual([call["id"] for call in calls], [result["tool_call_id"] for result in results])
        self.assertTrue(results[1]["result"]["ok"])
        self.assertEqual(results[2]["result"]["error_type"], "ConnectionLost")
        states = [data["state"] for data in of_kind(events, "lesson.service_state") if data["service"] == "loans"]
        self.assertEqual(states[-2:], ["reconnecting", "connected"])
        checks, metrics = report(events)
        self.assertTrue(checks["lost_not_success"]["passed"])
        self.assertNotIn("passed", checks["writes_recorded"])
        self.assertEqual(metrics["model_calls"], 4)
        self.assertTrue(answer.startswith(offline_marker("zh-CN")))

    def test_writes_off_hides_register_loan_from_the_model(self):
        _, events = run_exercise("agent", overrides={"allow_writes": False})
        offered = [tool["function"]["name"] for tool in of_kind(events, "request")[0]["body"]["tools"]]
        self.assertNotIn("loans__register_loan", offered)
        # 夹具照样提议写入：平台按白名单拒绝，服务进程没被杀，也就没有重连。
        refused = results_by_tool(events, "loans__register_loan")[0]
        self.assertFalse(refused["ok"])
        self.assertFalse(any(data["state"] == "stopped" for data in of_kind(events, "lesson.service_state")))

    def test_agent_needs_a_model(self):
        with self.assertRaises(ValueError):
            run_exercise("agent", completion=False)


class EnglishRunTests(unittest.TestCase):
    def test_english_runs_carry_no_chinese(self):
        for exercise_id in ("lifecycle", "crash-recover", "crash-giveup", "agent"):
            with self.subTest(exercise=exercise_id):
                answer, events = run_exercise(exercise_id, locale="en")
                text = json.dumps([answer, [data for _, data, _ in events]], ensure_ascii=False)
                self.assertIsNone(CJK.search(text), CJK.search(text) and text[max(0, CJK.search(text).start() - 80):][:160])


class StopTests(unittest.TestCase):
    def test_stop_during_a_run_reaps_every_server(self):
        # 第二个服务连上之后用户点停止：运行以 RunCancelled 结束，两个进程都被回收。
        def stop_after_second_connection(events):
            return sum(kind == "lesson.service_state" for kind, _, _ in events) >= 2

        with self.assertRaises(RunCancelled):
            run_exercise("crash-recover", cancelled=stop_after_second_connection)
        if Path("/proc").is_dir():
            self.assertEqual(lesson_children(), [])


class HostUnitTests(unittest.TestCase):
    def test_qualified_names_fit_the_function_name_alphabet(self):
        self.assertEqual(runtime.qualified_name("loans", "search"), "loans__search")
        for service, tool in (("docs.one", "get"), ("loans", "find books"), ("x" * 40, "y" * 30)):
            with self.assertRaises(ValueError):
                runtime.qualified_name(service, tool)

    def test_two_services_cannot_map_to_one_name(self):
        tool = SimpleNamespace(name="search")
        spec = runtime.ServiceSpec("loans", "lessons.x", "x", {"search": "read"}, ("search", {}))
        connections = [SimpleNamespace(spec=spec, tools=[tool]), SimpleNamespace(spec=spec, tools=[tool])]
        with self.assertRaises(ValueError):
            runtime.build_routes(connections)

    def test_fingerprint_changes_with_schema_only(self):
        base = SimpleNamespace(name="register_loan", description="d", input_schema={"required": ["book_id"]})
        same = SimpleNamespace(name="register_loan", description="d", input_schema={"required": ["book_id"]})
        changed = SimpleNamespace(name="register_loan", description="d", input_schema={"required": ["book_id", "due_days"]})
        self.assertEqual(runtime.fingerprint(base), runtime.fingerprint(same))
        self.assertNotEqual(runtime.fingerprint(base), runtime.fingerprint(changed))


class InputTests(unittest.TestCase):
    def test_inputs_are_validated(self):
        base = {"query": "MCP"}
        self.assertEqual(runtime.INPUT_MODEL(**base).task, "lifecycle")
        for bad in ({"task": "reboot"}, {"failing_restarts": 4}, {"max_reconnects": -1}, {"query": ""},
                    {"restart_variant": "v3"}, {"member_id": "M-99"}, {"unknown": 1}):
            with self.assertRaises(ValidationError, msg=bad):
                runtime.INPUT_MODEL(**{**base, **bad})
        with self.assertRaises(ValidationError):
            runtime.INPUT_MODEL()

    def test_servers_start_only_from_lesson_modules(self):
        self.assertTrue(all(spec.module.startswith("lessons.lesson_mcp_lifecycle.") for spec in runtime.SERVICES))
        self.assertEqual(sys.modules[runtime.__name__].SERVICES[0].service, "catalog")


if __name__ == "__main__":
    unittest.main()
