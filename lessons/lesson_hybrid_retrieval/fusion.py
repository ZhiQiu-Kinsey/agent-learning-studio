"""Merge ranked lists by rank, and filter chunks before ranking.

A BM25 score and a cosine similarity live on different scales, so adding them means
nothing. Reciprocal Rank Fusion uses only each chunk's position in each list:
score = sum over lists of 1 / (k + rank). A larger k flattens the gap between the top ranks.
"""
from __future__ import annotations

from lessons.lesson_document_loading.chunking import Chunk
from lessons.lesson_keyword_retrieval.bm25 import Hit


def rrf(rankings: dict[str, list[Hit]], *, k: int = 60, top_k: int = 5) -> list[Hit]:
    """Fuse named rankings; a chunk missing from a list simply gets nothing from it."""
    if k < 0 or top_k < 1:
        raise ValueError("k must be >= 0 and top_k >= 1")
    ranks: dict[str, dict[str, int]] = {}
    for name, hits in rankings.items():
        # Position in the list is the rank, so a list that was filtered earlier still counts from 1.
        for position, hit in enumerate(hits, start=1):
            ranks.setdefault(hit.chunk_id, {}).setdefault(name, position)
    fused = []
    for chunk_id, by_list in ranks.items():
        parts = {name: 1 / (k + rank) for name, rank in by_list.items()}
        fused.append((sum(parts.values()), min(by_list.values()), chunk_id, by_list, parts))
    fused.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [Hit(chunk_id, round(score, 6), rank,
                {"ranks": {name: by_list.get(name) for name in rankings},
                 "contributions": {name: round(value, 6) for name, value in parts.items()}})
            for rank, (score, _, chunk_id, by_list, parts) in enumerate(fused[:top_k], start=1)]


def apply_filter(chunks: list[Chunk], *, doc_ids=None,
                 newest_only: bool = False) -> tuple[list[Chunk], list[dict]]:
    """Keep matching chunks and record every removed one with a reason code.

    doc_ids: only these documents stay. newest_only: drop a document when another
    document still present declares `supersedes` for it. Reasons are codes
    ("doc_id_filter", "superseded"); lessons translate them.
    """
    allowed = set(doc_ids) if doc_ids is not None else None
    candidates = [chunk for chunk in chunks if allowed is None or chunk.doc_id in allowed]
    replaced_by = {old: chunk.doc_id for chunk in candidates for old in chunk.supersedes} if newest_only else {}
    kept, removed = [], []
    for chunk in chunks:
        if allowed is not None and chunk.doc_id not in allowed:
            removed.append({"chunk_id": chunk.chunk_id, "doc_id": chunk.doc_id, "reason": "doc_id_filter"})
        elif chunk.doc_id in replaced_by:
            removed.append({"chunk_id": chunk.chunk_id, "doc_id": chunk.doc_id, "reason": "superseded",
                            "by": replaced_by[chunk.doc_id]})
        else:
            kept.append(chunk)
    return kept, removed
