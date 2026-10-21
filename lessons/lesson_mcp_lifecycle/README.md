# MCP connection lifecycle and several services (`mcp-lifecycle`)

English · [简体中文](README.zh-CN.md)

The previous lesson (`mcp-basics`) connected one MCP service. Here the host keeps two separate service processes connected at once: a catalog (`catalog`) and a loan desk (`loans`), and both have a tool called `search`. The runner connects to them with the official Python SDK (`mcp` 2.x) in `legacy` mode and you watch the five stages of a connection (start, the `initialize` handshake, `tools/list` discovery, calls, close). It gives tools a service prefix, registers only the tools it means to offer, and lets a tool with side effects through only when the run explicitly allows it. Then it really kills the loan desk's process, and you see how calls fail, how reconnecting is limited, what the returning service has lost, what happens when a tool definition changed, and finally that no server process is left at exit. The three local exercises call no model; the agent exercise needs a real model connection. The lesson is still `planned` and has been verified offline only; no real-model run has been made.

## The two services

Both services are stdio processes written with `MCPServer`, started by the runner as `python -m lessons.lesson_mcp_lifecycle.<module> --locale <language>`; tool descriptions and business errors come from `locales/servers/`.

| Service | Tools | Registered by the host |
| --- | --- | --- |
| Catalog `catalog_server.py` | `search(query, limit)`, `get_book(book_id)`, `service_info()` | `search`, `get_book` (read-only) |
| Loan desk `loans_server.py` | `search(member_id)`, `register_loan(book_id, member_id)`, `purge_loans()`, `service_info()` | `search` (read-only), `register_loan` (write); `purge_loans` and `service_info` are not registered |

- Loan records live only in the loan desk's process memory, numbered from `L-0001`; after a restart the records are empty.
- `--variant v2`: `register_loan` gains a required `due_days` argument (7–30) and a `renew_loan` tool appears; this shows a returning service whose definitions changed.
- `--fault exit-on-start | hang-on-start`: fault injection, used for restarts only. The process really starts and then exits at once, or stays alive without reading standard input.
- `service_info` reports the process id, the number of loans and the **names** (not values) of the environment variables the process received. The host uses it to confirm a connection, check process reaping and verify that no key reached a child.

## Four exercises

| Exercise | Model | What it does |
| --- | --- | --- |
| Two services: handshake, names and permissions (`lifecycle`) | none | Connect both services; probe with `catalog__search` and `loans__search`; try three calls beyond permission (the bare `search`, the unregistered `loans__purge_loans`, `loans__register_loan` while writes are off); close and check the processes |
| The loan desk crashes: the second reconnect works (`crash-recover`) | none | Register one loan → the runner sends `SIGKILL` to the loan desk → a second write during the disconnect (-32000) → reconnect within the limit (the first restart is injected with `exit-on-start`, the second works) → look up loans (`count` is 0) → submit both writes again (neither is resent) → close and check processes |
| Reconnect timed out, and the service came back changed (`crash-changed`) | none | The same, but the first restart is injected with `hang-on-start` (waits the full 5-second read timeout, -32001), and the second connection reaches v2: the recheck finds `register_loan` changed and `renew_loan` added, and the changed tool is held |
| A model borrows through two services, with a disconnect midway (`agent`) | yes | Each round the model sees only the prefixed tools that are usable now; `catalog__search` first, then `loans__register_loan`; once the registration is confirmed the runner kills the loan desk and the model's `loans__search` gets `ConnectionLost`; the host reconnects between rounds; at most 4 model calls |

Inputs (`lab.inputs`): `task`, `allow_writes` (off by default), `restart_fault`, `failing_restarts` (0–3), `max_reconnects` (0–3), `restart_variant` (`v1`/`v2`), `query`, `member_id`. Changing `max_reconnects` and `failing_restarts` shows the "attempts used up, give up" path.

## What the host does

