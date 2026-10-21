"""Keyword retrieval with BM25 over the handbook chunks; this lesson calls no model.

Three exercises share one index: a hit table over the whole query set, one hit's score taken
apart term by term, and the misses (reworded queries, questions the handbook cannot answer).
Scoring lives in bm25.py and judging in query_set.py; this file runs them and records evidence.
"""
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_document_loading.chunking import Chunk, default_chunks, params_for
from lessons.lesson_document_loading.loader import corpus_version
from lessons.lesson_keyword_retrieval.bm25 import BM25Index, Hit
from lessons.lesson_keyword_retrieval.locales import texts_for
from lessons.lesson_keyword_retrieval.query_set import judge, load_queries, query_set_version

DEFAULT_K1, DEFAULT_B = 1.5, 0.75
# The ids in corpus/queries.json; a test keeps this list in step with the file.
QueryId = Literal["q01", "q02", "q03", "q04", "q05", "q06", "q07", "q08", "q09", "q10", "q11", "q12", "q13", "q14"]


class Inputs(LessonInputs):
    scenario: Literal["query_table", "explain", "misses"] = "query_table"
    top_k: int = Field(default=5, ge=1, le=10)
    k1: float = Field(default=DEFAULT_K1, ge=0.0, le=3.0)
    b: float = Field(default=DEFAULT_B, ge=0.0, le=1.0)
    # Only for "explain": a query from the query set, in the run's language...
    query_id: QueryId = "q03"
    # ...unless the learner types their own; it has no default so no language leaks into the form.
    query: str | None = Field(default=None, min_length=1, max_length=200)
    # Only for "explain": which chunk to take apart; empty means the top hit.
    chunk_id: str | None = Field(default=None, min_length=1, max_length=64)


INPUT_MODEL = Inputs


def build_index(context: RunContext, values: Inputs, *, with_queries: bool) -> BM25Index:
    """Index the standard chunks and record everything needed to rerun the same search later."""
    chunks = default_chunks(context.locale)
    index = BM25Index(chunks, context.locale, k1=values.k1, b=values.b)
    params = params_for(context.locale)
    context.emit("lesson.index", {
        "locale": context.locale, "corpus_version": corpus_version(context.locale),
        "query_set_version": query_set_version() if with_queries else None,
        "chunking": {"preset": "default", "max_chars": params.max_chars, "overlap_lines": params.overlap_lines},
        "chunks": len(chunks), "avg_length": round(index.avg_length, 2), "vocabulary": len(index.doc_freq),
        "k1": values.k1, "b": values.b, "tokens": "words" if context.locale == "en" else "cjk_bigrams",
    })
    return index


def ranked_chunks(index: BM25Index, hits: list[Hit]) -> list[Chunk]:
    return [index.chunks[index.position[hit.chunk_id]] for hit in hits]


def query_table(context: RunContext, values: Inputs) -> str:
    index = build_index(context, values, with_queries=True)
    versions = (corpus_version(context.locale), query_set_version())
    rows = []
    for query in load_queries(context.locale):
        context.check_cancelled()
        # 1. Search: only chunks sharing at least one query term come back, best first.
        hits = index.search(query.text, values.top_k)
        # 2. Judge against the gold anchors; chunk ids never enter the labels.
        verdict = judge(ranked_chunks(index, hits), query)
        context.emit("lesson.search", {
            "query_id": query.id, "kind": query.kind, "query": query.text,
            "terms": index.query_terms(query.text), "gold": list(query.gold), "top_k": values.top_k,
            "hits": [_hit(index, hit) for hit in hits], "judge": verdict,
        })
        rows.append((query, hits, verdict))
    # 3. Rerun on a freshly built index: the recorded versions are only useful if the result repeats.
    fresh = BM25Index(default_chunks(context.locale), context.locale, k1=values.k1, b=values.b)
    identical = all([(h.chunk_id, h.score) for h in fresh.search(query.text, values.top_k)]
                    == [(h.chunk_id, h.score) for h in hits] for query, hits, _ in rows)
    unchanged = versions == (corpus_version(context.locale), query_set_version())
    return _report_table(context, values, index, rows, identical, unchanged)


