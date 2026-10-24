"""Hybrid retrieval: compare keyword, vector and fused results on one query set, rerank a few candidates,
then filter by metadata and keep a saved index in step with a changed corpus.

Retrieval runs in local Python on the shared handbook and query set; vectors come from the
embeddings endpoint (context.embed) and the rerank exercise adds one chat request.
Every text that reaches the model or an event is in locales/, one catalog per run language.
"""
from __future__ import annotations

import time
from typing import Literal

from pydantic import Field, model_validator

from course.execution import LessonInputs, RunContext
from lessons.lesson_document_loading.chunking import Chunk, chunk_corpus, default_chunks
from lessons.lesson_document_loading.loader import corpus_version
from lessons.lesson_hybrid_retrieval import index_update
from lessons.lesson_hybrid_retrieval.fusion import apply_filter
from lessons.lesson_hybrid_retrieval.locales import Texts, texts_for
from lessons.lesson_hybrid_retrieval.rerank import build_request, parse_order
from lessons.lesson_hybrid_retrieval.retrieval import STRATEGIES, build_index, embed_texts, run_all
from lessons.lesson_keyword_retrieval.bm25 import BM25Index, Hit
from lessons.lesson_keyword_retrieval.query_set import Query, judge, load_queries, query_set_version

QueryId = Literal["q01", "q02", "q03", "q04", "q05", "q06", "q07",
                  "q08", "q09", "q10", "q11", "q12", "q13", "q14"]


class Inputs(LessonInputs):
    task: Literal["compare", "rerank", "update"] = "compare"
    top_k: int = Field(default=5, ge=1, le=8)
    rrf_k: int = Field(default=60, ge=0, le=200)
    candidates: int = Field(default=8, ge=2, le=10)  # rerank: how many fused results the model sees
    query_id: QueryId = "q06"  # rerank: which query of the shared set

    @model_validator(mode="after")
    def _rerank_window(self):
        if self.task == "rerank" and self.top_k > self.candidates:
            raise ValueError("top_k must not exceed candidates: reranking cannot add chunks it never saw")
        return self


INPUT_MODEL = Inputs
RRF_EXAMPLE = "q04"  # the query whose fusion arithmetic the compare report lays out
UPDATE_QUERIES = ("q13", "q03")  # a version conflict, and the rule the scripted edit changes


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    if values.task == "compare":
        return run_compare(context, t, values)
    if values.task == "rerank":
        return run_rerank(context, t, values)
    return run_update(context, t, values)


def run_compare(context: RunContext, t: Texts, values: Inputs) -> str:
    """Same chunks, same queries, three strategies; each result is judged on its own against the gold sections."""
    chunks, version = default_chunks(context.locale), corpus_version(context.locale)
    queries = load_queries(context.locale)
    # 1. Index: one vector per chunk, in batches the learner can see as requests.
    index, next_round = build_index(context, chunks, version, 1)
    # 2. Queries are embedded too, with the same model, or their vectors could not be compared with the chunks'.
    query_vectors, _ = embed_texts(context, [query.text for query in queries], next_round)
    bm25, by_id = BM25Index(chunks, context.locale), {chunk.chunk_id: chunk for chunk in chunks}
    # 3. Search: three lists per query, each judged separately; scores never cross between lists.
    results = []
    for query, vector in zip(queries, query_vectors):
        context.check_cancelled()
        lists = run_all(bm25, index, query.text, vector, top_k=values.top_k, k=values.rrf_k)
        verdicts = {name: judge([by_id[hit.chunk_id] for hit in lists[name]], query) for name in STRATEGIES}
        results.append((query, lists, verdicts))
    same_source = index.chunk_ids == list(by_id) and index.corpus_version == version
    return _compare_reports(context, t, values, results, same_source, version, len(chunks))


