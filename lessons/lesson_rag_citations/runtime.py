"""RAG with citations: retrieve, hand the chunks to the model as labelled data, check every citation it returns.

Retrieval is BM25 from the keyword-retrieval lesson, so each run has generation requests
only and the evidence chain stays short; any retriever that returns chunks would do (the
hybrid-retrieval lesson's fusion, for one). The answer is structured output in the manner
of the structured-output lesson: JSON layer, schema layer, then a fact layer, which here
is citations.check_answer. Every text that reaches the model or an event is in locales/.
"""
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_document_loading.chunking import Chunk, default_chunks
from lessons.lesson_keyword_retrieval.bm25 import BM25Index
from lessons.lesson_keyword_retrieval.query_set import Query, judge, load_queries
from lessons.lesson_rag_citations import citations
from lessons.lesson_rag_citations.locales import Texts, texts_for

# A synonym query that retrieval misses, then two questions whose evidence is retrieved.
TRIAGE = ("q04", "q01", "q10")
MAX_TOP_K = 8
QueryChoice = Literal["q01", "q02", "q03", "q04", "q05", "q06", "q07", "q08", "q09", "q10", "q11", "q12",
                      "q13", "q14", "triage"]


class Inputs(LessonInputs):
    # A query id from the shared query set (corpus/queries.json), or "triage" for the three TRIAGE queries.
    query: QueryChoice = "q03"
    top_k: int = Field(default=5, ge=1, le=MAX_TOP_K)


INPUT_MODEL = Inputs


def make_tools(chunks: list[Chunk], locale: str) -> dict:
    """The runner's retrieval tool; the model does not choose what to look up in this lesson."""
    index = BM25Index(chunks, locale)
    by_id = {chunk.chunk_id: chunk for chunk in chunks}

    def search_handbook(query: str, top_k: int = 5) -> dict:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if type(top_k) is not int or not 1 <= top_k <= MAX_TOP_K:
            raise ValueError(f"top_k must be an integer from 1 to {MAX_TOP_K}")
        return {"hits": [_hit(by_id[hit.chunk_id], hit.rank, hit.score) for hit in index.search(query, top_k)]}

    return {"search_handbook": search_handbook}


def _hit(chunk: Chunk, rank: int, score: float) -> dict:
    return {"chunk_id": chunk.chunk_id, "rank": rank, "score": score, "doc_id": chunk.doc_id, "title": chunk.title,
            "version": chunk.version, "supersedes": list(chunk.supersedes), "trust": chunk.trust, "text": chunk.text}


def source_block(hit: dict) -> str:
    """One chunk as tagged data: the id to cite, the version to compare, and a trust label."""
    supersedes = f' supersedes="{",".join(hit["supersedes"])}"' if hit["supersedes"] else ""
    return (f'<source id="{hit["chunk_id"]}" doc="{hit["doc_id"]}" title="{hit["title"]}" '
            f'version="{hit["version"]}"{supersedes} trust="{hit["trust"]}">\n{hit["text"]}\n</source>')


def build_request(t: Texts, question: str, hits: list[dict]) -> dict:
    # Rules go to the system prompt; sources and question are separate, labelled parts of the user message.
    user = t.user_prompt.format(sources="\n".join(source_block(hit) for hit in hits), question=question)
    return {"messages": [{"role": "system", "content": t.system_prompt}, {"role": "user", "content": user}],
            "temperature": 0}


