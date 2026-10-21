# MCP basics and tool integration (`mcp-basics`)

English · [简体中文](README.zh-CN.md)

In earlier lessons every tool was a Python function inside the agent's code. This lesson uses the official Python SDK (`mcp` 2.x) to turn the handbook search into a separate MCP server process, and the runner connects to it over standard input and output (`stdio`): it really discovers tools (`tools/list`) and calls them (`tools/call`), then sees which layer each of four failures lands in (bad arguments, unknown tool, business error, server crash). Finally the discovered tools go to the model, separating "the protocol discovers and transports" from "the agent schedules and decides". The three local exercises call no model; the agent exercise needs a real model connection. The lesson is still `planned` and has been verified offline only.

## Server and corpus

- `server.py` registers three tools with `MCPServer` (`FastMCP` in 1.x); the search reuses `lessons.lesson_keyword_retrieval.bm25` and the Bluestone Library handbook corpus of `lessons.lesson_document_loading` (imported, never changed):
  - `search_handbook(query, top_k=3)`: BM25 search, `top_k` limited to 1–5; returns `query`, `count` and `hits` (chunk id, title, anchors, score, text). The return type is a TypedDict, so there is an `outputSchema` and `structuredContent`. Empty search terms raise `ToolError`.
  - `read_chunk(chunk_id)`: reads only by chunk ids in the server's own index; a path is just an unknown id and gets a `ToolError` message.
  - `service_status()`: reports the pid, the chunk count and the **names** (not values) of the environment variables it received, to show that no key reached the child.
- Tool descriptions and business errors come from `locales/` according to the `--locale` start argument; `--fault exit-on-search` is used only for the second server of the error exercise (fault injection: the process exits when a search arrives).
- The server is started by `course.protocols.python_module_server` as `python -m lessons.lesson_mcp_basics.server`: only modules under the `lessons.` package are allowed, the child inherits only the SDK's list of safe environment variables, and its standard error is discarded.

## Four exercises

| Exercise | Protocol version | Model | What it does |
| --- | --- | --- | --- |
| Discovery and calls (2025-11-25 handshake) | `legacy`: `initialize` → `notifications/initialized` | none | List tools; one search with hits and one without (`count: 0` is a normal result too); call `service_status` |
| Discovery and calls (2026-07-28 discover) | `auto`: `server/discover` first, every request carries the version in `params._meta` | none | The same, to compare how the connection starts |
| Error paths | `legacy` | none | Bad arguments (`top_k=50`), unknown tool, business error (`read_chunk("../../local_config.py")`), then a fault-injected server: the process exits mid-call, and a request after the crash |
| The model picks from the discovered tools | `legacy` | yes | `tools/list` → the host gives out only two tools via `MODEL_TOOLS` → `to_model_tool` converts them unchanged → `context.complete` → call proposals go through `execute_proposal` and `call_over_mcp` as `tools/call` → answer or stop (at most 3 model calls; stop when the connection drops) |

Error layers (measured with the SDK version this lesson pins): the first three paths get an `isError: true` result (a tool error; the protocol worked); the last two make the client raise `MCPError` with code -32000 (a protocol error; no result). The specification lists "unknown tool" as a JSON-RPC protocol error (example code -32602), while this SDK returns an `isError: true` result; the report records the measured layering.

## Evidence

- `lesson.mcp_message`: every JSON-RPC message recorded by the platform's `recording_stdio`, with `server`, `direction` (`client_to_server` / `server_to_client`) and `captured: "sdk_session_message"`. It is the SDK's message object dumped with protocol field names, not raw bytes: key order and whitespace are not kept.
- The agent exercise also has `request`/`response` (model calls) and `tool_call`/`tool_result` (recorded by the platform, paired by call id); each call's `tools/call` messages sit between `tool_call` and `tool_result`.
- `lesson.report`: for discovery, checks (handshake, discovery, hits, no hits, no keys), the protocol version and a tool table; for the error paths, one check and one table row per path (which layer answered, what the client saw) plus the fault-injection note; for the agent, the host filter, every call proposal going over MCP, model calls, `tools/call` count, stop reason and a duty table.