def run_rerank(context: RunContext, t: Texts, values: Inputs) -> str:
    """Fuse, send the top candidates to the chat model once, and compare the top_k before and after."""
    chunks, version = default_chunks(context.locale), corpus_version(context.locale)
    query = next(q for q in load_queries(context.locale) if q.id == values.query_id)
    index, next_round = build_index(context, chunks, version, 1)
    (vector,), next_round = embed_texts(context, [query.text], next_round)
    bm25, by_id = BM25Index(chunks, context.locale), {chunk.chunk_id: chunk for chunk in chunks}
    # 1. Candidate pool: the fused list, cut to the few results the reranker may read.
    pool = run_all(bm25, index, query.text, vector, top_k=values.candidates, k=values.rrf_k)["hybrid"]
    candidates = [by_id[hit.chunk_id] for hit in pool]
    # 2. One chat request: the query beside every candidate text, answered with labels only.
    body, labels = build_request(t.rerank_system, query.text, candidates)
    started = time.perf_counter()
    response = context.complete(body, next_round)
    elapsed = round((time.perf_counter() - started) * 1000)
    # 3. Check the reply; an unusable one leaves the fused order in place, and the report says so.
    parsed = parse_order(_content(response), labels)
    reranked = [by_id[labels[label]] for label in parsed["order"]]
    before = judge(candidates[:values.top_k], query)
    after = judge(reranked[:values.top_k], query)
    usage = response.get("usage") if isinstance(response, dict) else None
    tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
    cost = {"tokens": tokens if isinstance(tokens, int) else None, "ms": elapsed,
            "prompt_chars": len(body["messages"][1]["content"])}
    return _rerank_report(context, t, values, query, candidates, reranked, parsed, before, after,
                          judge(candidates, query), cost)


def run_update(context: RunContext, t: Texts, values: Inputs) -> str:
    """Filter by metadata, change the working copy, show the saved index going stale, update it, reload it."""
    locale = context.locale
    queries = [q for q in load_queries(locale) if q.id in UPDATE_QUERIES]
    # 1. A fresh working copy under .runtime/; the repository corpus is never edited.
    folder = index_update.reset_working_copy(locale)
    store = index_update.working_folder(locale) / "index"
    documents = index_update.load_folder(folder, locale)
    chunks, version = chunk_corpus(documents), index_update.folder_version(documents)
    index, next_round = build_index(context, chunks, version, 1)
    index_update.save(index, index_update.fingerprints(chunks), store)
    query_vectors, next_round = embed_texts(context, [query.text for query in queries], next_round)
    # 2. Metadata filter: the same search without and with newest_only, before any top_k cut.
    bm25 = BM25Index(chunks, locale)
    filtered = {}
    for newest_only in (False, True):
        kept, removed = apply_filter(chunks, newest_only=newest_only)
        allowed = {chunk.chunk_id for chunk in kept}
        filtered[newest_only] = (removed, [run_all(bm25, index, q.text, v, top_k=values.top_k, k=values.rrf_k,
                                                   allowed=allowed)["hybrid"] for q, v in zip(queries, query_vectors)])
    _filter_report(context, t, queries, chunks, filtered)
    # 3. Change the corpus: one rule edited, the superseded document deleted.
    context.check_cancelled()
    changes = index_update.apply_changes(folder)
    documents = index_update.load_folder(folder, locale)
    chunks, version = chunk_corpus(documents), index_update.folder_version(documents)
    current = index_update.fingerprints(chunks)
    # 4. Restart: only the files on disk remain. The saved index describes the old corpus.
    old_index, saved = index_update.load(store)
    stale = old_index.is_stale(model=context.embedding_model, dimensions=old_index.dimensions, corpus_version=version)
    bm25 = BM25Index(chunks, locale)
    # Only the vector index is persisted; BM25 is rebuilt from the current files, so staleness shows in the vector list.
    before = [run_all(bm25, old_index, q.text, v, top_k=values.top_k, k=values.rrf_k)["vector"]
              for q, v in zip(queries, query_vectors)]
    _change_report(context, t, queries, changes, stale, old_index, version, before, saved, current)
    # 5. Incremental update: embed only new and changed chunk text, drop removed chunks, save both files.
    plan = index_update.plan_update(saved, current)
    fresh = set(plan["added"]) | set(plan["changed"])
    todo = [chunk for chunk in chunks if chunk.chunk_id in fresh]
    vectors, _ = embed_texts(context, [chunk.text for chunk in todo], next_round) if todo else ([], next_round)
    updated = index_update.apply_update(old_index, chunks, dict(zip([c.chunk_id for c in todo], vectors)), version)
    index_update.save(updated, current, store)
    # 6. Restart again and verify what a new process would load.
    loaded, loaded_prints = index_update.load(store)
    after = [run_all(bm25, loaded, q.text, v, top_k=values.top_k, k=values.rrf_k)
             for q, v in zip(queries, query_vectors)]
    return _update_report(context, t, queries, chunks, plan, len(todo), loaded, loaded_prints, version,
                          current, after)


