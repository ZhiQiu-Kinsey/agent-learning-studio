# Keyword retrieval and BM25 (`keyword-retrieval`)

English · [简体中文](README.zh-CN.md)

Lesson numbers follow the curriculum order and appear only on the web page; files refer to other lessons by course ID. **This lesson calls no model.** Every score is computed by local Python and the same input always gives the same result; offline tests and web runs execute the same code, with no fixtures.

**Status:** `available`. This lesson calls no model. Its exercises were run once in each run language through the real run path on 2026-10-21 ([verification record](../../docs/verification/live-runs-2026-10-21.md)); no real-model verification applies.

## The problem this lesson solves

`document-loading` cut the "Bluestone Library Handbook" into numbered chunks (38 in Chinese, 36 in English). When a reader asks a question, the program has to pick the few chunks most likely to hold the answer and be able to say why they rank first. This lesson uses BM25 for keyword retrieval: it looks only at the words a query shares with a chunk, and the rarer those words, the more often they occur and the shorter the chunk, the higher the score.

The lesson sets out to do three things:

1. Every result maps to a chunk id (file name and original line numbers) and a score, and the score can be taken apart term by term and checked by hand;
2. Hits and misses are counted on a fixed query set (14 queries in six kinds), with the corpus version, query set version and parameters recorded, so later lessons can rerun and compare under exactly the same conditions;
3. Every miss gets a reason: why reworded queries are not found, and why BM25 still returns results when the handbook has no answer.

## Files

| File | Contents |
| --- | --- |
| `runtime.py` | The runner: all three exercises share `build_index` (builds the index and emits `lesson.index`); `query_table` runs the whole query set; `explain` takes one result's score apart; `misses` analyses misses and unanswerable queries; report assembly sits at the end of the file in `_report_*` |
| `bm25.py` | BM25 (a shared RAG core module whose signatures and behavior stay fixed; later lessons import it): `tokenize` (lowercase English words minus stop words; Chinese character bigrams minus stop characters), `BM25Index.search/explain`, `Hit` |
| `query_set.py` | Query set structure (shared RAG core module): `load_queries`, `query_set_version`, `judge` (decides `hit`, `complete` and `first_rank` from the sections a chunk covers) |
| `stopwords.json` | Chinese and English stop words; Chinese has a word list and a character list. The code holds no language's word list |
| `locales/zh_CN.py`, `locales/en.py` | Runtime text: the three queries asked again in the handbook's words, report labels, checks and answers |
| `test_lesson.py` | Behavior tests: real indexing and scoring, the formula checked factor by factor, the effect of parameters and `top_k`, miss reasons, structured errors, input validation, stopping, both run languages, the experiments' observation points |
| `content.json`, `content.en.json` | Teaching content and its English translation layer |
| `lesson.json`, `lesson.en.json` | The implementation manifest and its English translation layer |

The shared corpus, query wording and chunking live in `lessons/lesson_document_loading/` (`corpus/`, `corpus/queries.json`, `chunking.py`, `loader.py`).

## Exercises

| Exercise | What it does | Main evidence |
| --- | --- | --- |
| Hit table for the whole query set | Searches each of the 14 queries once, keeps the first `top_k` (5 by default) and judges them against the annotations | One `lesson.search` per query (terms, result chunks with per-term contributions, verdict); the report: hit rate, full coverage rate, mean reciprocal rank, missed queries, versions and parameters, and whether a rebuilt index reproduces every row |
| Take one result's score apart | By default the top result of `q03`; `query_id`, your own `query` or a `chunk_id` can be set | `lesson.score`: per query term the document frequency, inverse document frequency (raw and floored), term frequency, term frequency part and contribution, plus length and the length normalization factor; the report checks that the contributions add up to the score and shows the score under default parameters for comparison |
| Misses and unanswerable queries | Finds a reason for each of the 3 reworded queries and asks them again in the handbook's words; shows what BM25 returns for the 2 unanswerable queries | One `lesson.miss` per miss (reason `no_shared_terms` or `outranked`, the terms the annotated chunks share and their rank, the rewrite result); one `lesson.no_answer` per unanswerable query (how many results, top score) |

