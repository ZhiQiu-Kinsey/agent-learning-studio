# Multi-agent patterns and trade-offs (`multi-agent-patterns`)

English · [简体中文](README.zh-CN.md)

Before splitting work across several agents, measure with one acceptance set. This lesson runs the same course-assistant task (write quiz questions from a document pack) four ways: a single agent, a fixed workflow, role switching and independent agents. Every mode hands its final questions to the same program verifier, and the report compares pass or fail, model calls, the usage the provider reported and wall-clock time side by side. The lesson needs a real model connection; it is still `planned` and has only been verified offline.

## Task and acceptance set

- Four documents: `d1` workflow patterns, `d2` orchestrator-workers, `d3` the revision loop, `d4` extra notes. The title of `d4` does not look old; only the rule in the task description says "d4 is an old draft and must not be used as evidence when it conflicts". Its subtask limit (6) contradicts `d2` (4).
- Three topics: `fallback_label`, `worker_cap`, `max_iters`; one four-option question per topic, each with evidence `{doc, quote}`.
- `verify_quiz` in `verifier.py` checks per topic: exactly one question; correct format; the `quote` appears word for word in the `doc` it names; `doc` is not `d4`; the correct option states the documented value and no other option does. The runner calls it as a tool after the last round (the events carry `origin: course_program`).

## Four modes

| Exercise | Model calls | Context | Run identities |
| --- | --- | --- | --- |
| Single agent (baseline) | 1 | One request holds the task, the rule and all four documents | `solo` |
| Fixed workflow | 3 | research → write → review, a fresh request per step, inputs picked by the program | `step-research`, `step-write`, `step-review` |
| Role switching | 3 | One shared message history; each stage only swaps the system prompt | `assistant` (3 roles) |
| Independent agents | 5 | Three researchers, one shard each, in parallel with their own `branch`; the program merges; writer and reviewer each work in a new context | `researcher-1..3`, `writer`, `reviewer` |

The `handoff` parameter only affects the independent agents: `minimal` (default) passes only the task and the assigned documents; `with_rules` also adds the rule that d4 is out of date. The `multi` exercise presets `minimal`; the separate `multi-with-rules` exercise presets `with_rules`, so the second experiment's arms are two exercises rather than edited inputs.

## Evidence

- `lesson.agent`: one per model call, with the run identity, role, `branch`, and the context read from the messages actually sent: number of messages, input characters, documents seen, `sees_rule`, and how many assistant replies are in the history; an `outdated_docs` field appears when the context holds `d4`.
- `lesson.merge` (independent agents only): every fact, `duplicates` (a topic looked up by more than one researcher), `conflicts` (contradicting values for a topic), `missing`. The program records and does not decide.
- `lesson.plan`: the task graph of each mode, `created` at the start and `progress` at the end, with the verifier as the last step.
- `lesson.report`: one check per topic; metrics for task acceptance, model calls, total `total_tokens` (only numbers the provider reported, otherwise "not reported"), wall-clock time, run identities and roles, total input characters, merge conflicts and duplicates (independent agents), and the handoff; one table row per call.

## What the experiments show

1. **Comparing modes for research, writing and review**: four arms, one task. Look at the first call's context, the number of run identities and roles, the verifier call, task acceptance, model calls (1, 3, 3, 5), usage and wall-clock time.
2. **A handoff package that leaves out one rule**: both arms are independent agents (exercises `multi` and `multi-with-rules`) and differ only in `handoff`. With the minimal handoff, `researcher-3` holds `d4` but not the rule, the merge shows a duplicate and a conflict, and the verifier fails `worker_cap`; with the rule the conflict disappears and the input characters grow.

The offline fixture (`fixtures.py`) only serves automated tests: a researcher skips `d4` only when the rule is in its context; the writer takes the last allowed fact per topic, so the minimal handoff always ends with a question built on `d4`; the reviewer passes the draft unchanged; usage is made up from the request size, and each call pauses 20 ms. A real model may choose differently, so trust your own real runs.

## Files

- `runtime.py`: input model, the four modes, context audit (`audit_context`), ledger, merge (`merge_facts`), task graph and report.
- `verifier.py`: the one program verifier.
- `locales/zh_CN.py`, `locales/en.py`: documents, task description, rule, role prompts and report text; `locales/fixture/` holds the offline script's question stems and quotes.
- `fixtures.py`, `test_lesson.py`: the deterministic test model and behavior tests (both run languages, budget, cancellation, structured errors and the experiments' observation points).

## Running

```powershell
# Offline tests (deterministic model data; the verifier really runs)
.\.venv\Scripts\python.exe -m unittest lessons.lesson_multi_agent_patterns.test_lesson -v
# Once the lesson is open, run one exercise against a real model (uses model quota); --locale en runs in English
.\.venv\Scripts\python.exe scripts/run_live.py multi-agent-patterns multi --url http://127.0.0.1:8765
```

**Run languages:** the documents, task, rule, prompts and report text come from `locales/` in the run language; topics, document ids, the documented values (`other`, `4`, `3`) and run identities are code and the same in every language.

## References and credits

The shared versus isolated context taxonomy, the three parts of a handoff package, the new-information test and the failure modes follow chapter 10 of Understanding AI Agents in Depth ([bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book), Apache-2.0); subagents and teams follow [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) (MIT) s06 and s13; multi-agent scenarios and visibility follow `08-multi-agent` in Microsoft AI Agents for Beginners (MIT); team orchestration and the shared clock follow [claude-cookbooks](https://github.com/anthropics/claude-cookbooks) (MIT) `patterns/agents/`. The task, documents, verifier, runner and experiments are written by this project; none of the referenced code is copied.
