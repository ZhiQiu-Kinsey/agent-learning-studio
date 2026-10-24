"""The fixed query set shared by every retrieval lesson.

Query wording is data (corpus/queries.json, one text per language); this module only
gives it structure. Gold answers are section anchors, not chunk ids, so the same labels
judge any chunking.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from lessons.lesson_document_loading.chunking import Chunk
from lessons.lesson_document_loading.loader import CORPUS_DIR

QUERIES_PATH = CORPUS_DIR / "queries.json"
KINDS = ("exact", "synonym", "no_answer", "cross_section", "multi_hop", "conflict")


@dataclass(frozen=True)
class Query:
    id: str
    kind: str
    text: str
    gold: tuple[str, ...]  # "doc_id#anchor"; empty for no_answer


def load_queries(locale: str) -> list[Query]:
    data = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    queries = []
    for item in data["queries"]:
        if item["kind"] not in KINDS:
            raise ValueError(f"query {item['id']}: unknown kind {item['kind']!r}")
        if locale not in item["text"]:
            raise ValueError(f"query {item['id']}: no text for locale {locale!r}")
        queries.append(Query(item["id"], item["kind"], item["text"][locale], tuple(item["gold"])))
    return queries


def query_set_version() -> str:
    """The declared version plus a content digest, so an edited file never passes as the old one."""
    raw = QUERIES_PATH.read_bytes()
    return f"{json.loads(raw)['version']}+{hashlib.sha256(raw).hexdigest()[:8]}"


def judge(hit_chunks: list[Chunk], query: Query) -> dict:
    """Compare ranked chunks with the gold anchors.

    hit: at least one gold section was retrieved. complete: all of them were, which is
    what cross-section, multi-hop and conflict queries need. For no_answer queries there
    is nothing to hit, so hit and complete are None: whatever came back is noise the
    answer step must refuse to use.
    """
    if not query.gold:
        return {"hit": None, "complete": None, "matched": [], "missing": [], "first_rank": None,
                "returned": len(hit_chunks)}
    matched, first_rank = [], None
    for rank, chunk in enumerate(hit_chunks, start=1):
        found = [anchor for anchor in chunk.anchors if anchor in query.gold]
        if found and first_rank is None:
            first_rank = rank
        matched.extend(anchor for anchor in found if anchor not in matched)
    missing = [anchor for anchor in query.gold if anchor not in matched]
    return {"hit": bool(matched), "complete": not missing, "matched": matched, "missing": missing,
            "first_rank": first_rank, "returned": len(hit_chunks)}
