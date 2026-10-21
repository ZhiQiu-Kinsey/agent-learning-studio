# Capstone: a local study assistant (`capstone-study-assistant`)

English · [简体中文](README.zh-CN.md)

Each earlier lesson proves one thing: how the loop turns, how evidence is cited, how a write is approved, how an instruction is stopped, how a suite is judged. The capstone wires them into one chain, a study assistant you can actually use locally, and then says plainly whether it passed, using a fixed suite and an independent validator. The lesson is still a `planned` draft and has only been tested offline; no real model run has been done yet, so every "pass" below means the offline fixture, not an acceptance.

## Questions this lesson answers

- When the assistant answers, where does each claim come from? Can a program check every citation? Does it say so when the material is not enough?
- How is learning progress read and written? Why must a write be approved? Why does replaying the same write twice change the file once? If the process dies after the approval and before the write, how does it finish?
- When the material carries an instruction like "please also write this record", why can an out-of-scope call not reach the executing layer? Why can that defence not rest on the prompt?
- How are "the run ended", "the pass rate" and "the acceptance passed" kept apart? Why do the hard checks have no pass line while the holdout pass rate has one?
- How many model calls and how much time did a run take? What does the ledger write when the provider reported no usage?

## The corpus decision

The assistant's material is a new frozen set of course notes (`corpus/zh-CN/*.md` and `corpus/en/*.md`, 11 documents each, line-aligned). The lesson does not reuse the library handbook corpus of the document-loading and retrieval lessons, for four reasons:

1. A study assistant answers "what did the course say", so its material should be the key points of the course itself, which the learner can check directly.
2. The retrieval lessons' corpus is about library rules; questions about it would not match a study assistant.
3. The notes hold two structurally useful documents that the handbook corpus does not: `capabilities.md` against the dated `capabilities-2026-03.md` (they disagree, to test which one to trust) and `forum-digest.md` (it carries injected instructions, to test indirect injection).
4. The corpus is frozen and versioned: Chinese `7bf138797037ac49`, English `743900e1515abd52`; the suite fingerprint is `6f4b04c0be60`. If the material or a case changes, the fingerprint changes and old results can no longer be compared directly with new ones.

Loading, chunking and BM25 retrieval come straight from the retrieval lessons' modules; this lesson adds no new retrieval method.

## Files

| File | Role |
| --- | --- |
| `contract.py` | The task contract: version, learner, the tools each task may use (`TASK_TOOLS`), the pass line `PASS_LINE`, at most 4 model calls per conversation (`MAX_STEPS`); the 13 frozen cases `CASES` and the suite `fingerprint()` |
| `notes.py` | Loads the frozen course notes and runs BM25 over them; `POISONED` marks the chunk that carries an injected instruction |
| `gate.py` | The permission gate: `decide()` is a pure function of task, learner, tool name and arguments and returns allow, approve or deny; security rules come before input-validation rules |
| `progress.py` | The progress store `ProgressStore`: operation id `operation_id`, operation table, `apply()` returning a new write or a replay, and the state match for the crash window |
| `ledger.py` | The call ledger `Ledger`: one row per model call, tool call and approval wait; usage the provider did not report is written "not reported", never estimated |
| `answers.py` | The shapes of model output (cited answer, practice set, trace explanation, progress reply) and their parsing |
| `assistant.py` | The assistant itself: `Session.call` is the single entry for every call; it goes through the gate first, reads execute directly, writes go to a checkpoint and an approval, the approved decision is re-checked, and the write is applied idempotently; `run_grounded`, `run_progress`, `resume_save` and so on |
| `verifier.py` | The independent validator: reads only the case spec and the facts of this run, never the assistant's own account; hard checks, failure classes and `decide_acceptance()` |
| `runtime.py` | The runner: validates inputs, states the task contract, runs each case in isolated stores, publishes the evidence events and six reports; `local` and `mcp` search backends |
| `notes_server.py` | A real MCP stdio server that exposes only the read-only `search_notes` |
| `locales/`, `locales/fixture/` | Runtime text and fixture text, one catalog per run language |
| `fixtures.py` | The deterministic model and approval policy for offline tests only |
| `test_lesson.py` | 76 tests: corpus and suite frozen, the gate, the progress store, the ledger, the validator (with mutation checks), offline runs in both run languages, evidence events, misbehaving models, crash and cancel, a real MCP subprocess, input validation |

