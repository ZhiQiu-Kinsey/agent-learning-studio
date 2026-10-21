# Background jobs and scheduled triggers (`long-running-tasks`)

English · [简体中文](README.zh-CN.md)

## The question of this lesson

A slow check should not block the conversation. The model sends it to the background, gets a job id at once and goes on with other work; when the job ends, its result has to come back to the model in a later round, with its source and time. The lesson answers four questions:

- which tasks deserve the background, and what the start call returns (a job id and `running`, no result);
- when and in what form a result enters the conversation (before the next request, as one separate message that names its source);
- who judges at the end of every round whether the goal is done, impossible or still going, and how a used-up budget stops the run (the harness's goal check, which does not look at what the model says);
- how a job is cancelled, which terminal states and exit codes it can have, and what happens to the jobs still running when the run ends (all cancelled, no orphan threads); and, besides, how a scheduled trigger starts jobs again and again and what it does when the previous run has not finished.

All of this holds **inside one run**. A real product that keeps jobs and trigger rules across runs needs an external scheduler (the system's `cron`, a timer) or a persistent queue; this lesson builds neither.

## The task and the time

The inspection assistant does two things for the teaching assistant: verify the SHA-256 of 6 submission packs (`checksum_pack`) and count how many of 12 students passed (`grade_stats`). Two more jobs show failure and timeout: `late_import` (row 6 of the late-score sheet reads `8x`, so the import raises an error 6 seconds after every start) and `deep_scan` (scanning 8 shards takes 80 seconds against a default deadline of 40).

The jobs **really compute** on the threads of `executor.py` (SHA-256, a sum, a parse, a duplicate scan), but the durations they declare run on a **virtual clock**: a thread does not `sleep`, it parks on the clock until a given moment, and only the runner can move the clock. This makes the timeline of a run the same every time, so a controlled comparison is possible, and a test can advance 120 seconds without waiting. The events say `clock: "virtual"`. Seconds on the virtual clock are not measured durations.

## File tour

| File | Content |
| --- | --- |
| `runtime.py` | The runner: tools, the round loop (move the clock → inject → request → goal check), the report; the local flow of the `schedule` scenario |
| `executor.py` | `VirtualClock`, the background executor (threads, cancel, timeout, `shutdown`), exit codes |
| `jobs.py` | The real computation of the four jobs and their declared durations |
| `goal.py` | The goal check of every round: `ok`, `impossible`, `continue`, and the stop when the budget is used up |
| `scheduler.py` | A fixed-interval trigger and three overlap policies (`skip`, `queue`, `parallel`) |
| `locales/` | Runtime text, one catalog per language; `locales/fixture/` serves only the test fixture |
| `fixtures.py` | The offline test model: it reads its state from the history it is sent and copies values from the injected messages |
| `test_lesson.py` | Behavior tests of the executor, the scheduler, the goal check, the tools and every exercise |

## Tools and events

The model has five tools: `start_background_job` (returns an id at once), `check_job` (status and progress, and no result before delivery), `cancel_job`, `read_policy` (a quick synchronous lookup) and `submit_report` (sends the report; it only records, it does not judge).

| Event | Meaning |
| --- | --- |
| `lesson.background_job` | One phase of a job: `started`, `finished`, `injected`, `cancelled`; carries `finished_at`, `observed_at` and the exit code |
| `lesson.clock` | Each move of the clock: from which second to which, with the reason `round` or `idle_wait` |
| `lesson.harness_injected` | A message inserted by the harness: `background_result` or `goal_feedback`, with `source` naming where it came from |
| `lesson.goal_check` | The goal check at the end of every round: verdict, reason, state of each job; the check that ends the run carries `outcome` |
| `lesson.schedule_fire` | The decision for every due trigger: start, skip, queue, drop or refuse, with its reason and run id |
| `lesson.report` | The lab report: checks, metrics, the job table or the trigger table |

## Exercises

| Exercise | What to look at |
| --- | --- |
| Background jobs and result injection | Two jobs end separately and are injected in two rounds; before injection a result appears in no request |
| A failing job and a retry | The failure of `late_import` is injected with exit code 1, the retry fails again, and after 2 starts the goal is judged impossible |
| Tight budget: polling, cancelling and restarting | 2 polls, a cancel, a restart, the 5-round budget runs out, and the job still running is cancelled together (exit code 143) |
| Scheduled trigger: skip, queue, parallel with a cap (three exercises) | A 12-second job triggered every 5 seconds; the three policies skip, queue and refuse differently; no model is called |

The first three exercises need a real model connection; the last three are local exercises and need no key. The offline test mode accepts only the preset inputs of an exercise, so each overlap policy is its own exercise; in a real run you can edit the parameters directly. The parameters of the lab can be changed: the virtual seconds per round, the round budget, the cap on jobs running at once, the retry limit, and the trigger interval, the run length, the overlap policy and the parallel cap.

## How to run

Offline tests (deterministic model data; the jobs and the scheduler really run as usual):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_long_running_tasks.test_lesson -v
```

A real run: start the service, pick this lesson in the web page and configure a model connection, or use the command line:

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py long-running-tasks background-basic --url http://127.0.0.1:8765 --locale en
```

The result of a real run depends on the model: it may write the report without waiting for the results, poll again and again, or retry a different number of times than the script of this lesson. The text of the lesson does not presume a real run's result and only describes how to check one from the events. The offline fixture serves tests only and the web page has no entry for it.

## What the experiments show

- **Background jobs and result injection**: the difference between `finished_at` and `observed_at` in `lesson.background_job` is the number of virtual seconds a result lost on the way; the `round` of `lesson.harness_injected` is the round in which the model first sees the result; the `not_seen_early` check in the report takes each injected line and looks for it in the requests that were really sent, and its first appearance must be exactly the round that injected it. Change the seconds per round from 5 to 10 and see the injection move one round earlier.
- **Three outcomes**: the `lesson.goal_check` of every round has a reason; `impossible` requires some kind of job to have been started to the limit without success and none to be running; the check where the budget runs out carries `outcome: budget_exhausted`, and afterwards the report shows 0 live threads.
- **Overlap policy**: with the same 8 due triggers, `skip` starts 3 runs, `queue` starts 3 with 4 queued and 3 dropped, and `parallel` starts 6 and refuses 2; every due trigger has a `lesson.schedule_fire`.

## Boundaries

- The jobs are fixed built-in code and run no command generated by a model. Running model-generated commands needs an isolation plan first.
- Cancelling is cooperative: a thread cannot be killed from outside, and a job ends only when it sees the stop flag while parked on the clock. Steps already done and requests already sent cannot be taken back.
- After a run is stopped the platform accepts no more events, so the records of the cleanup cannot be published; reclaiming the threads is still guaranteed, and the tests count the threads after a normal end, an exit through an error and a stop.
- The goal check verifies only facts with a definite answer (job states, and whether the values in the report equal the results); it cannot judge an open-ended reply.

## References and credits

The background thread plus a notification queue that does not reuse the original call id, and the five-field expression, the delivery queue and the persistence boundary of scheduling, follow `s11_background_tasks`, `s12_cron_scheduler` and `s17_goal_loop` of [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) (MIT). The three ways of handling events in an event loop (cancelling, queued, parallel) and the idea of a task handle that carries asynchronous meaning follow chapter 6 of Understanding AI Agents ([bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book), Apache-2.0). Capped concurrency and backpressure follow `16-deploying-scalable-agents` of [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners) (MIT). The tools, jobs, virtual clock, executor, goal check, scheduler and experiments are written for this project, and no code of the reference projects is copied.
