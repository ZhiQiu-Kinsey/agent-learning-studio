# A2A and delegation across processes (`a2a-delegation`)

English · [简体中文](README.zh-CN.md)

In the earlier lessons tools are functions, and MCP moved a function into a separate service. This lesson goes one step further and hands a **task that has state** to an agent in another process. The front-desk agent of the Bluestone Library (the delegating side, inside the runner) cannot read the service handbook; the handbook belongs to the reference checker (the remote agent, another process started by `worker.py`). The runner uses the official `a2a-sdk` to read its Agent Card (capability discovery), sends a message that creates a task, follows the task through `SUBMITTED → WORKING → COMPLETED`, collects the artifact and then accepts it itself. The four exercises are a normal delegation, a timeout followed by a cancel, a remote failure, and a remote agent that reports completion with an incomplete result. The lesson is still `planned` and has only been verified offline; it has not been run against a real model.

## An important trade-off: the remote agent is a deterministic program

The remote agent is another process and cannot reach this run's `RunContext`. If it called a model, its requests would not be recorded and the key would have to be handed to the child process, which breaks two red lines: keys stay in the backend, and run data comes only from real events. So the reference checker **calls no model**. It uses BM25 search (reusing `lessons.lesson_keyword_retrieval.bm25` and the Bluestone handbook corpus of `lessons.lesson_document_loading`, imported and unchanged) plus one version rule: the current version replaces an old one and the replacement is noted in `superseded`. The delegating side's model is called through `RunContext.complete` as usual, so its requests and responses are recorded.

This is a teaching trade-off, not an A2A requirement: the protocol sees only the Agent Card, the task states and the artifact, and does not care whether the other side holds a model or rules. Section seven of the lesson text and the deep dive on keeping observation and credentials apart when the remote side has a model explain what was traded away. The platform has no capability yet for a child process to send model requests back through the parent, and this lesson does not build a channel around `RunContext`.

## Files

- `runtime.py`: the input model (`fault`, `deadline_seconds`) and the delegation session `Session`:
  - `discover` reads the Agent Card and checks for a JSONRPC interface, that the address in the card equals the address this run started, and that a skill accepts `application/json`;
  - `delegation_tool` turns the card's skills into the model's only tool, `delegate_task`;
  - `delegate` and `follow` send the message, read the stream and classify the final state;
  - `cancel_after_timeout` sends `CancelTask` at the deadline and reads the final state back with `GetTask`;
  - `accept` is the delegating side's acceptance of the result;
  - `_report` builds the lab report.
- `worker.py`: the remote agent. `ReferenceChecker.execute` puts events on the queue in the order SUBMITTED, WORKING, artifact, final state; `--fault slow|fail|partial` injects faults; `--locale` sets the language of the text it writes. It binds a free port on 127.0.0.1 itself and prints `PORT <n>` as its first line.
- `locales/zh_CN.py`, `locales/en.py`: the delegating side's system prompt, errors and report text; `locales/worker/`: the remote agent's Agent Card and status notes; `locales/fixture/`: the offline script's claims and answer templates.
- `fixtures.py`, `test_lesson.py`: the deterministic test model and the behavior tests (a real child process; both run languages; timeout, remote failure and incomplete result; bad proposals; a card that points elsewhere; the process reclaimed after a stop; the child gets no API key).
- Platform: `course/protocols.py` (`spawn_local_service`, `run_until_cancelled`, `safe_child_environment`).

## The four exercises

| Exercise | Fault parameter of the remote agent | What to look at |
| --- | --- | --- |
| Normal delegation | `none` | Agent Card → tool → message → Task (SUBMITTED) → several WORKING → artifact → COMPLETED → acceptance passes |
| Timeout, then cancel | `slow` (waits 60 seconds before starting), deadline 2 seconds | `CancelTask` at the deadline, then `GetTask` reads back CANCELED; no endless wait |
| Remote failure | `fail` | Final state FAILED with the other side's own line; the protocol works, no retry, no invented answer |
| Incomplete result from the remote agent | `partial` (checks only the first claim) | The state is COMPLETED, yet the delegating side's result check fails |

The default exercise question is the same sentence each time: “How many items can I borrow on a B2 research card, and what time does the library close on Sunday?” The model has to split it into one to three claims and hand them over together; each run may delegate only once.

## Evidence

