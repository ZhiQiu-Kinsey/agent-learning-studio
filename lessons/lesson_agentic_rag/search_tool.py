"""search_handbook: keyword retrieval over the Bluestone Library Handbook, wrapped as a tool with a contract.

The idea of exposing the knowledge base as one search tool with chunk ids and scores in its result follows
knowledge_base_search in ai-agent-book chapter3/agentic-rag (Apache-2.0). The argument checks, the structured
errors, the search limit and the attempt log are written by this project. Retrieval reuses keyword-retrieval's
BM25Index over document-loading's default chunks, so every search can be taken apart in those lessons.
"""
from dataclasses import dataclass

from lessons.lesson_agentic_rag.locales import Texts
from lessons.lesson_document_loading.chunking import default_chunks
from lessons.lesson_keyword_retrieval.bm25 import BM25Index, tokenize

MAX_QUERY_CHARS = 200
MAX_TOP_K = 5


class InvalidQuery(ValueError):
    """The arguments break the contract: nothing was searched and no search was counted."""


class SearchBudgetExhausted(ValueError):
    """The run's search limit is used up: the call is refused before searching."""


def tool_definition(t: Texts) -> dict:
    """The one tool sent with every agentic request. Names are code; descriptions come in the run's language."""
    return {"type": "function", "function": {
        "name": "search_handbook",
        "description": t.tool_description,
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": t.tool_query},
            "top_k": {"type": "integer", "minimum": 1, "maximum": MAX_TOP_K, "description": t.tool_top_k}},
            "required": ["query"], "additionalProperties": False},
    }}


@dataclass(frozen=True)
class Attempt:
    """One search that really ran: what was asked, what came back, what was new."""
    n: int
    query: str
    terms: tuple[str, ...]
    top_k: int
    returned: tuple[str, ...]
    new: tuple[str, ...]
    duplicate_of: int | None


class Handbook:
    """One run's retrieval: the index, the search limit and the attempt log live together."""

    def __init__(self, t: Texts, locale: str, *, max_searches: int, default_top_k: int):
        self.t = t
        self.locale = locale
        self.chunks = {chunk.chunk_id: chunk for chunk in default_chunks(locale)}
        self.index = BM25Index(list(self.chunks.values()), locale)
        self.max_searches = max_searches
        self.default_top_k = default_top_k
        self.attempts: list[Attempt] = []
        self.seen: dict[str, int] = {}  # chunk_id -> the attempt that first returned it

    def search(self, query, top_k=None) -> dict:
        """The tool function: check the contract, then search, then log the attempt."""
        t = self.t
        # 1. Contract: a contract error is reported before the budget, so a bad call never uses up a search.
        if not isinstance(query, str) or not query.strip():
            raise InvalidQuery(t.query_not_text)
        query = query.strip()
        if len(query) > MAX_QUERY_CHARS:
            raise InvalidQuery(t.query_too_long.format(limit=MAX_QUERY_CHARS))
        top_k = self.default_top_k if top_k is None else top_k
        # bool is a subclass of int, so true would pass as 1 without the type() check.
        if type(top_k) is not int or not 1 <= top_k <= MAX_TOP_K:
            raise InvalidQuery(t.top_k_invalid.format(limit=MAX_TOP_K))
        # BM25 ignores word order and repeats, so the set of terms decides the result.
        terms = tuple(dict.fromkeys(tokenize(query, self.locale)))
        if not terms:
            raise InvalidQuery(t.query_no_terms)
        # 2. Budget: refuse once the limit is reached; the refusal is a structured error, not a crash.
        if len(self.attempts) >= self.max_searches:
            raise SearchBudgetExhausted(t.search_budget_exhausted.format(limit=self.max_searches))
        # 3. Search and log: same terms and no larger top_k than before is a repeat; it is still counted.
        hits = self.index.search(query, top_k)
        n = len(self.attempts) + 1
        repeat = next((a.n for a in self.attempts if set(a.terms) == set(terms) and top_k <= a.top_k), None)
        new = tuple(hit.chunk_id for hit in hits if hit.chunk_id not in self.seen)
        for chunk_id in new:
            self.seen[chunk_id] = n
        self.attempts.append(Attempt(n, query, terms, top_k, tuple(hit.chunk_id for hit in hits), new, repeat))
        return {"query": query, "top_k": top_k, "search": n,
                "results": [self.describe(hit.chunk_id, hit.score) for hit in hits]}

    def describe(self, chunk_id: str, score: float) -> dict:
        """What the model sees of a chunk: id, source, version, sections, score and text, marked as data."""
        chunk = self.chunks[chunk_id]
        return {"chunk_id": chunk.chunk_id, "doc_id": chunk.doc_id, "title": chunk.title, "version": chunk.version,
                "supersedes": list(chunk.supersedes), "sections": list(chunk.anchors), "score": score,
                "trust": chunk.trust, "text": chunk.text}


def cited_in_results(citations: list[str], handbook: Handbook) -> tuple[list[str], list[str]]:
    """Split citations into chunk ids this run's searches returned and ids they never returned.

    rag-citations has no shared citation module yet, so this lesson keeps only the check it needs.
    """
    known = [chunk_id for chunk_id in citations if chunk_id in handbook.seen]
    return known, [chunk_id for chunk_id in citations if chunk_id not in handbook.seen]
