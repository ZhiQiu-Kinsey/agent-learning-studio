"""MCP lifecycle: one host, two MCP services — connect, namespace, gate, lose a connection, reconnect and close.

The two servers (catalog_server.py, loans_server.py) are separate processes started over stdio with the
official SDK (mcp 2.x) in legacy mode, so every connection opens with the 2025-11-25 initialize handshake.
The host keeps one client per service, exposes only registered tools under a ``<service>__<tool>`` name,
never resends a write it cannot prove, and reconnects a lost service a bounded number of times. Every
JSON-RPC message is recorded by course.protocols.recording_stdio as a lesson.mcp_message event.
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from functools import partial
from typing import Literal

import anyio
from mcp import Client, MCPError
from mcp.types import Implementation
from pydantic import Field

from course.execution import LessonInputs, RunContext
from course.protocols import python_module_server, recording_stdio, run_until_cancelled
from lessons.lesson_mcp_lifecycle.locales import Texts, texts_for
from lessons.lesson_mcp_lifecycle.processes import stop_process, wait_gone

CLIENT_INFO = Implementation(name="mcp-lifecycle-host", version="1.0")
# Every request waits at most this long; a server that never answers initialize fails with -32001.
READ_TIMEOUT_SECONDS = 5
BACKOFF_SECONDS = (0.2, 0.5, 1.0)
MAX_ROUNDS = 4
SEPARATOR = "__"
TOOL_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")  # the function-name alphabet of OpenAI-compatible APIs
EXCERPT_CHARS = 160


class Inputs(LessonInputs):
    task: Literal["lifecycle", "crash", "agent"] = "lifecycle"
    # Writes are off unless the run allows them: discovering register_loan grants nothing.
    allow_writes: bool = False
    # Fault injection for restart attempts: the first `failing_restarts` attempts start a broken server.
    restart_fault: Literal["exit-on-start", "hang-on-start"] = "exit-on-start"
    failing_restarts: int = Field(default=1, ge=0, le=3)
    max_reconnects: int = Field(default=2, ge=0, le=3)
    restart_variant: Literal["v1", "v2"] = "v1"
    # No default: lesson.json supplies the keyword in the run's language.
    query: str = Field(min_length=1, max_length=100)
    member_id: Literal["M-07", "M-12"] = "M-07"


INPUT_MODEL = Inputs


class NotRoutable(ValueError):
    """No registered tool has this name: the host refuses before anything is sent."""


class ServiceUnavailable(ValueError):
    """The service is lost or was given up: the call is not sent at all."""


class ToolChanged(ValueError):
    """The tool's definition changed after a reconnect: it waits for someone to confirm it again."""


class WriteNotRepeated(ValueError):
    """The same write was already confirmed, or its outcome is unknown: the host will not send it again."""


class ConnectionLost(ValueError):
    """The call was sent and no answer came back (MCPError): its outcome is unknown, never a success."""


class ToolRefused(ValueError):
    """The server answered with isError=true: the connection works, the tool said no."""


@dataclass(frozen=True)
class ServiceSpec:
    service: str  # the host's id for the service, also its namespace prefix
    module: str  # what the host starts: for stdio, identity comes from here, not from serverInfo
    expected_name: str  # the serverInfo.name we expect; self-reported, so only checked for consistency
    tools: dict[str, str]  # registered tool -> "read" | "write"; everything else stays hidden
    probe: tuple[str, dict]  # a real read call that proves the tools work, not just the process


SERVICES = (
    ServiceSpec("catalog", "lessons.lesson_mcp_lifecycle.catalog_server", "library-catalog",
                {"search": "read", "get_book": "read"}, ("search", {"query": "MCP"})),
    ServiceSpec("loans", "lessons.lesson_mcp_lifecycle.loans_server", "library-loans",
                {"search": "read", "register_loan": "write"}, ("search", {"member_id": "M-07"})),
)


