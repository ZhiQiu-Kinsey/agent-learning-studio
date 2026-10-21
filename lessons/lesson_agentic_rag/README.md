# Agentic RAG with bounded iteration (`agentic-rag`)

English · [简体中文](README.zh-CN.md)

The lesson is still `planned`: the implementation, offline tests and bilingual content are done; acceptance with a real model has not been run yet.

## The problem

Static RAG searches once with the question as written and answers once. On a multi-hop question, where what to look up second depends on what the first hop found, evidence the first search missed never comes back. This lesson wraps retrieval as a tool with a contract, `search_handbook`, and lets the model decide what to search and how often. The runner does three things:

1. **Log every attempt**: the query, the terms it splits into, the chunks returned and the chunks that are new (`lesson.attempt`).
2. **Spot repeats**: a search with the same set of terms and no larger `top_k` is marked `duplicate_of`, counted as usual, and named in the next round's search record (`lesson.harness_injected`).
3. **Stop honestly at a limit**: searches, model calls and time, all checked before every request; the stop reason goes into `lesson.stop` and the lab report (`lesson.report`).

Whether the extra searches pay off is judged by program checks on the same question set: whether every cited chunk came from this run's searches, whether the citations cover every human-labelled section, plus the real number of model calls and the `total_tokens` the provider reported ("not reported" when it did not).

The material is the shared fictional corpus, the Bluestone Library Handbook (`lessons/lesson_document_loading/corpus/`); the questions come from the shared query set `corpus/queries.json`. Retrieval reuses the BM25 index in `lessons/lesson_keyword_retrieval/bm25.py` over the default chunks of `lesson_document_loading/chunking.py`.

## Files

| File | Contents |
| --- | --- |
| `search_tool.py` | The tool definition, `Handbook.search` (argument checks, then the search limit, then the BM25 search, then the attempt log), the structured errors `InvalidQuery` / `SearchBudgetExhausted`, and `cited_in_results` (whether citations came from this run's searches) |
| `runtime.py` | The input model `Inputs`; `stop_reason` (the three limits); `progress_note` (the search record); `run_agentic` (the bounded loop); `run_static` (the static baseline); `_report` (the lab report) |
| `locales/zh_CN.py`, `locales/en.py` | Runtime text: tool descriptions, errors, system prompts, the search record, stop reasons, report labels |
| `locales/fixtures/` | Query and answer wording of the offline test script (tests only) |
| `fixtures.py` | The offline test model: one fixed set of queries and a final answer per exercise; usage numbers are scripted |
| `test_lesson.py` | Tool contract, repeat detection, the four exercises, the three limits, citation checks, unreported usage, broken proposals from the model, a model that never stops searching, cancelling between rounds, the hand-worked search results quoted in the text, no Chinese in English runs, input validation |
| `content.json` / `content.en.json` | Lesson content and its English overlay |

## Exercises

| Exercise | Inputs | Result in offline test mode (the fixture plays the model; searches really run) |
| --- | --- | --- |
| Static RAG: one search + one answer | `mode=static`, q11 | 1 search made by the runner, 1 model call; citations cover the first hop only |
| Agentic RAG: split into sub-questions, fetch the second hop | q11, at most 4 searches and 5 model calls | 2 searches, 3 model calls, both hops covered; stop reason "The model judged the evidence enough" |
| No-answer question: stop within budget | q07, at most 3 searches | Search 2 is marked as a repeat; the loop stops after 3 searches, the last request has `tool_choice=none`, and the answer says the material is not enough, citing nothing |
| Search limit of 1 | q11, `max_searches=1` | 1 search, 2 model calls, the same evidence as Static RAG; stop reason "Search limit reached" |

Adjustable inputs: `mode`, `question_id` (q11 and q12 multi-hop, q04 synonym, q01 exact code, q07 and q08 no answer), `max_searches` (1–6), `max_model_calls` (2–8, the last call is kept for the final answer), `time_budget_s` (5–300 seconds; once spent, no more model requests), `top_k` (1–5).

## What to look at in the experiments

- **Multi-hop question**: Static RAG's search is made by the runner (`origin: course_program`); in the loop the first query is a sub-question the model wrote, and the second carries "Level 3" from the first hop. Compare "The citations cover every human-labelled section" and the model calls of the two arms.
- **No-answer question**: an empty result is still a search; look at `duplicate_of` on the repeated search, `repeats` in the search record, the reason in `lesson.stop`, and `tool_choice` of the last request.
- **A budget for one search only**: both arms get the same citation result but different model calls, a case where the extra cost buys nothing.

The human labels (`gold_covered`, the coverage checks in the report) are for the learner only and never reach the model. Passing the citation checks does not make the answer text correct; read the answer too.

## How to run

Offline tests (deterministic fixture plus real BM25 searches, no key needed):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_agentic_rag.test_lesson -v
```

Real runs (once the lesson is open; this uses model quota):

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py agentic-rag agentic --url http://127.0.0.1:8765
.\.venv\Scripts\python.exe scripts/run_live.py agentic-rag no-answer --url http://127.0.0.1:8765 --locale en
```

**Run language:** this lesson runs in Chinese and in English. The question is taken from `queries.json` in the run language and the chunks come from that language's corpus; tool names, parameter names, event names and stop codes are the same in every language.

## References and what changed

- AI Agents in Depth (bojieli/ai-agent-book, Apache-2.0), chapter 3 on agentic RAG and the companion `chapter3/agentic-rag/`: retrieval as a tool, the offline comparison of one search against decomposed searches, the search budget and the forced final answer (`campaign.py`). This lesson instead checks three limits before every request, writes the attempt log back into the request each round, and checks citations with a program; the code is written by this project.
- Microsoft AI Agents for Beginners (MIT), `05-agentic-rag`: the iterative loop and keeping state across steps to avoid going round in circles.
- Hugging Face Agents Course (Apache-2.0), `unit3/agentic-rag`: retrieval as one of the agent's tools.
- Mini-SWE-Agent (MIT), `agents/default.py`: checking step, cost and wall-clock limits before every model request.
