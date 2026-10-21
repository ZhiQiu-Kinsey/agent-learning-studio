"""Embedding retrieval: embed the handbook chunks in batches, keep the index with what it was built from, and compare it with BM25 on one query set.

Batching, saving the vectors so they are paid for once, and searching by cosine similarity follow
claude-cookbooks capabilities/contextual-embeddings (MIT); brute-force search over every vector follows
the exact search of ai-agent-book chapter3/dense-embedding (Apache-2.0). The staleness rule (model,
dimensions and corpus version must all match) and the experiments are written by this project.
Every text that reaches an event is in locales/, one catalog per run language.
"""
from __future__ import annotations

import hashlib
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from course.execution import EmbeddingNotConfigured, LessonInputs, RunContext
from course.locales import texts_for as platform_texts
from lessons.lesson_document_loading.chunking import Chunk, chunk_corpus
from lessons.lesson_document_loading.loader import ROOT, Document, load_corpus
from lessons.lesson_embedding_retrieval.locales import Texts, texts_for
from lessons.lesson_embedding_retrieval.vector_index import VectorIndex, index_path
from lessons.lesson_keyword_retrieval.bm25 import ANCHOR_MARK, BM25Index
from lessons.lesson_keyword_retrieval.query_set import judge, load_queries, query_set_version

# Sizes embedding providers commonly accept for `dimensions`; anything else is refused before any request.
SIZES = (64, 128, 256, 512, 768, 1024, 1536, 2048)
DocFilter = Literal["all", "borrowing", "fees", "membership", "rooms", "hours", "hours-2025",
                    "digital", "conduct", "floors", "reader-notes"]
# The corpus change the stale exercise simulates: the superseded 2025 opening hours go offline.
RETIRED_DOC = "hours-2025"
TOP_K = 5  # the comparison uses the same depth for both retrievers
# Offline test runs keep their index here when a test sets it; otherwise in a fresh temporary folder.
OFFLINE_INDEX_DIR: Path | None = None


class Inputs(LessonInputs):
    task: Literal["search", "compare", "stale"] = "search"
    # No default: lesson.json supplies the query in the run's language.
    query: str = Field(min_length=1, max_length=200)
    top_k: int = Field(default=5, ge=1, le=10)
    dimensions: int = Field(default=256, ge=64, le=2048)
    doc_filter: DocFilter = "all"
    change: Literal["dimensions", "corpus"] = "dimensions"
    new_dimensions: int = Field(default=512, ge=64, le=2048)

    @model_validator(mode="after")
    def _sizes(self):
        if self.dimensions not in SIZES or self.new_dimensions not in SIZES:
            raise ValueError(f"dimensions must be one of {SIZES}")
        if self.task == "stale" and self.change == "dimensions" and self.new_dimensions == self.dimensions:
            raise ValueError("new_dimensions must differ from dimensions")
        return self


INPUT_MODEL = Inputs


def embedding_text(chunk: Chunk) -> str:
    """What gets embedded: the chunk as written, minus the {#anchor} marks that carry no meaning."""
    return ANCHOR_MARK.sub("", chunk.text).strip()


def corpus_version_of(documents: list[Document]) -> str:
    """loader.corpus_version for any set of documents: one digest over every doc_id and content hash."""
    lines = sorted(f"{doc.doc_id}:{doc.sha256}" for doc in documents)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]