- **One connection per service**: `Host` holds one `ServiceConnection` per service, each with an owner task (`_own`) that enters, uses and leaves `async with Client(...)`, so connections can close in any order.
- **Registration and prefixes**: `ServiceSpec` states the service identifier, module, expected `serverInfo.name`, registered tools with read or write kind, and the probe call; `qualified_name` / `build_routes` produce `<service>__<tool>` routes and fail on a clash. A tool that was discovered but not registered has no route.
- **Three gates**: is it registered; does this run allow writes (the allowlist from `available`); is the service connected now and the tool not on hold. A refused call sends no `tools/call` at all.
- **Write record**: each write is identified by "tool name + arguments" and has a state of sent, confirmed, rejected by the service or outcome unknown; confirmed and unknown-outcome writes are not sent again (`WriteNotRepeated`).
- **Reconnecting**: the old client is never reused; the limit holds for the whole run; backoff is 0.2, 0.5, 1.0 seconds; every new connection handshakes, discovers and calls `service_info` again and then runs an availability probe, and only a passing probe counts as connected; when the attempts are used up the state becomes gave up reconnecting.
- **Definition recheck**: after the first discovery the host records a fingerprint of each tool definition (name, description, input Schema) as a baseline; after a reconnect it compares, a changed registered tool is held (`ToolChanged`), and a new tool gets no permission.
- **Closing**: `close_and_count` closes every connection and then really checks the process ids that completed a handshake (`wait_gone`). The SDK reaps processes whose handshake failed, and the lesson's tests additionally scan `/proc` on Linux.
- **Keys**: a child inherits only the SDK's safe environment variables, `service_info` reports the variable names, and the report checks for secret-like names.

## Evidence

- `lesson.mcp_message`: every JSON-RPC message recorded by the platform's `recording_stdio`, with `server` (`catalog` / `loans`), `direction` and `captured: "sdk_session_message"`. It is the SDK's message object dumped with protocol field names, not raw bytes.
- `lesson.service_state`: every connection state change: connected (protocol version, `serverInfo`, capabilities, tool names, process id, recheck result), process killed (`cause: "fault_injection"`), connection lost (error code), reconnecting (attempt, injected fault), reconnect failed, gave up reconnecting.
- `tool_call` / `tool_result`: calls the runner makes carry `origin: course_program`; in the agent exercise they are the model's proposals, paired by call id, with the protocol-level `tools/call` between the two events.
- `lesson.report`: one per exercise. Handshake, names, permissions, write gate, keys, process reaping; disconnect, reconnect limit, data loss, no resend, recheck; the tools the model saw, that no call during a disconnect counts as a success, and the write record. A check that was not carried out has no `passed`.

## What to look at in the experiments

1. **Two services: handshake, names and permissions** (two arms: read-only, writes allowed): each service's handshake reply and `tools` capability; the four tools the loan desk lists; `search` becoming two names; three calls beyond permission refused at the host's layer alone; the write gate flipping with `allow_writes`; no keys; processes left. The prediction asks how many `lesson.mcp_message` events the run records.
2. **Disconnect: the write's outcome is unknown, and the data is gone after the reconnect** (three arms: the second reconnect works, both fail and the host gives up, a model borrows through two services): `stopped` → `lost` (-32000) → `ConnectionLost` → a failed reconnect → `count` of 0 after the reconnect → no resend; the give-up path; the disconnect result the model sees.
3. **The returning service has changed its definition** (two arms: v2, still v1): the read timeout -32001; the new Schema of `register_loan` in `tools/list` after the reconnect; the recheck result; the held write never sent to the server.

The offline fixture (`fixtures.py`) serves automated tests only: in the agent exercise the model always searches first, registers the first book, looks up the loans, and finally writes an answer that honestly mentions the disconnect. The server processes, the protocol messages, the process kill, the reconnects and the process reaping really happen; only the model's decisions are scripted. Whether a real model handles a disconnect honestly as the system prompt asks cannot be verified offline.

