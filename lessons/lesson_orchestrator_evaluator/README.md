# Orchestrator-workers and evaluator-optimizer (`orchestrator-evaluator`)

English · [简体中文](README.zh-CN.md)

The task is fixed: write one four-option multiple-choice question for each of the lessons messages-context, application-state and context-budget. The lessons are named by slug, not by lesson number, which changes as the syllabus grows. This lesson needs a real model connection.

| Preset | Model requests | Evidence |
| --- | --- | --- |
| Single call (baseline) | 1 | The format check of the three questions |
| Orchestrator-workers | 1 + number of subtasks | `lesson.plan` (each subtask is a plan item), worker requests sent in parallel with `branch`, `lesson.worker` |
| Evaluator-optimizer, up to 3 rounds / 1 round | 1–2 per round | `lesson.draft`, `lesson.review` (`source` is `evaluator` or `format-check`), the stop reason |

- The orchestrator's subtask list is validated first (at most 4, unique ids, lesson must be one of the three slugs); if it fails, `lesson.plan_error` is recorded and no workers are dispatched.
- A program checks the question format; a format problem goes straight back without asking the evaluator.
- The revision loop has four stop reasons: the review passed, the review output had the wrong format, the revision made no change, the iteration limit was reached. When the generator hands back the previous question unchanged (`unchanged` is true in `lesson.draft`), the evaluator is not asked again and the loop stops.
- Every call goes into the ledger (`lesson.cost`): role, round, branch and the `total_tokens` the provider reported; when it was not reported, the ledger says so and does not estimate.

**Run language:** this lesson runs in Chinese and in English. The key points of the three lessons, the task, the system prompts of the four roles, the format problems, the stop reasons and the report text are in `locales/zh_CN.py` and `locales/en.py`; lesson slugs and review verdicts (pass, revise) are code and the same in every language, while the role names in the ledger follow the run language. The web page picks the language from the UI language, and every run record states the language it ran in.

Passing the format check does not mean a question is good; judge quality by reading it. `fixtures.py` serves automated tests only; in it the evaluator always asks for a revision the first time, and the usage numbers are scripted.

The two patterns follow `patterns/agents/orchestrator_workers.ipynb` and `evaluator_optimizer.ipynb` in [claude-cookbooks](https://github.com/anthropics/claude-cookbooks) (MIT). The original runs the workers one after another and its revision loop has no iteration limit; this lesson runs the workers in parallel, limits the revision loop, and stops early when a revision makes no change. The task, format checks and experiments are written by this project.

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_orchestrator_evaluator.test_lesson -v
```
