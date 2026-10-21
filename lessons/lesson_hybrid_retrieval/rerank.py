"""Rerank a few fused candidates with one chat request and a JSON reply the program checks.

The model reads the query next to each candidate text, which neither BM25 nor a cosine
does, but every candidate costs prompt tokens: only the top few of the fused list are
sent. Candidates get short labels (c1, c2, ...) so the reply cannot invent a chunk id.
Candidate texts are handbook data and may contain sentences that look like orders; the
system prompt says so, and the reply is used only as an order of known labels.
"""
from __future__ import annotations

import json

from lessons.lesson_document_loading.chunking import Chunk


def build_request(system_prompt: str, query: str, candidates: list[Chunk]) -> tuple[dict, dict[str, str]]:
    """The request body and the label -> chunk_id map; candidate order is the fused order."""
    labels = {f"c{position}": chunk.chunk_id for position, chunk in enumerate(candidates, start=1)}
    payload = {"query": query,
               "candidates": [{"id": label, "text": chunk.text} for label, chunk in zip(labels, candidates)]}
    body = {"messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            "temperature": 0}
    return body, labels


def parse_order(content: str, labels: dict[str, str]) -> dict:
    """Read {"order": [...]} and keep only what can be trusted.

    Unknown labels are dropped, repeats count once, and labels the reply left out are
    appended in fused order, so a partial answer never loses a candidate. When there is no
    usable list at all, `valid` is False and the fused order stands unchanged.
    """
    result = {"valid": False, "order": list(labels), "unknown": [], "duplicates": [], "missing": [], "error": None}
    start, end = content.find("{"), content.rfind("}")
    try:
        value = json.loads(content[start:end + 1]) if start >= 0 and end > start else None
    except json.JSONDecodeError:
        value = None
    order = value.get("order") if isinstance(value, dict) else None
    if not isinstance(order, list) or not order:
        result["error"] = "no_order"
        return result
    seen = []
    for item in order:
        if not isinstance(item, str) or item not in labels:
            result["unknown"].append(item if isinstance(item, str) else json.dumps(item))
        elif item in seen:
            result["duplicates"].append(item)
        else:
            seen.append(item)
    if not seen:
        result["error"] = "no_known_label"
        return result
    result["missing"] = [label for label in labels if label not in seen]
    result["order"] = seen + result["missing"]
    result["valid"] = True
    return result
