"""测试用 MCP stdio 服务：一个检索工具（含业务无结果和预期错误）、一个慢工具和一个报告环境变量的工具。

只由 tests/test_protocols.py 通过 `python -m tests.fixtures.mcp_demo_server` 启动。
"""
import os
import time
from typing import TypedDict

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

NOTES = {
    "agent-loop": "An agent loop sends the history, reads tool calls, runs tools and repeats.",
    "tool-call-id": "Each tool result carries the id of the call it answers.",
}

server = MCPServer("course-search-test")


class SearchResult(TypedDict):
    hits: list[str]
    count: int


@server.tool()
def search_notes(query: str) -> SearchResult:
    """Search course notes by keyword."""
    if not query.strip():
        # 预期的业务错误：ToolError 的说明会原样回到客户端（is_error=True）。
        raise ToolError("query must not be empty")
    hits = [key for key, text in NOTES.items() if query.lower() in (key + " " + text).lower()]
    return {"hits": hits, "count": len(hits)}


@server.tool()
def slow(seconds: float) -> str:
    """Sleep, so a test can stop the run while a call is pending."""
    time.sleep(seconds)
    return "done"


@server.tool()
def process_info() -> dict:
    """Report the server pid and which environment variable names reached it."""
    return {"pid": os.getpid(), "env_keys": sorted(os.environ)}


if __name__ == "__main__":
    server.run()
