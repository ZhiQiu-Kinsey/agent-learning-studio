"""Offline test model of rag-citations: serves automated tests only and stands for no real model.

It reads the question and the provided chunk ids from the request and returns a scripted JSON
answer. A script is used only when every chunk it cites was provided; otherwise the fixture says
the material is insufficient, so changing top_k never makes it cite what it was not given.
The "triage" exercise scripts two deliberate errors: an invented chunk id (q01) and a quote that
is not in the cited chunk (q10). Those responses carry x_offline_fixture, so the recorded
response event says the error was written by this fixture, not made by a model. No usage is
reported, so the lab report shows usage as not reported.
"""
import json
import re

from lessons.lesson_keyword_retrieval.query_set import load_queries
from lessons.lesson_rag_citations.locales.fixture import texts_for

SOURCE_ID = re.compile(r'<source id="([^"]+)"')
# Default chunk ids differ by language because each language has its own chunking budget.
CHUNKS = {
    "zh-CN": {"fees": "fees:7-13", "hours": "hours:8-18", "hours_old": "hours-2025:7-15",
              "borrowing": "borrowing:7-15", "pickup": "borrowing:39-47"},
    "en": {"fees": "fees:7-17", "hours": "hours:8-18", "hours_old": "hours-2025:7-21",
           "borrowing": "borrowing:7-15", "pickup": "borrowing:39-47"},
}
INVENTED_ID = "borrowing:11-13"  # looks like a chunk id, exists in neither language
ERROR_CODES = {"q01": "invented_chunk_id", "q10": "quote_not_in_chunk"}


def scripts(locale: str) -> dict:
    t, ids = texts_for(locale), CHUNKS[locale]

    def claim(name: str, chunk: str) -> dict:
        return {"text": t.claims[name], "citations": [{"chunk_id": ids[chunk], "quote": t.quotes[name]}]}

    def answer(*claims: dict, conflicts: list | None = None) -> dict:
        return {"claims": list(claims), "insufficient_evidence": False, "missing": "", "conflicts": conflicts or []}

    conflict = {"topic": t.conflict_topic, "resolution": t.conflict_resolution,
                "sources": [{"chunk_id": ids["hours"], "quote": t.quotes["sunday"]},
                            {"chunk_id": ids["hours_old"], "quote": t.quotes["sunday_old"]}]}
    return {"q03": answer(claim("fee_cap", "fees"), claim("fee_daily", "fees")),
            "q13": answer(claim("sunday", "hours"), conflicts=[conflict]),
            "q01": answer(claim("b2_limit", "borrowing")),
            "q10": answer(claim("pickup", "pickup"))}


def with_error(answer: dict, query_id: str, locale: str) -> dict:
    """Break one scripted answer on purpose: q01 gets an invented id, q10 a quote edited away from the chunk."""
    answer = json.loads(json.dumps(answer))
    first = answer["claims"][0]
    if query_id == "q01":
        first["citations"][0]["chunk_id"] = INVENTED_ID
    else:
        before, after = texts_for(locale).quote_edit
        first["text"] = first["text"].replace(before, after)
        first["citations"][0]["quote"] = first["citations"][0]["quote"].replace(before, after)
    return answer


def _cited(answer: dict) -> set[str]:
    items = answer["claims"] + [{"citations": c["sources"]} for c in answer["conflicts"]]
    return {citation["chunk_id"] for item in items for citation in item["citations"]}


def _reply(answer: dict, note: dict | None = None) -> dict:
    response = {"id": "offline_rag_citations", "object": "chat.completion", "model": "offline-script",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)}}]}
    if note:
        response["x_offline_fixture"] = note
    return response


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    t, script, queries = texts_for(locale), scripts(locale), load_queries(locale)

    def complete(body, api_key):
        user = body["messages"][-1]["content"]
        query = next((q for q in queries if user.rstrip().endswith(q.text)), None)
        answer = script.get(query.id) if query else None
        if answer is None or not _cited(answer) <= set(SOURCE_ID.findall(user)):
            return _reply({"claims": [], "insufficient_evidence": True, "missing": t.missing, "conflicts": []})
        if exercise_id == "triage" and query.id in ERROR_CODES:
            note = {"scripted_error": ERROR_CODES[query.id], "note": t.error_notes[query.id]}
            return _reply(with_error(answer, query.id, locale), note)
        return _reply(answer)

    return complete
