# LangChain tools and structured adapters (`langchain-tools`)

**English** · [简体中文](README.zh-CN.md)

This lesson hands the business contract of the `structured-output` lesson (`TaskCard` and the trusted facts) to LangChain components unchanged: the lookup tool `lookup_lesson` is registered with the tool decorator, and the lesson card is parsed with `with_structured_output`. The question is what happens once the framework does the parsing: is a tool failure still a failure, does a parsing failure get swallowed, and which capabilities does the provider actually support? The lesson needs a real model connection. ## Files

| File | Content |
| --- | --- |
| `runtime.py` | The runner: lookup (`look_up_facts`, at most 2 model calls) → lesson card (`generate_card`, at most 1 repair) → capability matrix and final report |
| `components.py` | Framework registration of the business contract: `make_lookup_tool` (`@tool` plus type hints), `handwritten_definition` (the same tool written by hand), `card_schema` (a `TaskCard` subclass that only adds the tool description), `business_checks` (the program's business check) |
| `locales/zh_CN.py`, `locales/en.py` | Runtime text: system prompt, injected instructions, tool descriptions, errors and report text |
| `fixtures.py` | Offline test fixture, for automated tests only: it tells lookup from card requests by `tool_choice`, and injected faults appear only the first time |
| `test_lesson.py` | Behavior tests: real tool execution, four exercises in two run languages, three "silent" failures, limits and stops, cancellation, observation selectors |

Every model call goes through `RunContextChatModel` in `course/frameworks.py`, so each call has a `lesson.framework_input` before and a `lesson.framework_output` after, with the `request` / `response` recorded by RunContext in between. Tools always run through `execute_tool_calls`, never through a prebuilt framework tool node. Framework code runs inside `local_tracing_only()`, so LangSmith tracing uploads nothing. The only framework dependency is `langchain-core` (1.6 series, checked on 1.6.12).

**Status:** `available`. Every exercise was run once in each run language against a real model on 2026-10-21 (`claude-haiku-5-5`, one sample each; [verification record](../../docs/verification/live-runs-2026-10-21.md)). That is a dated record for one model, not a guarantee for other models.

## Exercises

| Exercise | Injection | Requests offline | What to look at |
| --- | --- | --- | --- |
| Normal: look up, then produce the card | none | 2 | The generated tool definition matches the handwritten one; `tool_choice` is `required` in round 2; the raw `arguments` string next to the framework's `args` dict |
| Missing field on purpose | the first card leaves out `prerequisite` | 3 | Framework result `schema_error`, business check not run; the runner's repair feedback answers the failed call id |
| Valid schema, wrong fact | the first card says `prerequisite` is `dependent-calls` | 3 | Framework result `parsed`, business check fails; the repair passes |
| Tool error | the first lookup uses the directory name `task_contract` | 3 | `ToolException` becomes an `ok=false` tool result and reaches the next request; the final report still counts 1 tool failure |

With the input `repair` set to `false`, the run stops after the first failed attempt with the stop reason `repair_off`. Injections are written into the prompt, and a real model may not follow them (with a provider that constrains generation to the schema, the missing-field injection may have no effect), so trust your own run.

## What the experiments show

- **Structured study-task tool adapter**: the same `TaskCard` contract, comparing the framework's parsing result (`parsed`, `schema_error`, `invalid_arguments`, `no_structured_call`) with the program's business check. A valid schema is not a correct fact.
- **Tool errors keep their failure meaning**: `ToolException` → `tools_as_callables` → `ok=false`, `error_type=ValueError`. `handle_tool_error` stays off, because it returns the exception text as ordinary output.
- **Capability matrix**: each capability gets the evidence from this run and a status (observed in this run / adapter fallback / unverified). Offline runs say "offline fixture"; `strict` and provider-native JSON Schema output are never sent by this lesson, so they stay unverified.

## Running

```powershell
# Offline tests (deterministic model data, real tool execution)
.\.venv\Scripts\python.exe -m unittest lessons.lesson_langchain_tools.test_lesson -v
# A real run (uses model quota)
.\.venv\Scripts\python.exe scripts/run_live.py langchain-tools missing-field --url http://127.0.0.1:8765 --locale en
```

Real runs exist only for the one provider and model of the 2026-10-21 round (Anthropic, `claude-haiku-5-5`); the capability matrix has no observed record from any other provider.

## References and adaptation

Adapted from: the function schema and error-handling elements of `04-tool-use` in Microsoft AI Agents for Beginners (MIT); the Hugging Face Agents Course (Apache-2.0) unit 2 / unit 3 pages that register the same tool in three frameworks, and their "catch everything and return an empty string" counter-example; the tool-description and argument-fidelity principles in chapter 4 of the AI Agent book (深入理解 AI Agent, Apache-2.0); the forced-tool-call approach to structured JSON in claude-cookbooks (MIT) `tool_use`. The langchain-core behavior (how `with_structured_output` is assembled, the dropped `method` argument, `handle_tool_error`) was checked on 1.6.12 on this machine. The task, business table, fixture and experiments are this project's own.