class Embedder:
    """Every embeddings request of a run goes through here: batches, rounds and reported usage."""

    def __init__(self, context: RunContext, t: Texts):
        self.context, self.t = context, t
        self.calls = 0
        self.tokens: list[int | None] = []

    def embed(self, texts: list[str], dimensions: int) -> list[list[float]]:
        limit = self.context.embedding_batch_limit
        vectors = []
        # 1. One request per batch: the provider takes at most `limit` texts at a time.
        for start in range(0, len(texts), limit):
            self.calls += 1
            response = self.context.embed(texts[start:start + limit], self.calls, dimensions=dimensions)
            # 2. Put vectors back in input order by their index, not by position in the reply.
            for item in sorted(response["data"], key=lambda item: item["index"]):
                # 3. A provider that ignores `dimensions` must not slip a different size into the index.
                if len(item["embedding"]) != dimensions:
                    raise ValueError(self.t.size_mismatch.format(asked=dimensions, got=len(item["embedding"])))
                vectors.append(item["embedding"])
            usage = response.get("usage")
            total = usage.get("total_tokens") if isinstance(usage, dict) else None
            self.tokens.append(total if isinstance(total, int) else None)
        return vectors

    def usage(self) -> int | str:
        reported = [value for value in self.tokens if value is not None]
        if not reported:
            return self.t.not_reported
        missing = len(self.tokens) - len(reported)
        return sum(reported) if not missing else self.t.partly_reported.format(total=sum(reported), missing=missing)


def stale_reasons(t: Texts, index: VectorIndex, *, model: str, dimensions: int, version: str,
                  chunk_ids: list[str]) -> list[str]:
    """Why a saved index must not answer for these chunks; an empty list means it may be reused."""
    reasons = []
    if index.is_stale(model=model, dimensions=dimensions, corpus_version=version):
        for field, old, new in (("model", index.model, model), ("dimensions", index.dimensions, dimensions),
                                ("corpus_version", index.corpus_version, version)):
            if old != new:
                reasons.append(t.reason_field.format(field=field, old=old, new=new))
    # Checked on its own: the same corpus chunked another way would pair vectors with the wrong chunks.
    if index.chunk_ids != chunk_ids:
        current = set(chunk_ids)
        removed = sum(1 for chunk_id in index.chunk_ids if chunk_id not in current)
        added = len(current - set(index.chunk_ids))
        reasons.append(t.reason_chunks.format(removed=removed, added=added))
    return reasons


def open_index(context: RunContext, t: Texts, embedder: Embedder, chunks: list[Chunk], *, dimensions: int,
               version: str, path: Path, save: bool = True) -> VectorIndex:
    """Reuse the saved index when it was built from the same model, size and corpus; otherwise embed every chunk again."""
    model = context.embedding_model
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    saved, reasons = None, []
    if path.exists():
        try:
            saved = VectorIndex.load(path)
            reasons = stale_reasons(t, saved, model=model, dimensions=dimensions, version=version,
                                    chunk_ids=chunk_ids)
        except (ValueError, KeyError, TypeError) as error:
            # A damaged file is treated like a stale one: rebuilt, never trusted.
            saved, reasons = None, [t.reason_unreadable.format(error=type(error).__name__)]
    if saved is not None and not reasons:
        _index_report(context, t, saved, path, status=t.status_reused, calls=0, reasons=[])
        return saved
    calls_before = embedder.calls
    vectors = embedder.embed([embedding_text(chunk) for chunk in chunks], dimensions)
    index = VectorIndex(model, dimensions, version, chunk_ids, vectors)
    if save:
        index.save(path)
    status = t.status_built if not reasons else t.status_rebuilt
    _index_report(context, t, index, path if save else None, status=status,
                  calls=embedder.calls - calls_before, reasons=reasons)
    return index


def compare(context: RunContext, t: Texts, embedder: Embedder, index: VectorIndex, chunks: list[Chunk]) -> list[dict]:
    """Both retrievers answer the same queries over the same chunks; judge() scores them against the same gold."""
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    bm25 = BM25Index(chunks, context.locale)
    queries = load_queries(context.locale)
    # The query vectors go in batches too: 14 queries are two requests, not fourteen.
    query_vectors = embedder.embed([query.text for query in queries], index.dimensions)
    rows = []
    for query, vector in zip(queries, query_vectors):
        context.check_cancelled()
        keyword_hits = bm25.search(query.text, TOP_K)
        vector_hits = index.search(vector, TOP_K)
        rows.append({
            "query": query,
            "bm25": judge([by_id[hit.chunk_id] for hit in keyword_hits], query),
            "vector": judge([by_id[hit.chunk_id] for hit in vector_hits], query),
        })
    return rows


