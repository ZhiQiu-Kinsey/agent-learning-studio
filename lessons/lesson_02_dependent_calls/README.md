# Dependent calls across rounds (`dependent-calls`)

English · [简体中文](README.zh-CN.md)

**Goal:** see how the model first gets a fact and then decides the next step when one tool depends on another, and compare why two independent tasks can be proposed in the same round.

Command-line run (from the project root):

```powershell
.\.venv\Scripts\python.exe -m lessons.lesson_02_dependent_calls.main             # Chinese
.\.venv\Scripts\python.exe -m lessons.lesson_02_dependent_calls.main --locale en # English
```

Exercise one (`chain`):

> Add the current hour and minute.

Expected flow:

1. The first model request calls only `get_current_time()`.
2. Python returns structured data with `hour` and `minute`.
3. The model reads the real values, then requests `add_numbers(hour, minute)`.
4. Python returns the result and the model writes the final answer.

Exercise two (`both`):

> Add 19 and 23, and tell me what time it is.

The two tasks don't depend on each other, so the model may propose both calls in the same response; `run_agent` still executes them one by one in list order, and each tool result goes into the next request with its own `tool_call_id`.

This path uses at most three model requests. `setup(locale)` in `main.py` is written exactly like the one in the lesson "Executing tools and returning results"; only the system prompt changes. The tool definitions and the allowlist come from that lesson's `tools.py`, and the loop is `run_agent` in `course/runner.py`. The terminal shows the full request JSON of every round without the authentication header. Real Bailian calls incur usage.

**Run language:** the system prompt is in `locales/zh_CN.py` and `locales/en.py`; the tool descriptions and tool errors are in `lessons/lesson_01_tool_selection/locales/tools/`, shared with `tool-selection`. Tool and parameter names are code and the same in both languages. The web page picks the run language from the UI language.

You can also open this lesson from the course navigation on the web page to see the source, real run events and replay.
