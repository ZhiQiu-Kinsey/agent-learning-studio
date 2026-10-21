# LangGraph State and Branches (`langgraph-state`)

English · [简体中文](README.zh-CN.md)

State, Node and Edge turn "plan, call, verify, answer" into a graph with terminal states: the normal, missing-parameter and failure paths each stop at a terminal node, repairs after a failed check are bounded by a counter in the state, and LangGraph's `recursion_limit` is only a safety net. The lesson needs a real model connection (the missing-parameter exercise never calls the model). ## The problem

"Application State and Run Lifecycle" (`application-state`) keeps the task's progress in a dataclass and a few if branches. Once the flow has a loop such as "if the check fails, go back and repair; when repairs run out, fail", the branches and counters in one function are hard to see at a glance. This lesson hands the same kind of flow to LangGraph: the state is declared once, each node returns only the fields it changed, and the edges (conditional ones included) are listed in one place. The compiled graph can list every edge, so you can check that each path reaches `END` before running anything.

**Status:** `available`. Every exercise was run once in each run language against a real model on 2026-10-21 (`claude-haiku-5-5`, one sample each; [verification record](../../docs/verification/live-runs-2026-10-21.md)). That is a dated record for one model, not a guarantee for other models.

## Files

| File | What it holds |
| --- | --- |
| `graph.py` | `StudyState` (two list fields with reducers), the `check_evidence` verification rules, seven nodes, two router functions and the graph assembly |
| `runtime.py` | Input model, initial state, running the graph with `stream_graph` and catching `GraphRecursionError`; publishes the "Graph structure" and "Path of this run" reports |
| `study_tools.py` | The only tool, `estimate_study_days`: sums minutes from the lesson's own table, divides by the minutes per day and rounds up; unknown lessons return a structured error |
| `locales/zh_CN.py`, `locales/en.py` | Prompts, tool description and errors, verifier feedback, terminal reasons, report text |
| `locales/fixture/` | The answer template of the offline test model (tests only) |
| `fixtures.py` | Deterministic model for automated tests only: when planning it proposes the call with the exercise inputs as given; when answering it writes one sentence from the tool result it is shown |
| `test_lesson.py` | Behavior tests: real tool execution, the three paths and their terminal states, a successful repair, both limits, reducer rules, graph events never passing for model responses, no Chinese in English runs, input validation and stopping |

The framework adapter lives in `course/frameworks.py`: model calls go through `RunContextChatModel` and are recorded as `request`/`response`, tool calls go through `execute_tool_calls` and are recorded as `tool_call`/`tool_result`, and `stream_graph` records each node's update as `lesson.graph_update`. The lesson does not use LangGraph's prebuilt tool node: it calls functions directly, so the platform would not record those calls.

## Exercises

| Exercise | Inputs | Path | Model calls |
| --- | --- | --- | --- |
| Normal path: plan, call, verify, answer | three lessons, 30 minutes a day | intake → plan → tools → verify → answer | 2 |
| Missing parameter: no daily time | two lessons, `minutes_per_day` null | intake → ask_user | 0 |
| Failed terminal state: one repair, still failing | includes a lesson the table does not have, `max_repairs`=1 | intake → plan → tools → verify → plan → tools → verify → fail | 2 |
| Stopped by the ceiling: recursion_limit comes first | same, `max_repairs`=3, `recursion_limit`=6 | stopped after the sixth node, tools; no terminal state | 2 |

Paths and counts come from offline test mode. In a real run the model may change the arguments in the plan node (for example drop the unknown lesson); the verifier then reports `arguments_mismatch` and the path stays the same.

## What to look at in the experiments

- **Plan, call, verify, answer graph**: read the 11 edges in the "Graph structure" report, then use the `read` of each `lesson.graph_route` to explain why that branch went where it did, and finish with the terminal check in the report.
- **Loop budget and recursion limit**: when the business budget comes first the graph reaches `fail` with a reason and evidence; when the recursion limit comes first LangGraph raises and the runner can only report the last node it ran. Measured on langgraph 1.2.16: a path of N nodes needs `recursion_limit` of at least N+1.
- **State diffs and reducers**: the `tools` update carries only this attempt's evidence, `evidence` is appended with `operator.add`, `failed_checks` is overwritten, and "runs of nodes that call the model" equals the number of `request` events.

## Running

Offline tests (deterministic model data, real tool execution):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_langgraph_state.test_lesson -v
```

Real runs: pick an exercise in the lab, or with the backend running (this uses model quota):

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py langgraph-state normal --url http://127.0.0.1:8765 --locale en
```

Each exercise was run once for real in both run languages on 2026-10-21 and the text was checked against those runs (see the verification record).

**Run languages:** prompts, tool description and errors, verifier feedback and report text live in `locales/`; node names, state fields, problem codes and lesson ids are code and the same in every language.

## References

The explanation of State, Node, Edge and conditional edges draws on the Hugging Face Agents Course (Apache-2.0) `units/en/unit2/langgraph/`; constraints, verification and correction in the harness draw on chapter 1 of the book (深入理解 AI Agent) (Apache-2.0); script-based orchestration is compared with learn-claude-code (MIT) `s16_workflow_runtime`; plan-and-dispatch with Microsoft AI Agents for Beginners (MIT) `07-planning-design`. The LangGraph API follows the 1.2 official documentation (checked 2026-10-20) and measurements with langgraph 1.2.16. The graph, tool, verification rules and experiments are written by this project.
