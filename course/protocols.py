"""Protocol helpers: MCP and A2A lessons talk to real local processes under RunContext.

Three things every protocol lesson needs and should not reinvent:

- Cancellation. RunContext reports a stop through a polled ``cancelled()`` callable;
  ``run_until_cancelled`` turns it into an anyio cancellation, so pending protocol calls
  stop and the SDK's own cleanup (closing stdin, then terminating the process tree) runs.
- Child processes. Servers start only from modules under ``lessons.`` (or ``tests.`` for
  the platform tests), with the SDK's short list of safe environment variables: API keys
  in this process's environment never reach a child.
- Evidence. ``recording_stdio`` records every JSON-RPC message between the MCP client and
  server as a ``lesson.mcp_message`` event. The data is the SDK's message object dumped
  with protocol field names (``captured: "sdk_session_message"``): outgoing messages are
  serialized from exactly that dump; incoming ones were parsed from one stdout line, so
  key order and whitespace of the original line are not kept.
"""
from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Iterator

import anyio
from mcp import StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client

from course.execution import RunContext
from course.runner import RunCancelled

MCP_MESSAGE_EVENT = "lesson.mcp_message"
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
_MODULE = re.compile(r"(lessons|tests)(\.[A-Za-z_][A-Za-z0-9_]*)+")


async def run_until_cancelled(context: RunContext, function: Callable[..., Awaitable[Any]], *args: Any,
                              poll_interval: float = 0.1) -> Any:
    """Await ``function(*args)``; when the run is stopped, cancel it and raise RunCancelled.

    Cancelling (not just abandoning) the coroutine matters: ``async with Client(...)`` then
    unwinds, and the SDK shuts the server process down instead of leaving it running.
    """
    result = None

    async with anyio.create_task_group() as group:
        async def watch():
            while not context.cancelled():
                await anyio.sleep(poll_interval)
            group.cancel_scope.cancel()

        async def work():
            nonlocal result
            result = await function(*args)
            group.cancel_scope.cancel()

        group.start_soon(watch)
        group.start_soon(work)
    context.check_cancelled()
    return result


def safe_child_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The SDK's inherit list (PATH, HOME and the like) plus explicit extras; never the parent's keys."""
    return {**get_default_environment(), **(extra or {})}


def _check_module(module: str) -> str:
    if not isinstance(module, str) or not _MODULE.fullmatch(module):
        raise ValueError("a protocol server must be a module under lessons. (or tests.), e.g. "
                         "lessons.lesson_mcp_basics.server")
    return module


def python_module_server(module: str, *args: str, env: dict[str, str] | None = None) -> StdioServerParameters:
    """Stdio parameters that run ``python -m <module>`` from the repository root with a safe environment.

    ``-m`` from the repository root lets a server import lesson code; the SDK merges ``env``
    over its safe inherit list, so nothing else from this process's environment is passed on.
    """
    return StdioServerParameters(command=sys.executable, args=["-m", _check_module(module), *map(str, args)],
                                 cwd=str(REPOSITORY_ROOT), env=dict(env or {}))


class _RecordingStream:
    """Forward one direction of an MCP transport and record each message on the way."""

    def __init__(self, inner, record: Callable[[Any], None]):
        self._inner = inner
        self._record = record

    async def send(self, message):
        self._record(message)
        await self._inner.send(message)

    async def receive(self):
        message = await self._inner.receive()
        self._record(message)
        return message

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return await self.receive()
        except (anyio.EndOfStream, anyio.ClosedResourceError):
            raise StopAsyncIteration from None

    async def __aenter__(self):
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, *exc_info):
        return await self._inner.__aexit__(*exc_info)

    def __getattr__(self, name):
        return getattr(self._inner, name)


@asynccontextmanager
async def recording_stdio(context: RunContext, params: StdioServerParameters, *, server: str,
                          round_number: int | None = None) -> AsyncIterator[Any]:
    """An MCP stdio transport that records each JSON-RPC message as ``lesson.mcp_message``.

    Pass it to ``mcp.Client(...)``. ``server`` names the connection in the events, so a
    lesson with two servers can tell their messages apart. The server's stderr goes to
    the null device: tracebacks there can carry local paths, which events must not.
    """
    def record(direction: str, item: Any):
        if isinstance(item, Exception):
            data = {"server": server, "direction": direction, "parse_error": type(item).__name__}
        else:
            data = {"server": server, "direction": direction, "captured": "sdk_session_message",
                    "message": item.message.model_dump(mode="json", by_alias=True, exclude_unset=True)}
        try:
            context.emit(MCP_MESSAGE_EVENT, data, round_number)
        except RunCancelled:
            # Raising inside the SDK's reader task would be logged, not propagated;
            # run_until_cancelled performs the actual stop.
            pass

    with open(os.devnull, "w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (read_stream, write_stream):
            yield (_RecordingStream(read_stream, lambda item: record("server_to_client", item)),
                   _RecordingStream(write_stream, lambda item: record("client_to_server", item)))


@dataclass(frozen=True)
class LocalService:
    pid: int
    port: int

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def _stop_process(process: subprocess.Popen, grace_seconds: float):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(grace_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(grace_seconds)
    if process.stdout:
        process.stdout.close()


@contextmanager
def spawn_local_service(module: str, *args: str, ready_prefix: str = "PORT ", startup_timeout: float = 15.0,
                        grace_seconds: float = 3.0, env: dict[str, str] | None = None) -> Iterator[LocalService]:
    """Start ``python -m <module>`` as a local HTTP service and stop it on exit, whatever happened.

    The service binds 127.0.0.1 itself and prints ``PORT <n>`` as its first stdout line, so
    no fixed port can collide with the learner's own server. On exit the process gets
    SIGTERM, then a kill after ``grace_seconds``; the run never leaves it behind.
    """
    flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    process = subprocess.Popen([sys.executable, "-m", _check_module(module), *map(str, args)],
                               cwd=str(REPOSITORY_ROOT), env=safe_child_environment(env), stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                               **flags)
    try:
        # readline() blocks, and pipes have no portable timeout: read on a helper thread.
        lines: queue.Queue = queue.Queue()
        threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
        try:
            line = lines.get(timeout=startup_timeout)
        except queue.Empty:
            raise TimeoutError(f"{module} did not report its port within {startup_timeout} seconds") from None
        if not line.startswith(ready_prefix):
            raise RuntimeError(f"{module} exited or printed something else before its port")
        port = int(line[len(ready_prefix):].strip())
        yield LocalService(pid=process.pid, port=port)
    finally:
        _stop_process(process, grace_seconds)
