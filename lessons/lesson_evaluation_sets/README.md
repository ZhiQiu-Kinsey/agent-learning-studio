# Evaluation sets and validators (`evaluation-sets`)

English · [简体中文](README.zh-CN.md)

One successful run does not show that a new version is better. This lesson turns the tool tasks of the `tool-selection`, `dependent-calls` and `fail-safely` lessons into a fixed case suite, runs the same tool loop with two versions of the system prompt, and lets a validator outside the agent judge every case and pair the two versions case by case. ## Questions this lesson answers

- How are "the run ended", "the answer is correct", "the evidence is sufficient" and "no process violation" judged separately? Which cases can a program not judge, so they are marked unassessable?
- Why keep a development set and a holdout set apart, and why does the holdout set run only once a version is chosen?
- When two versions differ by a few passed cases, is that an improvement or luck? Which cases regressed?
- Before an open-ended case is left to a judge model, how do you check the judge against human annotations?

**Status:** `available`. Every exercise was run once in each run language against a real model on 2026-10-21 (`claude-haiku-5-5`, one sample each; [verification record](../../docs/verification/live-runs-2026-10-21.md)). That is a dated record for one model, not a guarantee for other models. Judge calibration had no disagreement to read in those runs.

## Files

| File | Role |
| --- | --- |
| `cases.py` | The versioned suite: each case's category, expected calls (arguments may reference another tool's result), comparison rule `mode` and right answer; suite version `SUITE_VERSION`, case revision `rev`, `fingerprint()`; the judge calibration samples `JUDGE_SAMPLES` |
| `verifier.py` | The independent validator: `verify()` reads only the case spec and this run's trace and gives five checks (run ended, call comparison, answer correct, evidence sufficient, no process violation) plus a case verdict; `same_call()` compares parsed arguments as numbers |
| `runtime.py` | The agent under test (the tool loop of the first three lessons, at most 3 model calls per case), running the suite per version, `paired()` analysis, `sign_test()`, the Wilson interval, and judge calibration |
| `locales/zh_CN.py`, `locales/en.py` | Runtime text: both versions' system prompts, every case's question, check details, report text, the judge rubric and the 6 sample answers |
| `fixtures.py` | Deterministic model for offline tests only |
| `test_lesson.py` | Validator tests case by case, the statistics, offline runs of all four exercises, both run languages |

The tools are reused as they are from `lessons/lesson_01_tool_selection/tools.py` (`add_numbers`, `get_current_time`) and `lessons/lesson_03_fail_safely/tools.py` (`divide_numbers`); they are not modified.

## The suite

| Case | Set | Category | Expected |
| --- | --- | --- | --- |
| `add-basic` | development | simple | one `add_numbers(19, 23)`, answer 42 |
| `clock-sum` | development | dependent | `get_current_time` first, then `add_numbers` with hour and minute in a later step; the validator computes the answer itself |
| `divide-zero` | development | tool failure | `divide_numbers(100, 0)` fails, answer NONE |
| `greeting` | development | no call expected | no tool call; open-ended answer, so answer correct is unassessable |
| `two-sums` | development | parallel | two `add_numbers` calls in any order, answers 42 and 105 |
| `unknown-balance` | development | missing evidence | no tool can read a balance; no call, answer NONE |
| `add-holdout` | holdout | simple | `add_numbers(58, 67)`, answer 125 |
| `divide-zero-holdout` | holdout | tool failure | `divide_numbers(7, 0)` fails, answer NONE |
| `given-distance` | holdout | no call expected | the question already gives 12 km; no call, answer 12 |
| `clock-half` | holdout | dependent | read the clock, then `divide_numbers(hour, 2)` |

The final answer ends with a line `<answer>number</answer>`, or `<answer>NONE</answer>` when no number can be had. Both versions share this format; version B adds one paragraph of rules: always call a tool for calculations and the time, send dependent calls in separate steps, and answer NONE after a tool error or when no tool can provide the evidence.

## Exercises