- `lesson.a2a_message`: one event per A2A protocol object, with `name`, `method`, `direction` (`client_to_agent` / `agent_to_client`), `captured: "sdk_protobuf_message"` and `message`; objects that carry a task state also have `state`, and final states add `terminal: true`. `message` is the SDK's protobuf object exported with `MessageToDict` using the protocol's field names, **not the raw bytes on the wire**: there is no HTTP header and no JSON-RPC wrapper, and `method` is the protocol method name this lesson writes down from the SDK call.
- `lesson.a2a_process`: `started` for the remote process (process id, port, fault parameter, the names of the environment variables it received) and `stopped` (whether the port no longer accepts connections).
- `request`/`response`, `tool_call`/`tool_result`: the delegating side's model calls and the result of the delegation tool (with `ok: false` it carries an error type such as `DelegationTimeout`, `RemoteTaskFailed`, `IncompleteResult` or `RemoteUnavailable`). The remote agent has no `request` events because it calls no model.
- `lesson.report`: checks for discovery, connecting only to the address this run started, matching task numbers, a bounded wait, result acceptance, no secrets and the process being stopped; metrics for the delegation outcome, last state, state sequence, deadline, this side's model-call count, message count, process id and the source of the injected fault; and a table of the messages in time order.

## What to look at in the experiments

1. **Normal delegation: from Agent Card to artifact**: the Agent Card, the tool built from it, the message sent, the Task in SUBMITTED, WORKING with its progress notes, the artifact, the final-state flag, the task number check and result acceptance. The prediction asks how many `lesson.a2a_message` events the run records.
2. **Three failure paths: timeout, remote failure, incomplete result**: `CancelTask` and its reply, the bounded-wait check, the final-state flag, the three error types, the result check, the delegation outcome and the model's answer.
3. **The process boundary: the invisible inside and the keys it cannot get**: the environment variable names the child received, the no-secret check, this side's model-call count, the message table, the source of the fault and the closed port.

The offline fixture (`fixtures.py`) serves automated tests only: in the first round it proposes one `delegate_task`, and once the tool result is in it answers by quoting the passage ids that came back, or says plainly that the check failed. The service process, the A2A messages and the BM25 search all really run; only the model's decisions are scripted. The faults the fixture exercises are injected through the remote agent's start-up parameter and the report states the source. A real model may split the claims differently, and the conclusions are those of your own real run.

## Running it

```powershell
# Offline tests (deterministic model data; the remote process, the A2A messages and the search really run; about a minute)
.\.venv\Scripts\python.exe -m unittest lessons.lesson_a2a_delegation.test_lesson -v
# Start the remote agent on its own to see what it looks like (it prints its port first; Ctrl+C quits)
.\.venv\Scripts\python.exe -m lessons.lesson_a2a_delegation.worker --locale en --fault none
# Real runs once the lesson is open (they use model quota); --locale en runs in English
.\.venv\Scripts\python.exe scripts/run_live.py a2a-delegation delegate --url http://127.0.0.1:8765
.\.venv\Scripts\python.exe scripts/run_live.py a2a-delegation timeout --url http://127.0.0.1:8765
```

**Run language:** the text of both the delegating side and the remote agent comes from their own `locales/` catalogs; the remote agent receives the same catalog through `--locale`. Tool names, skill ids, protocol method names and state names are code and are the same in every language.

**Stopping and reclaiming:** the whole delegation session is wrapped in `run_until_cancelled`. When the learner presses stop, the current A2A call is canceled, the SDK cleans up, and then `with spawn_local_service(...)` exits: the child first receives a termination signal and is killed after 3 seconds. The runner then tries the port once more and records `port_closed` only if the connection fails. The child gets only the SDK's safe environment variables, so the API key is never passed on, and a test puts a fake key in the parent process to confirm that.

## References and attribution

The division into Agent Card, executor, artifact and event queue, and the split of work between MCP and A2A, follow the `11-agentic-protocols` lesson of Microsoft AI Agents for Beginners (MIT). Collaboration without shared context, communication and control between agents (status queries, graceful and forced termination, cascading cancellation), cross-organization A2A and the multi-agent failure modes follow chapter 10 and the “collaboration tools” section of chapter 4 of *Understanding AI Agents in Depth* (深入理解 AI Agent), and the message envelope of `chapter10/parallel-web-research/message_bus.py` ([bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book), Apache-2.0). Task states, cancellation semantics (`TaskNotCancelableError`), `contextId`, polling and push were checked against the A2A specification (a2a-protocol.org, Apache-2.0), and SDK usage against `a2a-sdk` 1.2.x ([a2aproject/a2a-python](https://github.com/a2aproject/a2a-python), Apache-2.0). The runner, remote agent, experiments and corpus usage were written for this project and none of the code above was copied.
