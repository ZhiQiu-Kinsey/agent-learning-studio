# Delegation, merging and budgets (`delegation-budget`)

English · [简体中文](README.zh-CN.md)

This lesson asks one question: once a coordinator has decided to split work among subagents, how should it hand the work out and take results back so that every step can be checked? The task is fixed: answer four questions about a final project (deadline, team size, share of the final grade, late policy) from five short fictional documents (a course syllabus, a registrar notice, team rules, grading rules and a late policy). The syllabus and the notice disagree about the deadline, which is how the lesson shows a conflict. Other lessons are named by slug, not by lesson number, which changes as the syllabus grows. This lesson needs a real model connection.

**Status:** `available`. Every exercise was run once in each run language against a real model on 2026-10-21 (`claude-haiku-5-5`, one sample each; [verification record](../../docs/verification/live-runs-2026-10-21.md)). That is a dated record for one model, not a guarantee for other models.

## Mechanism

The coordinator is the runner, a program, not a model:

- **Delegation contract.** Each subtask has a contract: one question, the ids of the documents assigned to it, the JSON format to hand back (`status`, a `value` of at most 40 characters, `evidence`), the stop conditions (one call, `not_found` when the documents do not say, never guess), a deadline and a priority. A subtask's context is a brand-new message list holding only its contract and its own documents.
- **Merge check.** The runner passes every result that came back in time to the registered tool `merge_check`: the format is valid, `value` is not too long, evidence is present, every quote appears word for word in the document it names, and that document was assigned to this subtask. Accepted values are grouped by question; different values for one question are listed as a conflict as they are, and nobody rules on them.
- **Shared budget.** Model calls, provider-reported tokens and run time sit in one ledger (`SharedBudget`) and subtasks ask for them by priority. Calls are charged before the request goes out; tokens are charged only from the `total_tokens` the provider reported (when none was reported, one call is noted as not reported, never estimated and never counted as 0). A refusal states its reason, and every subtask that never started is listed.
- **Cancellation propagation.** The coordinator holds the root scope and each subtask gets a child scope; cancel the root once and every child sees it. A subtask past its deadline is cancelled and recorded as timed out; its request has already gone out and cannot be called back, so at wrap-up the runner waits for the response, books its usage into the ledger and does not merge its result (`lesson.late_response`).
- **Final verdict.** The program judges in a fixed order: a required question without an answer is "incomplete", a conflict is "needs confirming", a subtask not done is "required questions answered, some subtasks not done", and only all-passed with no conflict is "complete". The final answer is also assembled by the program from the merge result, with no model involved.

## Exercises

| Exercise | How it differs from the baseline | What to look at |
| --- | --- | --- |
| Full contract (baseline) | None | Each subtask's context in `lesson.delegate`, the deadline conflict in `lesson.merge`, the verdict "needs confirming" |
| Contract without an evidence requirement | The evidence requirement is removed from the contract | The returned JSON has no `evidence`, the merge check accepts none of it (`no_evidence`), the verdict is "incomplete" |
| Tight shared budget | Call budget of 3 | `lesson.budget_stop`: `deadline-notice` and `late-policy` never start; with no cross-check the conflict is not found |
| One subtask times out | A deadline of 50 ms for `weight` | `timed_out_after_ms` in `lesson.subtask`, `discarded` in `lesson.late_response`, a missing required question, the verdict "incomplete" while the other results are still delivered |

The evidence is mostly in `lesson.task_card`, `lesson.plan`, `lesson.delegate`, `lesson.subtask`, `lesson.budget_stop`, `lesson.late_response`, `lesson.merge` and the lab report (`lesson.report`). Parallel requests each carry their own `branch` (the subtask id), which the timeline uses to pair requests with responses.

## Files

| File | Contents |
| --- | --- |
| `runtime.py` | The custom runner: dispatch, waiting, timeouts, wrap-up, merging, the verdict, events and the report |
| `contracts.py` | Contracts, building a subtask's context, reply parsing, the merge check |
| `budget.py` | The shared budget and cancellation scopes |
| `locales/` | Runtime text in Chinese and English: documents, questions, prompts, the task card, the report |
| `fixtures.py` | Deterministic answers for automated tests only; the web page has no way in |
| `content.json`, `content.en.json`, `lesson.json`, `lesson.en.json` | Teaching content and the implementation manifest, with the English overlay |
| `test_lesson.py` | Behavior tests: the merge check, budget, cancellation and input validation run for real, in both run languages |

**Run language:** this lesson runs in Chinese and in English. The documents, questions, subtask prompts, the task card, problem-code descriptions, verdicts and report text are in `locales/zh_CN.py` and `locales/en.py`; subtask ids, field names, status codes and event names are code and the same in every language. The web page picks the language from the UI language, and every run record states the language it ran in.

## Running it

Offline tests (the fixture supplies deterministic answers; the merge check, budget and cancellation really execute):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_delegation_budget.test_lesson -v
```

A real run needs a configured model (environment variables or `local_config.py`), then the server:

```powershell
.\.venv\Scripts\python.exe run_web.py
.\.venv\Scripts\python.exe scripts/run_live.py delegation-budget full-contract --url http://127.0.0.1:8765 [--locale en]
```

A real run uses model quota.

## What it proves and does not prove

- A verbatim check proves that a quote really comes from the document assigned to the subtask; it does not prove that `value` was read correctly.
- The verdict rules, the priorities and the way the task is split are hard-coded for this task; another task needs its own.
- Cancellation stops the waiting and what follows; a request already sent cannot be called back, and the provider still generates and meters it.
- The answers, delays and usage numbers in the offline fixture are scripted; for real models go by your own experiment report.

## References

The ideas are adapted, not copied as text or code: structured handoff, a verified settlement point, cancellation that travels from parent to child and budget awareness from chapter 10 of *Understanding AI Agents in Depth* (Apache-2.0); the orchestrator-workers and shared-clock examples in claude-cookbooks (MIT); subagent message isolation and one level of delegation from learn-claude-code (MIT). The task, documents, checks and experiments are written by this project.