def answer_one(context: RunContext, t: Texts, tools: dict, by_id: dict, query: Query, top_k: int,
               round_number: int) -> dict:
    """One question: retrieve, judge retrieval, generate, check citations, classify the first broken link."""
    # 1. Retrieve: a runner-initiated call, recorded as tool_call and tool_result.
    result = context.call_tool("search_handbook", {"query": query.text, "top_k": top_k}, tools, round_number)
    hits = result["result"]["hits"] if result["ok"] else []
    provided = [by_id[hit["chunk_id"]] for hit in hits]
    # 2. Judge retrieval against the human annotation; the model never sees the gold anchors.
    retrieval = judge(provided, query)
    context.emit("lesson.retrieval_judge", {"query_id": query.id, "kind": query.kind, "gold": list(query.gold),
                                            "provided": [chunk.chunk_id for chunk in provided], **retrieval},
                 round_number)
    # 3. Generate: no chunks means nothing to ground an answer on, so no request is sent.
    usage, source, problems = None, "program", []
    if hits:
        response = context.complete(build_request(t, query.text, hits), round_number)
        usage, source = _usage(response), "offline_fixture" if context.mode == "offline" else "model"
        answer, problems = citations.parse_answer(_content(response))
    else:
        answer = citations.GroundedAnswer(claims=[], insufficient_evidence=True, missing=t.no_hits)
    # 4. Check every citation against the chunks provided in step 3, then classify.
    check = citations.check_answer(answer, provided) if answer else None
    category, reasons = citations.classify(check, hit=retrieval["hit"], complete=retrieval["complete"])
    context.emit("lesson.citation_check", {"query_id": query.id, "answer_source": source, "format_problems": problems,
                                           **(check.to_dict() if check else {}), "category": category,
                                           "reasons": list(reasons)}, round_number)
    return {"query": query, "retrieval": retrieval, "check": check, "category": category, "reasons": reasons,
            "source": source, "usage": usage, "requested": bool(hits)}


def _content(response: dict) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""
    return content if isinstance(content, str) else ""


def _usage(response: dict) -> int | None:
    usage = response.get("usage")
    tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
    return tokens if type(tokens) is int else None


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    chunks = default_chunks(context.locale)
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    tools = make_tools(chunks, context.locale)
    queries = {query.id: query for query in load_queries(context.locale)}
    chosen = TRIAGE if values.query == "triage" else (values.query,)
    results = []
    for round_number, query_id in enumerate(chosen, start=1):
        context.check_cancelled()
        results.append(answer_one(context, t, tools, by_id, queries[query_id], values.top_k, round_number))
    _report_citations(context, t, results)
    _report_triage(context, t, results)
    return _answer(t, results)


def _total_usage(t: Texts, results: list[dict]) -> str | int:
    """Only what the provider reported is added up; a missing number is never estimated."""
    requested = [r for r in results if r["requested"]]
    reported = [r["usage"] for r in requested if r["usage"] is not None]
    if not reported:
        return t.value_not_reported
    missing = len(requested) - len(reported)
    return sum(reported) if not missing else t.tokens_partly_reported.format(total=sum(reported), missing=missing)


def _yes_no(t: Texts, value: bool | None) -> str:
    return t.value_none if value is None else t.value_yes if value else t.value_no


def _report_citations(context: RunContext, t: Texts, results: list[dict]) -> None:
    """lesson.report with the citation table; a check appears only when this run had something to check."""
    checks, rows = [], []
    asked = [r for r in results if r["requested"]]
    parsed = [r for r in asked if r["check"] is not None]
    if asked:
        checks.append({"id": "format", "label": t.check_format, "passed": len(parsed) == len(asked),
                       "detail": t.detail_count.format(ok=len(parsed), total=len(asked))})
    all_citations = [c for r in results if r["check"] for c in r["check"].citations]
    claims = [claim for r in results if r["check"] for claim in r["check"].claims]
    if all_citations:
        provided = [c for c in all_citations if c.exists]
        found = [c for c in provided if c.ok]
        checks.append({"id": "provided", "label": t.check_provided, "passed": len(provided) == len(all_citations),
                       "detail": t.detail_count.format(ok=len(provided), total=len(all_citations))})
        if provided:
            checks.append({"id": "quotes", "label": t.check_quotes, "passed": len(found) == len(provided),
                           "detail": t.detail_count.format(ok=len(found), total=len(provided))})
    numbered = [claim for claim in claims if claim.numbers_checked]
    if numbered:
        clean = [claim for claim in numbered if not claim.unmatched_numbers]
        checks.append({"id": "numbers", "label": t.check_numbers, "passed": len(clean) == len(numbered),
                       "detail": t.detail_count.format(ok=len(clean), total=len(numbered))})
    no_gold = [r for r in results if r["retrieval"]["hit"] is None]
    if no_gold:
        declined = [r for r in no_gold if r["category"] == "declined_ok"]
        checks.append({"id": "declined", "label": t.check_declined, "passed": len(declined) == len(no_gold),
                       "detail": t.detail_count.format(ok=len(declined), total=len(no_gold))})
    paired = [r for r in results if r["check"] and r["check"].conflict_disclosed is not None]
    if paired:
        disclosed = [r for r in paired if r["check"].conflict_disclosed]
        checks.append({"id": "conflict", "label": t.check_conflict, "passed": len(disclosed) == len(paired),
                       "detail": t.detail_count.format(ok=len(disclosed), total=len(paired))})
    for r in results:
        for claim in (r["check"].claims if r["check"] else ()):
            for c in claim.citations:
                rows.append([r["query"].id, claim.text, c.chunk_id, _yes_no(t, c.exists), _yes_no(t, c.quote_found),
                             _yes_no(t, not claim.unmatched_numbers if claim.numbers_checked else None)])
    context.emit("lesson.report", {
        "title": t.report_citations_title, "summary": t.report_citations_summary, "checks": checks,
        "metrics": [{"id": "model_calls", "label": t.label_model_calls, "value": len(asked)},
                    {"id": "citations", "label": t.label_citations, "value": len(all_citations)},
                    {"id": "unprovided", "label": t.label_unprovided,
                     "value": sum(not c.exists for c in all_citations)},
                    {"id": "quote_missing", "label": t.label_quote_missing,
                     "value": sum(c.reason == "quote_not_found" for c in all_citations)},
                    {"id": "usage", "label": t.label_usage, "value": _total_usage(t, results)},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.columns_citations), "rows": rows},
    })