@dataclass(frozen=True)
class Route:
    qualified: str
    service: str
    tool: str
    kind: str


def qualified_name(service: str, tool: str) -> str:
    name = f"{service}{SEPARATOR}{tool}"
    if not TOOL_NAME.fullmatch(name):
        raise ValueError(f"tool name {name!r} does not fit the model's function-name alphabet")
    return name


def build_routes(connections) -> dict[str, Route]:
    """Registered tools that a service really listed, each under its <service>__<tool> name."""
    table = {}
    for connection in connections:
        for tool in connection.tools:
            kind = connection.spec.tools.get(tool.name)
            if kind is None:
                continue  # discovered is not registered: no route, whatever the description says
            name = qualified_name(connection.spec.service, tool.name)
            if name in table:
                raise ValueError(f"two services map to the same tool name {name!r}")
            table[name] = Route(name, connection.spec.service, tool.name, kind)
    return table


def fingerprint(tool) -> str:
    """Name, description and inputSchema: what the model reads and what a call must fit."""
    material = json.dumps({"name": tool.name, "description": tool.description, "inputSchema": tool.input_schema},
                          sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


@dataclass
class ServiceConnection:
    spec: ServiceSpec
    state: str = "closed"  # connected | lost | gave_up | closed
    client: Client | None = None
    done: anyio.Event | None = None  # set it to close the connection
    closed: anyio.Event | None = None  # set once the owner task has reaped the process
    pid: int | None = None
    pids: list[int] = field(default_factory=list)  # every server process this connection started
    attempts: int = 0  # reconnect attempts used so far
    tools: list = field(default_factory=list)
    baseline: dict[str, str] = field(default_factory=dict)  # fingerprints confirmed at first discovery
    quarantined: list[str] = field(default_factory=list)  # registered tools whose definition changed
    handshakes: list[dict] = field(default_factory=list)  # what each initialize negotiated


def first_mcp_error(error: BaseException) -> MCPError | None:
    """The SDK raises a failed connect inside an ExceptionGroup; the MCPError is the part that explains it."""
    if isinstance(error, MCPError):
        return error
    for inner in getattr(error, "exceptions", ()):
        found = first_mcp_error(inner)
        if found is not None:
            return found
    return None


class Host:
    """One client per service, a namespaced route table, a write record and a reconnect policy."""

    def __init__(self, context: RunContext, t: Texts):
        self.context, self.t = context, t
        self.connections = {spec.service: ServiceConnection(spec) for spec in SERVICES}
        self.writes: list[dict] = []
        self.lost_calls: list[str] = []
        self.timeline: list[list[str]] = []

    async def __aenter__(self):
        # Every connection lives in its own task under this group, so connections can close in any order.
        self._group_cm = anyio.create_task_group()
        self.group = await self._group_cm.__aenter__()
        return self

    async def __aexit__(self, *exc_info):
        try:
            if exc_info[0] is None:
                await self.close_all()  # on success close in order; on stop or error the group cancels them
        finally:
            return await self._group_cm.__aexit__(*exc_info)

    async def connect(self, service: str, *server_args: str, attempt: int = 0) -> dict:
        connection = self.connections[service]
        params = python_module_server(connection.spec.module, "--locale", self.context.locale, *server_args)
        connection.done, connection.closed = anyio.Event(), anyio.Event()
        client, listed, info, error = await self.group.start(self._own, service, params, connection.done,
                                                             connection.closed)
        if error is not None:
            raise error
        connection.client, connection.state, connection.tools = client, "connected", listed.tools
        connection.pid = info.structured_content["pid"]
        connection.pids.append(connection.pid)
        handshake = {"protocol_version": client.protocol_version, "server_name": client.server_info.name,
                     "capabilities": client.server_capabilities.model_dump(mode="json", by_alias=True, exclude_none=True)}
        connection.handshakes.append(handshake)
        self.emit_state(service, "connected", attempt=attempt, pid=connection.pid, **handshake,
                        tools=[tool.name for tool in listed.tools], recheck=self._recheck(connection) if attempt else None,
                        secret_like_env=info.structured_content["secret_like_env"])
        return info.structured_content

    async def close(self, service: str):
        connection = self.connections[service]
        if connection.done is not None:
            connection.done.set()
            await connection.closed.wait()
        connection.client, connection.done = None, None
        if connection.state == "connected":
            connection.state = "closed"

    async def close_all(self):
        for service in self.connections:
            await self.close(service)

    # ---- one connection's life ----

    async def _own(self, service, params, done, closed, *, task_status):
        started = False
        try:
            # 1. Start: python -m <module> with the SDK's safe environment; no API key reaches the child.
            # 2. Initialize: initialize -> capabilities -> notifications/initialized, all inside Client(...).
            async with Client(recording_stdio(self.context, params, server=service), mode="legacy",
                              client_info=CLIENT_INFO, read_timeout_seconds=READ_TIMEOUT_SECONDS, cache=None) as client:
                # 3. Discover: tools/list without cache, so a restarted server is really asked again.
                listed = await client.list_tools()
                info = await client.call_tool("service_info", {})
                task_status.started((client, listed, info, None))
                started = True
                await done.wait()  # 4. Operate: calls come from other tasks until someone closes it.
        except Exception as error:
            # Before the handshake finished the caller gets the MCPError; after it, a failure shows on the next call.
            if not started:
                task_status.started((None, None, None, first_mcp_error(error) or error))
        finally:
            closed.set()  # 5. Close: leaving the block closed stdin, then SIGTERM/SIGKILL if needed, and reaped it

    async def reconnect(self, service: str, inputs: dict) -> bool:
        connection = self.connections[service]
        await self.close(service)  # the old client is never reused; closing it reaps the dead process
        while connection.attempts < inputs["max_reconnects"]:  # bounded for the whole run
            connection.attempts += 1
            attempt = connection.attempts
            await anyio.sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS)) - 1])
            fault = ("--fault", inputs["restart_fault"]) if attempt <= inputs["failing_restarts"] else ()
            self.emit_state(service, "reconnecting", attempt=attempt, fault=fault[1] if fault else None)
            try:
                await self.connect(service, "--variant", inputs["restart_variant"], *fault, attempt=attempt)
            except MCPError as error:
                self.emit_state(service, "failed", attempt=attempt, error_code=error.error.code,
                                error=error.error.message)
                continue
            if await self.probe(service):  # a finished handshake is not enough: a real tool must answer
                return True
            await self.close(service)
        connection.state = "gave_up"  # its tools stay registered but are not offered or sent any more
        self.emit_state(service, "gave_up", attempt=connection.attempts, max_reconnects=inputs["max_reconnects"])
        return False

    def _recheck(self, connection: ServiceConnection) -> dict:
        """After a reconnect, compare every definition with the one confirmed at first discovery."""
        now = {tool.name: fingerprint(tool) for tool in connection.tools}
        changed = [name for name, value in now.items() if connection.baseline.get(name, value) != value]
        connection.quarantined = [name for name in changed if name in connection.spec.tools]
        return {"changed": changed, "added": [name for name in now if name not in connection.baseline],
                "removed": [name for name in connection.baseline if name not in now],
                "quarantined": connection.quarantined}

    async def probe(self, service: str) -> bool:
        connection = self.connections[service]
        tool, arguments = connection.spec.probe
        try:
            result = await connection.client.call_tool(tool, arguments)
        except MCPError:
            connection.state = "lost"
            return False
        return not result.is_error

    # ---- routing and calls ----

    def routes(self) -> dict[str, Route]:
        return build_routes(self.connections.values())

    def available(self, allow_writes: bool) -> dict:
        """The allowlist handed to the platform: a name not in it is refused as an unknown tool."""
        return {name: partial(self.bridge, name) for name, route in self.routes().items()
                if route.kind == "read" or allow_writes}

    def usable(self, route: Route) -> bool:
        connection = self.connections[route.service]
        return connection.state == "connected" and route.tool not in connection.quarantined

    def bridge(self, qualified: str, /, **arguments):
        """Runs in the platform's worker thread; the MCP call itself goes back to the event loop."""
        return anyio.from_thread.run(self.call, qualified, arguments)

    async def call(self, qualified: str, arguments: dict):
        route = self.routes().get(qualified)
        if route is None:
            raise NotRoutable(self.t.not_routable.format(name=qualified))
        connection = self.connections[route.service]
        # 1. Refuse before sending: the service is down, or the tool changed and is not confirmed again.
        if connection.state != "connected":
            raise ServiceUnavailable(self.t.service_unavailable.format(service=route.service,
                                                                       state=self.t.states[connection.state]))
        if route.tool in connection.quarantined:
            raise ToolChanged(self.t.tool_changed.format(name=qualified))
        entry = None
        if route.kind == "write":
            # 2. A write is identified by tool and arguments; a confirmed or unknown one is never resent.
            key = qualified + json.dumps(arguments, sort_keys=True, ensure_ascii=False)
            earlier = next((w for w in self.writes if w["key"] == key and w["status"] in ("confirmed", "unknown")), None)
            if earlier is not None:
                raise WriteNotRepeated(self.t.write_not_repeated.format(status=self.t.write_status[earlier["status"]]))
            entry = {"key": key, "tool": qualified, "arguments": arguments, "status": "sent", "result": None}
            self.writes.append(entry)
        try:
            result = await connection.client.call_tool(route.tool, arguments)
        except MCPError as error:
            # 3. No answer: the connection is lost and the outcome unknown; nothing counts as done.
            connection.state = "lost"
            self.lost_calls.append(qualified)
            self.emit_state(route.service, "lost", error_code=error.error.code, error=error.error.message)
            if entry is not None:
                entry["status"] = "unknown"
            raise ConnectionLost(self.t.connection_lost.format(service=route.service, code=error.error.code,
                                                               message=error.error.message)) from None
        if entry is not None:
            # 4. An answer: isError=true means the tool refused; only a clean result confirms the write.
            entry["status"] = "rejected" if result.is_error else "confirmed"
            entry["result"] = None if result.is_error else result.structured_content
        if result.is_error:
            raise ToolRefused(text_of(result))
        return result.structured_content if result.structured_content is not None else text_of(result)

    def emit_state(self, service: str, state: str, **data):
        self.context.emit("lesson.service_state", {"service": service, "state": state,
                                                   **{key: value for key, value in data.items() if value is not None}})
        self.timeline.append([service, self.t.states[state], _state_detail(self.t, data)])