def explain(context: RunContext, values: Inputs) -> str:
    t = texts_for(context.locale)
    index = build_index(context, values, with_queries=values.query is None)
    query = values.query or next(item.text for item in load_queries(context.locale) if item.id == values.query_id)
    hits = index.search(query, values.top_k)
    chunk_id = values.chunk_id or (hits[0].chunk_id if hits else None)
    # 1. Nothing to take apart: no chunk shares a term, or the chunk id is not in this index.
    if chunk_id is None or chunk_id not in index.position:
        error_type = "no_match" if chunk_id is None else "unknown_chunk"
        error = t.error_no_match if chunk_id is None else t.error_unknown_chunk.format(chunk_id=chunk_id)
        context.emit("lesson.score", {"ok": False, "error_type": error_type, "error": error,
                                      "query_id": None if values.query else values.query_id, "query": query,
                                      "terms": index.query_terms(query)})
        return _report_explain_failed(context, values, error)
    # 2. Every factor of the score: idf per term, tf, and the length normalization shared by all terms.
    detail = index.explain(query, chunk_id)
    position = index.position[chunk_id]
    for term in detail["terms"]:
        idf = index.idf(term["term"])
        term["tf_part"] = round(index.term_score(term["term"], position) / idf, 4) if term["tf"] else 0.0
    # 3. Where the chunk ranks among every chunk that shares a term, not only the top k.
    rank = _rank_of(index, query, chunk_id)
    chunk = index.chunks[position]
    context.emit("lesson.score", {"ok": True, "query_id": None if values.query else values.query_id,
                                  "query": query, "rank": rank, "top_k": values.top_k,
                                  "anchors": list(chunk.anchors), "text": chunk.text, **detail})
    # 4. The same chunk under the default k1 and b, so a changed parameter shows its effect.
    default = index
    if (values.k1, values.b) != (DEFAULT_K1, DEFAULT_B):
        default = BM25Index(index.chunks, context.locale)
    baseline = {"score": default.explain(query, chunk_id)["score"],
                "rank": _rank_of(default, query, chunk_id)}
    listed = next((hit.score for hit in hits if hit.chunk_id == chunk_id), None)
    return _report_explain(context, values, detail, rank, listed, baseline)


def misses(context: RunContext, values: Inputs) -> str:
    t = texts_for(context.locale)
    index = build_index(context, values, with_queries=True)
    queries = load_queries(context.locale)
    diagnosed, unanswerable = [], []
    for query in (item for item in queries if item.kind == "synonym"):
        context.check_cancelled()
        hits = index.search(query.text, values.top_k)
        verdict = judge(ranked_chunks(index, hits), query)
        # 1. Look at the gold chunks themselves: which query terms do they contain, and where do they rank?
        gold_chunks = [_gold_chunk(index, query.text, chunk) for chunk in index.chunks
                       if set(chunk.anchors) & set(query.gold)]
        reason = None if verdict["hit"] else _miss_reason(gold_chunks)
        # 2. Ask again in the handbook's own words; if that hits, the miss came from the wording.
        rewrite = t.rewrites[query.id]
        rewrite_hits = index.search(rewrite, values.top_k)
        rewrite_verdict = judge(ranked_chunks(index, rewrite_hits), query)
        record = {"query_id": query.id, "query": query.text, "terms": index.query_terms(query.text),
                  "gold": list(query.gold), "top_k": values.top_k, "hit": verdict["hit"], "reason": reason,
                  "hits": [_hit(index, hit) for hit in hits], "gold_chunks": gold_chunks,
                  "rewrite": {"query": rewrite, "terms": index.query_terms(rewrite), "hit": rewrite_verdict["hit"],
                              "first_rank": rewrite_verdict["first_rank"]}}
        context.emit("lesson.miss", record)
        diagnosed.append(record)
    for query in (item for item in queries if item.kind == "no_answer"):
        context.check_cancelled()
        # 3. No gold at all: BM25 has no notion of "nothing relevant" and still ranks whatever shares a word.
        hits = index.search(query.text, values.top_k)
        record = {"query_id": query.id, "query": query.text, "terms": index.query_terms(query.text),
                  "returned": len(hits), "top_score": hits[0].score if hits else None,
                  "hits": [_hit(index, hit) for hit in hits]}
        context.emit("lesson.no_answer", record)
        unanswerable.append(record)
    return _report_misses(context, values, diagnosed, unanswerable)


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    if values.scenario == "query_table":
        return query_table(context, values)
    if values.scenario == "explain":
        return explain(context, values)
    return misses(context, values)


# ---------- Evidence helpers: they read the index, they never change a score ----------

def _hit(index: BM25Index, hit: Hit) -> dict:
    chunk = index.chunks[index.position[hit.chunk_id]]
    return {"rank": hit.rank, "chunk_id": hit.chunk_id, "score": hit.score, "anchors": list(chunk.anchors),
            "path": chunk.path, "start_line": chunk.start_line, "end_line": chunk.end_line,
            "terms": hit.detail["terms"]}