| Exercise | Preset | Max model calls | Main evidence |
| --- | --- | --- | --- |
| Development set: version A vs version B | `split=dev`, `versions=both` | 36 | 12 `lesson.case_result` events, two version reports, one paired analysis report |
| Holdout set: one run once the version is chosen | `split=holdout`, `versions=both` | 24 | as above, on the 4 holdout cases |
| Same version, two runs | `split=dev`, `versions=B`, `repeats=2` | 36 | two verdicts per case, `Pass^2`, `Pass@2`, cases whose verdict flipped |
| Judge model vs human annotation | `task=judge` | 6 | 6 `lesson.judgement` events, agreement, false passes, kappa |

- One `lesson.case_result` per case: the status of each of the five checks (passed, failed, not applicable, unassessable) with its detail, and the lists `violations`, `failures` and `unassessable`.
- One `lesson.report` per version: runs ended and accepted side by side, plus unassessable count, Wilson interval, suite version and fingerprint.
- With both versions, one more report for the paired analysis: improvements, regressions, cases with different verdicts, sign test p-value; with fewer than 6 differing cases the report says plainly that the difference is only a hint about direction.
- `lesson.task_card` at the start states which cases run, the suite fingerprint and the stop condition.
- Before running, the runner checks the worst case, cases × versions × repeats × 3 model calls, against this lesson's limit (80) and refuses up front instead of stopping halfway.

## What to look at in the lab

1. **Version comparison**: the suite fingerprint on the task card; the first case with a violation and a check marked unassessable; runs ended against accepted in a version report; finally the regressions and the p-value of the paired analysis.
2. **Same version, two runs**: how far "passed both times" is from "passed at least once", and whether any verdict flipped.
3. **Judge model calibration**: read the answers where the judge model and the human annotations disagree, especially false passes.

## How to run

Offline tests (deterministic model data; the tools really run, and the clock cases use this machine's real time):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_evaluation_sets.test_lesson -v
```

`fixtures.py` gives the two versions fixed behaviors: version A guesses arguments in the same step on dependent cases, gives a number after a tool error and invents a balance; version B makes one extra tool call on the holdout case `given-distance`, producing a regression; the scripted judge misjudges only `j6`. All of this is written by the script to test the reports and the validator; it does not represent any real model.

Real runs: run an exercise from the lab bench on the web page, or use `scripts/run_live.py evaluation-sets <exercise> --url http://127.0.0.1:8765 [--locale en]`. One development-set comparison uses up to 36 model calls and incurs the corresponding usage.

**Run languages:** this lesson runs in Chinese and English. System prompts, questions, check details, report text, the judge rubric and the sample answers are in `locales/zh_CN.py` and `locales/en.py`; case ids, categories, check statuses and judge verdicts (`pass`, `fail`) are code and the same in every language. The web page picks the UI language, and the run record states the language of the run.

## Limits

- The validator judges only by the case spec; a wrong spec gives wrong verdicts, which is why `test_lesson.py` tests the validator against hand-written traces first.
- Results on 6 or 4 cases describe only this suite; the p-value is for reference, and comparing several versions at once needs a stricter threshold or a rerun.
- The 6 calibration answers and their human annotations were written by the lesson author; they are evaluation data, not run records, and 6 samples cannot prove a judge model reliable.

## References

- Understanding AI Agents in Depth (深入理解 AI Agent), Apache-2.0, chapter 7: defining success, designing evaluation sets, automated evaluation, statistical significance; accompanying code `chapter1/context/grounding.py` (whether answer numbers have a source, declining to judge) and `chapter7/user-memory-policy-eval/runner.py` (deterministic rule scoring).
- claude-cookbooks (MIT): `tool_evaluation/tool_evaluation.ipynb`, `misc/building_evals.ipynb`.
- Hugging Face Agents Course (Apache-2.0): `units/en/bonus-unit2/`, `units/en/unit4/hands-on.mdx`; Microsoft AI Agents for Beginners (MIT): `10-ai-agents-production/README.md`.

What is borrowed is method (separate checks, tracing numbers to a source, exact matching, pairing and small-sample uncertainty); the suite, validator, versions and experiments are written by this project, and no reference code is copied.
