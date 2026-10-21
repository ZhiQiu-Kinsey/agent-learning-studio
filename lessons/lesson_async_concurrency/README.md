# Parallelism, timeouts and a concurrency limit (`async-concurrency`)

English · [简体中文](README.zh-CN.md)

This lesson answers one question: when several things have to happen at once, how do you decide which ones can run together, how do you avoid overwhelming the provider, and how do you face a slow task, a failure or a cancel without leaving half-finished, unclaimed work behind? The job is a small review sheet: read four lesson notes (a local tool with a delay), have the model squeeze each note into one sentence, then assemble the sentences into a sheet. The lesson refers to other lessons by slug, never by a lesson number that changes with the curriculum. Three of the scenarios need a real model connection; the `dependency` scenario does not call a model.

## How it works

The whole mechanism is split into four files, each doing one thing:

- **Dependencies are read from references (`graph.py`).** When a task needs another task's result, its arguments hold a `Ref(task, field)`. `Task` finds every `Ref` in its arguments when it is created, which gives the tasks it depends on; `levels` then computes the levels, and only tasks on one level are independent and may run together. A cycle, a reference to a task that does not exist and a duplicate task id are all refused. `critical_path_ms` computes the longest dependency chain from measured durations: the lower bound of any parallel schedule.
- **The scheduler (`scheduler.py`).** Every task is one asyncio task: it waits until its dependencies have an outcome, then for a free slot of the semaphore, creates its timeout only after the slot is granted, and then hands the blocking work to a thread the scheduler starts itself. The slot comes back only when the thread has really ended; a model request that was already sent cannot be recalled, so it still counts as holding the slot. A watcher coroutine looks at the clock and the Stop button every 10 ms; the Stop button, the overall deadline and the failure policy all go through one entry point, `cancel_all`. Every task ends in one outcome: done, failed, timed out, cancelled or skipped, each with a reason.
- **The local tools (`tools.py`).** `read_note` reads one note; it waits on the stop signal instead of sleeping, so a stop returns within milliseconds. The wait comes from the call argument `delay_ms` (injected), the note is real. A locked note (`lock`) fails after a part of the delay. `build_sheet` assembles the sheet; with missing input it returns a structured error, and when partial results are allowed it returns a sheet that marks itself `complete` false.
- **The runner (`runtime.py`).** One run goes through the same job several ways within one scenario (one scheduler per variant) and then writes a comparison table. Each variant has its own `lesson.graph` and `lesson.task` events, possibly a `lesson.stop`, and a report with checks, metrics and a task table.

## Exercises

Each exercise is a scenario: one run goes through the same job in several ways, so the comparison comes from one run under one load.

| Exercise | Scenario | Variants | What to look at |
| --- | --- | --- | --- |
| Dependency graph and scheduling order (no model) | `dependency` | serial, by dependency, ignoring dependencies | the levels in `lesson.graph`; in the ignoring variant the sheet gets empty values and returns `MissingInput`; the dependency check says it started before the reads ended; the three wall-clock times |
| Concurrency limit 1, 2 and 4 | `limits` | limit 1, 2, 4 | peak concurrency recomputed from timestamps equals the limit; 4 model calls per variant; wall-clock about 4 : 2 : 1; request `branch` carries the variant name |
| Timeouts and the overall deadline | `timeouts` | slow with no timeout, task timeout, overall deadline | `TaskStopped`; the summary that depended on the timed-out read is skipped (`blocked_by`); the sheet marks itself incomplete; `lesson.stop`; tasks that only stopped after the wait was given up (`late_ms`) |
| Carry on or cancel everything after a failure | `failure` | carry on, cancel all | `NoteLocked`; carrying on makes 3 model calls, cancelling all makes 0; `lesson.stop` records who triggered it and what was running |

Pressing Stop and disconnecting the event stream must be triggered by hand; the steps are in the lab's "manual checks". After a stop the platform accepts no more lesson events, so the evidence is the `tool_call` without a `tool_result` and the `cancel_reason` in the `done` event.

## Files

| File | Contents |
| --- | --- |
| `graph.py` | `Ref`, `Task`, dependency levels, longest dependency chain |
| `scheduler.py` | the asyncio scheduler: dependencies, concurrency limit, task timeout, overall deadline, failure policy, cancel, thread registry |
| `tools.py` | `read_note` (injectable delay, lockable, listens to the stop signal) and `build_sheet` (errors on missing input or marks itself incomplete) |
| `runtime.py` | the custom runner: scenarios and variants, the task list, events, each variant's report and the comparison table |
| `locales/` | Chinese and English runtime text: notes, prompts, task and report text; `locales/fixture/` holds the summaries of the offline fixture |
| `fixtures.py` | deterministic answers for automated tests only; the web page has no entry for it |
| `content.json`, `content.en.json`, `lesson.json`, `lesson.en.json` | the teaching content and the manifest, with their English layers |
| `test_lesson.py` | behaviour tests: the tools and the scheduler really run (real waits, threads, timeouts and cancels), both run languages |

**Run languages:** the lesson runs in Chinese and English. Notes, the summary prompt, tool errors, task reasons and report text are in `locales/zh_CN.py` and `locales/en.py`; task ids, field names, status codes and event names are code and are the same in every language.

## Running

Offline tests (the fixture gives deterministic summaries; the tools, threads, timeouts and cancels all really run, with very short real delays and no virtual clock):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_async_concurrency.test_lesson -v
```

A real run needs a model configured first (environment variables or `local_config.py`), then the server:

```powershell
.\.venv\Scripts\python.exe run_web.py
.\.venv\Scripts\python.exe scripts/run_live.py async-concurrency concurrency-limit --url http://127.0.0.1:8765 [--locale en]
```

A real run uses model quota: the limits scenario sends 12 summary requests, the timeouts scenario at most 11 and the failure scenario 3. The lesson is still a planned draft: it has been verified offline only, never with a real model.

## What this proves and what it does not

- Times come from the backend's monotonic clock, but the delays are injected: real slow tools and real providers vary, so the ratios are not general.
- Peak concurrency is recomputed from timestamps, which catches a slot given back too early; it cannot prove how many requests the provider is serving at once, because that side is out of sight.
- Cancelling only stops the waiting and what comes after: a tool hears the stop signal and quits within milliseconds; a model request already sent cannot be recalled, the thread can only wait for the response, and the provider still generates and meters it.
- "Ignoring dependencies" is a deliberately wrong schedule and appears only in the `dependency` scenario. In real systems an error from missing input is not always refused by the tool; some quietly use an old value.
- A concurrency limit does not replace dependencies: a limited number of slots only changes the order, it does not guarantee the results a task needs already exist (see the comparison in `test_lesson.py`).

## References

Ideas adapted, not copied text or code: *Understanding AI Agents in Depth* (Apache-2.0), chapter 6 on parallel versus serial work, cancel points and safe points, and chapter 10 on graceful termination, concurrency quotas and treating a timeout as a failure; claude-cookbooks (MIT), the async orchestration and latency examples (the number of concurrent helpers is a cost guard, cancel and `gather` in `finally`); AI Agents for Beginners (MIT), concurrency and backpressure; learn-claude-code (MIT), background tasks (one call gets exactly one result, process-group cleanup is not a sandbox). The job, the notes, the scheduler, the tools and the experiments are written by this project.
