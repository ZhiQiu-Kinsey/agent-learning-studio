# Plan-and-execute and replanning (`plan-and-replan`)

English · [简体中文](README.zh-CN.md)

The task is fixed: "write a weekly study report for learner lin", which needs the learning progress and the quiz score of each lesson. Scores have two data sources: `primary` always fails in this lesson (a controlled fault written into the runner) and `backup` works. This lesson needs a real model connection.

| Preset | Approach | Model requests |
| --- | --- | --- |
| Static plan | The planner writes one JSON plan; the executor follows it to the end and changes nothing on failure | planning 1 + report 1 |
| Replan after failure | When a step fails, the step statuses and the real error go back to the planner, which replaces only the steps not yet run; at most 2 revisions | planning 1 + revisions + report 1 |
| ReAct baseline | No plan; the model looks at each result before deciding the next step | 1 per step |

- The plan is checked before execution: step ids are unique, revised steps do not reuse an id from an earlier plan version, tools are on the allowlist and arguments are JSON objects. A plan that fails a check is recorded as `lesson.plan_error` and the run stops.
- Every step status change and every revision publishes `lesson.plan` (version, steps, `reason`, `diff`); the plan lens in the UI follows the replay position.
- All three groups use the same `verify`: progress and scores must come from successful tool results, and the report must state the real scores (keyword screen).

Each group runs once, which is not enough to compare how reliable the strategies are. A real model may pick `backup` right away, and then no revision happens. `fixtures.py` serves automated tests only.

**Run language:** this lesson runs in Chinese and in English. The task, the three system prompts (planner, report writer, ReAct), the execution status sent back to the planner, the tool descriptions and errors, the plan errors and the lab report are in `locales/zh_CN.py` and `locales/en.py`. Tool names, parameter names, sources (primary, backup), step ids and the JSON keys of a plan are code and the same in both languages. The web page picks the run language from the UI language, and every run record states the language it ran in.

Task decomposition, structured plans and "replan iteratively when results affect later steps" follow chapter 07-planning-design of [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners) (MIT); the planner prompt, plan format, executor and experiments are written for this project.

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_plan_and_replan.test_lesson -v
```
