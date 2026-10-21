# Hybrid retrieval and reranking (`hybrid-retrieval`)

English · [简体中文](README.zh-CN.md)

Lesson numbers follow the curriculum order and appear only in the web page; this file refers to other lessons by lesson ID. The lesson is still `planned`: the implementation, offline tests and teaching content are written, but it has not been accepted with a real model yet.

## The problem

`keyword-retrieval` and `embedding-retrieval` each left misses behind: keyword retrieval cannot read paraphrases ("late fee" never finds "overdue charge"), and vector retrieval may rank code queries poorly ("How many seats does R-305 have?"). This lesson compares three strategies on the same handbook and the same 14 queries, and handles the three things retrieval cannot avoid once it is used for real:

1. **Merging**: keyword and vector results are merged by rank (Reciprocal Rank Fusion, RRF); BM25 scores and cosine similarities are never compared with each other.
2. **Reranking**: the top fused candidates go to the chat model to be reordered; hits before and after are compared, and the extra call and tokens are recorded.
3. **Filtering and updates**: superseded versions are removed by metadata; after documents are edited or deleted, outdated vectors are found, only the necessary chunks are re-embedded, and old chunks no longer count as current evidence.

All three exercises check retrieval only and generate no answer. Separating hits from correct answers is left to `rag-citations`.

## Files

| File | Role |
| --- | --- |
| `runtime.py` | The runner: the `compare`, `rerank` and `update` flows, plus assembling the lab reports (`lesson.report`) |
| `retrieval.py` | The three strategies: `embed_texts` requests Embeddings in batches (at most `context.embedding_batch_limit` texts each), `build_index`, `keyword_search`, `vector_search`, `hybrid_search`, `run_all` |
| `fusion.py` | `rrf` (merge by rank) and `apply_filter` (metadata filter that returns a record of every removed chunk); the signatures are fixed by the shared RAG modules |
| `rerank.py` | Builds the rerank request (candidates labeled `c1`, `c2`, ...) and checks the reply with `parse_order` |
| `index_update.py` | The working copy under `.runtime/hybrid-retrieval/<locale>/`, the file changes, fingerprints, the incremental update plan, and saving/loading the index with its fingerprint manifest |
| `locales/zh_CN.py`, `locales/en.py` | Runtime text: the rerank system prompt, report titles and labels, verdict wording |
| `fixtures.py`, `fixture_vocab.json` | Deterministic Embeddings and rerank replies for automated tests only (see below) |
| `test_lesson.py` | Behavior tests |
| `content.json`, `content.en.json` | Teaching content (Chinese source and English overlay) |

Shared modules: the handbook and chunking come from `lesson_document_loading`, BM25 and the query set from `lesson_keyword_retrieval`, the vector index from `lesson_embedding_retrieval/vector_index.py`. This lesson imports them and changes none of them.

## Exercises

| Exercise | Model requests (with batches of 10) | Evidence |
| --- | --- | --- |
| Compare three strategies on one query set (`compare`) | 6 Embedding requests: 4 chunk batches + 2 query batches | One report each for keyword, vector and hybrid (each on its own score scale); a ranks-only comparison report; "RRF step by step" |
| Reranking: paraphrased query (`rerank-synonym`, q06) | 5 Embedding requests + 1 chat request | Verdicts of the top 3 before and after, whether the candidate pool covers the human labels, the reply check, total tokens, time, request length |
| Reranking: exact-code query (`rerank-exact`, q02) | Same | Same |
| Metadata filtering and index updates (`update`) | 6 Embedding requests: 4 chunk batches + 1 query batch + 1 update batch | Filter records; the old index detected as out of date after the change, with its invalid chunks; the update plan; five checks after reloading |

Every `update` run copies the repository handbook to `.runtime/hybrid-retrieval/<locale>/corpus/` and edits only that copy: the overdue charge in `fees.md` goes from 0.5 to 0.3 (version 2026-10) and `hours-2025.md` is deleted. The handbook in the repository is never changed. The index is saved as `vectors.json` (vectors) and `manifest.json` (corpus version and one fingerprint per chunk), and the two files are checked against each other when read back.

## Running it

Offline tests (deterministic fixtures + real Python retrieval, filtering, file changes and index reads and writes):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_hybrid_retrieval.test_lesson -v
```

The tests point the working folder at a temporary directory under `.runtime/` and delete it afterwards.

A real run needs a provider with both a chat model and an Embedding model configured (without an Embedding model the platform refuses before starting, with error code `embedding_model_missing`). Once the lesson is `available`, run it from the lab page, or:

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py hybrid-retrieval compare --url http://127.0.0.1:8765
.\.venv\Scripts\python.exe scripts/run_live.py hybrid-retrieval update --url http://127.0.0.1:8765 --locale en
```

Real runs incur model usage. As of this writing, the lesson has **not been verified with a real model**.

## What to look at

- **Three strategies**: open the three strategy reports one by one and compare their verdicts on paraphrases and code queries; then read "Keyword hit, vector missed" and "Vector hit, keyword missed" in the comparison report; finally work out one row of "RRF step by step" by hand. The comparison report compares ranks and verdicts only, never scores.
- **Reranking**: first check "The candidates already contain every labeled section", then compare the ranks of the ★ chunks in the two columns; for the cost, look at total tokens ("not reported" when the provider gives none), time and the length of the user message. Run both arms without assuming either will improve.
- **Filtering and updates**: the filter records list the superseded `hours-2025` chunks; after the change, "The loaded index is detected as out of date" passes and a search with the old index returns "source deleted" and "text edited" chunks; the incremental update re-embeds 1 chunk; after reloading, all five checks pass.

## About the test fixtures

The Embeddings in `fixtures.py` are not a model: they count words against the hand-written concept vocabulary in `fixture_vocab.json`, one dimension per concept, synonyms on the same dimension, no dimension for codes, plus a small constant so no vector is all zeros. The rerank fixture orders candidates by their overlap with the query on the same vocabulary. They exist only to give automated tests fixed results and say nothing about how a real model retrieves; the web page has no fixture entry point.

## Run languages

The lesson runs in Chinese and English. Queries come from the matching language of the shared query set `corpus/queries.json`, and the handbook in the same language is used; the rerank system prompt, report text and verdicts live in `locales/zh_CN.py` and `locales/en.py`. Strategy names (keyword, vector, hybrid), filter reasons and update plan keys are code and the same in every language.

## References

- AI Agents in Depth (深入理解 AI Agent) (bojieli/ai-agent-book, Apache-2.0), chapter 3, "Hybrid retrieval" and "How knowledge should be updated", plus `chapter3/retrieval-pipeline/` (RRF and weighted fusion in `fusion.py`, the rerank stage, rank changes per stage). Adapted here: the RRF formula with k=60, bi-encoders versus cross-encoders, filtering outdated content by version metadata at retrieval time, and the index as a rebuildable derived artifact; the code is written by this project.
- Claude Cookbooks (MIT) `capabilities/contextual-embeddings/guide.ipynb`: hybrid search with BM25 + vectors + RRF, over-retrieving before reranking, measuring with Pass@k. Adapted here: reranking only a few candidates, and weighted RRF as a contrast.
- Hugging Face Agents Course (Apache-2.0) `units/en/unit3/agentic-rag/invitees.mdx` (starting from a BM25 retrieval tool) and `units/en/unit2/llama-index/components.mdx` (persisting the index and metadata so it need not be rebuilt).