def text_of(result) -> str:
    return "\n".join(block.text for block in result.content if getattr(block, "type", None) == "text")


async def runner_call(context: RunContext, host: Host, name: str, arguments: dict, allow_writes: bool) -> dict:
    """A call the runner makes itself: recorded as tool_call/tool_result with origin course_program."""
    return await anyio.to_thread.run_sync(context.call_tool, name, arguments, host.available(allow_writes))


async def runner_submit(context: RunContext, host: Host, name: str, arguments: dict, allow_writes: bool) -> dict:
    """Same, but the name may be one the host never exposes, to show the refusal."""
    return await anyio.to_thread.run_sync(context.submit_call, name, json.dumps(arguments, ensure_ascii=False),
                                         host.available(allow_writes))


async def connect_all(host: Host) -> dict:
    infos = {}
    for spec in SERVICES:
        infos[spec.service] = await host.connect(spec.service)
        connection = host.connections[spec.service]
        connection.baseline = {tool.name: fingerprint(tool) for tool in connection.tools}
    return infos


async def close_and_count(host: Host) -> tuple[list[int], list[int]]:
    """Close every connection, then look for any server process this run started that is still running."""
    pids = [pid for connection in host.connections.values() for pid in connection.pids]
    await host.close_all()
    return pids, await anyio.to_thread.run_sync(wait_gone, pids)


