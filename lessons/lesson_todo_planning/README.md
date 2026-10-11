# Planning: a TODO list and status reminders (`todo-planning`)

English · [简体中文](README.zh-CN.md)

The task is fixed: "look up the review points of the three lessons messages-context, application-state and context-budget, and save them with their point IDs on a review card". The tool arguments name the three lessons by slug, not by number, because display numbers change with the curriculum. This lesson needs a real model connection. The three conditions use the same model, the same task and the same acceptance check:

| Preset | Tools | Harness reminder |
| --- | --- | --- |
| No TODO | `lookup_note`, `save_card` | none |
| TODO, no reminder | plus `todo_write` | none |
| TODO, with reminder | plus `todo_write` | after `reminder_after` rounds in a row without a successful `todo_write` update, a user reminder is appended after this round's tool messages |

- `todo_write` replaces the whole list; when the checks pass, the version goes up by one and `lesson.todo` is published (the complete list and the diff).
- The harness reminder also publishes `lesson.harness_injected` with `source` set to `harness`, to tell it apart from what the model or the user said.
- `verify_card` looks only at the review card and the real `lookup_note` results of this run; the model's last claim and the done items on the list go into the report but do not count toward the verdict.

Each condition runs once, which is not enough to compare completion rates. `fixtures.py` serves automated tests only; "the no-TODO group skips the context-budget lesson" is written by its script and stands for no real model.

**Run language:** this lesson runs in Chinese and in English. The task, the system prompt and the list rules, the text of the three review points, the tool descriptions and errors, the reminder and the lab report are in `locales/zh_CN.py` and `locales/en.py`. Tool names, parameter names, statuses (pending, in_progress, done) and point IDs are code and the same in both languages. The web page picks the run language from the UI language, and every run record states the language it ran in.

The `todo_write` rules and the "remind after a few rounds without an update" approach follow s03 (TodoWrite) of [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) (MIT); the tools, reminder text, acceptance check and experiments are written for this project.

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_todo_planning.test_lesson -v
```
