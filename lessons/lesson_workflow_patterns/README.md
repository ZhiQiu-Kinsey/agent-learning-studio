# Workflow patterns: chaining, routing, and parallelization (`workflow-patterns`)

English · [简体中文](README.zh-CN.md)

Three workflows where the program decides the flow and the model does each step. This lesson needs a real model connection and uses no tools.

| Preset | Model requests | Evidence |
| --- | --- | --- |
| Prompt chain: three steps with gates | Up to 3 | `lesson.chain_step`: each step's output and gate result; the chain stops on a failed gate |
| Routing: 20 human-labeled tickets | 20 | `lesson.route`: label, prediction, raw reply, whether it took the fallback, plus `fallback_reason` when it did; the report gives accuracy, a confusion matrix and the misrouted tickets |
| Three subtasks, serial | 3 | `lesson.parallel`: wall-clock time, start and end of each branch |
| Three subtasks, parallel | 3, sent at the same time | Same as above; requests and responses carry `branch`, and the timeline pairs them by it |

- Routing accepts only the four labels `course`, `account`, `error` and `other`; any other output takes the fallback `other` and the raw reply is recorded.
- The tickets were labeled by the course author, and a few are deliberately ambiguous; 20 tickets do not represent real traffic.
- Time is measured on the backend with `perf_counter` and depends on the network and provider queues; one measurement speaks only for that run.

**Run language:** this lesson runs in Chinese and in English. The note, the three step instructions, the 20 ticket texts, the router prompt, the recap tasks and the report text are in `locales/zh_CN.py` and `locales/en.py`; the labels, the human labels (`GOLD`) and the lesson identifiers are code and the same in every language. The title length limit of step 3 is also per language: 8 characters in Chinese, 30 in English. The web page picks the language from the UI language, and every run record states the language it ran in.

`fixtures.py` serves automated tests only: the routing script deliberately misroutes two tickets and answers one with a label that is not in the list; each recap task pauses for a fixed 50 ms.

The split into three patterns follows `patterns/agents/basic_workflows.ipynb` in [claude-cookbooks](https://github.com/anthropics/claude-cookbooks) (MIT); that example raises on an unknown label, while this lesson takes the fallback and records it. The tickets, gates, timing and experiments are written by this project.

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_workflow_patterns.test_lesson -v
```