def _content(response) -> str:
    try:
        content = response["choices"][0]["message"].get("content")
    except (KeyError, IndexError, TypeError, AttributeError):
        return ""
    return content if isinstance(content, str) else ""


# ---------- reports: lesson.report events and the final answer ----------

def verdict_text(t: Texts, verdict: dict) -> str:
    if verdict["hit"] is None:
        return t.verdict_no_answer.format(count=verdict["returned"])
    if verdict["complete"]:
        return t.verdict_complete.format(rank=verdict["first_rank"])
    if verdict["hit"]:
        return t.verdict_partial.format(rank=verdict["first_rank"], missing=t.separator.join(verdict["missing"]))
    return t.verdict_miss


def hit_list(t: Texts, hits: list[Hit]) -> str:
    return t.separator.join(t.hit_item.format(chunk=hit.chunk_id, score=hit.score) for hit in hits) or t.value_none


def _count(results, name: str, key: str) -> int:
    return sum(1 for _, _, verdicts in results if verdicts[name][key] is True)


def _compare_reports(context, t: Texts, values: Inputs, results, same_source: bool, version: str,
                     chunk_count: int) -> str:
    answerable = sum(1 for query, _, _ in results if query.gold)
    no_answer = [(query, verdicts) for query, _, verdicts in results if not query.gold]
    # One report per strategy: its own hits with its own score scale.
    for name in STRATEGIES:
        context.emit("lesson.report", {
            "title": t.strategy_titles[name], "summary": t.strategy_summaries[name],
            "metrics": [
                {"id": f"{name}-hit", "label": t.label_hit, "value": f"{_count(results, name, 'hit')}/{answerable}"},
                {"id": f"{name}-complete", "label": t.label_complete,
                 "value": f"{_count(results, name, 'complete')}/{answerable}"},
                {"id": f"{name}-noise", "label": t.label_no_answer_returned,
                 "value": sum(verdicts[name]["returned"] for _, verdicts in no_answer)},
            ],
            "table": {"columns": [t.col_query, t.col_kind, t.list_columns[name], t.col_verdict],
                      "rows": [[query.id, t.kinds[query.kind], hit_list(t, lists[name]), verdict_text(t, verdicts[name])]
                               for query, lists, verdicts in results]},
        })
    # The comparison uses ranks and verdicts only.
    keyword_only = [q.id for q, _, v in results if v["keyword"]["hit"] is True and v["vector"]["hit"] is False]
    vector_only = [q.id for q, _, v in results if v["vector"]["hit"] is True and v["keyword"]["hit"] is False]
    incomplete = [q.id for q, _, v in results if q.gold and not any(v[name]["complete"] for name in STRATEGIES)]
    context.emit("lesson.report", {
        "title": t.compare_title, "summary": t.compare_summary,
        "checks": [{"id": "same-source", "label": t.check_same_source, "passed": same_source,
                    "detail": t.check_same_source_detail.format(version=version, queries=query_set_version(),
                                                                chunks=chunk_count, count=len(results))}],
        "metrics": [
            *[{"id": f"hits-{name}", "label": t.label_hits_of[name], "value": f"{_count(results, name, 'hit')}/{answerable}"}
              for name in STRATEGIES],
            {"id": "keyword-only", "label": t.label_keyword_only, "value": t.separator.join(keyword_only) or t.value_none},
            {"id": "vector-only", "label": t.label_vector_only, "value": t.separator.join(vector_only) or t.value_none},
            {"id": "incomplete", "label": t.label_incomplete_all, "value": t.separator.join(incomplete) or t.value_none},
            {"id": "settings", "label": t.label_settings, "value": t.settings.format(top_k=values.top_k, k=values.rrf_k)},
        ],
        "table": {"columns": list(t.compare_columns),
                  "rows": [[query.id, t.kinds[query.kind], *[verdict_text(t, verdicts[name]) for name in STRATEGIES]]
                           for query, _, verdicts in results]},
    })
    # The fusion arithmetic for one query: each list's rank and its 1/(k + rank) share.
    query, lists, _ = next(item for item in results if item[0].id == RRF_EXAMPLE)
    rows = []
    for hit in lists["hybrid"]:
        ranks, parts = hit.detail["ranks"], hit.detail["contributions"]
        rows.append([hit.chunk_id, *[ranks.get(name) or t.value_absent for name in ("keyword", "vector")],
                     *[parts.get(name, 0) for name in ("keyword", "vector")], hit.score, hit.rank])
    context.emit("lesson.report", {
        "title": t.rrf_title.format(query=query.id), "summary": t.rrf_summary.format(k=values.rrf_k, text=query.text),
        "metrics": [{"id": "rrf-k", "label": t.label_rrf_k, "value": values.rrf_k}],
        "table": {"columns": list(t.rrf_columns), "rows": rows},
    })
    return t.compare_answer.format(total=answerable, **{name: _count(results, name, "hit") for name in STRATEGIES})


