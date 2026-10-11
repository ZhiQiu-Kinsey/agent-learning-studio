# Application state and the run lifecycle (`application-state`)

English · [简体中文](README.zh-CN.md)

This lesson calls no model; it runs only local Python and needs no model connection. Three presets show completion with evidence, missing material and a used-up budget. The state machine really checks legal transitions, evidence and a result before completion, and a reason for every terminal state; `lesson.state` is the actual state snapshot of this run. Every run has its own run_id, and after it ends only the event replay keeps the evidence; this lesson has no persistence across runs.

Material keys match lesson slugs: `messages-context`, `application-state`, plus the nonexistent `missing`. The report is assembled in `_report`, and the Code scene shows only the state machine and the run flow.

**Run language:** this lesson runs in Chinese and in English. The material, step names, snapshot actions, terminal reasons, the state machine's errors and the report text are in `locales/zh_CN.py` and `locales/en.py`; the task goal `goal` has no default in code, and its preset is written per language in `lesson.json`. State names (`ready`, `running`, ...) and material keys are code and stay the same in both languages.

The walkthroughs are illustrations; go by `lesson.state` and `lesson.report` for the actual results. For the scope of the references, see `docs/architecture/context-state-sources.md`.

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_08_application_state.test_lesson tests.test_lessons_context_state -v
```
