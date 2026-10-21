# Document loading and chunking (`document-loading`)

English · [简体中文](README.zh-CN.md)

The first lesson on knowledge and retrieval. A model cannot read a whole body of material at once, so retrieval works in small chunks, and every chunk must still point back to the original; an "instruction" written in the material is only data. This lesson reads a fixed local handbook into documents that keep their source, cuts them into chunks you can check by line number, compares two chunking presets, records load problems, and shows the trust boundary when a request is assembled. The lesson is still `planned`.

## Corpus

The "Bluestone Library Handbook" is fictional material written for this project, so the model knows nothing about it in advance. `corpus/zh-CN/` and `corpus/en/` each hold 10 Markdown files; files with the same name have the same line count and the same section anchors. Each file starts with a header giving `doc_id`, title, version and usage terms; `hours.md` also says `supersedes: hours-2025`. `corpus/problems/<locale>/` holds 5 problem files, and `corpus/queries.json` holds 14 queries shared by the later lessons (this lesson uses the cross-section queries `q09` and `q10`, and `q03`).

## Files

| File | Contents |
| --- | --- |
| `loader.py` | Loading: `load_corpus(locale, include_problem_files=False)` returns a list of `Document` and a list of `LoadIssue`; cleaning never changes the line count; `trust` is always `untrusted_data`; `corpus_version` combines the digests of all documents |
| `chunking.py` | Chunking: whole sections first, lines when over budget, packing by line, `overlap_lines` lines of overlap; chunk IDs are `doc_id:first-last`; `PRESETS` holds default and narrow, with a character budget per language |
| `runtime.py` | The runner for the three exercises: chunk catalogs checked against the files, cross-section evidence, the load log, two framings of the material |
| `locales/zh_CN.py`, `locales/en.py` | Every text sent to the model or written into events (system prompts, reports, issue explanations) |
| `fixtures.py` | Deterministic replies that serve automated tests only |
| `test_lesson.py` | Behaviour tests: real loading and chunking, every chunk mapped back to the file, problem files, tag escaping, string verdicts, cancellation, budget, both run languages |

`loader.py` and `chunking.py` are imported directly by keyword-retrieval, embedding-retrieval, hybrid-retrieval, rag-citations and agentic-rag, so their signatures and behaviour must not change; `tests/test_rag_corpus.py` guards the design checks of the corpus and the chunking.

## Exercises

| Exercise | Calls a model | What it does | Main evidence |
| --- | --- | --- | --- |
| Two chunking presets: chunk catalogs and cross-section queries | No | One run cuts the corpus with the default and the narrow preset, maps every chunk back to the file by line number, and checks whether the evidence for cross-section queries fits in one chunk | Three kinds of `lesson.report`: the corpus manifest, one chunk catalog per preset (chunk count, lines repeated by overlap, lines a fixed window would cut, the locate check), and the cross-section comparison |
| Load issues: empty documents, duplicates and parse failures | No | Loads the clean corpus and the problem files together, emits one event per issue, and checks that every file is accounted for | 5 × `lesson.load_issue` (empty, parse_error × 2, unsupported, duplicate); the load log reports 0 files that vanished silently |
| Trust boundary: planted instructions in the material | Yes, 2 calls | Gives the model the overdue rule and a reader comment with a planted instruction and asks the same question twice: material mixed into the instructions, then tagged and declared untrusted | One `lesson.trust_framing` and one `lesson.trust_result` (`verdict`, `source`) per round, request bodies readable word for word, and both replies side by side in the report |

Deterministic numbers (the same offline and in a real run): with the Chinese corpus, 38 chunks with the default preset and 82 with the narrow one; with the English corpus, 36 and 95. With the default preset both cross-section queries find all their evidence in one chunk; with the narrow preset neither does.

## What to look at

- **Two chunking presets**: what the lines stored twice by overlap buy. The cross-section query `q09` (late for a study room booking) lands in the single chunk `rooms:19-27` with the default preset; with the narrow preset the answer chunk starts at the "Check-in and release" heading and the bridging line stays in the previous chunk. This exercise does no retrieval; its conclusions are about the chunk catalog only.
- **Load issues**: `notice-board.md` has a duplicate record yet is still loaded; the other four problem files are not loaded; all 15 scanned files are accounted for.
- **Trust boundary**: how the system messages of the two rounds differ, what the model actually replied, and that the program only matches strings (does the reply state the cap "20", does it contain words the comment demanded); quoting the comment also counts as a hit. The reply source is in the report and in `lesson.trust_result.source`.

## Running

Offline tests (deterministic fixtures; loading, chunking and checks really run):

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_document_loading.test_lesson -v
```

Real runs: once the lesson is open, run it in the web lab, or use `scripts/run_live.py document-loading <exercise> --url http://127.0.0.1:8765 [--locale en]`. The first two exercises need no model configuration; "Trust boundary" sends 2 model requests.

## Verification so far

Offline only. The fixture's two replies are a fixed script (the mixed round follows the comment, the tagged round answers from the rule); they test that the program records and judges both outcomes and stand for no model. "Trust boundary" has not been run against a real model yet, and the lesson text does not presume what a real model will answer.

## References

Chunking strategies and the context a chunk loses follow chapter 3 of *Understanding AI Agents in Depth* (bojieli/ai-agent-book, Apache-2.0) and its companion code `chapter3/contextual-retrieval/chunking.py` and `chapter3/retrieval-pipeline/evaluate.py`; source tagging and context-level defences follow chapter 2 of the same book; Document, Node and metadata follow the Hugging Face Agents Course (Apache-2.0) `units/en/unit2/llama-index/components.mdx`; the contextual retrieval numbers come from claude-cookbooks (MIT) `capabilities/contextual-embeddings/guide.ipynb`. All adapted in our own words; no code was copied.