@contextmanager
def index_folder(context: RunContext):
    """Live runs keep indexes in .runtime/ (git-ignored); an offline test run never touches it."""
    if context.mode == "live":
        yield None
    elif OFFLINE_INDEX_DIR is not None:
        yield OFFLINE_INDEX_DIR
    else:
        with tempfile.TemporaryDirectory(prefix="rag-index-") as folder:
            yield Path(folder)


def locate(context: RunContext, folder: Path | None, dimensions: int) -> Path:
    path = index_path(context.locale, context.embedding_model, dimensions)
    return path if folder is None else folder / path.relative_to(ROOT)


def run(context: RunContext):
    t = texts_for(context.locale)
    inputs = context.inputs
    if not context.embedding_model:
        # Normally refused before the run starts; the same coded error if it ever slips through.
        raise EmbeddingNotConfigured(platform_texts(context.locale).embedding_not_configured)
    documents, _ = load_corpus(context.locale)
    chunks = chunk_corpus(documents)
    version = corpus_version_of(documents)
    embedder = Embedder(context, t)
    with index_folder(context) as folder:
        index = open_index(context, t, embedder, chunks, dimensions=inputs["dimensions"], version=version,
                           path=locate(context, folder, inputs["dimensions"]))
        if inputs["task"] == "compare":
            return _compare_task(context, t, embedder, index, chunks)
        if inputs["task"] == "stale":
            return _stale_task(context, t, embedder, index, documents, chunks, folder)
        return _search_task(context, t, embedder, index, chunks)


def _search_task(context, t, embedder, index, chunks):
    inputs = context.inputs
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    [vector] = embedder.embed([inputs["query"]], index.dimensions)
    wanted = inputs["doc_filter"]
    # Metadata filter: chunks of other documents are dropped before ranking, not after.
    where = None if wanted == "all" else (lambda chunk_id: by_id[chunk_id].doc_id == wanted)
    hits = index.search(vector, inputs["top_k"], where=where)
    rows = [[hit.rank, hit.chunk_id, hit.score, ", ".join(by_id[hit.chunk_id].anchors),
             _preview(by_id[hit.chunk_id])] for hit in hits]
    _report(context, t.search_title, t.search_summary.format(query=inputs["query"], count=len(hits)),
            metrics=[_metric("doc_filter", t.label_doc_filter, t.filter_all if wanted == "all" else wanted),
                     _metric("returned", t.label_returned, len(hits)),
                     *_cost_metrics(t, embedder)],
            table={"columns": list(t.search_columns), "rows": rows})
    if not hits:
        return t.search_answer_empty.format(doc=wanted)
    return t.search_answer.format(count=len(hits), first=hits[0].chunk_id, score=hits[0].score)