## Files

- `runtime.py`: the input model, `ServiceSpec` and `SERVICES`, `qualified_name`, `build_routes`, `fingerprint`, `Host` (connections, reconnecting, recheck, probe, `call`), the three tasks and the reports.
- `catalog_server.py`, `loans_server.py`, `serving.py`: the two MCP servers and what they share (command line, startup faults and the `service_info` content).
- `processes.py`: `stop_process` (kill a process with no grace period), `pid_alive`, `wait_gone` (cross-platform).
- `locales/zh_CN.py`, `locales/en.py`: the system prompt, structured errors and report text; `locales/servers/` holds the two servers' tool descriptions, catalog data and business errors; `locales/fixture/` holds the offline script's search term and answer.
- `fixtures.py`, `test_lesson.py`: the deterministic test model and the behavior tests (real child processes; both run languages; handshake order, names and permissions, disconnect and reconnect, state loss, no resend, the reconnect limit, the read timeout, a changed definition, reaping after a stop, no keys in children, input validation).
- Platform: `course/protocols.py` (`python_module_server`, `recording_stdio`, `run_until_cancelled`).

## Running

```powershell
# Offline tests (deterministic model data; the two MCP server processes, the kill and the reconnects really run; about a minute in all)
.\.venv\Scripts\python.exe -m unittest lessons.lesson_mcp_lifecycle.test_lesson -v
# Start one server on its own to see what it is like (it only reads standard input; Ctrl+C exits)
.\.venv\Scripts\python.exe -m lessons.lesson_mcp_lifecycle.loans_server --locale en --variant v2
# Real runs once the lesson is open; --locale en runs in English
.\.venv\Scripts\python.exe scripts/run_live.py mcp-lifecycle lifecycle --url http://127.0.0.1:8765
.\.venv\Scripts\python.exe scripts/run_live.py mcp-lifecycle agent --url http://127.0.0.1:8765
```

**Run language:** the system prompt, structured errors, report text and the two servers' tool descriptions, catalog data and business errors come from `locales/` according to the run language (the servers get the same catalog through `--locale`); tool names, argument names, service identifiers, state codes and protocol method names are code and the same in every language. Text the SDK generates itself (`Connection closed`, `Request 'initialize' timed out`) is English in both runs.

**Stopping:** the whole protocol session runs inside `run_until_cancelled`; on stop the host's task group is cancelled, the SDK closes each server process's standard input and terminates them after a grace period, the run is recorded as cancelled, and no process is left.

## What was not done

- No real-model run: the agent exercise was verified only with the offline script, and the lesson stays `planned`.
- Only the stdio transport was exercised; sessions, resumption and authentication of Streamable HTTP are described in the lesson text from the 2025-11-25 specification and were not run.
- The SDK's `ClientSessionGroup` and `listen(tools_list_changed=True)` in the newer protocol mode were only read as interfaces and not run against this lesson's services.
- A process whose handshake failed has no process id, so the process-reaping check does not cover it.

## References and credit

The host's division of work across several services, the three server risks, tool shadowing, on-demand exposure and per-service environments draw on chapter 4 of *Understanding AI Agents* (深入理解 AI Agent) and its `chapter4/docker-compose.yml` and `DOCKER_DEPLOYMENT.md` ([bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book), Apache-2.0); the one-to-one connection of host, client and server draws on `11-agentic-protocols` of Microsoft AI Agents for Beginners (MIT); the `mcp__{server}__{tool}` prefix, the collision check after renaming and the host permission table draw on s14 of [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) (MIT); MCP as one tool interface and the smolagents import example draw on Hugging Face Agents Course units 1 and 2 (Apache-2.0). The statements about lifecycle, capability negotiation, shutdown order, timeouts and transports were checked against `basic/lifecycle` and `basic/transports` of the MCP specification 2025-11-25. The servers, host, fault injection, experiments and tests were written for this project, and none of the code above was copied.
