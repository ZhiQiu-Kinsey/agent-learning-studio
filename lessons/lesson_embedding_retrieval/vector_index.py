"""A brute-force vector index that remembers what it was built from.

With a few dozen chunks, comparing the query with every vector is fast enough and
leaves nothing hidden. The index stores the embedding model, its dimensions and the
corpus version next to the vectors: if any of them changes, the saved vectors no longer
describe the current chunks and must not be reused.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from lessons.lesson_document_loading.loader import ROOT
from lessons.lesson_keyword_retrieval.bm25 import Hit

INDEX_FORMAT = 1


def cosine(a: list[float], b: list[float]) -> float:
    """Angle-based similarity in [-1, 1]; vector length (how much text) does not matter."""
    if len(a) != len(b):
        raise ValueError(f"vector lengths differ: {len(a)} != {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


@dataclass
class VectorIndex:
    model: str
    dimensions: int
    corpus_version: str
    chunk_ids: list[str]
    vectors: list[list[float]]

    def __post_init__(self):
        if len(self.chunk_ids) != len(self.vectors):
            raise ValueError("chunk_ids and vectors must have the same length")
        if any(len(vector) != self.dimensions for vector in self.vectors):
            raise ValueError(f"every vector must have {self.dimensions} dimensions")

    def search(self, query_vector: list[float], top_k: int = 5, *,
               where: Callable[[str], bool] | None = None) -> list[Hit]:
        """Most similar chunks first; `where` filters by chunk_id before ranking."""
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if len(query_vector) != self.dimensions:
            raise ValueError(f"query vector has {len(query_vector)} dimensions, index has {self.dimensions}")
        scored = [(cosine(query_vector, vector), index)
                  for index, (chunk_id, vector) in enumerate(zip(self.chunk_ids, self.vectors))
                  if where is None or where(chunk_id)]
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [Hit(self.chunk_ids[index], round(score, 4), rank, {"cosine": round(score, 4)})
                for rank, (score, index) in enumerate(scored[:top_k], start=1)]

    def is_stale(self, *, model: str, dimensions: int, corpus_version: str) -> bool:
        return (self.model, self.dimensions, self.corpus_version) != (model, dimensions, corpus_version)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"format": INDEX_FORMAT, "model": self.model, "dimensions": self.dimensions,
                "corpus_version": self.corpus_version, "chunk_ids": self.chunk_ids, "vectors": self.vectors}
        # Write then rename, so a crash never leaves a half-written index that looks valid.
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(data), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path) -> "VectorIndex":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("format") != INDEX_FORMAT:
            raise ValueError(f"unsupported index format {data.get('format')!r}")
        return cls(data["model"], data["dimensions"], data["corpus_version"], data["chunk_ids"], data["vectors"])


def index_path(locale: str, model: str, dimensions: int) -> Path:
    """Local, uncommitted location (.runtime/ is git-ignored); one file per language, model and size."""
    safe_model = re.sub(r"[^A-Za-z0-9._-]+", "_", model)
    return ROOT / ".runtime" / "rag-index" / locale / f"{safe_model}-{dimensions}.json"