def _compare_task(context, t, embedder, index, chunks):
    rows = compare(context, t, embedder, index, chunks)
    answerable = [row for row in rows if row["query"].gold]
    counts = {name: sum(1 for row in answerable if row[name]["hit"]) for name in ("bm25", "vector")}
    complete = {name: sum(1 for row in answerable if row[name]["complete"]) for name in ("bm25", "vector")}
    only = {name: sum(1 for row in answerable if row[name]["hit"] and not row[other]["hit"])
            for name, other in (("bm25", "vector"), ("vector", "bm25"))}
    unanswerable = [row for row in rows if not row["query"].gold]
    # Both fairness checks are computed from what actually ran, not assumed: the saved index must describe the
    # very chunks BM25 searched, and every query of the set must have been judged for both retrievers.
    same_chunks = index.chunk_ids == [chunk.chunk_id for chunk in chunks]
    same_queries = [row["query"].id for row in rows] == [query.id for query in load_queries(context.locale)]
    table = [[row["query"].id, t.kinds[row["query"].kind], row["query"].text, _outcome(t, row["bm25"]),
              _outcome(t, row["vector"]), _verdict(t, row)] for row in rows]
    _report(context, t.compare_title, t.compare_summary.format(total=len(rows), answerable=len(answerable)),
            metrics=[_metric("query_set", t.label_query_set, query_set_version()),
                     _metric("bm25_hits", t.label_bm25_hits, f"{counts['bm25']}/{len(answerable)}"),
                     _metric("vector_hits", t.label_vector_hits, f"{counts['vector']}/{len(answerable)}"),
                     _metric("bm25_complete", t.label_bm25_complete, f"{complete['bm25']}/{len(answerable)}"),
                     _metric("vector_complete", t.label_vector_complete, f"{complete['vector']}/{len(answerable)}"),
                     _metric("only_bm25", t.label_only_bm25, only["bm25"]),
                     _metric("only_vector", t.label_only_vector, only["vector"]),
                     _metric("no_answer_returned", t.label_no_answer_returned,
                             ", ".join(f"{row['query'].id}: {row['vector']['returned']}" for row in unanswerable)),
                     *_cost_metrics(t, embedder)],
            checks=[{"id": "same_queries", "label": t.check_same_queries, "passed": same_queries,
                     "detail": t.check_same_queries_detail.format(count=len(rows))},
                    {"id": "same_chunks", "label": t.check_same_chunks, "passed": same_chunks,
                     "detail": t.check_same_chunks_detail.format(count=len(chunks), version=index.corpus_version)}],
            table={"columns": list(t.compare_columns), "rows": table})
    return t.compare_answer.format(answerable=len(answerable), bm25=counts["bm25"], vector=counts["vector"],
                                   only_bm25=only["bm25"], only_vector=only["vector"])


def _stale_task(context, t, embedder, old, documents, chunks, folder):
    """Change one thing the index was built from, show the old index is refused, then rebuild for the new state."""
    inputs = context.inputs
    model = context.embedding_model
    if inputs["change"] == "dimensions":
        new_chunks, new_version, new_size = chunks, old.corpus_version, inputs["new_dimensions"]
    else:
        kept = [doc for doc in documents if doc.doc_id != RETIRED_DOC]
        new_chunks, new_version, new_size = chunk_corpus(kept), corpus_version_of(kept), old.dimensions
    new_ids = [chunk.chunk_id for chunk in new_chunks]
    reasons = stale_reasons(t, old, model=model, dimensions=new_size, version=new_version, chunk_ids=new_ids)
    [probe] = embedder.embed([inputs["query"]], new_size)
    checks = [{"id": "stale_detected", "label": t.check_stale, "passed": bool(reasons),
               "detail": "; ".join(reasons) or t.check_stale_missed}]
    if inputs["change"] == "dimensions":
        # Third guard: even if the wrong file were loaded, vectors of different sizes cannot be compared.
        try:
            old.search(probe, TOP_K)
            checks.append({"id": "size_guard", "label": t.check_size_guard, "passed": False, "detail": ""})
        except ValueError as error:
            checks.append({"id": "size_guard", "label": t.check_size_guard, "passed": True, "detail": str(error)})
        new_path = locate(context, folder, new_size)
        checks.append({"id": "separate_files", "label": t.check_separate_files,
                       "passed": new_path != locate(context, folder, old.dimensions),
                       "detail": new_path.name})
        new = open_index(context, t, embedder, new_chunks, dimensions=new_size, version=new_version, path=new_path)
    else:
        orphans = [chunk_id for chunk_id in old.chunk_ids if chunk_id not in set(new_ids)]
        old_hits = old.search(probe, TOP_K)
        leaked = [hit.chunk_id for hit in old_hits if hit.chunk_id in orphans]
        checks.append({"id": "orphans", "label": t.check_orphans, "passed": bool(orphans),
                       "detail": ", ".join(orphans)})
        checks.append({"id": "old_results_leak", "label": t.check_old_leak, "passed": bool(leaked),
                       "detail": ", ".join(leaked) or t.none})
        # The simulated corpus exists only in this run, so its index is not written over the real one.
        new = open_index(context, t, embedder, new_chunks, dimensions=new_size, version=new_version,
                         path=locate(context, folder, new_size), save=False)
    new_hits = new.search(probe, TOP_K)
    checks.append({"id": "new_results_clean", "label": t.check_new_clean,
                   "passed": all(hit.chunk_id in set(new_ids) for hit in new_hits),
                   "detail": ", ".join(hit.chunk_id for hit in new_hits)})
    if inputs["change"] == "dimensions":
        change = t.change_dimensions.format(old=old.dimensions, new=new_size)
        columns, table = t.stale_columns_dimensions, [[rank, _cell(new_hits, rank)] for rank in range(1, TOP_K + 1)]
    else:
        change = t.change_corpus.format(doc=RETIRED_DOC)
        columns = t.stale_columns_corpus
        table = [[rank, _cell(old_hits, rank), _cell(new_hits, rank)] for rank in range(1, TOP_K + 1)]
    _report(context, t.stale_title, t.stale_summary.format(change=change),
            metrics=[_metric("change", t.label_change, change), *_cost_metrics(t, embedder)],
            checks=checks, table={"columns": list(columns), "rows": table})
    return t.stale_answer.format(change=change, reasons="; ".join(reasons))


