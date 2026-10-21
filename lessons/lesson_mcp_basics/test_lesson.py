"""Behavior tests for mcp-basics: the MCP server is a real child process and the BM25 search really runs;
only the model's decisions in the agent exercise come from the deterministic fixture.
"""
import asyncio
import json
import os
import re
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

import anyio
from mcp import Client, MCPError
from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_mcp_basics import runtime
from lessons.lesson_mcp_basics.fixtures import create_completion
from lessons.lesson_mcp_basics.locales import texts_for
from lessons.lesson_mcp_basics.locales.fixture import texts_for as fixture_texts_for
from lessons.lesson_mcp_basics.server import build_server
from server.catalog import lesson_presets, load_lessons

LOCALES = ("zh-CN", "en")
ROOT = Path(__file__).resolve().parents[2]
CJK = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")
SPEC = next(spec for spec in load_lessons(include_planned=True) if spec["id"] == "mcp-basics")


def presets(exercise_id, locale):
    exercises, defaults = lesson_presets(SPEC, locale)
    exercise = next(item for item in exercises if item["id"] == exercise_id)
    return exercise, {**defaults, **exercise.get("inputs", {})}


def run_exercise(exercise_id, locale="zh-CN", completion=None, cancelled=lambda: False, events=None, **overrides):
    exercise, inputs = presets(exercise_id, locale)
    values = validate_inputs(runtime, {**inputs, **overrides})
    events = [] if events is None else events
    if completion is None and exercise_id == "agent":
        completion = create_completion(exercise_id, values, locale)
    context = RunContext(
        lesson_id="mcp-basics", exercise_id=exercise_id, question=exercise["question"], mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="", completion=completion,
        emit_event=lambda kind, data, number: events.append((kind, data, number)), cancelled=cancelled,
        max_model_calls=SPEC["runtime"]["max_rounds"], locale=locale,
    )
    answer = execute_lesson({"runtime": SPEC["runtime"]}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def messages(events, direction=None):
    return [data["message"] for data in of(events, "lesson.mcp_message")
            if direction is None or data["direction"] == direction]


def report(events):
    return of(events, "lesson.report")[-1]


def checks(events):
    return {item["id"]: item["passed"] for item in report(events)["checks"]}


def metric(events, metric_id):
    return next(item["value"] for item in report(events)["metrics"] if item["id"] == metric_id)


def process_gone(pid, wait_seconds=8.0):
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def live_server_pids():
    """Running (not zombie) children of this test process that run the lesson's server module."""
    pids = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            status = (entry / "status").read_text()
        except OSError:
            continue
        if runtime.SERVER_MODULE in command and f"PPid:\t{os.getpid()}\n" in status and "State:\tZ" not in status:
            pids.append(int(entry.name))
    return pids


def scripted(*replies):
    """A completion that returns the given assistant messages in order and records each request body."""
    bodies = []

    def complete(body, api_key):
        bodies.append(body)
        message = replies[min(len(bodies), len(replies)) - 1]
        return {"choices": [{"message": {"role": "assistant", "content": None, **message}}]}

    complete.bodies = bodies
    return complete


def proposal(name, arguments, call_id="call_1"):
    return {"tool_calls": [{"id": call_id, "type": "function",
                            "function": {"name": name, "arguments": json.dumps(arguments)}}]}


class InputTests(unittest.TestCase):
    def test_presets_validate_in_both_languages(self):
        for locale in LOCALES:
            for exercise in ("tour", "tour-discover", "errors", "agent"):
                values = validate_inputs(runtime, presets(exercise, locale)[1])
                self.assertIn(values["task"], runtime.TASKS)

    def test_rejects_bad_inputs(self):
        _, inputs = presets("tour", "en")
        for bad in ({**inputs, "task": "delete"}, {**inputs, "protocol": "2024-11-05"}, {**inputs, "query": ""},
                    {**inputs, "miss_query": "x" * 201}, {**inputs, "server": "os"},
                    {key: value for key, value in inputs.items() if key != "query"}):
            with self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)


