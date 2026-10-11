# Task goals and acceptance (`task-contract`)

English · [简体中文](README.zh-CN.md)

## Running it

This lesson does not call a model. It runs entirely on your machine and needs no model key. Open the lesson on the web page, pick a preset and run it: the lab report on the right shows the checks, and you can expand the events to see the raw records. Replay only reads what was recorded.

| Preset | What happens | Verdict |
| --- | --- | --- |
| Normal | Computes 19 + 23; the claim references this result | passed |
| Claim only, no evidence | Calls no tool and claims 42 directly | failed |
| Evidence present, wrong result | Computes 19 + 22 and honestly reports 41 | failed |
| Claim and evidence disagree | Computes 19 + 22 but claims 42 | failed |
| Goal loop with a limit | Attempt 1 has an injected fault and the validator writes down why; attempt 2 redoes the task | passed with a limit of 3, failed with a limit of 1 |

Everything except "Normal" is a fault injected by the runner, not a model mistake. The question box holds a learner note: it goes into the report and does not change the task.

**Run language:** this lesson runs in Chinese and in English. The task card, the checks and the report text are in `locales/zh_CN.py` and `locales/en.py`; the exercise questions and the executor's completion claim are written per language in `lesson.json`. The web page picks the language from the UI language, and every run record states the language it ran in.

## Reading the source

The task card is `task_card` in `locales/zh_CN.py` and `locales/en.py`; it defines the scope, the evidence and the stop condition. `add_numbers` really runs in Python. `verify` in `runtime.py` uses only the claim's `evidence_ref` to find the call and the `tool_result` recorded in this run, then checks their arguments and value against the task card and the value against the claim. The goal loop publishes `lesson.goal_check` for each attempt and stops on a pass or at the limit.

Offline tests:

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_04_task_contract.test_lesson -v
```

## Limits and references

This lesson reads no external paths and keeps no long-term state. It only proves the acceptance logic for one fixed local case. The fix in attempt 2 of the goal loop is a fixed script; whether a real model corrects itself from the reasons has to be tested with real runs in the lesson "Goal loops and give-up conditions". Source scope and pinned commits: [source record](../../docs/architecture/chapter2-sources.md).