def _report_triage(context: RunContext, t: Texts, results: list[dict]) -> None:
    """lesson.report that names, per question, whether retrieval or generation broke first."""
    retrieval_codes = {"retrieval_miss", "retrieval_partial"}
    passed_codes = {"ok", "declined_ok"}
    rows = []
    for r in results:
        hit, complete = r["retrieval"]["hit"], r["retrieval"]["complete"]
        found = "no_gold" if hit is None else "miss" if not hit else "hit" if complete else "partial"
        answered = "invalid" if r["check"] is None else "declined" if r["check"].insufficient_evidence else "answered"
        rows.append([f'{r["query"].id} {r["query"].text}', t.kinds[r["query"].kind], t.retrieval_values[found],
                     t.answer_values[answered], t.categories[r["category"]],
                     t.separator.join(t.reasons[code] for code in r["reasons"]) or t.value_none, t.sources[r["source"]]])
    context.emit("lesson.report", {
        "title": t.report_triage_title, "summary": t.report_triage_summary,
        "metrics": [{"id": "retrieval_failures", "label": t.label_retrieval_failures,
                     "value": sum(r["category"] in retrieval_codes for r in results)},
                    {"id": "generation_failures", "label": t.label_generation_failures,
                     "value": sum(r["category"] not in retrieval_codes | passed_codes for r in results)},
                    {"id": "passed", "label": t.label_passed, "value": sum(r["category"] in passed_codes for r in results)}],
        "table": {"columns": list(t.columns_triage), "rows": rows},
    })


def _answer(t: Texts, results: list[dict]) -> str:
    """The answer shown to the learner is rebuilt from checked claims; nothing unchecked passes as an answer."""
    parts = []
    for r in results:
        lines = [t.answer_heading.format(query_id=r["query"].id, question=r["query"].text)]
        check = r["check"]
        if check is None:
            lines.append(t.answer_invalid)
        else:
            for claim in check.claims:
                ids = ", ".join(c.chunk_id for c in claim.citations)
                lines.append(t.answer_claim.format(text=claim.text, ids=ids,
                                                   status=t.status_checked if claim.supported else t.status_failed))
            for item in check.conflicts:
                lines.append(t.answer_conflict.format(topic=item.topic, docs=", ".join(item.doc_ids),
                                                      current=item.current or t.answer_current_unknown))
            if check.insufficient_evidence:
                lines.append(t.answer_insufficient.format(missing=check.missing))
        lines.append(t.answer_category.format(category=t.categories[r["category"]]))
        parts.append("\n".join(lines))
    return "\n\n".join(parts)
