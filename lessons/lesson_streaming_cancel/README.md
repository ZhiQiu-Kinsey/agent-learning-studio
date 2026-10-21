# Streaming and cancelling (`streaming-cancel`)

English · [简体中文](README.zh-CN.md)

## The question of this lesson

A model answer can arrive in pieces. The program receives and records them as they come, and then three things that look alike have to be told apart: the **user presses Stop**, the **client disconnects** (only the connection that reads events closes) and the **backend really ends**. The lesson answers five questions:

- what a streamed response is (chunks, the `data:` lines of SSE, the usage chunk, `[DONE]`) and why the time to first token matters more to a reader than the total time;
- how the chunks are assembled into one answer, and in what ways the assembled response differs from a non-streamed one (it is assembled by the platform; it is not the response body the provider sent);
- what a cancel request does: no new chunk is recorded after it, chunks that had arrived but were not handed to the run are counted in `discarded_after_cancel`, and `done` records the reason;
- why a client disconnect does not stop the run, and why the final state is whatever the backend's `done` says;
- what to do with the half text a stop leaves behind: it is marked incomplete, it is checked by the program, and it is not put back as a finished assistant message.

The lesson calls a model in every exercise. Nothing in it is a sandbox or runs model-written code.

## The task and the numbers

Every exercise asks the model for a numbered list (items 1 to N, one line each, one or three sentences per item) about one round of an Agent loop. The task is plain on purpose: Python can check whether a list is whole (numbers 1 to N, each once, every line ends at a sentence end), so a cut-off answer is judged by the data and not by how fluent it sounds.

The time to first chunk (`first_chunk_ms`), the time to first token (`first_token_ms`) and the total time come from the platform's own clock in this process, from just before the request is sent. Nothing is estimated and the page types nothing out letter by letter. The one exception is the non-streamed side of the comparison: `context.complete` returns only the body, so the runner times that call itself and the report says so. A usage the provider did not send is written "not reported", never 0.

## File tour

| File | Content |
| --- | --- |
| `runtime.py` | The runner: four scenarios (`compare`, `long`, `stop`, `continue`), the stop function `stop_at` and the two continuation requests |
| `reports.py` | The `lesson.report` of every scenario, and the answer the runner writes itself; every number is read from the platform's measurements or from a check |
| `analysis.py` | Pure checks: numbered items, where a cut landed (`analyse_partial`), the two merge rules, the numbering check, response shapes |
| `locales/` | Runtime text, one catalog per language; `locales/fixture/` serves only the test fixture |
| `fixtures.py` | The offline test model: a scripted stream with small sleeps between chunks, and the non-streamed and continuation replies |
| `test_lesson.py` | Behavior tests: the analysis, every exercise in both languages, a stop mid-stream, and the real run path (stop button, closing the event stream) |
| `course/execution.py` | Platform code, shown in the code view because the lesson is about it: `complete_stream` and `StreamResult` |

## Platform calls and events

The runner calls `context.complete_stream(body, round, stop_when=...)` and `context.complete` and writes only `lesson.report`; the stream events are the platform's. The request body carries no `stream` field of the lesson's own: the platform adds `stream: true` and `stream_options: {include_usage: true}`.

| Event | Meaning |
| --- | --- |
| `request` | With `data.stream: true` for a streamed request |
| `response_delta` | The chunks received since the previous event, unchanged; the first chunk is alone, later ones merge by time or count; `chunk_range` and `received_ms` locate them |
| `response` | The body the platform assembled from the chunks, and `data.stream`: `status`, `chunk_count`, `first_chunk_ms`, `first_token_ms`, `done_marker`, plus `stop_reason` (a stop by the lesson) or `cancel_reason` and `discarded_after_cancel` (a cancel) |
| `lesson.report` | The lab report: checks, metrics and a table. A cancelled run has none, because the code after a stop does not run |
| `done` | The backend's final state; `cancel_reason` after a stop, `client_disconnects` after the event stream was closed |

## Exercises