Three more exercises are the same two scenarios with different preset parameters, one per experiment arm that changes a parameter: "Hit table: top 1 only" (`top_k=1`), "Score breakdown: length normalization off (b=0)" and "Score breakdown: term frequency saturates later (k1=3)". The test mode accepts only an exercise's own preset inputs, so each such arm points at its own exercise instead of carrying inputs.

Inputs: `top_k` (1–10), `k1` (0–3), `b` (0–1); the explain exercise also takes `query_id`, `query` and `chunk_id`. The question box on the web page is a learner note; it goes into the report and does not change the search.

With default parameters both languages give the same hit table: of 12 annotated queries, 9 hit, 7 are fully covered, the mean reciprocal rank is 0.75, and `q04`, `q05` and `q06` miss. In Chinese all three misses share no term at all; in English `q06` shares only `after` with its annotated chunk, which ranks 9th, so setting `top_k` to 10 makes it hit.

## What to look at in the experiments

- **Keyword retrieval on one query set** ("Top 5 (default)" runs the exercise "Hit table for the whole query set", "Top 1 only" runs "Hit table: top 1 only"): versions and parameters in `lesson.index`; the first query's terms and top result; `hit`, `complete` and `first_rank` in the verdict; the report table, hit rate and full coverage rate (with `top_k=1` coverage drops clearly while the hit count holds); the rerun check.
- **Take one result's score apart** (default, `b=0`, `k1=3`; each arm is its own exercise): the per-term table; the length normalization factor (1 when `b=0`); the total; the check that term contributions add up to the score; the score under default parameters for comparison.
- **Where misses come from**: the first miss's reason and shared terms; the first hit rank after asking in the handbook's words; how many results the unanswerable queries return and their top score; the report table.

Prediction: how many `lesson.search` events a "Top 5 (default)" run emits (one per query).

## Running

Offline tests (no key needed; this lesson calls no model anyway):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_keyword_retrieval.test_lesson -v
.\.venv\Scripts\python.exe -m unittest tests.test_rag_corpus -v   # design checks of the shared corpus, BM25 and query set
```

It runs on the web page, or from a script that prints an event summary (no model usage):

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py keyword-retrieval query-table --url http://127.0.0.1:8765
.\.venv\Scripts\python.exe scripts/run_live.py keyword-retrieval misses --url http://127.0.0.1:8765 --locale en
```

## Run languages

The lesson runs in Chinese and English. Query wording is in `corpus/queries.json` per language; the three handbook-worded rewrites and the report text are in `locales/`; query ids, annotation anchors, chunk ids, event fields and miss reason codes are the same in every language. Chinese is cut into character bigrams and English into words, so vocabulary, average length and scores differ between the languages while the conclusions of the hit table agree. English runs emit no Chinese (checked by `test_lesson.py`).

## References and adaptation

- *AI Agents in Depth* (bojieli/ai-agent-book, Apache-2.0), Chapter 3, "Sparse embeddings: from TF-IDF to BM25", "Hybrid retrieval" and the retrieval metrics, plus Experiment 3-5 `chapter3/sparse-embedding/` (`bm25_engine.py`, `README.md`): the BM25 formula with RSJ inverse document frequency, `k1=1.5`/`b=0.75` as starting values, the floor on inverse document frequency, per-term contribution logs, keeping codes whole, the footnote that `recall@k` is really a hit rate, and the contrast "exact words found precisely, synonyms not understood".
- Hugging Face Agents Course (Apache-2.0) `unit2/llama-index/components.mdx`: the five stages of loading, indexing, storing, querying and evaluation, and measuring changes against a fixed evaluation.
- Microsoft AI Agents for Beginners (MIT) `05-agentic-rag/README.md`: rewriting the query and searching again when retrieval falls short, and keeping retrieval traceable (used here only as a lead-in to `agentic-rag`).

Only adapted in our own words; no code was copied and nothing was translated sentence by sentence. Chinese bigram tokenizing, annotations by section anchor, the miss reason categories, rewrite verification and all experiments were written for this project.
