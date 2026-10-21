# Reliable tools, retries and idempotency (`reliable-tools`)

English · [简体中文](README.zh-CN.md)

Tools time out, run into someone else's lock, and sometimes succeed at a write whose result never comes back. This lesson answers three questions: which failures are worth retrying, how far retries may go, and how to make sure a retry never makes one write take effect twice. This lesson calls no model.

**Status:** `available`. This lesson calls no model. Its exercises were run once in each run language through the real run path on 2026-10-21 ([verification record](../../docs/verification/live-runs-2026-10-21.md)); no real-model verification applies.

## The tools and the faults

Every run creates a practice-submission store (SQLite) and an outbox folder in a throwaway temporary directory. Real runs and offline test mode run the same code from the same starting point: learner `learner-a` has 3 grading credits, `learner-b` has 0.

| Tool | Read or write | What it does |
| --- | --- | --- |
| `read_account` | read only | looks up credits left and active submissions |
| `submit_practice` | write | takes 1 credit and records 1 submission; may carry an `idempotency_key` |
| `write_outbox` | write (safe to repeat) | writes the answer as `outbox/<id>.json`; writing the same submission twice still leaves one file |
| `cancel_submission` | write (safe to repeat) | the compensation for `submit_practice`: refunds the credit and marks the submission `cancelled` |

The runner makes the faults on purpose, and each one is preceded by a `lesson.fault` event whose `source` is `fault_injection`:

- `store_locked`: another connection runs `BEGIN EXCLUSIVE` on the database, so the tool really waits out its limit (`timeout_ms`) and raises `StoreTimeout`;
- `outbox_locked`: someone else's lock file sits in the outbox, so `write_outbox` really finds it busy and raises `OutboxBusy`;
- `response_lost`: the tool really runs and commits; its result is dropped on the way back and the caller gets `ResponseLost`.

## Files

| File | Contents |
| --- | --- |
| `retry.py` | the `CATEGORIES` table, `classify`, `decide`, `backoff_delay` (exponential backoff with jitter), `call_with_retry` (attempt limit and time budget; one `lesson.retry` per failure) |
| `store.py` | `PracticeStore`: the four tools, the `operations` idempotency table, `snapshot` (reads the database and the outbox directly) |
| `faults.py` | `FaultInjector`: sets up faults by operation and attempt number and emits `lesson.fault` |
| `runtime.py` | the flow and report of the four exercises; `run(context)` is the entry point |
| `locales/` | tool errors, report text and the answers the program writes, in Chinese and English |
| `test_lesson.py` | behavior tests: real SQLite and file I/O, real lock timeouts, an injectable clock (backoff waits never really sleep) |

## Exercises

| Exercise | What it does | Where to look |
| --- | --- | --- |
| Read-only query: locked twice | the first two queries hit a locked database; after backing off, the third succeeds | `wait_ms` in `lesson.retry`; two `StoreTimeout` rows of about 200 ms each in the report table; the check "the store is identical before and after the retries" |
| Error classification: which failures are worth retrying | a nonexistent exercise, a learner with 0 credits, a submission and an outbox write that each meet a lock on the first attempt | the first two have `decision` `stop`, the other two succeed after a `retry`; the store holds 1 submission and 1 file |
| A write takes effect, its result is lost | three fresh stores, one fault: blind retry, stop when unknown, retry with an idempotency key | the three `lesson.storage` events count 2, 1 and 1 submissions; the tool result in round 3 has `replayed` set to true; the key in the `operations` table |
| Two-step write: failure halfway and compensation | step 1 writes the store, step 2 keeps finding the outbox held, gives up after 4 attempts and compensates | `cancel_submission` in round 3; status `cancelled`, 3 credits and no file in `lesson.storage`; final status "not completed, compensated" |

The structured inputs can be changed in the lab: set `locked_attempts` to 6 to see the attempt limit, lower `budget_ms` and raise `base_delay_ms` to see the time budget stop first, set `outbox_busy_attempts` to 1 to see both steps complete. The question box is a learner note and only goes into the report.

## Boundaries

- This lesson's `StoreTimeout` clearly happens before the transaction starts, which is why even a write can be retried; timeouts of remote calls usually have to be treated as outcome unknown.
- The jitter uses a fixed seed only so that the same inputs can be reproduced; with a single caller, this lesson cannot show jitter spreading out many callers.
- The idempotency records live in the same SQLite file as the business data, which is what lets one transaction hold both; how a remote service keeps keys, and for how long, depends on that service.
- This lesson does not show a failing compensation; the report only reserves "partly completed, compensation failed".

**Run language:** this lesson runs in Chinese and in English. Tool errors, report labels and values and the answers the program writes are in `locales/zh_CN.py` and `locales/en.py`; tool names, argument names, event names and error class names are code and the same in both languages.

## How to run

Offline tests (real tools, real locks, backoff waits through an injectable clock):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_reliable_tools.test_lesson -v
```

Run it in the web lab or with `scripts/run_live.py reliable-tools <exercise>` (it calls no model and uses no model quota).

References: *Understanding AI Agents in Depth* (深入理解 AI Agent), chapter 4, idempotency and cancellation semantics under "execution tools", and chapter 5, "faults and error recovery"; Microsoft AI Agents for Beginners `04-tool-use` and `06-building-trustworthy-agents`; the backoff retries in Learn Claude Code `s15_integrated_harness`; the SRE incident response agent in Claude Cookbooks (separate constraints for read and write tools). The code and experiments were written for this project.