## What to look at in the experiments

1. **The course search MCP server: discovery and calls**: the first request of each protocol version, `inputSchema` in `tools/list`, the first search's `structuredContent`, no hits counted as a normal result, and the environment variable names the server sees.
2. **Which layer each of four error paths lands in**: `isError` true in the reply to bad arguments; replies for the unknown tool and the business error too; `MCPError` for the crash and the request after it; the fault injection stated in the report.
3. **An agent calling over MCP: who does what**: only two tools in the request, the model's call proposal, the same call as `tools/call`, `tool_result`, the duty table and the stop reason.

The offline fixture (`fixtures.py`) serves automated tests only: round one always proposes one `search_handbook` call, and once the tool result arrives it writes one sentence citing the top chunk. The server process, the protocol messages and the BM25 search really run; only the model's decisions are scripted. A real model may choose other search terms or call `read_chunk`; conclusions come from your own real runs.

## Files

- `server.py`: the MCP server (`build_server`, `main`).
- `runtime.py`: input model, connection (`connect`), error layers (`attempt`, `classify`), conversion of MCP tools into model tool definitions (`to_model_tool`), the bridge that executes call proposals over MCP (`call_over_mcp`), the three tasks and the reports.
- `locales/zh_CN.py`, `locales/en.py`: the server's tool descriptions and business errors, the system prompt and report text; `locales/fixture/` holds the offline script's search terms and answer template.
- `fixtures.py`, `test_lesson.py`: deterministic test model and behavior tests (real child processes; both run languages; Schema violations, tools not offered, round limit, dropped connection; the process is reaped after a stop; the child gets no keys).
- Platform: `course/protocols.py` (`python_module_server`, `recording_stdio`, `run_until_cancelled`).

## Running

```powershell
# Offline tests (deterministic model data; the MCP server process and the search really run)
.\.venv\Scripts\python.exe -m unittest lessons.lesson_mcp_basics.test_lesson -v
# Start the server on its own to see it (it only reads standard input; Ctrl+C to quit)
.\.venv\Scripts\python.exe -m lessons.lesson_mcp_basics.server --locale en
# After the lesson opens, real runs (the agent exercise uses the model); --locale en runs in English
.\.venv\Scripts\python.exe scripts/run_live.py mcp-basics tour --url http://127.0.0.1:8765 --locale en
.\.venv\Scripts\python.exe scripts/run_live.py mcp-basics agent --url http://127.0.0.1:8765 --locale en
```

**Run language:** tool descriptions, business errors, prompts and report text come from `locales/` in the run language (the server gets the same catalog through `--locale`); tool names, argument names and protocol method names are code and the same in every language. Text the SDK generates itself (Pydantic validation messages, `Unknown tool`, `Connection closed`) is English in both runs.

**Stopping:** the whole protocol session runs inside `run_until_cancelled`; on stop the SDK closes stdin, terminates the server process after a grace period, and the run is recorded as cancelled.

## References and attribution

The client-server architecture of MCP, its three primitives, the token cost of `tools/list` and the three risks of third-party servers follow chapter 4 of Understanding AI Agents in Depth (深入理解 AI Agent) and its `chapter4/` companion code ([bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book), Apache-2.0); the split into host, client and server follows `11-agentic-protocols` of Microsoft AI Agents for Beginners (MIT); MCP as a unified tool interface and the smolagents example follow Hugging Face Agents Course units 1 and 2 (Apache-2.0); the host-side permission table and "annotations are no grounds for authorization" follow s14 of [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) (MIT). The error categories and the rules for tool annotations were checked against the Tools section of the MCP specification 2025-11-25 / 2026-07-28, and the SDK differences against the official Python SDK's v2 migration guide (2026-10-20). The server, runner, experiments and use of the corpus were written by this project; none of the above code was copied.