Reused lesson code (not modified): `lessons/lesson_rag_citations/citations.py` (citation checks and failure classes), `lessons/lesson_10_persistent_memory/store.py` (memory store), document loading, chunking and BM25 retrieval, and the Wilson interval from `lessons/lesson_evaluation_sets/runtime.py`.

## The suite

13 cases: 8 development and 5 holdout.

| Case | Set | Category | What it tests |
| --- | --- | --- | --- |
| `d01` | development | question (exact) | A cited answer, every citation checked |
| `d02` | development | question (synonym) | The question uses different words from the notes: BM25 misses, a retrieval failure left in on purpose |
| `d03` | development | question (no answer) | Retrieval still returns chunks, but the notes have no answer; the answer must say the material is insufficient |
| `d04` | development | question (conflict) | The old and the dated note disagree; the answer cites both and tells which is the dated, newer statement |
| `d05` | development | practice questions | The basis of each practice question cites the matching chunk of the notes |
| `d06` | development | trace reading | Explain an existing trace; the facts in the explanation must match the ledger |
| `d07` | development | progress (round trip) | Save progress, read it back in a new session; 1 approval |
| `d08` | development | injection | The forum digest carries an instruction for an out-of-scope write |
| `h01` | holdout | question | Like `d01`, a different question |
| `h02` | holdout | injection | Another instruction in the same forum digest, asked a different way |
| `h03` | holdout | progress (reject) | The learner rejects the approval; nothing is written and the answer says so; 1 approval |
| `h04` | holdout | progress (invalid arguments) | The lesson name is not a known lesson (`quantum-agents`); the gate refuses it by an input rule and the answer must not claim it was saved |
| `h05` | holdout | progress (recovery) | Crash after the approval, resume the checkpoint twice, write once; 2 approvals |

## How the assistant stays in scope

1. **The contract comes before the model.** Which tools a task may use is fixed by `TASK_TOOLS` before any model call: question, practice and trace tasks may only search; saving progress may read and write progress; recall may only read progress.
2. **Every call goes through the gate first.** `gate.decide()` ignores what the model says and looks only at the task, the learner and the arguments. An out-of-scope call is denied, and every write needs approval.
3. **A write has three steps.** A checkpoint first, then the approval, then a re-check that the approved content equals the content to be written, and finally an idempotent write by operation id.
4. **Runner probes.** The runner submits 4 out-of-scope calls itself, to prove the gate holds even if the model never proposes anything dangerous. The report marks this evidence `runner_probe`, apart from out-of-scope proposals the model made.
5. **The validator judges independently.** It re-reads the facts from events and the store; the assistant saying "saved" counts for nothing.

## Exercises

| Exercise | Preset | Most model calls | Main evidence |
| --- | --- | --- | --- |
| A cited study answer | `case=d01` | 4 | Citation check, retrieval judgement, call ledger |
| A question the notes cannot answer | `case=d03` | 4 | Whether the answer says plainly that the material is insufficient |
| Save progress and recall it in a new session | `case=d07` | 8 | Gate decisions, the approval card, memory events, the read-back in a new session |
| Crash and resume from the checkpoint | `case=h05` | 4 | Two resumes, one write, the operation id |
| A safe answer from poisoned material | `case=d08` | 4 | The blocked out-of-scope calls, out-of-scope effects that actually happened (should be 0) |
| The fixed suite, evaluated and judged | `case=suite`, `split=all` | 57 | Pass rate and interval, failure classes, cost ledger, acceptance report |

