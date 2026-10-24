"""MCP basics: discover, call and fail over a real MCP stdio connection, then let a model choose among the tools it found.

The server (server.py) is the handbook search of the retrieval lessons, run as its own process with the official
SDK (mcp 2.x). The protocol finds tools and carries calls; the runner decides which tools the model sees, executes
each proposal through the MCP client and decides when to stop. Every JSON-RPC message is recorded by
course.protocols.recording_stdio as a lesson.mcp_message event (the SDK message dumped with protocol field names).
"""
import json
from functools import partial
from typing import Literal

import anyio
from mcp import Client, MCPError
from mcp.types import Implementation
from pydantic import Field

from course.execution import LessonInputs, RunContext
from course.protocols import python_module_server, recording_stdio, run_until_cancelled
from lessons.lesson_mcp_basics.locales import Texts, texts_for

SERVER_MODULE = "lessons.lesson_mcp_basics.server"
SERVER = "handbook"
CRASH_FAULT = "exit-on-search"
CLIENT_INFO = Implementation(name="mcp-basics-runner", version="1.0")
# The host decides which discovered tools reach the model: service_status is for the runner only.
MODEL_TOOLS = ("search_handbook", "read_chunk")
READ_TIMEOUT_SECONDS = 20
MAX_ROUNDS = 3
EXCERPT_CHARS = 160


class Inputs(LessonInputs):
    task: Literal["tour", "errors", "agent"] = "tour"
    # legacy: the 2025-11-25 initialize handshake; auto: the SDK negotiates 2026-07-28 with server/discover.
    protocol: Literal["legacy", "auto"] = "legacy"
    # No defaults: lesson.json supplies both queries in the run's language.
    query: str = Field(min_length=1, max_length=200)
    miss_query: str = Field(min_length=1, max_length=200)


INPUT_MODEL = Inputs


class McpToolError(ValueError):
    """The server answered the call with isError=true: the protocol worked, the tool refused or failed."""


class McpConnectionError(ValueError):
    """The call got no answer at all (MCPError): the connection or the server process is gone."""


def connect(context: RunContext, protocol: str, *server_args: str) -> Client:
    # python -m from the repository root, with the SDK's safe environment: no API key reaches the child.
    params = python_module_server(SERVER_MODULE, "--locale", context.locale, *server_args)
    return Client(recording_stdio(context, params, server=SERVER), mode=protocol, client_info=CLIENT_INFO,
                  read_timeout_seconds=READ_TIMEOUT_SECONDS, cache=None)  # no cache: every list is a real request


def text_of(result) -> str:
    return "\n".join(block.text for block in result.content if getattr(block, "type", None) == "text")


async def attempt(client: Client, name: str, arguments: dict):
    """One tools/call; returns (result, None) when the server answered, (None, MCPError) when nothing came back."""
    try:
        return await client.call_tool(name, arguments), None
    except MCPError as error:
        return None, error


def classify(result, error) -> str:
    """Which layer answered: two layers of failure are told apart by where they show up, not by their text."""
    if error is not None:
        return "protocol_error"  # raised by the client: no JSON-RPC result arrived
    if result.is_error:
        return "tool_error"      # a result arrived, flagged isError=true
    count = (result.structured_content or {}).get("count")
    return "no_hits" if count == 0 else "result"


def to_model_tool(tool) -> dict:
    """An MCP tool definition becomes an OpenAI-compatible function tool: same name, description and inputSchema."""
    return {"type": "function",
            "function": {"name": tool.name, "description": tool.description or "", "parameters": tool.input_schema}}


def call_over_mcp(client: Client, ledger: list, name: str, /, **arguments):
    """Runs in execute_proposal's worker thread; the tools/call itself goes back to the event loop."""
    ledger.append(name)
    try:
        result = anyio.from_thread.run(client.call_tool, name, arguments)
    except MCPError as error:
        raise McpConnectionError(f"MCPError {error.error.code}: {error.error.message}") from error
    if result.is_error:
        raise McpToolError(text_of(result))
    return result.structured_content if result.structured_content is not None else text_of(result)


async def run_tour(context: RunContext, t: Texts, inputs: dict) -> str:
    # 1. Connect: the SDK starts the server process and negotiates a protocol version.
    async with connect(context, inputs["protocol"]) as client:
        version = client.protocol_version
        # 2. Discover: tools/list returns each tool's name, description and inputSchema.
        listed = await client.list_tools()
        # 3. Call: the same tool twice, then the status tool that shows what reached the process.
        found = await client.call_tool("search_handbook", {"query": inputs["query"], "top_k": 3})
        missed = await client.call_tool("search_handbook", {"query": inputs["miss_query"], "top_k": 3})
        status = await client.call_tool("service_status", {})
    # 4. Leaving the block closed stdin and reaped the server process.
    context.emit("lesson.report", _tour_report(t, inputs["protocol"], version, listed.tools, found, missed, status))
    return t.tour_answer.format(version=version, tools=len(listed.tools),
                                hits=found.structured_content["count"], misses=missed.structured_content["count"])