def _rerank_report(context, t: Texts, values: Inputs, query: Query, candidates: list[Chunk], reranked: list[Chunk],
                   parsed: dict, before: dict, after: dict, pool: dict, cost: dict) -> str:
    def cell(chunk: Chunk) -> str:
        marked = any(anchor in query.gold for anchor in chunk.anchors)
        return t.candidate_cell.format(chunk=chunk.chunk_id, mark=t.gold_mark if marked else "")

    problems = [t.problem_labels[key].format(items=t.separator.join(parsed[key]))
                for key in ("unknown", "duplicates", "missing") if parsed[key]]
    tokens = cost["tokens"] if cost["tokens"] is not None else t.value_not_reported
    context.emit("lesson.report", {
        "title": t.rerank_title.format(query=query.id), "summary": t.rerank_summary.format(text=query.text),
        "checks": [
            {"id": "reply-valid", "label": t.check_reply_valid, "passed": parsed["valid"],
             "detail": (t.separator.join(problems) or t.reply_clean) if parsed["valid"] else t.reply_errors[parsed["error"]]},
            *([{"id": "pool-covers", "label": t.check_pool_covers, "passed": bool(pool["complete"]),
                "detail": verdict_text(t, pool)}] if query.gold else []),
        ],
        "metrics": [
            {"id": "before", "label": t.label_before.format(k=values.top_k), "value": verdict_text(t, before)},
            {"id": "after", "label": t.label_after.format(k=values.top_k), "value": verdict_text(t, after)},
            {"id": "extra-calls", "label": t.label_extra_calls, "value": 1},
            {"id": "rerank-tokens", "label": t.label_rerank_tokens, "value": tokens},
            {"id": "rerank-ms", "label": t.label_rerank_ms, "value": cost["ms"]},
            {"id": "prompt-chars", "label": t.label_prompt_chars, "value": cost["prompt_chars"]},
            {"id": "candidates", "label": t.label_candidates, "value": len(candidates)},
        ],
        "table": {"columns": list(t.rerank_columns),
                  "rows": [[rank, cell(old), cell(new)] for rank, (old, new) in enumerate(zip(candidates, reranked), 1)]},
    })
    return t.rerank_answer.format(k=values.top_k, before=verdict_text(t, before), after=verdict_text(t, after),
                                  tokens=tokens)


def _doc_ids(t: Texts, chunk_ids) -> str:
    return t.separator.join(dict.fromkeys(chunk_id.split(":")[0] for chunk_id in chunk_ids))


def _filter_report(context, t: Texts, queries: list[Query], chunks: list[Chunk], filtered: dict) -> None:
    removed, _ = filtered[True]
    rows = []
    for position, query in enumerate(queries):
        for newest_only in (False, True):
            hits = filtered[newest_only][1][position]
            rows.append([query.id, t.filter_off if not newest_only else t.filter_on,
                         t.separator.join(hit.chunk_id for hit in hits), _doc_ids(t, (hit.chunk_id for hit in hits))])
    old_hits = sum(1 for hits in filtered[False][1] for hit in hits if hit.chunk_id.split(":")[0] in {r["doc_id"] for r in removed})
    context.emit("lesson.report", {
        "title": t.filter_title, "summary": t.filter_summary,
        "metrics": [
            {"id": "filtered-out", "label": t.label_filtered_out, "value": len(removed)},
            {"id": "filtered-records", "label": t.label_filtered_records,
             "value": t.separator.join(t.removed_item.format(
                 chunk=r["chunk_id"], reason=t.filter_reasons[r["reason"]].format(by=r.get("by", "")))
                 for r in removed) or t.value_none},
            {"id": "old-version-hits", "label": t.label_old_hits, "value": old_hits},
            {"id": "candidates-left", "label": t.label_candidates_left, "value": len(chunks) - len(removed)},
        ],
        "table": {"columns": list(t.filter_columns), "rows": rows},
    })


