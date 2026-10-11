# Executing tools and returning results (`tool-selection`)

English · [简体中文](README.zh-CN.md)

**Goal:** have Python execute the calls the model proposes, checked against an allowlist, write each tool result back into the message history with the same call id, and request the model again. That is the smallest agent loop.

The call proposal itself (tool definitions, `tool_calls`, JSON string arguments) was covered in the previous lesson, "Tool definitions and call proposals"; this lesson executes it.

Reading order:

1. `execute_tool` in `course/runner.py`: parse `arguments`, look the function up by name only in the allowlist (the dict `available_tools` returns), run it and wrap the outcome as `{"ok": true, "result": ...}`; on failure it is `ok: false` with `error_type` and `error`.
2. `run_agent` in `course/runner.py`: a four-step loop — build the message history, request the model, return the answer when there are no `tool_calls`, otherwise execute them and write `role: tool` messages (with `tool_call_id`) back into the history; at most `max_tool_rounds` rounds.
3. `tools.py`: `tool_definitions` (the tool definitions sent to the model), the implementations of `add_numbers` and `get_current_time`, and `available_tools`.
4. `main.py`: `setup(locale)` returns one run's system prompt, tool definitions and allowlist; `main` is the command-line entry.

Exercises: `sum` (add two numbers) and `time` (look up local time). Two independent calls in the same round come in the lesson "Dependent calls across rounds".

**Run language:** the system prompt, tool descriptions and tool error messages are in `locales/` (`locales/tools/` holds the part for `tools.py`, which the call-proposal and dependent-call lessons share), one file each for Chinese and English. Tool and parameter names are code and the same in both languages. The web page picks the run language from the UI language.

Command-line run (from the project root):

```powershell
.\.venv\Scripts\python.exe -m lessons.lesson_01_tool_selection.main             # Chinese
.\.venv\Scripts\python.exe -m lessons.lesson_01_tool_selection.main --locale en # English
```

Bailian requests need `local_config.py` on this machine and `DASHSCOPE_API_KEY`. The request body printed each round never contains the API key. You can also open this lesson from the course navigation on the web page to see the source, real run events and replay; replay only reads recorded events and never requests the model or runs tools again.
