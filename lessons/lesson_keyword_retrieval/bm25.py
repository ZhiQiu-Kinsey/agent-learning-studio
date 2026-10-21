"""Okapi BM25 over handbook chunks, written so every score can be taken apart.

English is split into lowercase words; Chinese has no spaces, so it is split into
overlapping two-character pieces (bigrams) instead of pulling in a segmentation library.
Stop words live in stopwords.json so the code holds no language-specific text.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from lessons.lesson_document_loading.chunking import Chunk

STOPWORDS = json.loads((Path(__file__).resolve().parent / "stopwords.json").read_text(encoding="utf-8"))
ANCHOR_MARK = re.compile(r"\{#[^}]*\}")
# Codes such as R-301, B2, 0.5 or 20:00 must stay whole: they are what exact queries ask about.
WORD_OR_CODE = r"[a-z0-9]+(?:[-.:][a-z0-9]+)*"
CJK_RUN = r"[\u3400-\u4dbf\u4e00-\u9fff]+"  # re reads the escapes: CJK ideographs
TOKEN = re.compile(f"(?P<cjk>{CJK_RUN})|(?P<word>{WORD_OR_CODE})")
# Raw BM25 idf turns negative for a term in more than half of the chunks; a tiny floor keeps
# such a term from lowering a score, the same choice as the reference engine.
IDF_FLOOR = 1e-6


def tokenize(text: str, locale: str) -> list[str]:
    stop = STOPWORDS[locale]
    text = ANCHOR_MARK.sub(" ", text).lower()
    tokens = []
    for match in TOKEN.finditer(text):
        if match.group("word"):
            word = match.group("word")
            if word not in (stop["words"] if locale == "en" else ()):
                tokens.append(word)
        elif locale != "en":
            tokens.extend(cjk_bigrams(match.group("cjk"), stop))
    return tokens


def cjk_bigrams(run: str, stop: dict) -> list[str]:
    # Stop words and characters act as separators, so no bigram spans a removed piece.
    for word in sorted(stop["words"], key=len, reverse=True):
        run = run.replace(word, " ")
    for char in stop["chars"]:
        run = run.replace(char, " ")
    tokens = []
    for piece in run.split():
        if len(piece) == 1:
            tokens.append(piece)
        else:
            tokens.extend(piece[i:i + 2] for i in range(len(piece) - 1))
    return tokens


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    score: float
    rank: int  # 1-based
    detail: dict  # per-term contributions, or per-list ranks for fused results


class BM25Index:
    def __init__(self, chunks: list[Chunk], locale: str, *, k1: float = 1.5, b: float = 0.75):
        self.chunks = list(chunks)
        self.locale = locale
        self.k1 = k1
        self.b = b
        self.term_counts = [Counter(tokenize(chunk.text, locale)) for chunk in self.chunks]
        self.lengths = [sum(counts.values()) for counts in self.term_counts]
        self.avg_length = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        self.doc_freq = Counter(term for counts in self.term_counts for term in counts)
        self.position = {chunk.chunk_id: index for index, chunk in enumerate(self.chunks)}

    def raw_idf(self, term: str) -> float:
        n, df = len(self.chunks), self.doc_freq.get(term, 0)
        return math.log((n - df + 0.5) / (df + 0.5))

    def idf(self, term: str) -> float:
        return max(self.raw_idf(term), IDF_FLOOR)

    def length_norm(self, index: int) -> float:
        # 1.0 for an average-length chunk; longer chunks need more matches for the same score.
        if not self.avg_length:
            return 1.0
        return 1 - self.b + self.b * self.lengths[index] / self.avg_length

    def term_score(self, term: str, index: int) -> float:
        tf = self.term_counts[index].get(term, 0)
        if not tf:
            return 0.0
        return self.idf(term) * tf * (self.k1 + 1) / (tf + self.k1 * self.length_norm(index))

    def query_terms(self, query: str) -> list[str]:
        # A repeated query word counts once, so a learner can read each term's share directly.
        return list(dict.fromkeys(tokenize(query, self.locale)))

    def search(self, query: str, top_k: int = 5) -> list[Hit]:
        """Chunks that share at least one term with the query, best first; ties keep corpus order."""
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        terms = self.query_terms(query)
        scored = []
        for index in range(len(self.chunks)):
            parts = {term: self.term_score(term, index) for term in terms}
            parts = {term: value for term, value in parts.items() if value > 0}
            if parts:
                scored.append((sum(parts.values()), index, parts))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [Hit(self.chunks[index].chunk_id, round(total, 4), rank,
                    {"terms": {term: round(value, 4) for term, value in parts.items()}})
                for rank, (total, index, parts) in enumerate(scored[:top_k], start=1)]

    def explain(self, query: str, chunk_id: str) -> dict:
        """Every factor of one chunk's score, including query terms the chunk does not contain."""
        if chunk_id not in self.position:
            raise KeyError(f"unknown chunk_id {chunk_id!r}")
        index = self.position[chunk_id]
        terms = []
        for term in self.query_terms(query):
            terms.append({"term": term, "df": self.doc_freq.get(term, 0), "raw_idf": round(self.raw_idf(term), 4),
                          "idf": round(self.idf(term), 4), "tf": self.term_counts[index].get(term, 0),
                          "contribution": round(self.term_score(term, index), 4)})
        return {
            "chunk_id": chunk_id, "k1": self.k1, "b": self.b, "chunks": len(self.chunks),
            "length": self.lengths[index], "avg_length": round(self.avg_length, 2),
            "length_norm": round(self.length_norm(index), 4), "terms": terms,
            "score": round(sum(self.term_score(t["term"], index) for t in terms), 4),
        }