async def run_lifecycle(context: RunContext, host: Host, t: Texts, inputs: dict) -> str:
    allow = inputs["allow_writes"]
    # 1. Connect both services: two processes, two initialize handshakes.
    infos = await connect_all(host)
    # 2. Probe with real read calls under the namespaced names.
    probes = {spec.service: await runner_call(context, host, qualified_name(spec.service, spec.probe[0]),
                                              spec.probe[1], allow) for spec in SERVICES}
    # 3. Permission checks: a bare name, an unregistered tool and a write.
    attempts = {
        "bare": await runner_submit(context, host, "search", {"query": inputs["query"]}, allow),
        "unregistered": await runner_submit(context, host, "loans__purge_loans", {}, allow),
        "write": await runner_submit(context, host, "loans__register_loan",
                                     {"book_id": "B-101", "member_id": inputs["member_id"]}, allow),
    }
    routes = host.routes()
    # 4. Close everything and check that no server process is left.
    pids, left = await close_and_count(host)
    context.emit("lesson.report", _lifecycle_report(t, host, infos, probes, attempts, routes, allow, pids, left))
    return t.lifecycle_answer.format(routes=len(routes), refused=sum(not result["ok"] for result in attempts.values()),
                                     left=len(left))


async def run_crash(context: RunContext, host: Host, t: Texts, inputs: dict) -> str:
    allow, member = inputs["allow_writes"], inputs["member_id"]
    await connect_all(host)
    # 1. Normal work: a search on one service, a write on the other.
    found = await runner_call(context, host, "catalog__search", {"query": inputs["query"]}, allow)
    book = found["result"]["books"][0]["book_id"] if found["ok"] and found["result"]["books"] else "B-101"
    first = await runner_call(context, host, "loans__register_loan", {"book_id": book, "member_id": member}, allow)
    # 2. Fault injection: kill the loan desk's process, as a crash would. The host does not know yet.
    loans = host.connections["loans"]
    stop_process(loans.pid)
    host.emit_state("loans", "stopped", pid=loans.pid, cause="fault_injection")
    # 3. The next write goes out on a dead connection: MCPError, outcome unknown.
    second = await runner_call(context, host, "loans__register_loan", {"book_id": "B-104", "member_id": member}, allow)
    # 4. Reconnect within the limit, recheck the tools, probe; then ask what the new process remembers.
    recovered = await host.reconnect("loans", inputs) if loans.state == "lost" else False
    after = await runner_call(context, host, "loans__search", {"member_id": member}, allow)
    # 5. Resume the plan: both writes again. The host refuses to resend either.
    resumed = [await runner_call(context, host, "loans__register_loan", {"book_id": book_id, "member_id": member}, allow)
               for book_id in (book, "B-104")]
    pids, left = await close_and_count(host)
    context.emit("lesson.report", _crash_report(t, host, inputs, first, second, recovered, after, resumed, pids, left))
    return t.crash_answer.format(state=_final_state(t, loans, recovered), attempts=loans.attempts,
                                 confirmed=sum(w["status"] == "confirmed" for w in host.writes),
                                 unknown=sum(w["status"] == "unknown" for w in host.writes), left=len(left))


