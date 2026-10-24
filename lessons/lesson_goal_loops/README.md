# Goal loops and abandon conditions (`goal-loops`)

English · [简体中文](README.zh-CN.md)

This lesson answers one question: when should a loop that keeps trying stop, and who decides? The answer has three layers. At the end of every round an independent goal evaluation judges, by a completion condition written beforehand, whether to continue, finish or give up. The budget (rounds, model calls, time) and the abandon conditions (unreachable, the same failure repeating, no progress for several rounds) are written down before the run. And the outcome is one of three, complete, abandoned or budget exhausted, each with its reason and none passing for another. This lesson needs a real model connection.

The task is fixed: fill in a reading group notice card from four notes. The date comes from the schedule, the room from the booking receipt, the start time from the speaker's reply, and the fourth note is the minutes of the last session, whose date, room and start time have the right shape from the wrong source, put there to mislead. The notes are read with `read_note`. Neighbouring lessons are named by slug, not by lesson number, which changes as the syllabus grows.

| Exercise | Goal | Worker | Round limit | What to look at |
| --- | --- | --- | --- | --- |
| Reachable goal: complete within the budget | date, room, start time | careful | 5 | what each round read, how many checks passed, why it continued, and the last round judged complete |
| Unreachable goal: no contact phone in the notes | plus a contact phone | careful | 5 | after all four sources are read, cannot be completed, so abandoned; three checks passing still does not count as complete |
| Budget too small: progress, but the rounds run out | same as the first | careful | 2 | rounds used up, and the outcome is budget exhausted, not abandoned |
| The worker claims done and the evaluation fails it | same as the first | hasty: urged to say done in round 1 | 5 | the rounds where `status` and the verdict disagree; the reasons go back to the worker |

Besides the exercises, the lab bench lets you adjust seven parameters one by one: `goal`, `worker_style`, `max_rounds`, `max_model_calls`, `max_seconds`, `max_stall` and `repeat_limit`.

**Status:** `available`. Every exercise was run once in each run language against a real model on 2026-10-21 (`claude-haiku-5-5`, one sample each; [verification record](../../docs/verification/live-runs-2026-10-21.md)). That is a dated record for one model, not a guarantee for other models. With this model the 2-round arm and the hasty worker both finished in one round, so the budget and false-done exercises did not show their point.

## Mechanism

- **Completion condition** (`CRITERIA`): each field has the shape of a value (a regular expression) and a source note. The value must appear as written in the source, and that note must have been read in this run; a lucky guess does not count.
- **Goal evaluation** (`evaluate_goal`): reads only the notice card and what `read_note` really returned, never the worker's `status`. Three verdicts: `complete` (every check passes), `unreachable` (for some check all sources were read and none has a value of the right shape) and `continue` (everything else).
- **Abandon conditions** (`Progress` and `decide`): unreachable; the same failure (same items, statuses and values) for `repeat_limit` rounds in a row; passing checks failing to beat the best so far for `max_stall` rounds in a row.
- **Budget**: `max_rounds`, `max_model_calls` and `max_seconds`, checked only before a round starts; if fewer model calls remain than a round needs (at most `ROUND_STEPS`), no new round starts.
- **Order of decision**: the goal verdict first, then the abandon conditions, then the budget. So a completion in the last round stays a completion and is not recorded as budget exhausted.
- **Outcome**: complete, abandoned or budget exhausted. The final answer is assembled by the program from the outcome; abandoned and budget exhausted both say the goal was not reached, with the reason, the number of checks passing when it stopped and the current card.

## Events

| Event | Content |
| --- | --- |
| `lesson.task_card` | Sent before the run: goal, input scope, output, evidence requirement, abandon conditions and budget |
| `lesson.completion_claim` | The worker's card and `status` each round; a reply that cannot be read is recorded as `invalid` with a `parse_error` |
| `lesson.goal_evaluation` | One evaluation record per round: `evidence` (notes read and this round's card), `claim`, `verdict`, `checks`, `claim_agrees`, `progress`, `budget`, `decision`, `reason_code`, `reason` |
| `lesson.report` | The outcome, stop reason, passing checks, rounds, model calls, accumulated `total_tokens`, rounds with done, rounds where claim and verdict disagree, and the round-by-round table |

There are eight `reason_code` values: `goal_met`, `unreachable`, `repeated_failure`, `no_progress`, `max_rounds`, `max_model_calls`, `max_seconds` and `keep_going`. `total_tokens` adds up only what the provider reported; missing ones are written with their count as not reported, never estimated and never written as 0.

## Files

| File | Content |
| --- | --- |
| `runtime.py` | The custom runner: `CRITERIA`, `evaluate_goal`, `Progress`, `decide`, `Worker`, `run` |
| `locales/zh_CN.py`, `locales/en.py` | Runtime text: the notes, prompts, evaluation reasons and report text; field names, note ids and reason codes are code and the same in every language |
| `fixtures.py` | The deterministic model for offline tests: one fixed worker script per exercise, serving tests only |
| `test_lesson.py` | 27 behaviour tests: the evaluation rules, abandon conditions, budgets, cancellation, input validation and both run languages |
| `content.json`, `content.en.json` | The teaching content (Chinese source text and the English overlay) |
| `lesson.json`, `lesson.en.json` | The implementation manifest and its English overlay |

## Running

Offline tests (no key needed; the tools and the evaluation program really run, and the model answers come from the fixture):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_goal_loops.test_lesson -v
```

A real run needs a configured model (see `local_config.example.py`) and uses model quota. An automation agent should start its own port and leave 8765 alone:

```powershell
.\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 8813
.\.venv\Scripts\python.exe scripts/run_live.py goal-loops reachable --url http://127.0.0.1:8813 --locale en
```

Each of the four exercises was run once in each run language on 2026-10-21 and the lesson text was checked against what happened (see the verification record).

## What to look at in the experiments

1. **Continue, complete and give up** (reachable goal / unreachable goal): the task card's `failure` field; `notes_read` and `checks` in the first evaluation record; why the contact phone item (`field_contact_phone`) in the report did not pass; the outcome and the stop reason.
2. **Budget exhausted is not abandoned** (5 rounds / 2 rounds): the task card's `stop`; `budget` and `progress` in the evaluation record; the last row of the round-by-round table; a stop reason that names the rounds, not an abandon condition.
3. **The worker claims it is done** (careful / hasty): `status` in `lesson.completion_claim`; `claim_agrees`; the rounds with done and the rounds of disagreement; the failing checks.

## Limits

- The evaluation checks only the shape of a value and its source, not whether the notes are right; passing says only that the card agrees with the notes that were read.
- In the offline fixture what the worker reads, fills in and claims is scripted. Whether a real model can fix the card after reading the evaluation's reasons, and how many notes it reads at once, depends on a real run, and the lesson text does not presuppose it.
- The time limit is checked only before a round starts and is not a hard deadline; cost has no limit of its own, and model calls stand in for it.

## References and credit

The shape of the loop (an independent judgment at the stop boundary, the two verdicts `ok` and `impossible`, a cap on consecutive blocks) follows `s17_goal_loop` in [Learn Claude Code](https://github.com/shareAI-lab/learn-claude-code) (MIT). Stop conditions, layered validation and budget-capability curves draw on chapters 1, 7 and 9 of *Understanding AI Agents in Depth* ([ai-agent-book](https://github.com/bojieli/ai-agent-book), Apache-2.0). The reminder that self-assessment is only a reference draws on the 09-metacognition chapter of [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners) (MIT). The task, the notes, the program validator, the progress and repeated-failure rules, the split of outcomes and the experiments are written by this project, and no upstream code is copied.