def _change_report(context, t: Texts, queries, changes, stale: bool, old_index, version: str, before, saved, current):
    rows = [[change["file"], t.change_actions[change["action"]], change["before"] or t.value_none,
             change["after"] or t.value_none] for change in changes]
    stale_rows = []
    for query, hits in zip(queries, before):
        found = index_update.stale_hits(hits, saved, current)
        stale_rows.append(t.stale_item.format(query=query.id, items=t.separator.join(
            t.stale_entry.format(chunk=item["chunk_id"], reason=t.stale_reasons[item["reason"]]) for item in found)
            or t.value_none))
    context.emit("lesson.report", {
        "title": t.change_title, "summary": t.change_summary,
        "checks": [{"id": "index-stale", "label": t.check_index_stale, "passed": stale,
                    "detail": t.versions_detail.format(index=old_index.corpus_version, corpus=version)}],
        "metrics": [{"id": "stale-hits", "label": t.label_stale_hits, "value": "\n".join(stale_rows)}],
        "table": {"columns": list(t.change_columns), "rows": rows},
    })


def _update_report(context, t: Texts, queries, chunks, plan, embedded: int, loaded, loaded_prints, version: str,
                   current, after) -> str:
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    deleted_doc = index_update.DELETED_FILE.removesuffix(".md")
    returned = [hit for lists in after for name in ("vector", "hybrid") for hit in lists[name]]
    leftovers = sorted({hit.chunk_id for hit in returned if hit.chunk_id.startswith(deleted_doc + ":")})
    stale_after = index_update.stale_hits(returned, loaded_prints, current)
    edited = [by_id[cid] for cid in plan["changed"] if cid.startswith(index_update.EDITED_FILE.removesuffix(".md") + ":")]
    new_text = bool(edited) and all(index_update.NEW_VALUE in chunk.text and index_update.OLD_VALUE not in chunk.text
                                    for chunk in edited)
    _, removed = apply_filter(chunks, newest_only=True)
    checks = [
        {"id": "version-match", "label": t.check_version_match,
         "passed": not loaded.is_stale(model=loaded.model, dimensions=loaded.dimensions, corpus_version=version),
         "detail": t.versions_detail.format(index=loaded.corpus_version, corpus=version)},
        {"id": "ids-match", "label": t.check_ids_match,
         "passed": loaded.chunk_ids == list(by_id) and loaded_prints == current,
         "detail": t.ids_detail.format(index=len(loaded.chunk_ids), corpus=len(by_id))},
        {"id": "no-deleted", "label": t.check_no_deleted, "passed": not leftovers,
         "detail": t.separator.join(leftovers) or t.value_none},
        {"id": "no-stale", "label": t.check_no_stale, "passed": not stale_after,
         "detail": t.separator.join(item["chunk_id"] for item in stale_after) or t.value_none},
        {"id": "edited-text", "label": t.check_edited_text, "passed": new_text,
         "detail": t.separator.join(chunk.chunk_id for chunk in edited) or t.value_none},
    ]
    rows = [[query.id, t.separator.join(hit.chunk_id for hit in lists["hybrid"]),
             _doc_ids(t, (hit.chunk_id for hit in lists["hybrid"]))] for query, lists in zip(queries, after)]
    context.emit("lesson.report", {
        "title": t.update_title, "summary": t.update_summary,
        "checks": checks,
        "metrics": [
            *[{"id": f"plan-{key}", "label": t.plan_labels[key], "value": len(plan[key])} for key in plan],
            {"id": "embedded", "label": t.label_embedded, "value": embedded},
            {"id": "filter-after-delete", "label": t.label_filter_after_delete, "value": len(removed)},
            {"id": "index-version", "label": t.label_index_version, "value": loaded.corpus_version},
        ],
        "table": {"columns": list(t.update_columns), "rows": rows},
    })
    passed = sum(1 for check in checks if check["passed"])
    return t.update_answer.format(changed=len(plan["changed"]), added=len(plan["added"]), removed=len(plan["removed"]),
                                  embedded=embedded, passed=passed, total=len(checks))
