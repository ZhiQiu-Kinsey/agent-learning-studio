# Embedding and vector retrieval (`embedding-retrieval`)

English · [简体中文](README.zh-CN.md)

Lesson numbers follow the curriculum order and only appear on the web page; files refer to other lessons by lesson ID. ## The problem this lesson solves

BM25 from the previous lesson, `keyword-retrieval`, only matches words: a query about a "late fee" misses a document that only says "overdue charge". This lesson sends every chunk to an embedding model to turn it into a vector, searches by meaning with cosine similarity, and compares hits and misses with BM25 query by query on the same query set. Vectors cost model calls, so the lesson also covers how the index is saved, what it records about where it came from, and when an old index must not be used any more.

This lesson only sends embedding requests. It does not call a chat model and writes no answer.

**Status:** `available`, with a known limit. The lesson needs a provider with an Embedding interface. None was configured on 2026-10-21 (Anthropic has none), the platform refused every run of this lesson at creation, and so it has **not been run against a real model**; only the offline tests cover it ([verification record](../../docs/verification/live-runs-2026-10-21.md)).

## Files

| File | Contents |
| --- | --- |
| `runtime.py` | The runner: `Embedder` calls `context.embed` in batches of `context.embedding_batch_limit`; `open_index` loads or rebuilds the index; `stale_reasons` says, item by item, why an old index cannot be used; `compare` has both retrievers answer the same query set |
| `vector_index.py` | Brute-force vector index (a shared RAG core module, signatures unchanged): `cosine`, `VectorIndex.search/save/load/is_stale`, `index_path` |
| `locales/zh_CN.py`, `locales/en.py` | Runtime text such as report labels, checks and answers, one file per run language |
| `fixtures.py`, `test_vectors.json` | Offline test vectors built from a concept vocabulary; for automated tests only |
| `test_lesson.py` | Behavior tests: batching, saving and reuse, staleness checks, comparison results, error paths, both run languages |
| `content.json`, `content.en.json` | Teaching content and its English overlay |

Shared modules: the corpus and chunking live in `lessons/lesson_document_loading/`, BM25 and the query set in `lessons/lesson_keyword_retrieval/`.

## Exercises

| Exercise | What it does | Embedding requests on a first run |
| --- | --- | --- |
| Build the index and search | Builds an index of the default chunks (reused when it exists and is not stale), then runs vector search for "How much is the late fee for returning a book late?"; can filter by document | 4 chunk batches + 1 query = 5; only 1 when the index is reused |
| Vector retrieval against the keyword baseline | All 14 queries go to vector retrieval and BM25, top 5 each, judged against the same human labels | 4 + 2 = 6; 2 when the index is reused |
| New dimensions: the old index cannot be used | 256 to 512 dimensions: the old index is judged stale, vectors of different sizes cannot be compared, a new index is built and saved to another file | 4 + 1 + 4 = 9 |
| Changed documents: the old index cannot be used | Simulates taking the 2025 opening hours offline: the old index is judged stale, misusing it would return chunks that were taken offline, an index is built for the new documents (in memory only, the real index is not overwritten) | 4 + 1 + 4 = 9 |

Embedding requests count against the call limit in `lesson.json` (`max_rounds` is 12). There are 38 default chunks in Chinese and 36 in English, at most 10 per batch.

## Where the index lives and when it goes stale

- Live runs write `.runtime/rag-index/<locale>/<model>-<dimensions>.json` (never committed). Offline test mode never touches that folder; each run uses a temporary folder.
- The index records the embedding model, the dimensions, the corpus version (`corpus_version`, a digest over every document's content digest) and the chunk list. If the model, the dimensions or the corpus version differ, or the chunk list differs, the index is judged stale and rebuilt, and the index report says why.
- Three guards: the file name includes the dimensions; `is_stale` checks where the index came from; `search` refuses a query vector whose size differs from the index.
- If the provider ignores the `dimensions` parameter and returns another length, the runner stops with an error instead of mixing vectors of different sizes into the index.
- What gets embedded is `embedding_text`: the original chunk text minus the `{#anchor}` section marks. BM25's tokenizer drops them too, so both retrievers read the same words; the cost is that the embedded text is no longer identical to the original chunk text. `hybrid-retrieval` embeds the original chunk text directly, and the two lessons keep separate indexes that cannot be reused for each other. `corpus_version` only digests the document contents, so changing how `embedding_text` prepares the text does not make an old index stale; rebuild it yourself.
- If the selected provider has no embedding model configured, the platform refuses the run before it starts (error code `embedding_model_missing`) and points to the model settings.

## What to look at in the experiments

- **Build the index and search**: `data.body.input` and `dimensions` of the first batch request; a vector in the response; the model, dimensions, corpus version and status (built or reused) in the index report; the cosine similarities in the results table.
- **Vector retrieval against the keyword baseline**: the two checks (same query set, same chunks); the hit rate and full coverage rate of both retrievers; the per-query table; for queries the documents cannot answer, vector retrieval still returns 5 chunks.
- **Stale index check**: the stale reasons with old and new values; the old index refusing a query vector of another size; with changed documents, `hours-2025` chunks in the old index's results and none in the new index's.

## Running it

Offline tests (no key needed; vectors come from the fixture):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_embedding_retrieval.test_lesson -v
```

A live run needs a provider with an embedding model (Bailian defaults to `text-embedding-v4`; for other providers see the model settings). run it on the web page or with:

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py embedding-retrieval build-and-search --url http://127.0.0.1:8765 --locale en
```

## About the offline test vectors

`fixtures.py` builds vectors from the concept vocabulary in `test_vectors.json`: one dimension per concept, counting how often its words occur, plus one constant dimension shared by every text. Synonyms (late fee / overdue charge) share a dimension; codes such as room numbers and card codes have none. That is why, offline, only vector retrieval hits the paraphrased queries and only BM25 hits `q02` (R-305): the split is reproduced by design and says nothing about any real model. The report's "Vector source" metric says these are test vectors. The usage numbers are scripted too.

## References

- *Understanding AI Agents in Depth* (深入理解 AI Agent), bojieli/ai-agent-book (Apache-2.0), chapter 3 "Dense embeddings" and `chapter3/dense-embedding/`: working cosine similarity by hand, exact search versus ANN, the note on what recall@k measures.
- Claude Cookbooks (MIT), `capabilities/contextual-embeddings/guide.ipynb`: embedding in batches, saving vectors to avoid paying twice, Pass@k evaluation and the idea of a context prefix.
- Hugging Face Agents Course (Apache-2.0), `unit2/llama-index/components.mdx`: queries must use the same embedding model as the index.
- Microsoft AI Agents for Beginners (MIT), `05-agentic-rag`: retrieval results should be evaluable and traceable.

Ideas were adapted, not copied or translated sentence by sentence; batching, the staleness rule, the experiments and the test vectors are written by this project.
