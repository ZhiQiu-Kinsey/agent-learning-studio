# Human in the Loop, Checkpoints and Resume (`human-in-the-loop`)

English · [简体中文](README.zh-CN.md)

Pause before a step with a side effect (saving a model-written exercise into a local exercise bank) and wait for a person to approve, edit or reject; keep the execution position in checkpoints; after a restart or a crash that followed the write, resume from a checkpoint, look the operation id up in the bank first, and only then decide whether to write. The lesson needs a real model connection (one model call for the draft and one for the receipt). ## The problem

"Hooks and approval gates" (`hooks-approval`) lets a run stop at an approval point and wait for a person. But the wait happens inside one run: restart the service and that run is gone. This lesson answers three questions: how to save "where the run got to"; how an edit a person makes at the pause leaves a trace; and how to make sure that after a resume a write that already happened is not repeated. The answer keeps three things apart: the checkpoint stores the position, the approval travels with a digest, and "was it done" must be asked of the outside world.

**Status:** `available`. Every exercise was run once in each run language against a real model on 2026-10-21 (`claude-haiku-5-5`, one sample each; [verification record](../../docs/verification/live-runs-2026-10-21.md)). That is a dated record for one model, not a guarantee for other models.

## Files

| File | What it holds |
| --- | --- |
| `runtime.py` | Input model; `run` is a small state machine made of `draft_step` (the model drafts, the operation id is made, `drafted` is saved), `approve_step` (approval, checking the person's edit, `approved` saved), `commit_step` (checking the digest, look-then-write, `saved` saved) and `finish` (the receipt request, the reports, the answer); `stop_at` ends the first run after a step to simulate a process dying |
| `bank.py` | The exercise bank (SQLite, one folder per thread): the read-only `lookup_operation`, the appending `save_exercise` and the `exercise_problems` check; the table deliberately has no uniqueness constraint |
| `report.py` | `RunTrace` collects the facts of one run; two `lesson.report` events: "What the exercise bank holds" (read straight from the database) and "This run" (checks, metrics and the draft / approved / bank-row comparison table) |
| `locales/zh_CN.py`, `locales/en.py` | Prompts, tool errors, answers, report text |
| `locales/fixture/` | Templates the offline test model uses to write the draft and the receipt (tests only) |
| `fixtures.py` | Deterministic model and approver for automated tests only: the model writes a fixed draft for the topic and a receipt from the facts; the approver approves, and in `edit-state` also edits difficulty and title |
| `test_lesson.py` | Behavior tests: real bank writes, the three checkpoints, rejection and timeout, valid and invalid edits, the three stop points, one and many resumes, a blind resume writing two rows, a touched digest being refused, a checkpoint that disagrees with the bank, cancelling, no Chinese in English runs, and the resume through the platform API after reopening the run store plus `checkpoint_stale` |

The platform side is in `course/execution.py`: `request_approval` and `checkpoint`; the resume endpoint `POST /api/runs/{id}/resume` is in `server/app.py`; the event formats are in section 7 of `docs/architecture/event-envelope-v2.md`. The lesson does not use LangGraph's `interrupt`; the comparison is in a deep dive in the text.

## Exercises

| Exercise | Parameters | First run | Model calls |
| --- | --- | --- | --- |
| Normal flow: save after approval | defaults | draft, `drafted`, approval, `approved`, lookup, write, `saved`, receipt; business status `saved` | 2 |
| Pause after approval, restart and resume | `stop_at`=`before_save` | ends at `approved`, the bank has 0 rows; business status `suspended`; resuming from `approved` writes one row | 1, then 1 more after the resume |
| Crash after the write: resume without saving twice | `stop_at`=`after_save` | the write happened, the last checkpoint is still `approved`, the bank has 1 row; after the resume the lookup finds it and the status is `already_saved` | 1, then 1 more after the resume |
| Resume after a human edit | `stop_at`=`before_save` | change difficulty and title on the approval card; in the `approved` checkpoint `draft` and `approved` differ and `edited` is true | 1, then 1 more after the resume |

The counts come from offline test mode. In a real run you decide on the approval card on the page, and in "Resume after a human edit" you change a field yourself; if the model's draft has the wrong format the run ends as `failed` with the reason `bad_draft`.

## What to look at in the experiments

- **Confirming before the write, and editing by hand**: first guess how many `checkpoint` events the normal flow records (3); then see that the write call appears only after the approval, the `edited` flag and the two digests in `approval_resolved`, and the draft versus the approved version in the `approved` checkpoint.
- **Pausing, restarting and resuming**: see the business status `suspended` of the first run; press "Resume from “approved”" on the `approved` checkpoint (to get closer to reality, restart the backend first); in the resumed run look at "Resumed from", "Thread ID", "Model calls" and the check "The draft request was not sent again".
- **Crash after the write, resume without saving twice**: see the row id of the write tool and the rows in the bank; after the resume see "Operation id lookup before the write" say found and "Write" say not written; then set `resume_guard` to `blind` for a contrast: the same operation id gets two rows and the `written-once` check fails.

## Running it

Offline tests (deterministic model and approval data; the bank, the checkpoints and the resume endpoint are real):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_human_in_the_loop.test_lesson -v
```

In the tests a "restart" closes the run store and reopens it from the same path, so the new process can read only what is on disk; it is not a real process restart.

Real run: pick an exercise in the lab on the page, decide on the approval card when the run stops at the approval point, then press resume on a checkpoint in the events. From the command line (this produces model usage; `--ask-approvals` lets a person at the terminal decide the approval):

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py human-in-the-loop approve-save --url http://127.0.0.1:8765 --locale en --ask-approvals
```

The bank lives in `.runtime/human-in-the-loop/<thread id>/bank.sqlite3` (real runs) or the system temp folder (offline test mode); events and reports carry only file names and rows, never a local path. Each exercise was run once with a real model in both run languages on 2026-10-21, with real backend restarts and resumes for `restart-resume` and `crash-after-write` (see the verification record).

**Run language:** prompts, answers and report text live in `locales/`; status codes, checkpoint names, tool names and field names are code and the same in every language.

## References

The ideas of checkpoint and resume are compared with the Hugging Face Agents Course (Apache-2.0) `units/en/unit2/langgraph/building_blocks.mdx`; the two ways to idempotency and the two-phase pre-check then confirm follow chapters 4 and 6 of the book Understanding AI Agents (Apache-2.0); the journal that resumes by stable keys is compared with learn-claude-code (MIT) `s16_workflow_runtime`; human in the loop is compared with Microsoft AI Agents for Beginners (MIT) `06-building-trustworthy-agents`. LangGraph's `interrupt`, checkpoint storage and `update_state` follow the official LangChain documentation (checked 2026-10-21). The exercise bank, the checkpoint state design, the reports and the experiments were written for this project.