def model_tools(host: Host, allow_writes: bool) -> list[dict]:
    """Allowed by the registry and the run, and usable right now: a lost service's tools are not offered."""
    routes = host.routes()
    definitions = {qualified_name(c.spec.service, tool.name): tool for c in host.connections.values() for tool in c.tools}
    # The MCP definition under its namespaced name: same description and inputSchema.
    return [{"type": "function", "function": {"name": name, "description": definitions[name].description or "",
                                              "parameters": definitions[name].input_schema}}
            for name in host.available(allow_writes) if host.usable(routes[name])]


async def run_agent_task(context: RunContext, host: Host, t: Texts, inputs: dict) -> str:
    if context.completion is None:
        raise ValueError(t.agent_needs_model)
    allow = inputs["allow_writes"]
    await connect_all(host)
    messages = [{"role": "system", "content": t.agent_system}, {"role": "user", "content": context.question}]
    answer, stop, offered, killed = None, "rounds", [], False
    for round_number in range(1, MAX_ROUNDS + 1):
        # 1. Each round the model sees only the tools of services that are connected right now.
        tools = model_tools(host, allow)
        offered.append([tool["function"]["name"] for tool in tools])
        body = {"messages": messages, "tools": tools, "tool_choice": "auto"}
        response = await anyio.to_thread.run_sync(partial(context.complete, body, round_number))
        message = response["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        if not calls:
            answer, stop = message.get("content") or "", "answered"
            break
        messages.append(message)
        available = host.available(allow)
        for call in calls:
            result = await anyio.to_thread.run_sync(context.execute_proposal, call, available)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)})
            # 2. Fault injection: once the first write is confirmed, the loan desk's process is killed.
            if not killed and any(w["status"] == "confirmed" for w in host.writes):
                stop_process(host.connections["loans"].pid)
                host.emit_state("loans", "stopped", pid=host.connections["loans"].pid, cause="fault_injection")
                killed = True
        # 3. Between rounds the host, not the model, reconnects lost services within the limit.
        for service, connection in host.connections.items():
            if connection.state == "lost":
                await host.reconnect(service, inputs)
    pids, left = await close_and_count(host)
    context.emit("lesson.report", _agent_report(t, host, offered, stop, round_number, pids, left))
    return answer if stop == "answered" else t.stop_answers[stop]


