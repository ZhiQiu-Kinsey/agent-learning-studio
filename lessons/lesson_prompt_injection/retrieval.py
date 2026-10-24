"""search_handbook over the handbook plus this lesson's own untrusted documents.

The index is the shared handbook chunks (document-loading) and two documents written for this lesson:
partner-bulletin carries an instruction for the assistant, transfer-notice points at a workspace file
that carries one. Both are ordinary Markdown loaded the ordinary way, and BM25 ranks them like any
other chunk. The planted-document list is for the report only; the tool result never says which
chunk is poisoned, because in a real system nothing does.
"""
from pathlib import Path

from lessons.lesson_document_loading.chunking import Chunk, chunk_document, default_chunks
from lessons.lesson_document_loading.loader import load_file
from lessons.lesson_keyword_retrieval.bm25 import BM25Index
from lessons.lesson_prompt_injection.guard import MAX_QUERY_CHARS, MAX_TOP_K
from lessons.lesson_prompt_injection.workspace import ToolError

LOCAL_CORPUS = Path(__file__).resolve().parent / "corpus"
# Documents in which an instruction aimed at the assistant is hidden: two written for this lesson, one from the shared handbook.
PLANTED_DOCS = frozenset({"partner-bulletin", "transfer-notice", "reader-notes"})
# The sections that carry the instruction; a chunk is planted when it covers one of them.
PLANTED_SECTIONS = frozenset({"partner-bulletin#fee-audit", "transfer-notice#pickup-flow", "reader-notes#note-fees"})
# Workspace files that carry such an instruction.
PLANTED_FILES = frozenset({"public/transfer-guide.txt"})


def local_chunks(locale: str) -> list[Chunk]:
    chunks = []
    for path in sorted((LOCAL_CORPUS / locale).glob("*.md")):
        document, issue = load_file(path, locale)
        if issue is not None:
            raise ValueError(f"lesson document {path.name} did not load: {issue.kind}")
        chunks.extend(chunk_document(document))
    return chunks


class Handbook:
    """The retrieval tool. include_planted=False leaves out every planted document (the direct-injection scenario)."""

    def __init__(self, locale: str, *, include_planted: bool = True, default_top_k: int = 3):
        self.default_top_k = default_top_k
        chunks = default_chunks(locale) + local_chunks(locale)
        if not include_planted:
            chunks = [chunk for chunk in chunks if chunk.doc_id not in PLANTED_DOCS]
        self.by_id = {chunk.chunk_id: chunk for chunk in chunks}
        self.index = BM25Index(chunks, locale)

    def search(self, query, top_k=None) -> dict:
        top_k = self.default_top_k if top_k is None else top_k
        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS:
            raise ToolError(f"query must be a non-empty string of at most {MAX_QUERY_CHARS} characters")
        if type(top_k) is not int or not 1 <= top_k <= MAX_TOP_K:
            raise ToolError(f"top_k must be an integer from 1 to {MAX_TOP_K}")
        hits = self.index.search(query, top_k)
        return {"query": query, "results": [self._describe(hit.chunk_id, hit.rank, hit.score) for hit in hits]}

    def _describe(self, chunk_id: str, rank: int, score: float) -> dict:
        chunk = self.by_id[chunk_id]
        return {"chunk_id": chunk_id, "rank": rank, "score": score, "doc_id": chunk.doc_id, "title": chunk.title,
                "version": chunk.version, "sections": list(chunk.anchors), "trust": chunk.trust, "text": chunk.text}


def planted_chunks(result: dict) -> list[str]:
    """Chunk ids in a search result that cover a planted section (known only because this lesson planted it)."""
    return [hit["chunk_id"] for hit in result.get("results", []) if PLANTED_SECTIONS & set(hit["sections"])]
