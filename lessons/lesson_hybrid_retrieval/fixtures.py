"""Offline test models for hybrid-retrieval: they serve automated tests only and stand for no real model.

Embeddings: each vector has one dimension per concept in fixture_vocab.json, holding how
many times that concept's terms occur in the text (capped), plus a small constant so no
vector is all zeros. Synonyms share a dimension (overdue charge / late fee), while codes
such as B2 or R-305 have none, so these toy vectors reproduce the behaviour the lesson
studies: they find paraphrases and miss exact codes. Real embedding models are trained,
not counted; nothing here says how a real model ranks the handbook.

Reranking: the chat reply orders the candidate labels by the same concept overlap with the
query (ties keep the fused order). Every response carries scripted usage.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

VOCAB = json.loads((Path(__file__).resolve().parent / "fixture_vocab.json").read_text(encoding="utf-8"))


def _patterns(locale: str) -> list[list[re.Pattern]]:
    patterns = []
    for concept in VOCAB["concepts"]:
        terms = concept[locale]
        if locale == "en":
            patterns.append([re.compile(rf"\b{term}\b", re.IGNORECASE) for term in terms])
        else:
            patterns.append([re.compile(re.escape(term)) for term in terms])
    return patterns


PATTERNS = {locale: _patterns(locale) for locale in ("zh-CN", "en")}


def concept_vector(text: str, locale: str) -> list[float]:
    values = []
    for patterns in PATTERNS[locale]:
        count = sum(len(pattern.findall(text)) for pattern in patterns)
        values.append(float(min(count, VOCAB["cap"])))
    return values + [VOCAB["bias"]]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def create_embedding(exercise_id, inputs=None, locale="zh-CN"):
    def embedding(body, api_key):
        texts = body["input"]
        return {"object": "list", "model": body["model"],
                "data": [{"object": "embedding", "index": i, "embedding": concept_vector(text, locale)}
                         for i, text in enumerate(texts)],
                "usage": {"prompt_tokens": 8 * len(texts), "total_tokens": 8 * len(texts)}}

    return embedding


def _reply(content: str, tokens: int) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": tokens - 20, "completion_tokens": 20, "total_tokens": tokens}}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    """Reads the query and candidates the runner put into the user message (JSON) and returns an order."""

    def complete(body, api_key):
        payload = json.loads(body["messages"][1]["content"])
        query = concept_vector(payload["query"], locale)
        scored = [(-_cosine(query, concept_vector(item["text"], locale)), position, item["id"])
                  for position, item in enumerate(payload["candidates"])]
        order = [label for _, _, label in sorted(scored)]
        return _reply(json.dumps({"order": order}), 400 + 60 * len(order))

    return complete