TASKS = {"lifecycle": run_lifecycle, "crash": run_crash, "agent": run_agent_task}


async def run(context: RunContext):
    t = texts_for(context.locale)

    async def guarded():
        # run_until_cancelled wraps exceptions in an ExceptionGroup; hand them back as values and re-raise below.
        try:
            # Leaving the Host block closes every connection, also on stop or error: no server outlives the run.
            async with Host(context, t) as host:
                return await TASKS[context.inputs["task"]](context, host, t, context.inputs), None
        except Exception as error:
            return None, first_mcp_error(error) or _unwrap(error)

    answer, error = await run_until_cancelled(context, guarded)
    if error is not None:
        raise error
    return answer


def _unwrap(error: BaseException) -> BaseException:
    """A task group raises ExceptionGroup even for one failure; report the failure itself."""
    while isinstance(error, BaseExceptionGroup) and len(error.exceptions) == 1:
        error = error.exceptions[0]
    return error


# ---- lab reports ----

def _excerpt(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= EXCERPT_CHARS else text[:EXCERPT_CHARS] + "…"


def _state_detail(t: Texts, data: dict) -> str:
    parts = []
    if data.get("attempt"):
        parts.append(t.detail_attempt.format(attempt=data["attempt"]))
    if data.get("pid"):
        parts.append(f"pid {data['pid']}")
    if data.get("error_code") is not None:
        parts.append(f"MCPError {data['error_code']}: {data.get('error', '')}")
    if data.get("fault"):
        parts.append(t.detail_fault.format(fault=data["fault"]))
    if data.get("recheck"):
        recheck = data["recheck"]
        parts.append(t.detail_recheck.format(changed=", ".join(recheck["changed"]) or "-",
                                             added=", ".join(recheck["added"]) or "-"))
    return "; ".join(parts) or "-"


def _outcome(t: Texts, result: dict) -> str:
    if result["ok"]:
        return t.outcome_ok.format(result=_excerpt(json.dumps(result["result"], ensure_ascii=False)))
    return t.outcome_error.format(error_type=result["error_type"], error=_excerpt(result["error"]))


def _check(identifier: str, label: str, passed: bool | None, detail: str) -> dict:
    """A check that was not carried out in this run has no passed field at all, rather than a guess."""
    check = {"id": identifier, "label": label, "detail": detail}
    if passed is not None:
        check["passed"] = bool(passed)
    return check


def _reap_check(t: Texts, pids: list[int], left: list[int]) -> dict:
    return _check("reaped", t.check_reaped, not left,
                  t.detail_reaped.format(pids=", ".join(map(str, pids)), left=", ".join(map(str, left)) or "-"))


def _lifecycle_report(t, host, infos, probes, attempts, routes, allow, pids, left) -> dict:
    connections = host.connections.values()
    shared = sorted(set.intersection(*({tool.name for tool in c.tools} for c in connections)))
    handshakes = {c.spec.service: c.handshakes[0] for c in connections}
    rows = []
    for connection in connections:
        for tool in connection.tools:
            kind = connection.spec.tools.get(tool.name)
            if kind is None:
                status = t.route_hidden
            elif kind == "write" and not allow:
                status = t.route_write_off
            else:
                status = t.route_exposed
            rows.append([qualified_name(connection.spec.service, tool.name), connection.spec.service, tool.name,
                         t.kinds[kind or "none"], status])
    secrets = [name for info in infos.values() for name in info["secret_like_env"]]
    return {
        "title": t.report_titles["lifecycle"],
        "summary": t.lifecycle_summary.format(services=len(handshakes), routes=len(routes), shared=", ".join(shared)),
        "checks": [
            _check("handshake", t.check_handshake, all(h["protocol_version"] for h in handshakes.values()),
                   "; ".join(t.detail_handshake.format(service=service, version=h["protocol_version"],
                                                       tools=json.dumps(h["capabilities"].get("tools"), sort_keys=True))
                             for service, h in handshakes.items())),
            _check("identity", t.check_identity,
                   all(handshakes[c.spec.service]["server_name"] == c.spec.expected_name for c in connections),
                   t.detail_identity.format(names=", ".join(f"{service}={h['server_name']}"
                                                            for service, h in handshakes.items()))),
            _check("namespaced", t.check_namespaced, bool(shared) and all(SEPARATOR in name for name in routes),
                   t.detail_namespaced.format(shared=", ".join(shared) or "-",
                                              names=", ".join(sorted(n for n in routes if n.endswith(SEPARATOR + "search"))))),
            _check("probes", t.check_probes, all(result["ok"] for result in probes.values()),
                   "; ".join(f"{service}: {_outcome(t, result)}" for service, result in probes.items())),
            _check("bare_refused", t.check_bare, not attempts["bare"]["ok"], _outcome(t, attempts["bare"])),
            _check("unregistered_refused", t.check_unregistered, not attempts["unregistered"]["ok"],
                   _outcome(t, attempts["unregistered"])),
            _check("write_gate", t.check_write_gate, attempts["write"]["ok"] == allow,
                   t.detail_write_gate.format(allowed=t.yes_no[allow], outcome=_outcome(t, attempts["write"]))),
            _check("no_secret", t.check_no_secret, not secrets,
                   t.detail_env.format(names=", ".join(infos["loans"]["env_names"]))),
            _reap_check(t, pids, left),
        ],
        "metrics": [
            {"id": "protocol_version", "label": t.label_protocol_version, "value": handshakes["catalog"]["protocol_version"]},
            {"id": "routes", "label": t.label_routes, "value": len(routes)},
            {"id": "hidden", "label": t.label_hidden, "value": sum(row[4] == t.route_hidden for row in rows)},
            {"id": "processes_left", "label": t.label_processes_left, "value": len(left)},
        ],
        "table": {"columns": list(t.columns_routes), "rows": rows},
    }


def _final_state(t: Texts, connection: ServiceConnection, recovered: bool) -> str:
    # close_all turns a working connection into "closed"; report what it was before the run ended.
    return t.states["connected" if recovered and connection.state == "closed" else connection.state]


def _crash_report(t, host, inputs, first, second, recovered, after, resumed, pids, left) -> dict:
    loans = host.connections["loans"]
    confirmed = [w for w in host.writes if w["status"] == "confirmed"]
    unknown = [w for w in host.writes if w["status"] == "unknown"]
    return {
        "title": t.report_titles["crash"],
        "summary": t.crash_summary.format(attempts=loans.attempts, limit=inputs["max_reconnects"],
                                          fault=inputs["restart_fault"], failing=inputs["failing_restarts"]),
        "checks": [
            _check("first_write", t.check_first_write, first["ok"], _outcome(t, first)),
            _check("connection_error", t.check_connection_error,
                   not second["ok"] and second["error_type"] == ConnectionLost.__name__, _outcome(t, second)),
            _check("bounded", t.check_bounded, loans.attempts <= inputs["max_reconnects"],
                   t.detail_bounded.format(attempts=loans.attempts, limit=inputs["max_reconnects"],
                                           state=_final_state(t, loans, recovered))),
            # Only a reconnected service can be asked what it still remembers.
            _check("state_lost", t.check_state_lost,
                   (after["ok"] and after["result"]["count"] < len(confirmed)) if recovered else None,
                   t.detail_state_lost.format(confirmed=len(confirmed), outcome=_outcome(t, after))),
            _check("no_replay", t.check_no_replay, all(not result["ok"] for result in resumed),
                   " | ".join(_outcome(t, result) for result in resumed)),
            _check("rechecked", t.check_rechecked, True if recovered else None,
                   t.detail_quarantine.format(names=", ".join(loans.quarantined) or "-")),
            _reap_check(t, pids, left),
        ],
        "metrics": [
            {"id": "reconnect_attempts", "label": t.label_attempts, "value": loans.attempts},
            {"id": "final_state", "label": t.label_final_state, "value": _final_state(t, loans, recovered)},
            {"id": "writes", "label": t.label_writes,
             "value": t.writes_value.format(confirmed=len(confirmed), unknown=len(unknown))},
            {"id": "processes_left", "label": t.label_processes_left, "value": len(left)},
        ],
        "table": {"columns": list(t.columns_timeline), "rows": host.timeline},
    }


def _agent_report(t, host, offered, stop, rounds, pids, left) -> dict:
    loans = host.connections["loans"]
    return {
        "title": t.report_titles["agent"],
        "summary": t.agent_summary.format(rounds=rounds, stop=t.stop_reasons[stop], attempts=loans.attempts),
        "checks": [
            _check("namespaced_tools", t.check_model_tools, all(SEPARATOR in n for names in offered for n in names),
                   " | ".join(t.detail_offered.format(round=index, names=", ".join(names) or "-")
                              for index, names in enumerate(offered, 1))),
            # Only when a call met a dead connection is there something to check here.
            _check("lost_not_success", t.check_lost_not_success, True if host.lost_calls else None,
                   ", ".join(host.lost_calls) or t.value_none),
            _check("writes_recorded", t.check_writes_recorded, None,
                   "; ".join(f"{w['tool']} {json.dumps(w['arguments'], ensure_ascii=False)}: {t.write_status[w['status']]}"
                             for w in host.writes) or t.value_none),
            _reap_check(t, pids, left),
        ],
        "metrics": [
            {"id": "model_calls", "label": t.label_model_calls, "value": rounds},
            {"id": "reconnect_attempts", "label": t.label_attempts, "value": loans.attempts},
            {"id": "stop_reason", "label": t.label_stop_reason, "value": t.stop_reasons[stop]},
        ],
        "table": {"columns": list(t.columns_timeline), "rows": host.timeline},
    }