class ServerToolTests(unittest.TestCase):
    """The server's tools in process (no subprocess), to pin down results and business errors quickly."""

    def call(self, locale, name, arguments):
        async def go():
            async with Client(build_server(locale)) as client:
                return await client.call_tool(name, arguments)
        return asyncio.run(go())

    def test_search_returns_structured_hits_from_bm25(self):
        result = self.call("zh-CN", "search_handbook", {"query": "B2 研究证最多能借几册？", "top_k": 2})
        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["count"], 2)
        self.assertEqual(result.structured_content["hits"][0]["chunk_id"], "borrowing:7-15")
        self.assertIn("15", result.structured_content["hits"][0]["text"])

    def test_no_hits_is_a_normal_result(self):
        for locale, query in (("zh-CN", "附近有停车场吗？"), ("en", "Is there parking nearby?")):
            result = self.call(locale, "search_handbook", {"query": query})
            self.assertEqual((result.is_error, result.structured_content["count"]), (False, 0))

    def test_business_errors_come_back_as_tool_errors(self):
        t = texts_for("en")
        empty = self.call("en", "search_handbook", {"query": "  "})
        self.assertTrue(empty.is_error)
        self.assertIn(t.empty_query, empty.content[0].text)
        unknown = self.call("en", "read_chunk", {"chunk_id": "../../local_config.py"})
        self.assertTrue(unknown.is_error)
        self.assertIn("../../local_config.py", unknown.content[0].text)
        chunk = self.call("en", "read_chunk", {"chunk_id": "borrowing:7-15"})
        self.assertEqual(chunk.structured_content["trust"], "untrusted_data")

    def test_tool_definitions_follow_the_run_language(self):
        async def listed(locale):
            async with Client(build_server(locale)) as client:
                return (await client.list_tools()).tools
        for locale in LOCALES:
            tools = {tool.name: tool for tool in asyncio.run(listed(locale))}
            self.assertEqual(list(tools), ["search_handbook", "read_chunk", "service_status"])
            self.assertEqual(tools["search_handbook"].description, texts_for(locale).search_description)
            schema = tools["search_handbook"].input_schema
            self.assertEqual((schema["required"], schema["properties"]["top_k"]["maximum"]), (["query"], 5))
            self.assertTrue(tools["read_chunk"].annotations.read_only_hint)
        self.assertFalse(CJK.search(json.dumps([tool.model_dump() for tool in asyncio.run(listed("en"))])))