async def run_errors(context: RunContext, t: Texts, inputs: dict) -> str:
    rows = []
    async with connect(context, inputs["protocol"]) as client:
        await client.list_tools()
        # 1. Arguments outside the inputSchema: top_k allows 1 to 5.
        rows.append(("invalid_arguments", "search_handbook", {"query": inputs["query"], "top_k": 50},
                     *await attempt(client, "search_handbook", {"query": inputs["query"], "top_k": 50})))
        # 2. A name the server never listed.
        rows.append(("unknown_tool", "delete_handbook", {}, *await attempt(client, "delete_handbook", {})))
        # 3. A business rule of the tool itself: only ids in the server's own index resolve.
        bad_id = {"chunk_id": "../../local_config.py"}
        rows.append(("business_error", "read_chunk", bad_id, *await attempt(client, "read_chunk", bad_id)))
    # 4. Fault injection: a second server started with --fault exits in the middle of a search.
    async with connect(context, inputs["protocol"], "--fault", CRASH_FAULT) as client:
        await client.list_tools()
        crash_args = {"query": inputs["query"]}
        rows.append(("server_crash", "search_handbook", crash_args,
                     *await attempt(client, "search_handbook", crash_args)))
        # 5. After the crash the same client gets no answer to anything.
        try:
            await client.list_tools()
            rows.append(("after_crash", "tools/list", {}, None, None))
        except MCPError as error:
            rows.append(("after_crash", "tools/list", {}, None, error))
    context.emit("lesson.report", _errors_report(t, rows))
    layers = [classify(result, error) if result or error else "result" for *_, result, error in rows]
    return t.errors_answer.format(tool_errors=layers.count("tool_error"), protocol_errors=layers.count("protocol_error"))


async def run_agent_task(context: RunContext, t: Texts, inputs: dict) -> str:
    if context.completion is None:
        raise ValueError(t.agent_needs_model)
    async with connect(context, inputs["protocol"]) as client:
        # 1. Discovery is the protocol's job; choosing what the model may see is the host's.
        listed = await client.list_tools()
        offered = [tool for tool in listed.tools if tool.name in MODEL_TOOLS]
        tools = [to_model_tool(tool) for tool in offered]
        ledger: list[str] = []
        bridge = {tool.name: partial(call_over_mcp, client, ledger, tool.name) for tool in offered}
        messages = [{"role": "system", "content": t.agent_system}, {"role": "user", "content": context.question}]
        answer, stop, proposals = None, "rounds", []
        for round_number in range(1, MAX_ROUNDS + 1):
            # 2. The model decides: which tool, which arguments, or no call at all.
            body = {"messages": messages, "tools": tools, "tool_choice": "auto"}
            response = await anyio.to_thread.run_sync(partial(context.complete, body, round_number))
            message = response["choices"][0]["message"]
            calls = message.get("tool_calls") or []
            if not calls:
                answer, stop = message.get("content") or "", "answered"
                break
            messages.append(message)
            # 3. Each proposal runs through the platform's checks, then over MCP; the result goes back as a tool message.
            for call in calls:
                result = await anyio.to_thread.run_sync(context.execute_proposal, call, bridge)
                proposals.append(call["function"]["name"])
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": json.dumps(result, ensure_ascii=False)})
                if result.get("error_type") == McpConnectionError.__name__:
                    stop = "connection_lost"
            # 4. The program, not the protocol, stops: a dead connection ends the loop.
            if stop == "connection_lost":
                break
    context.emit("lesson.report", _agent_report(t, listed.tools, offered, proposals, ledger, stop, round_number))
    return answer if stop == "answered" else t.stop_answers[stop]


TASKS = {"tour": run_tour, "errors": run_errors, "agent": run_agent_task}


async def run(context: RunContext):
    t = texts_for(context.locale)
    task = TASKS[context.inputs["task"]]

    async def guarded():
        # run_until_cancelled runs this in a task group, which wraps any exception in an ExceptionGroup;
        # hand it back as a value and re-raise it below, so the run records the original error.
        try:
            return await task(context, t, context.inputs), None
        except Exception as error:
            return None, error

    answer, error = await run_until_cancelled(context, guarded)
    if error is not None:
        raise error
    return answer