# ---- Evidence: report events, kept out of the teaching code above ----

def _index_report(context, t, index, path, *, status, calls, reasons):
    if path is None:
        location = t.location_memory
    else:
        location = t.location_project if context.mode == "live" else t.location_temporary
    source = t.source_live.format(model=index.model) if context.mode == "live" else t.source_test
    metrics = [_metric("index_status", t.label_status, status),
               _metric("embedding_model", t.label_model, index.model),
               _metric("dimensions", t.label_dimensions, index.dimensions),
               _metric("corpus_version", t.label_corpus_version, index.corpus_version),
               _metric("chunks", t.label_chunks, len(index.chunk_ids)),
               _metric("index_calls", t.label_index_calls, calls),
               _metric("index_file", t.label_index_file, location if path is None else
                       f"{_display_path(path)} ({location})"),
               _metric("vector_source", t.label_vector_source, source)]
    if reasons:
        metrics.append(_metric("stale_reasons", t.label_stale_reasons, "; ".join(reasons)))
    _report(context, t.index_title, t.index_summary.format(status=status, chunks=len(index.chunk_ids)), metrics=metrics)


def _display_path(path: Path) -> str:
    # Never an absolute local path in an event: show it from the .runtime folder on.
    parts = path.parts
    return "/".join(parts[parts.index(".runtime"):]) if ".runtime" in parts else path.name


def _cost_metrics(t, embedder):
    return [_metric("embedding_calls", t.label_embedding_calls, embedder.calls),
            _metric("embedding_usage", t.label_embedding_usage, embedder.usage())]


def _outcome(t, result):
    if result["hit"] is None:
        return t.outcome_no_gold.format(returned=result["returned"])
    if not result["hit"]:
        return t.outcome_miss
    return (t.outcome_complete if result["complete"] else t.outcome_partial).format(rank=result["first_rank"])


def _verdict(t, row):
    keyword, vector = row["bm25"]["hit"], row["vector"]["hit"]
    if keyword is None:
        return t.verdict_no_gold
    return t.verdicts[f"{int(keyword)}{int(vector)}"]


def _cell(hits, rank):
    return hits[rank - 1].chunk_id + f" ({hits[rank - 1].score})" if len(hits) >= rank else ""


def _preview(chunk: Chunk, limit: int = 60) -> str:
    text = " ".join(embedding_text(chunk).split())
    return text if len(text) <= limit else text[:limit] + "…"


def _metric(identifier, label, value):
    return {"id": identifier, "label": label, "value": value}


def _report(context, title, summary, *, metrics, checks=None, table=None):
    data = {"title": title, "summary": summary, "metrics": metrics}
    if checks is not None:
        data["checks"] = checks
    if table is not None:
        data["table"] = table
    context.emit("lesson.report", data)
