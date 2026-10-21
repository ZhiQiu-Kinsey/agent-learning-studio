---
doc_id: retrieval
title: Retrieval and Citation Notes
version: 2026-10
license: Original to this project; released under the repository license
---
## Chunking {#chunks}

The default chunk budget is 450 characters in English and 150 in Chinese, and neighbouring chunks overlap by 1 line.

Every chunk is an exact line range of its source file, so a citation can point back to specific lines.

## Keyword retrieval {#keyword}

BM25 defaults to k1 of 1.5 and b of 0.75, and it is good at codes and exact names.

Keyword retrieval does not know synonyms, so a query worded differently from the material misses it.

## Citation checks {#citation}

A citation check has two steps: first whether the chunk id is among the chunks this request provided, then whether the quote really occurs in that chunk.

A quote shorter than 4 characters is no evidence, and every number in a claim must occur in its quote.

## Insufficient material {#insufficient}

When the material has no answer, the reply must say plainly that it is insufficient and name what is missing.

Retrieval still returns nearby chunks; they are noise and must not be used as grounds for an answer.
