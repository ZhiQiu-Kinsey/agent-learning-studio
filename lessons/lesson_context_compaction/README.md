# Context compression and probe questions (`context-compaction`)

English · [简体中文](README.zh-CN.md)

One history, three ways to compress it, and one probe question to check whether the earliest tool result survived. This lesson needs a real model connection.

The runner really reads two materials in turn (`messages-context`, `application-state`), with `noise_repeats` rounds of side discussion between them. The goal, the first read and the side discussion are the "older part"; the second read and the last round of side discussion are the "recent part". Each compression rewrites only the older part and keeps the recent part as it is.

| Round | Request | What the older part becomes |
| --- | --- | --- |
| 1 | No compression (control) | kept as it is |
| 2 | Rule-based compression | one record that `rule_record` builds from goal, constraints, sources, facts and to-do; if it exceeds `char_budget` it is refused and this round sends nothing |
| 3 | Clearing old tool results | the same number of messages; the content of the earlier tool result becomes a `cleared` note |
| 4 | Summary request | the older part's original text plus one compression instruction (`summary_style` picks which) |
| 5 | Summary compression | the summary the model wrote in round 4 |

Rounds 1, 2, 3 and 5 ask the same probe question: "Which item did the earliest material you read come from? What is its original wording?" The lab report keeps two things apart: whether the original wording is still in the context (a local string check, recorded as `phrase_in_context` in `lesson.compaction`), and whether the answer gives both the source name and the original wording (a keyword screen; read the answer even on a hit).

| Exercise | Inputs | Model calls |
| --- | --- | --- |
| Three compression methods, one probe question | budget 300, instruction that keeps sources | 5 |
| Rule-based compression's budget cannot hold the evidence | budget 100 | 4 |
| Switch to a brief summary instruction | `summary_style=brief` | 5 |

Character counts are local JSON lengths, not tokens; usage shows only the `usage` that the provider's response actually returned, and says "not reported" when there is none. The character count, the local string check, the helpers that build tool pairs and side discussion, and the material lookup are imported from the `runtime.py` of the lesson "Context budget and the truncation window". `fixtures.py` serves automated tests only; its summaries and answers are written by the script.

**Run language:** this lesson runs in Chinese and in English. The goal, the probe question, the system prompts, the summary instructions, the template of the rule-based record, the names of the four arms and the report text are in `locales/zh_CN.py` and `locales/en.py`; the material and the side discussion come from `locales/helpers/` of "Context budget and the truncation window". The English rule-based record also fits the default budget of 300 and does not fit 100, so both languages reach the same result.

The trade-off between rule-based compression and model summaries follows the ideas of chapter 2, "Context compression strategies", of *Understanding AI Agents in Depth* and its `chapter2/context-compression/compression_strategies.py`; the code and experiments were written for this project. For the reading scope, see `docs/architecture/budget-memory-sources.md`.

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_context_compaction.test_lesson -v
```