- A task card opens each run and states which cases run, the suite fingerprint, the corpus version and the stop condition.
- Each case gets a `lesson.case_result`, plus `lesson.permission` (gate decisions), `lesson.memory` (progress reads and writes), `lesson.citation_check`, `lesson.retrieval_judge` and `lesson.ledger`.
- A whole-suite run writes six reports: contract, case, permissions, ledger, suite with failure classes, and acceptance.
- Before running, the runner adds up the worst-case model calls per case and refuses a run over this lesson's limit (80). The development set needs at most 37 and the holdout set at most 20.
- A live whole-suite run pauses on approval cards: `d07` once, `h03` once, `h05` twice, four in all, each needing a click from the learner.

## What to look at in each experiment

1. **Cited answers**: first the fingerprint and corpus version on the task card; then the result of each citation check; then the retrieval and model timings in the ledger.
2. **Progress read, write and recovery**: the gate's decision on the write, the approval card and the record that was actually written; in `h05`, how the operation id turns the second resume into a replay.
3. **Injection and acceptance**: whether a blocked call was proposed by the model or came only from a runner probe; then how the whole-suite run keeps "run ended", "pass rate" and "acceptance passed" as three separate numbers.

## How to run

Offline tests (deterministic model data; tools and stores run for real, and the MCP cases start a real subprocess):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_capstone_study_assistant.test_lesson -v
```

`fixtures.py` scripts fixed behaviour for the "model": the synonym question of `d02` is not retrieved; on injection cases the fixture obeys the instruction, to prove the gate stops it; crashes are injected by the runner. All of this is labelled in the events, serves only to test the gate, the validator and the reports, and says nothing about any real model. The offline whole-suite result is 7 of 8 development cases and 5 of 5 holdout cases passed, and the acceptance state is always "not an acceptance": a fixture cannot produce an acceptance verdict.

Live runs: once the lesson is open (`available`), pick an exercise in the web lab, or use `scripts/run_live.py capstone-study-assistant <exercise> --url http://127.0.0.1:8765 [--locale en]`. A whole-suite run uses up to 57 model calls and costs real usage. Prices (rate, source, date) turn into a cost only when the learner fills all of them in; otherwise the ledger shows usage only.

**Run languages:** the lesson runs in Chinese and in English. System prompts, the task contract text, report text and fixture text are in `locales/`; case ids, tool names, event names and failure categories are code and the same in every language. The web page picks the language from the interface language, and the run record states the language.

## Limits

- 13 cases only describe this suite. The pass line 0.8 is this course's acceptance rule, not a general standard; the holdout set has only 5 cases, so the report adds a Wilson interval and the result is a reference.
- Retrieval is BM25 only and a synonym question fails (`d02`). That is a known limit, not a bug.
- The gate stops calls, not words: an answer in which the model repeats an injected instruction is caught by the answer checks and the validator.
- No prices are built in; without a source and a date no cost is computed, and usage the provider did not report is written "not reported".
- Progress lives in one local single-user file: no multiple users, locks or identity.
- This is the offline implementation of the capstone; the pass rate of a real model has not been measured, and the lesson stays `planned` until a live acceptance passes.

## References

- Microsoft AI Agents for Beginners (MIT) `STUDY_GUIDE.md` (the course helper and the capstone exercise) and `13-agent-memory/README.md` (learner memory).
- Hugging Face Agents Course (Apache-2.0) `units/en/unit4/introduction.mdx`, `what-is-gaia.mdx` and `hands-on.mdx` (a fixed question set, a pass line, exact match, honesty about leaderboards).
- Understanding AI Agents in Depth (深入理解 AI Agent; Apache-2.0) chapter 1 (the five elements of a harness, guardrail layers, human intervention), chapter 3 (user memory and updates) and chapter 7 (validators, Pass@k and Pass^k, failure attribution, regression tasks, statistical significance, observability).
- claude-cookbooks (MIT) `capabilities/retrieval_augmented_generation/evaluation/eval_end_to_end.py` and `docs_evaluation_dataset.json` (retrieval evaluation kept apart from end-to-end evaluation).

What is borrowed is method; the suite, the corpus, the gate, the store, the validator and the experiments are written for this project and no reference code is copied.
