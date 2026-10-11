# Tool definitions and call proposals (`tool-proposals`)

English · [简体中文](README.zh-CN.md)

**Goal:** send the tool definitions with the request and look only at the calls the model proposes: which tool it picked and what the arguments are. This lesson executes no tool.

This lesson is a custom runner (`runtime.py`) that sends one request:

1. Besides `messages`, the body has `tools` (the tool definitions, built by `tool_definitions` in `tools.py` of the lesson "Executing tools and returning results") and `tool_choice: "auto"`.
2. `context.complete` sends the request; the platform records the `request` and `response` events.
3. `read_proposals` lists the `tool_calls` of the response unchanged: call id, tool name, `arguments` as a JSON string, and whether it parses as a JSON object. No function is registered for execution, so the events have no `tool_call` and no `tool_result`.

| Exercise | Question | What to look at |
| --- | --- | --- |
| `sum` Ask for a sum | Add 19 and 23 for me. | Whether it proposes `add_numbers`, and how it writes the arguments |
| `time` Ask for the time | What is the local time now? | Whether it proposes `get_current_time` with an empty object |
| `chat` Small talk | Hello, introduce yourself in one sentence. | No call proposal, a direct answer, `finish_reason` is `stop` |

Executing call proposals and handing the results back to the model is the next lesson, "Executing tools and returning results".

**Run language:** this lesson runs in Chinese and in English. The system prompt, the answer the runner writes and the lab report texts are in `locales/zh_CN.py` and `locales/en.py`; the tool descriptions are in `locales/tools/`, shared with `tool-selection`; the exercise questions are written per language in `lesson.json`. The web page picks the run language from the UI language, and every run record states the language it ran in. Tool and parameter names are code and the same in both languages.

Open this lesson from the course navigation on the web page to see the source, real run events and replay. Offline tests:

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_tool_proposals.test_lesson -v
```

`fixtures.py` serves automated tests only; its proposals are a fixed script, not a real model's choice.