| Exercise | What to look at |
| --- | --- |
| Streamed and not streamed, side by side | The same request is sent twice (rounds 1 and 2); the table puts the first chunk, the first token, the total time, the finish reason, the usage and the message shape side by side |
| Long output: stop and disconnect | A long list; you run it three times: do nothing, press "Stop run", press "Disconnect the event stream" and reconnect |
| The program stops after chunk N | `stop_when` ends the stream after the stop point (`stop_after_chunks`); the result is `stopped`, with no finish reason and no usage |
| The next round after an incomplete answer | After the stop, the cut text goes back two ways (rounds 2 and 3) and the merged lists are checked |

All four need a real model connection. The offline test mode accepts only the preset inputs of an exercise. In a real run you can edit the parameters: the scenario, the number of list items, the length of an item and the stop point.

## How to run

Offline tests (deterministic stream data; the checks and the platform's stop path really run):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_streaming_cancel.test_lesson -v
```

A real run: start the service, pick this lesson in the web page and configure a model connection, or use the command line:

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py streaming-cancel stream-vs-block --url http://127.0.0.1:8765 --locale en
```

The stop and disconnect arms need hands: start `long-stream` in the web page, press "Stop run" or "Disconnect the event stream" while text is arriving, and read the `response` and `done` events afterwards. The result of a real run depends on the model and the provider (how long the answer is, how the chunks are cut, whether a usage chunk is sent). The text of the lesson does not presume a real run's result and only describes how to check one from the events. The offline fixture serves tests only and the web page has no entry for it.

## What the experiments show

- **Streamed and not streamed**: `first_token_ms` against the streamed `duration_ms` is how much earlier the reader sees the first word; the `shape_match` check compares the role, the text and the finish reason of the two first messages, and the report lists the top-level fields that exist on one side only (for example `object` on the non-streamed response). One sample each, streamed first: nothing here is the provider's latency level.
- **Cancelling part-way**: the same exercise ends as `completed` after nothing, `cancelled` with a `cancel_reason` after a stop, and `completed` with a `client_disconnects` after a disconnect and reconnect. In the stopped run the assembled content holds only what arrived before the stop, `finish_reason` is empty and `discarded_after_cancel` tells how many chunks had arrived but were not recorded.
- **A partial result in the next round**: a stream stopped by the program has `stop_reason: lesson`, an empty finish reason and no usage; the two continuations differ in the request they send and in the merge rule, and the report checks both merged lists with the same rule.

## Boundaries

- A stop ends the receiving, not the provider's generation. The platform closes the upstream connection when the next chunk arrives or the network times out; whether the provider keeps writing or billing is not visible, and usage is not reported for a stopped stream.
- Stopping is cooperative: the loop of `complete_stream` looks every 0.05 seconds. A stopped run can publish nothing, so it has no report; what it received is in the platform's `response` event.
- The numbering check proves structure, not content: it cannot see a garbled line, such as a rewritten sentence glued straight after half a sentence.
- Only a chunk the platform recorded counts as received. A `stopped` stream also drops chunks queued but not handed to the run, and the platform does not count them (only a cancel records `discarded_after_cancel`).
- In the offline script the "glued on as it is" continuation is written in advance to restart the cut item on a new line, so that the check has something to catch. A real model may continue cleanly and then the same check passes.

## References and credits

The cancellation-based handling of events, the idea that a half-written output is not a legal prefix to feed back, and the way a speech system marks the turn that was interrupted follow chapter 6 and `chapter6/streaming-speech/interruption_manager.py` of Understanding AI Agents ([bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book), Apache-2.0); the streaming advantage and the first-token delay follow its chapter 2. The latency metric follows `10-ai-agents-production` of [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners) (MIT), and typed streaming events are shown in `extended_thinking` of [Claude Cookbooks](https://github.com/anthropics/claude-cookbooks) (MIT). The SSE format and `stream_options.include_usage` were checked against the Alibaba Cloud Model Studio streaming guide and OpenAI's chat completions streaming reference. The runner, the checks, the numbered-list task and the experiments are written for this project, and no code of the reference projects is copied.
