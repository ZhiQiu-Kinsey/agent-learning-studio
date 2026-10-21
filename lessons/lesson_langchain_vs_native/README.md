# LangChain vs. the native implementation (`langchain-vs-native`)

English · [简体中文](README.zh-CN.md)

One task, done twice: with the platform's native tool loop (`run_agent` in `course/runner.py`) and with the same loop written in LangChain. Both sides share the question, system prompt, Python tool functions, round limit (3 each) and the acceptance function `accept`; they run one after the other in the same run, so the timeline can be compared round by round. The lesson answers which steps the framework takes over (message objects, generating tool definitions, parsing calls, writing results back) and which you still write yourself (the loop, the stop condition, error handling, the cap on model calls, acceptance).

**Status:** `available`. Every exercise was run once in each run language against a real model on 2026-10-21 (`claude-haiku-5-5`, one sample each; [verification record](../../docs/verification/live-runs-2026-10-21.md)). That is a dated record for one model, not a guarantee for other models.

## Files

| File | Contents |
| --- | --- |
| `runtime.py` | The runner: `run_native` (reuses `run_agent` and the earlier lessons' `setup`), `run_langchain` (framework messages, `bind_tools`, `invoke`, `execute_tool_calls`, with our own loop), the shared `accept`, the field-by-field request comparison `request_diff`, and two exercises that call no model |
| `tools.py` | Registers the same tool functions from `tool-selection` and `fail-safely` as LangChain tools with `@tool`; `StrictNumbers` is a strict parameter Schema |
| `locales/zh_CN.py`, `locales/en.py` | Report labels, answers the runner writes, the sample note. System prompts and tool descriptions reuse the earlier lessons' runtime text, so both implementations send exactly the same words |
| `fixtures.py` | A deterministic model for tests only: proposes one call when there is no tool result yet (arguments written compactly), answers once there is |
| `test_lesson.py` | Behavior tests: both implementations' event sequence, request differences, the framework body matching the recorded request, the failing task, the round limit, the model call cap, broken and id-less calls, the two local exercises, a pin on the generated Schema, no Chinese in English runs, cancellation |

The framework is used only through the platform adapter `course/frameworks.py` (`RunContextChatModel`, `execute_tool_calls`, `tools_as_callables`, `RunContextCallbackHandler`, `ai_message_from_response`), inside `local_tracing_only()`; LangGraph's prebuilt tool node is not used because it bypasses the event record. The only dependency is `langchain-core` (pinned to 1.6.x, 1.6.12 installed); neither the whole `langchain` package nor a provider integration package is installed.

## Exercises

| Exercise | Calls a model | What to look at |
| --- | --- | --- |
| Normal task: addition | Yes, at most 2 × 3 calls | Rounds 1–2 are the native loop, LangChain starts at round 3; the layers `lesson.framework_input` → `request` → `response` → `lesson.framework_output`; two `lesson.report` events: the responsibility map (every number from this run) and the field-by-field request comparison |
| Failing task: zero divisor | Yes | Both sides get an `ok=false` structured error that is written into the next request; `on_tool_error` in `lesson.framework_callback` |
| Argument coercion (runner-built) | No | The same arguments go to the native tool, the default `@tool` and the strict Schema: a number as a string, a boolean and an extra argument all "succeed" with the default `@tool` |
| Call parsing (runner-built) | No | A runner-built provider response (truncated JSON, array arguments, a missing call id) parsed by the adapter: `invalid_tool_calls`, the filled-in `framework_call_1_3`, a changed write-back order |

The inputs of the two local exercises are built by the runner; the events carry `origin: course_program` and the sample response is recorded as `lesson.sample_response`, not as model output.

## What the experiments show

- **The same task, two implementations**: the first request pair differs in the tool definitions `@tool` generates (no parameter descriptions, no `additionalProperties`) and in the missing `tool_choice`; the second pair differs in the `arguments` the framework re-serializes and the tool result turned into a float (42 vs. 42.0). The acceptance function reads only tool results and request bodies.
- **What the framework does quietly**: defaults hiding failures (lax validation), invalid tool calls not being in `tool_calls`, missing ids filled in by the adapter and listed separately, valid calls written back first.

## Running

Offline tests:

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_langchain_vs_native.test_lesson -v
```

Real runs (they use model quota; run once in each run language):

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py langchain-vs-native sum --url http://127.0.0.1:8765
.\.venv\Scripts\python.exe scripts/run_live.py langchain-vs-native divide-zero --url http://127.0.0.1:8765 --locale en
```

In a real run, check how the provider treats a missing `tool_choice`, how it writes `arguments` (which decides whether the second pair differs), and whether both sides pass acceptance. Do not assume the result; go by the events.

**Run language:** the lesson runs in Chinese and in English. Tool names, parameter names and event names are code and the same in every language; English runs contain no Chinese (Pydantic's validation errors are English already).

## References

- Hugging Face Agents Course (Apache-2.0), unit 2 framework introduction and the LangGraph and LlamaIndex intro pages: when a framework is needed and what parts it should provide.
- Microsoft AI Agents for Beginners (MIT), lessons 02 and 04: modular components; tool Schemas generated from functions with type hints.
- *Understanding AI Agents in Depth* (深入理解 AI Agent, Apache-2.0), chapter 1, "Harness engineering": the five parts of the harness, of which frameworks mostly cover context and tools.
- learn-claude-code (MIT) s01: the minimal loop without a limit, as the skeleton frameworks add layers to.
- The LangChain docs tools page (checked 2026-10-20) and the installed langchain-core 1.6.12 source: `tool`, `bind_tools`, `AIMessage.tool_calls` / `invalid_tool_calls`, `parse_tool_call`, `convert_to_openai_tool`.

Only organization and ideas are borrowed; the code and text are written by this project.
