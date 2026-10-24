"""Three retrieval strategies over one chunk list, each result kept apart from the others.

Keyword (BM25) and vector (cosine) lists are produced separately and keep their own
scores; the hybrid list is built from their ranks only (fusion.rrf), so no BM25 score is
ever compared with a cosine. Vectors come from the embeddings endpoint through
RunContext.embed, one visible request per batch.
"""
from __future__ import annotations

import math

from lessons.lesson_document_loading.chunking import Chunk
from lessons.lesson_embedding_retrieval.vector_index import VectorIndex
from lessons.lesson_hybrid_retrieval.fusion import rrf
from lessons.lesson_keyword_retrieval.bm25 import BM25Index, Hit

# Each list hands its top 10 to the fusion: deep enough that a chunk ranked 6th by one
# strategy can still be lifted by the other, small enough to read every rank in the report.
FUSION_DEPTH = 10
STRATEGIES = ("keyword", "vector", "hybrid")


def embed_texts(context, texts: list[str], first_round: int) -> tuple[list[list[float]], int]:
    """Embed texts in batches of at most context.embedding_batch_limit; returns vectors and the next round."""
    limit = context.embedding_batch_limit
    vectors, round_number = [], first_round
    for start in range(0, len(texts), limit):
        context.check_cancelled()
        response = context.embed(texts[start:start + limit], round_number)
        # The provider may return items out of order; "index" says which input each vector belongs to.
        for item in sorted(response["data"], key=lambda item: item["index"]):
            vectors.append(clean_vector(item.get("embedding")))
        round_number += 1
    return vectors, round_number


def clean_vector(value) -> list[float]:
    if not isinstance(value, list) or not value:
        raise ValueError("an embedding must be a non-empty list of numbers")
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in value):
        raise ValueError("an embedding must contain only finite numbers")
    return [float(x) for x in value]


def build_index(context, chunks: list[Chunk], corpus_version: str, first_round: int) -> tuple[VectorIndex, int]:
    """One vector per chunk text, tagged with the model, size and corpus version it was built from."""
    vectors, next_round = embed_texts(context, [chunk.text for chunk in chunks], first_round)
    index = VectorIndex(model=context.embedding_model, dimensions=len(vectors[0]), corpus_version=corpus_version,
                        chunk_ids=[chunk.chunk_id for chunk in chunks], vectors=vectors)
    return index, next_round


def keyword_search(bm25: BM25Index, query: str, depth: int = FUSION_DEPTH,
                   allowed: set[str] | None = None) -> list[Hit]:
    if allowed is None:
        return bm25.search(query, top_k=depth)
    # Filter before cutting to depth (as vector_search does), and keep idf computed over the whole corpus.
    kept = [hit for hit in bm25.search(query, top_k=len(bm25.chunks)) if hit.chunk_id in allowed][:depth]
    return [Hit(hit.chunk_id, hit.score, rank, hit.detail) for rank, hit in enumerate(kept, start=1)]


def vector_search(index: VectorIndex, query_vector: list[float], depth: int = FUSION_DEPTH,
                  allowed: set[str] | None = None) -> list[Hit]:
    # A metadata filter decided before ranking: chunks outside `allowed` never compete for a rank.
    where = None if allowed is None else allowed.__contains__
    return index.search(query_vector, top_k=depth, where=where)


def hybrid_search(keyword_hits: list[Hit], vector_hits: list[Hit], *, k: int, top_k: int) -> list[Hit]:
    """Ranks only: each chunk gets 1/(k + rank) from every list it appears in."""
    return rrf({"keyword": keyword_hits, "vector": vector_hits}, k=k, top_k=top_k)


def run_all(bm25: BM25Index, index: VectorIndex, query: str, query_vector: list[float], *,
            top_k: int, k: int, allowed: set[str] | None = None) -> dict[str, list[Hit]]:
    """The three result lists for one query; keyword and vector are cut to top_k only after fusion used them."""
    keyword = keyword_search(bm25, query, allowed=allowed)
    vector = vector_search(index, query_vector, allowed=allowed)
    hybrid = hybrid_search(keyword, vector, k=k, top_k=top_k)
    return {"keyword": keyword[:top_k], "vector": vector[:top_k], "hybrid": hybrid,
            "keyword_depth": keyword, "vector_depth": vector}
