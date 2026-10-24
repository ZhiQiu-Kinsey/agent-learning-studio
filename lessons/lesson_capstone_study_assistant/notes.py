"""The frozen course-notes corpus of the capstone, loaded and searched with the retrieval lessons' own modules.

Nothing here is a new retrieval method: loading, chunking and BM25 come from the
document-loading and keyword-retrieval lessons, unchanged. This file only points them at a
different folder, because the handbook corpus of those lessons describes a library and the
capstone is a study assistant. Every document is data (trust = untrusted_data), including the
forum digest that carries an injected instruction on purpose.
"""
import hashlib
from functools import lru_cache
from pathlib import Path

from lessons.lesson_document_loading.chunking import Chunk, chunk_corpus
from lessons.lesson_document_loading.loader import Document, LoadIssue, find_repeated_lines, load_file
from lessons.lesson_keyword_retrieval.bm25 import BM25Index

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
# The chunk that carries the injected instruction; the cases and the verifier name it, the model never sees this id list.
POISONED = "forum-digest#shortcut"
MAX_TOP_K = 8


@lru_cache(maxsize=None)
def load_notes(locale: str) -> tuple[tuple[Document, ...], tuple[LoadIssue, ...]]:
    """Load every note of one language; load problems are returned, never skipped silently."""
    folder = CORPUS_DIR / locale
    if not folder.is_dir():
        raise ValueError(f"no course notes for locale {locale!r}")
    documents, issues, seen_lines = [], [], {}
    for path in sorted(folder.glob("*.md")):
        document, issue = load_file(path, locale)
        if issue:
            issues.append(issue)
            continue
        issues.extend(find_repeated_lines(document, seen_lines))
        documents.append(document)
    return tuple(documents), tuple(issues)


@lru_cache(maxsize=None)
def notes_chunks(locale: str) -> tuple[Chunk, ...]:
    return tuple(chunk_corpus(list(load_notes(locale)[0])))


def corpus_version(locale: str) -> str:
    """One digest over all documents: any edit, addition or removal changes it, so a score names its corpus."""
    lines = sorted(f"{doc.doc_id}:{doc.sha256}" for doc in load_notes(locale)[0])
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]


def hit_record(chunk: Chunk, rank: int, score: float) -> dict:
    """One search hit as the tool returns it: the id to cite, the version to compare, and the trust label."""
    return {"chunk_id": chunk.chunk_id, "rank": rank, "score": score, "doc_id": chunk.doc_id, "title": chunk.title,
            "version": chunk.version, "supersedes": list(chunk.supersedes), "trust": chunk.trust, "text": chunk.text}


class NotesSearch:
    """BM25 over the notes of one language."""

    def __init__(self, locale: str):
        self.chunks = {chunk.chunk_id: chunk for chunk in notes_chunks(locale)}
        self.index = BM25Index(list(self.chunks.values()), locale)

    def search(self, query: str, top_k: int = 5) -> dict:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if type(top_k) is not int or not 1 <= top_k <= MAX_TOP_K:
            raise ValueError(f"top_k must be an integer from 1 to {MAX_TOP_K}")
        return {"hits": [hit_record(self.chunks[hit.chunk_id], hit.rank, hit.score)
                         for hit in self.index.search(query, top_k)]}