def _rank_of(index: BM25Index, query: str, chunk_id: str) -> int | None:
    every = index.search(query, len(index.chunks))
    return next((hit.rank for hit in every if hit.chunk_id == chunk_id), None)


def _gold_chunk(index: BM25Index, query: str, chunk: Chunk) -> dict:
    detail = index.explain(query, chunk.chunk_id)
    return {"chunk_id": chunk.chunk_id, "anchors": list(chunk.anchors), "score": detail["score"],
            "shared_terms": [term["term"] for term in detail["terms"] if term["tf"]],
            "rank": _rank_of(index, query, chunk.chunk_id), "text": chunk.text}


def _miss_reason(gold_chunks: list[dict]) -> str:
    # No shared term means no score at all: only a change of wording can bring the chunk back.
    if all(not item["shared_terms"] for item in gold_chunks):
        return "no_shared_terms"
    return "outranked"


def _note(context: RunContext) -> dict:
    t = texts_for(context.locale)
    return {"id": "note", "label": t.label_note, "value": context.question or t.value_none}


def _versions(context: RunContext, values: Inputs, chunk_count: int, with_queries: bool) -> list[dict]:
    t = texts_for(context.locale)
    metrics = [{"id": "corpus_version", "label": t.label_corpus_version, "value": corpus_version(context.locale)}]
    if with_queries:
        metrics.append({"id": "query_set_version", "label": t.label_query_set_version, "value": query_set_version()})
    return metrics + [{"id": "chunks", "label": t.label_chunks, "value": chunk_count},
                      {"id": "params", "label": t.label_params,
                       "value": t.params_value.format(k1=values.k1, b=values.b, top_k=values.top_k)},
                      {"id": "model_calls", "label": t.label_model_calls, "value": 0}]


def _yes_no(t, value) -> str:
    return t.value_not_applicable if value is None else t.value_yes if value else t.value_no


def _report_table(context, values, index, rows, identical, unchanged) -> str:
    t = texts_for(context.locale)
    graded = [(query, verdict) for query, _, verdict in rows if query.gold]
    hit_count = sum(1 for _, verdict in graded if verdict["hit"])
    complete_count = sum(1 for _, verdict in graded if verdict["complete"])
    mrr = sum(1 / verdict["first_rank"] for _, verdict in graded if verdict["first_rank"]) / len(graded)
    missed = [query.id for query, verdict in graded if not verdict["hit"]]
    traceable = all(hit.chunk_id in index.position and hit.score > 0 for _, hits, _ in rows for hit in hits)
    context.emit("lesson.report", {
        "title": t.table_title,
        "summary": t.table_summary,
        "checks": [
            {"id": "traceable", "label": t.check_traceable, "passed": traceable, "detail": t.check_traceable_detail},
            {"id": "versions_recorded", "label": t.check_versions, "passed": unchanged,
             "detail": t.check_versions_detail.format(corpus=corpus_version(context.locale),
                                                      queries=query_set_version())},
            {"id": "rerun_identical", "label": t.check_rerun, "passed": identical, "detail": t.check_rerun_detail},
        ],
        "metrics": [
            {"id": "hit_rate", "label": t.label_hit_rate, "value": round(hit_count / len(graded), 4)},
            {"id": "hit_count", "label": t.label_hit_count, "value": f"{hit_count}/{len(graded)}"},
            {"id": "complete_rate", "label": t.label_complete_rate, "value": round(complete_count / len(graded), 4)},
            {"id": "mrr", "label": t.label_mrr, "value": round(mrr, 4)},
            {"id": "missed", "label": t.label_missed, "value": t.separator.join(missed) or t.value_none},
            *_versions(context, values, len(index.chunks), True), _note(context),
        ],
        "table": {"columns": list(t.table_columns), "rows": [
            [query.id, t.kinds[query.kind], query.text, t.separator.join(query.gold) or t.value_none,
             verdict["first_rank"] or "—", _yes_no(t, verdict["hit"]), _yes_no(t, verdict["complete"]),
             t.separator.join(f"{hit.chunk_id} {hit.score}" for hit in hits) or t.value_none]
            for query, hits, verdict in rows]},
    })
    return t.table_answer.format(hits=hit_count, graded=len(graded), complete=complete_count,
                                 missed=t.separator.join(missed) or t.value_none)