class TourTests(unittest.TestCase):
    def test_legacy_handshake_discovery_and_calls_are_real_messages(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_exercise("tour", locale)
                sent = [message.get("method") for message in messages(events, "client_to_server")]
                self.assertEqual(sent, ["initialize", "notifications/initialized", "tools/list",
                                        "tools/call", "tools/call", "tools/call"])
                data = of(events, "lesson.mcp_message")
                self.assertEqual({item["captured"] for item in data}, {"sdk_session_message"})
                self.assertEqual({item["server"] for item in data}, {runtime.SERVER})
                replies = messages(events, "server_to_client")
                self.assertEqual(replies[0]["result"]["protocolVersion"], "2025-11-25")
                self.assertEqual([tool["name"] for tool in replies[1]["result"]["tools"]],
                                 ["search_handbook", "read_chunk", "service_status"])
                self.assertEqual(replies[3]["result"]["structuredContent"]["count"], 0)
                self.assertFalse(replies[3]["result"]["isError"])
                self.assertTrue(all(checks(events).values()), report(events))
                self.assertEqual(metric(events, "protocol_version"), "2025-11-25")
                self.assertIn("2025-11-25", answer)
                # Nothing from the server's stderr or this machine's paths ends up in the events.
                self.assertNotIn(str(ROOT), json.dumps([data for _, data, _ in events], ensure_ascii=False))

    def test_newer_protocol_starts_with_discover_and_has_no_handshake(self):
        _, events = run_exercise("tour-discover", "en")
        sent = [message.get("method") for message in messages(events, "client_to_server")]
        self.assertEqual(sent[:2], ["server/discover", "tools/list"])
        self.assertNotIn("initialize", sent)
        first = messages(events, "client_to_server")[0]
        self.assertEqual(first["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"], "2026-07-28")
        self.assertEqual(metric(events, "protocol_version"), "2026-07-28")

    def test_english_run_has_no_chinese(self):
        for exercise in ("tour", "errors", "agent"):
            _, events = run_exercise(exercise, "en")
            self.assertFalse(CJK.search(json.dumps([data for _, data, _ in events], ensure_ascii=False)), exercise)

    def test_the_server_process_never_sees_the_api_key(self):
        secret = "sk-test-must-not-reach-the-mcp-server"
        with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": secret, "OPENAI_API_KEY": secret}):
            _, events = run_exercise("tour", "en")
        status = messages(events, "server_to_client")[-1]["result"]["structuredContent"]
        self.assertNotIn("DASHSCOPE_API_KEY", status["env_names"])
        self.assertEqual(status["secret_like_env"], [])
        self.assertTrue(checks(events)["no_secret"])
        self.assertNotIn(secret, json.dumps([data for _, data, _ in events]))
        self.assertTrue(process_gone(status["pid"]), "closing the client must end the server process")

    def test_a_query_with_hits_fails_the_no_hit_check_honestly(self):
        _, events = run_exercise("tour", "zh-CN", miss_query="R-305 有几个座位？")
        self.assertFalse(checks(events)["miss"])
        self.assertTrue(checks(events)["hit"])


class ErrorPathTests(unittest.TestCase):
    def test_tool_errors_and_protocol_errors_are_told_apart(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_exercise("errors", locale)
                self.assertEqual(checks(events), {"invalid_arguments": True, "unknown_tool": True,
                                                  "business_error": True, "server_crash": True, "after_crash": True})
                replies = [message for message in messages(events, "server_to_client") if "result" in message]
                tool_errors = [reply["result"] for reply in replies if reply["result"].get("isError")]
                self.assertEqual(len(tool_errors), 3)
                self.assertIn("validation error", tool_errors[0]["content"][0]["text"])
                self.assertEqual(tool_errors[1]["content"][0]["text"], "Unknown tool: delete_handbook")
                self.assertIn("../../local_config.py", tool_errors[2]["content"][0]["text"])
                # Two connections; the crashed one sent a tools/call that never got a reply.
                sent = [message.get("method") for message in messages(events, "client_to_server")]
                self.assertEqual(sent.count("initialize"), 2)
                last_call = [m for m in messages(events, "client_to_server") if m.get("method") == "tools/call"][-1]
                self.assertEqual(last_call["params"]["name"], "search_handbook")
                rows = report(events)["table"]["rows"]
                self.assertEqual([row[2] for row in rows[-2:]], [t.layers["protocol_error"]] * 2)
                self.assertIn("-32000", rows[-1][3])
                self.assertIn(runtime.CRASH_FAULT, metric(events, "fault"))
                self.assertEqual(answer, t.errors_answer.format(tool_errors=3, protocol_errors=2))

    def test_classify_reads_the_layer_from_where_the_failure_shows_up(self):
        error = MCPError(-32000, "Connection closed")
        self.assertEqual(runtime.classify(None, error), "protocol_error")
        result = type("Result", (), {"is_error": True, "structured_content": None})()
        self.assertEqual(runtime.classify(result, None), "tool_error")
        result.is_error, result.structured_content = False, {"count": 0}
        self.assertEqual(runtime.classify(result, None), "no_hits")


class AgentTests(unittest.TestCase):
    def test_model_picks_from_discovered_tools_and_calls_run_over_mcp(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_exercise("agent", locale)
                order = [kind if kind != "lesson.mcp_message" else data["message"].get("method", "reply")
                         for kind, data, _ in events]
                self.assertEqual(order[:5], ["initialize", "reply", "notifications/initialized", "tools/list", "reply"])
                self.assertEqual(order[5:12], ["request", "response", "tool_call", "tools/call", "reply",
                                               "tool_result", "request"])
                listed = messages(events, "server_to_client")[1]["result"]["tools"]
                body = of(events, "request")[0]["body"]
                # The model gets exactly the MCP definitions of the offered tools, converted 1:1.
                self.assertEqual(body["tools"], [{"type": "function", "function": {
                    "name": tool["name"], "description": tool["description"], "parameters": tool["inputSchema"]}}
                    for tool in listed if tool["name"] in runtime.MODEL_TOOLS])
                self.assertNotIn("service_status", json.dumps(body["tools"]))
                call, result = of(events, "tool_call")[0], of(events, "tool_result")[0]
                self.assertEqual(result["tool_call_id"], call["id"])
                mcp_call = next(m for m in messages(events, "client_to_server") if m.get("method") == "tools/call")
                self.assertEqual(mcp_call["params"]["arguments"], json.loads(call["function"]["arguments"]))
                self.assertTrue(result["result"]["ok"])
                self.assertEqual(result["result"]["result"]["hits"][0]["chunk_id"], "borrowing:7-15")
                self.assertIn("borrowing:7-15", answer)
                self.assertTrue(answer.startswith("[Offline script answer]" if locale == "en" else "【离线脚本回答】"))
                self.assertTrue(all(checks(events).values()), report(events))
                self.assertEqual((metric(events, "model_calls"), metric(events, "mcp_calls")), (2, 1))

    def test_fixture_answer_quotes_the_real_tool_result(self):
        fixture = fixture_texts_for("en")
        answer, _ = run_exercise("agent", "en")
        self.assertIn(fixture.answer.split("{")[0].strip(), answer)

    def test_arguments_outside_the_schema_are_refused_by_the_server(self):
        completion = scripted(proposal("search_handbook", {"query": "B2", "top_k": 50}), {"content": "done"})
        answer, events = run_exercise("agent", "en", completion=completion)
        result = of(events, "tool_result")[0]["result"]
        self.assertEqual((result["ok"], result["error_type"]), (False, "McpToolError"))
        self.assertIn("less than or equal to 5", result["error"])
        self.assertEqual([m.get("method") for m in messages(events, "client_to_server")].count("tools/call"), 1)
        # The refusal went back to the model as a tool message in the next request.
        tool_message = completion.bodies[1]["messages"][-1]
        self.assertEqual((tool_message["role"], json.loads(tool_message["content"])["ok"]), ("tool", False))
        self.assertEqual(answer, "done")

    def test_a_tool_the_runner_did_not_offer_never_reaches_the_server(self):
        completion = scripted(proposal("service_status", {}), {"content": "done"})
        _, events = run_exercise("agent", "en", completion=completion)
        result = of(events, "tool_result")[0]["result"]
        self.assertEqual((result["ok"], result["error_type"]), (False, "ValueError"))
        self.assertNotIn("tools/call", [m.get("method") for m in messages(events, "client_to_server")])
        self.assertFalse(checks(events)["calls_over_mcp"])

    def test_the_runner_stops_at_the_round_limit(self):
        completion = scripted(proposal("search_handbook", {"query": "B2"}))
        answer, events = run_exercise("agent", "zh-CN", completion=completion)
        t = texts_for("zh-CN")
        self.assertEqual(answer, t.stop_answers["rounds"])
        self.assertEqual(len(of(events, "request")), runtime.MAX_ROUNDS)
        self.assertEqual(metric(events, "stop_reason"), t.stop_reasons["rounds"])

    def test_a_dead_server_stops_the_loop(self):
        original = runtime.connect
        crashing = lambda context, protocol, *args: original(context, protocol, "--fault", runtime.CRASH_FAULT)
        with mock.patch.object(runtime, "connect", crashing):
            answer, events = run_exercise("agent", "en")
        t = texts_for("en")
        result = of(events, "tool_result")[0]["result"]
        self.assertEqual((result["ok"], result["error_type"]), (False, "McpConnectionError"))
        self.assertIn("-32000", result["error"])
        self.assertEqual(answer, t.stop_answers["connection_lost"])
        self.assertEqual(len(of(events, "request")), 1)

    def test_bridge_turns_mcp_errors_into_structured_errors(self):
        class Dead:
            async def call_tool(self, name, arguments):
                raise MCPError(-32000, "Connection closed")

        async def go():
            return await anyio.to_thread.run_sync(lambda: runtime.call_over_mcp(Dead(), [], "search_handbook", query="x"))
        with self.assertRaises(runtime.McpConnectionError):
            anyio.run(go)

    def test_agent_needs_a_model_and_raises_the_original_error(self):
        _, inputs = presets("tour", "en")
        context = RunContext(lesson_id="mcp-basics", exercise_id="tour", question="", mode="offline", model="m",
                             representation="sdk_standardized", inputs=validate_inputs(runtime, {**inputs, "task": "agent"}),
                             api_key="", completion=None, emit_event=lambda *args: None, locale="en")
        with self.assertRaises(ValueError) as caught:
            execute_lesson({"runtime": SPEC["runtime"]}, runtime, context)
        self.assertEqual(str(caught.exception), texts_for("en").agent_needs_model)


class StopTests(unittest.TestCase):
    def test_stop_after_a_call_reaps_the_server(self):
        events = []

        def status_arrived():
            # The learner presses stop right after the service_status result arrived.
            return any("pid" in (data["message"].get("result", {}).get("structuredContent") or {})
                       for kind, data, _ in events
                       if kind == "lesson.mcp_message" and data["direction"] == "server_to_client")

        with self.assertRaises(RunCancelled):
            run_exercise("tour", "en", cancelled=status_arrived, events=events)
        pid = messages(events, "server_to_client")[-1]["result"]["structuredContent"]["pid"]
        self.assertTrue(process_gone(pid))
        self.assertEqual(of(events, "lesson.report"), [])

    @unittest.skipUnless(sys.platform.startswith("linux"), "reads /proc")
    def test_stop_during_a_model_call_reaps_the_server(self):
        state = {"stopped": False}
        inner = create_completion("agent", None, "en")

        def completion(body, api_key):
            state["stopped"] = True  # stop pressed while the model request is in flight
            return inner(body, api_key)

        with self.assertRaises(RunCancelled):
            run_exercise("agent", "en", completion=completion, cancelled=lambda: state["stopped"])
        deadline = time.monotonic() + 8
        while live_server_pids() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(live_server_pids(), [])


if __name__ == "__main__":
    unittest.main()