def _excerpt(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= EXCERPT_CHARS else text[:EXCERPT_CHARS] + "…"


def _tour_report(t: Texts, protocol: str, version: str, tools, found, missed, status) -> dict:
    first_method = "initialize" if protocol == "legacy" else "server/discover"
    hits = found.structured_content["hits"]
    env = status.structured_content
    return {
        "title": t.report_titles["tour"],
        "summary": t.tour_summary.format(version=version, method=first_method, tools=len(tools)),
        "checks": [
            {"id": "handshake", "label": t.check_handshake, "passed": bool(version),
             "detail": t.detail_handshake.format(method=first_method, version=version)},
            {"id": "discovered", "label": t.check_discovered, "passed": bool(tools),
             "detail": ", ".join(tool.name for tool in tools)},
            {"id": "hit", "label": t.check_hit, "passed": classify(found, None) == "result",
             "detail": t.detail_hit.format(error=str(found.is_error).lower(), count=len(hits),
                                           first=hits[0]["chunk_id"] if hits else "-")},
            {"id": "miss", "label": t.check_miss, "passed": classify(missed, None) == "no_hits",
             "detail": t.detail_miss.format(error=str(missed.is_error).lower(), count=missed.structured_content["count"])},
            {"id": "no_secret", "label": t.check_no_secret, "passed": not env["secret_like_env"],
             "detail": t.detail_env.format(names=", ".join(env["env_names"]))},
        ],
        "metrics": [
            {"id": "protocol_version", "label": t.label_protocol_version, "value": version},
            {"id": "tool_count", "label": t.label_tool_count, "value": len(tools)},
            {"id": "server_pid", "label": t.label_server_pid, "value": env["pid"]},
        ],
        "table": {"columns": list(t.columns_tools),
                  "rows": [[tool.name, ", ".join(tool.input_schema.get("required", [])) or "-",
                            ", ".join(tool.input_schema.get("properties", {})) or "-", tool.description or ""]
                           for tool in tools]},
    }


EXPECTED_LAYER = {"invalid_arguments": "tool_error", "unknown_tool": "tool_error", "business_error": "tool_error",
                  "server_crash": "protocol_error", "after_crash": "protocol_error"}


def _errors_report(t: Texts, rows: list) -> dict:
    checks, table = [], []
    for path, target, arguments, result, error in rows:
        layer = classify(result, error) if result or error else "result"
        seen = (f"MCPError {error.error.code}: {error.error.message}" if error is not None
                else f"isError={str(result.is_error).lower()}: {_excerpt(text_of(result))}")
        checks.append({"id": path, "label": t.paths[path], "passed": layer == EXPECTED_LAYER[path],
                       "detail": t.detail_layer.format(expected=t.layers[EXPECTED_LAYER[path]], seen=t.layers[layer])})
        table.append([t.paths[path], f"{target} {json.dumps(arguments, ensure_ascii=False)}", t.layers[layer], seen])
    return {"title": t.report_titles["errors"], "summary": t.errors_summary.format(fault=CRASH_FAULT),
            "checks": checks,
            "metrics": [{"id": "fault", "label": t.label_fault, "value": t.fault_value.format(fault=CRASH_FAULT)}],
            "table": {"columns": list(t.columns_errors), "rows": table}}


def _agent_report(t: Texts, tools, offered, proposals: list, ledger: list, stop: str, rounds: int) -> dict:
    offered_names = [tool.name for tool in offered]
    hidden = [tool.name for tool in tools if tool.name not in offered_names]
    return {
        "title": t.report_titles["agent"],
        "summary": t.agent_summary.format(found=len(tools), offered=len(offered), proposals=len(proposals),
                                          calls=len(ledger), stop=t.stop_reasons[stop]),
        "checks": [
            {"id": "host_filter", "label": t.check_host_filter, "passed": "service_status" in hidden,
             "detail": t.detail_host_filter.format(offered=", ".join(offered_names) or "-",
                                                   hidden=", ".join(hidden) or "-")},
            {"id": "calls_over_mcp", "label": t.check_calls_over_mcp, "passed": len(proposals) == len(ledger),
             "detail": t.detail_calls_over_mcp.format(proposals=len(proposals), calls=len(ledger))},
        ],
        "metrics": [
            {"id": "model_calls", "label": t.label_model_calls, "value": rounds},
            {"id": "mcp_calls", "label": t.label_mcp_calls, "value": len(ledger)},
            {"id": "stop_reason", "label": t.label_stop_reason, "value": t.stop_reasons[stop]},
        ],
        "table": {"columns": list(t.columns_duties),
                  "rows": [[t.duties[key], t.owners[key], value] for key, value in (
                      ("discover", ", ".join(tool.name for tool in tools)),
                      ("expose", ", ".join(offered_names)),
                      ("choose", ", ".join(proposals) or t.value_none),
                      ("transport", str(len(ledger))),
                      ("stop", t.stop_reasons[stop]))]},
    }