def _report_explain(context, values, detail, rank, listed, baseline) -> str:
    t = texts_for(context.locale)
    total = round(sum(term["contribution"] for term in detail["terms"]), 4)
    adds_up = abs(total - detail["score"]) < 0.001 and (listed is None or abs(listed - detail["score"]) < 0.001)
    context.emit("lesson.report", {
        "title": t.explain_title,
        "summary": t.explain_summary,
        "checks": [{"id": "sum_matches", "label": t.check_sum, "passed": adds_up,
                    "detail": t.check_sum_detail.format(total=total, score=detail["score"])}],
        "metrics": [
            {"id": "chunk", "label": t.label_chunk, "value": detail["chunk_id"]},
            {"id": "rank", "label": t.label_rank, "value": rank if rank is not None else t.value_none},
            {"id": "score", "label": t.label_score, "value": detail["score"]},
            {"id": "length", "label": t.label_length,
             "value": t.length_value.format(length=detail["length"], avg=detail["avg_length"])},
            {"id": "length_norm", "label": t.label_length_norm, "value": detail["length_norm"]},
            {"id": "baseline_score", "label": t.label_baseline_score, "value": baseline["score"]},
            {"id": "baseline_rank", "label": t.label_baseline_rank,
             "value": baseline["rank"] if baseline["rank"] is not None else t.value_none},
            *_versions(context, values, detail["chunks"], values.query is None),
            _note(context),
        ],
        "table": {"columns": list(t.explain_columns), "rows": [
            [term["term"], term["df"], term["raw_idf"], term["idf"], term["tf"], term["tf_part"],
             term["contribution"]] for term in detail["terms"]]},
    })
    return t.explain_answer.format(chunk_id=detail["chunk_id"], score=detail["score"],
                                   rank=rank if rank is not None else t.value_none)


def _report_explain_failed(context, values, error) -> str:
    t = texts_for(context.locale)
    context.emit("lesson.report", {
        "title": t.explain_title,
        "summary": t.explain_failed_summary,
        "checks": [{"id": "chunk_found", "label": t.check_found, "passed": False, "detail": error}],
        "metrics": [*_versions(context, values, len(default_chunks(context.locale)), values.query is None),
                    _note(context)],
    })
    return t.explain_failed_answer.format(error=error)


def _report_misses(context, values, diagnosed, unanswerable) -> str:
    t = texts_for(context.locale)
    missed = [item for item in diagnosed if not item["hit"]]
    rewrites_hit = sum(1 for item in diagnosed if item["rewrite"]["hit"])
    context.emit("lesson.report", {
        "title": t.misses_title,
        "summary": t.misses_summary,
        "checks": [
            {"id": "reasons", "label": t.check_reasons, "passed": all(item["reason"] for item in missed),
             "detail": t.check_reasons_detail},
            {"id": "rewrites_hit", "label": t.check_rewrites, "passed": rewrites_hit == len(diagnosed),
             "detail": t.check_rewrites_detail.format(hits=rewrites_hit, total=len(diagnosed))},
            {"id": "no_answer_returns", "label": t.check_no_answer,
             "passed": all(item["returned"] > 0 for item in unanswerable), "detail": t.check_no_answer_detail},
        ],
        "metrics": [
            {"id": "missed", "label": t.label_missed, "value": f"{len(missed)}/{len(diagnosed)}"},
            {"id": "rewrites", "label": t.label_rewrites_hit, "value": f"{rewrites_hit}/{len(diagnosed)}"},
            {"id": "no_answer_top", "label": t.label_no_answer_top,
             "value": t.separator.join(f"{item['query_id']} {item['top_score']}" for item in unanswerable)},
            *_versions(context, values, len(default_chunks(context.locale)), True), _note(context),
        ],
        "table": {"columns": list(t.misses_columns), "rows": [
            *([item["query_id"], item["query"], t.reasons[item["reason"]] if item["reason"] else t.value_hit,
               t.separator.join(f"{chunk['chunk_id']}: {t.separator.join(chunk['shared_terms']) or t.value_none}"
                                for chunk in item["gold_chunks"]),
               item["rewrite"]["query"], item["rewrite"]["first_rank"] or "—"] for item in diagnosed),
            *([item["query_id"], item["query"], t.reason_no_answer,
               t.separator.join(f"{hit['chunk_id']} {hit['score']}" for hit in item["hits"][:3]) or t.value_none,
               "—", "—"] for item in unanswerable)]},
    })
    return t.misses_answer.format(missed=len(missed), total=len(diagnosed), rewrites=rewrites_hit,
                                  no_answer=len(unanswerable))
