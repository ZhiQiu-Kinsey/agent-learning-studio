# RAG answers and citations (`rag-citations`)

English · [简体中文](README.zh-CN.md)

The question this lesson answers: once retrieved chunks go to the model, how do you know each claim in the answer really comes from those chunks? The model answers in structured JSON, every claim carrying a chunk ID and a verbatim quote, and a program checks them one by one; when an answer is wrong, the lesson first decides whether retrieval missed the evidence or the model misused it. The lesson is still `planned`, and only offline verification has been done so far (see the end).

Retrieval is BM25 from the `keyword-retrieval` lesson (`lessons/lesson_keyword_retrieval/bm25.py`), not Embedding, so each run has generation requests only and the evidence chain stays short. The retrieval method is not the point of the lesson: swap in the hybrid retrieval of the `hybrid-retrieval` lesson and the format, checks and triage stay the same. The material is the shared "Bluestone Library Handbook" corpus, and the questions come from the shared query set `lessons/lesson_document_loading/corpus/queries.json`.

## Files

| File | Contents |
| --- | --- |
| `citations.py` | Citation checks (public API, also used by `agentic-rag`): `GroundedAnswer` (answer structure), `parse_answer` (JSON and field layers), `check_citation` / `check_answer` (existence first, then quote and numbers, editions by `supersedes`), `classify` (retrieval/generation triage), `CATEGORIES` |
| `runtime.py` | The runner: `search_handbook` retrieval → `judge` against the human annotation → model request → checks and triage → two `lesson.report` events |
| `locales/zh_CN.py`, `locales/en.py` | Runtime text: system prompt, user message template, category and reason names, report text |
| `fixtures.py`, `locales/fixture/` | Offline fixture for automated tests only: returns scripted JSON based on the question and chunk IDs in the request |
| `test_lesson.py` | Behavior tests: real BM25 retrieval, every branch of the citation checks, both run languages, stopping and input validation |
| `content.json`, `content.en.json` | Teaching content and its English overlay |

The stable API of `citations.py`:

```python
parse_answer(raw: str) -> tuple[GroundedAnswer | None, list[str]]
check_answer(answer: GroundedAnswer, provided: Sequence[Chunk]) -> AnswerCheck
check_citation(citation: Citation, provided: Mapping[str, Chunk], replaced=None) -> CitationCheck
classify(check: AnswerCheck | None, *, hit: bool | None, complete: bool | None) -> tuple[str, tuple[str, ...]]
```

- `provided` holds only the chunks handed to the model in this request: existence is relative to this one request, so a chunk that is in the corpus but was not provided this time counts as not provided.
- `CitationCheck.reason` is `ok`, `not_provided`, `quote_too_short` or `quote_not_found`; `ClaimCheck.unmatched_numbers` lists numbers in a claim that occur in none of its found quotes.
- `hit` / `complete` for `classify` come from `query_set.judge` (the human annotation); `None` means the handbook has no answer. Category codes are in `CATEGORIES`; their names per language are in `locales/`.

## Exercises

| Exercise | Query | Model requests | Evidence to look at |
| --- | --- | --- | --- |
| A question with evidence | q03 What is the maximum overdue charge per item? | 1 | `<sources>` in the request (including the reader comment dressed up as an instruction), the citation checks in `lesson.citation_check` |
| A question the handbook cannot answer | q07 Does the library have a car park? | 1 | Retrieval still returns 5 chunks; `insufficient_evidence` and the report's `declined` check |
| A question with conflicting versions | q13 What time does the library close on Sunday? | 1 | `conflicts` cites both the 2026 and 2025 editions; `current` is computed from `supersedes` by the program |
| Three failure-triage questions | q04, q01, q10 | 3 | A retrieval miss, a citation to a chunk that was not provided, and evidence found but misused |

Inputs: `query` takes any id from the query set (q01–q14) or `triage`; `top_k` (1–8, default 5) is how many chunks each question hands to the model. In a Chinese run, setting `top_k` to 3 for the conflict question keeps every 2026 chunk out of the request, and the category becomes "Retrieval: evidence incomplete"; in an English run the 2026 edition ranks first, so `top_k` 1 leaves out the old edition instead.

## What the experiments show

1. **Questions with evidence, without evidence and with conflicting sources**: the same prompt and checking rules, only the question changes. Look at what retrieval returned in `tool_result`, how the request keeps the chunks apart from the question, `exists` and `quote_found` for each citation, and how the report lists only the checks that actually ran.
2. **Retrieval failure or generation failure?**: `lesson.retrieval_judge` uses the human annotation to decide whether the evidence reached the request; `lesson.citation_check` records each citation's checks and the category; the second `lesson.report` counts retrieval failures and generation failures.

What this proves: which chunks retrieval provided this time, which ones the answer cited, whether each citation was present, whether its quote can be found word for word, whether the numbers match, and where a failure broke. What it does not prove: that a claim means what its quote means (string checks cannot tell "at most" from "at least"), or anything about the overall quality of the model or the retriever.

## Running it

Offline tests (fixture plus real BM25 retrieval and checks, no model calls):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_rag_citations.test_lesson -v
```

Real run (once the lesson is available; this uses model quota):

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py rag-citations triage --url http://127.0.0.1:8765 --locale en
```

## Honesty notes

- `fixtures.py` serves tests only. The two generation errors in "Three failure-triage questions" (the invented chunk ID `borrowing:11-13`, and "5 opening days" changed to "7 opening days") are written on purpose by the fixture; `x_offline_fixture` in the response and `answer_source: offline_fixture` in `lesson.citation_check` both say so. A real model may make neither mistake.
- The fixture reports no usage, so the report shows usage as not reported.
- This environment had no model key, so **no real model run has been made**; the lesson stays `planned`. Before it opens, every exercise must be run for real once in each run language and checked against the text.

## References

- *Understanding AI Agents in Depth* (bojieli/ai-agent-book, Apache-2.0), chapter 3 on RAG basics, retrieval metrics, knowledge updates and the security boundary of RAG, and chapter 2 on source marking.
- Microsoft AI Agents for Beginners (MIT) `05-agentic-rag`; Hugging Face Agents Course (Apache-2.0) `unit3/agentic-rag`.
- claude-cookbooks (MIT) `misc/using_citations.ipynb`, `capabilities/retrieval_augmented_generation/guide.ipynb`, `capabilities/contextual-embeddings/guide.ipynb`.

Ideas were adapted, not copied: no code was reused and nothing was translated sentence by sentence; the corpus, query set, checking rules and experiments are written by this project.
