# Error handling and safety boundaries (`fail-safely`)

English · [简体中文](README.zh-CN.md)

**Goal:** make a tool fail explicitly on bad arguments or business errors; have the model state the failure truthfully; on API or network errors, stop and leave the decision to a person.

## Run the offline demo first

From the project root:

```powershell
.\.venv\Scripts\python.exe -m lessons.lesson_03_fail_safely.offline_demo             # Chinese
.\.venv\Scripts\python.exe -m lessons.lesson_03_fail_safely.offline_demo --locale en # English
```

The demo reads no API key, sends no request to Bailian and incurs no usage. It shows four cases: a successful division, a zero divisor, an unknown tool and invalid JSON arguments. A tool error becomes a structured result with `ok=false`; an unknown name finds no function in the allowlist.

The web lab's "Unregistered tool (program-built)" and "Malformed arguments (program-built)" exercises work the same way: in `runtime.py` the runner builds the call and hands it to the same `execute_tool` for checking, without calling a model; the events mark the call as program-initiated instead of passing it off as a model proposal.

## Then the real model loop

```powershell
.\.venv\Scripts\python.exe main.py --lesson fail-safely
.\.venv\Scripts\python.exe main.py --lesson fail-safely --locale en
```

Ask `What is 12 divided by 3?` and then `What is 12 divided by 0?`. In the second case Python returns the error as a `role: tool` message; the system prompt asks the model to admit the failure, ask you to fix the input, and never make up a quotient.

## Failure boundaries

- **Tool argument or computation failure:** becomes a tool result with `ok=false`, so the model answers from the real error.
- **Unknown tool:** only the allowlist returned by `available_tools` is consulted; a name the model returns is never executed dynamically.
- **API or network error:** show the status and end the run without resending. After a timeout you can't know whether the server processed the original request; a blind retry may consume Bailian usage twice.
- **Loop control:** this lesson sends at most two model requests, so the model can't keep requesting tools.

Look at the error wrapping and the allowlist in `course/runner.py`, and the network error handling in `course/api_client.py`. This flow leaves it to a person to decide when to fix and resubmit.

**Run language:** the system prompt, the tool description, tool errors, the answers of the fault-injection arms and the demo texts are in `locales/zh_CN.py` and `locales/en.py`. Tool and parameter names are code and the same in both languages. The web page picks the run language from the UI language.
