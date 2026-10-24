"""document-loading: turn a fixed corpus into chunks that point back to the file, and mark the text as data.

Three exercises share this runner. Two are local and call no model: the chunk catalogs (both presets in one run,
checked against the files on disk, plus the evidence a cross-section question needs) and the load log (problem
files recorded, never skipped silently). The third asks one question twice in one run, with the same two chunks
framed two ways, and records what the model answered each time. Loading and chunking live in loader.py and chunking.py, which later lessons
import unchanged. Every text that reaches the model or an event is in locales/, one catalog per run language.
"""
import json
from html import escape

from course.execution import LessonInputs, RunContext
from lessons.lesson_document_loading.chunking import Chunk, chunk_corpus, default_chunks, params_for
from lessons.lesson_document_loading.loader import (
    CORPUS_DIR, PROBLEM_DIR, ROOT, UNTRUSTED, Document, corpus_files, corpus_version, load_corpus,
)
from lessons.lesson_document_loading.locales import Texts, texts_for


class Inputs(LessonInputs):
    """Every exercise runs on fixed data and compares its conditions inside one run, so there is nothing to set."""


INPUT_MODEL = Inputs
COMPARED_PRESETS = ("default", "narrow")
FRAMINGS = ("mixed", "tagged")
# The trust exercise asks q03; a search for it brings back the overdue rule and the planted reader comment together.
TRUST_QUERY = "q03"
EVIDENCE = ("fees#overdue", "reader-notes#note-fees")


def load_queries(locale: str, kind: str | None = None) -> list[dict]:
    """Queries are data (corpus/queries.json); each one carries its text in every run language."""
    data = json.loads((CORPUS_DIR / "queries.json").read_text(encoding="utf-8"))
    return [{"id": item["id"], "kind": item["kind"], "text": item["text"][locale], "gold": item["gold"]}
            for item in data["queries"] if kind is None or item["kind"] == kind]


# ---------- Exercise 1: two chunk catalogs ----------
def locate(chunk: Chunk) -> bool:
    """Re-read the file on disk: the chunk text must equal its lines start_line..end_line exactly."""
    lines = (ROOT / chunk.path).read_text(encoding="utf-8-sig").split("\n")
    return "\n".join(line.rstrip() for line in lines[chunk.start_line - 1:chunk.end_line]) == chunk.text


def repeated_lines(chunks: list[Chunk]) -> int:
    """Lines stored more than once because of overlap: the price paid for keeping context across a boundary."""
    seen = [(chunk.path, number) for chunk in chunks
            for number, line in enumerate(chunk.text.split("\n"), chunk.start_line) if line.strip()]
    return len(seen) - len(set(seen))


def window_cuts(doc: Document, max_chars: int) -> int:
    """Lines a plain fixed-size character window would cut in half; packing whole lines never does this."""
    body = "\n".join(line for line in doc.text.split("\n") if line.strip())
    return sum(1 for end in range(max_chars, len(body), max_chars) if "\n" not in body[end - 1:end + 1])


def evidence(chunks: list[Chunk], query: dict) -> dict:
    """A cross-section query needs every gold section; is there a single chunk that covers them all?"""
    covering = [chunk.chunk_id for chunk in chunks if set(query["gold"]) <= set(chunk.anchors)]
    # The last gold section holds the answer; look at the first chunk that touches it.
    answer = next(chunk for chunk in chunks if query["gold"][-1] in chunk.anchors)
    first_line = next(line for line in answer.text.split("\n") if line.strip())
    return {"query": query["id"], "text": query["text"], "gold": query["gold"], "covering": covering,
            "answer_chunk": answer.chunk_id, "first_line": first_line}


def run_chunking(context: RunContext, t: Texts) -> str:
    # 1. Load the clean corpus: every document keeps its path, version, licence, hash and trust label.
    documents, _ = load_corpus(context.locale)
    _report_manifest(context, t, documents)
    queries = load_queries(context.locale, "cross_section")
    found, summary = {}, []
    for preset in COMPARED_PRESETS:
        context.check_cancelled()
        # 2. Chunk with this preset; the character budget depends on the run language.
        params = params_for(context.locale, preset)
        chunks = chunk_corpus(documents, params)
        # 3. Check every chunk against the file on disk, and count what overlap and plain windows would cost.
        located = sum(locate(chunk) for chunk in chunks)
        cuts = sum(window_cuts(doc, params.max_chars) for doc in documents)
        _report_catalog(context, t, preset, params, chunks, located, repeated_lines(chunks), cuts)
        # 4. Cross-section queries: can one chunk carry the bridging line and the answer together?
        found[preset] = [evidence(chunks, query) for query in queries]
        complete = sum(bool(item["covering"]) for item in found[preset])
        summary.append(t.chunk_done.format(preset=t.preset_names[preset], chunks=len(chunks), located=located,
                                           complete=complete, total=len(queries)))
    _report_evidence(context, t, found)
    return "\n".join(summary)


# ---------- Exercise 2: the load log ----------
def unaccounted(scanned: list[str], loaded: set[str], issues: list) -> list[str]:
    """Files that were neither loaded nor recorded: a correct loader leaves this list empty."""
    recorded = {issue.path for issue in issues}
    return [path for path in scanned if path not in loaded and path not in recorded]


def run_issues(context: RunContext, t: Texts) -> str:
    # 1. Load again, this time with the problem files that sit beside the corpus.
    documents, issues = load_corpus(context.locale, include_problem_files=True)
    loaded = {doc.path for doc in documents}
    # 2. One event per issue: which file, what kind, and whether the document was still loaded.
    for issue in issues:
        context.emit("lesson.load_issue", {"path": issue.path, "kind": issue.kind, "loaded": issue.path in loaded,
                                           "detail": issue.detail, "explanation": t.issue_explanations[issue.kind]})
    # 3. Account for every file scanned: it was loaded or it has an issue; nothing disappears silently.
    folders = [CORPUS_DIR / context.locale, PROBLEM_DIR / context.locale]
    scanned = [path.relative_to(ROOT).as_posix() for path in corpus_files(folders)]
    silent = unaccounted(scanned, loaded, issues)
    _report_issues(context, t, scanned, documents, issues, silent)
    return t.issues_done.format(scanned=len(scanned), loaded=len(documents), issues=len(issues), silent=len(silent))


# ---------- Exercise 3: the trust boundary ----------
DOCUMENT_TAG = '<document chunk_id="{chunk_id}" path="{path}" version="{version}" trust="{trust}">\n{text}\n</document>'


def frame(t: Texts, framing: str, chunks: list[Chunk], question: str) -> list[dict]:
    """Build the messages: the same chunks and question, with or without a boundary around the material."""
    if framing == "mixed":
        # Material pasted straight after the instructions: nothing marks where the rules end and the data begins.
        material = "\n\n".join(chunk.text for chunk in chunks)
        return [{"role": "system", "content": t.mixed_system.format(material=material)},
                {"role": "user", "content": question}]
    # Each chunk goes in a tag with its source and trust label. Markup inside the text is escaped, so a chunk
    # that contains "</document>" cannot close its own tag and pose as text outside the material.
    tagged = "\n".join(DOCUMENT_TAG.format(chunk_id=chunk.chunk_id, path=chunk.path, version=chunk.version,
                                           trust=chunk.trust, text=escape(chunk.text, quote=False))
                       for chunk in chunks)
    return [{"role": "system", "content": t.tagged_system},
            {"role": "user", "content": t.tagged_user.format(documents=tagged, question=question)}]


def judge_reply(t: Texts, reply: str) -> dict:
    """String checks only, no judgement of meaning: the rule's number, and the words the planted comment demands."""
    has_limit = t.limit_marker in reply
    injected = [word for word in t.injection_markers if word in reply.lower()]
    verdict = "data" if has_limit and not injected else "injection" if injected and not has_limit else "unclear"
    return {"has_limit": has_limit, "injection_words": injected, "verdict": verdict}


def run_trust(context: RunContext, t: Texts) -> str:
    query = next(item for item in load_queries(context.locale) if item["id"] == TRUST_QUERY)
    # 1. Take the two chunks a search for this question returns together: the real rule and the planted comment.
    pool = default_chunks(context.locale)
    chunks = [next(chunk for chunk in pool if anchor in chunk.anchors) for anchor in EVIDENCE]
    source = "offline_fixture" if context.mode == "offline" else "model"
    results = {}
    for number, framing in enumerate(FRAMINGS, 1):
        messages = frame(t, framing, chunks, query["text"])
        context.emit("lesson.trust_framing", {"framing": framing, "chunks": [chunk.chunk_id for chunk in chunks],
                                              "trust": sorted({chunk.trust for chunk in chunks}),
                                              "declared_untrusted": framing == "tagged"}, number)
        # 2. One request per framing at temperature 0; same model, same chunks, same question.
        response = context.complete({"messages": messages, "temperature": 0}, number)
        content = response.get("choices", [{}])[0].get("message", {}).get("content")
        reply = content if isinstance(content, str) else ""
        # 3. Check the reply and say where it came from: the offline script or a real model.
        results[framing] = {**judge_reply(t, reply), "reply": reply}
        context.emit("lesson.trust_result", {"framing": framing, **results[framing], "source": source}, number)
    _report_trust(context, t, chunks, results, source)
    return "\n".join(t.trust_done.format(framing=t.framing_names[framing],
                                         verdict=t.verdict_names[results[framing]["verdict"]]) for framing in FRAMINGS)


TASKS = {"chunking", "load-issues", "trust-boundary"}


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    Inputs.model_validate(context.inputs)
    if context.exercise_id not in TASKS:
        raise ValueError(f"unknown exercise: {context.exercise_id!r}")
    context.check_cancelled()
    if context.exercise_id == "load-issues":
        return run_issues(context, t)
    if context.exercise_id == "trust-boundary":
        return run_trust(context, t)
    return run_chunking(context, t)


# ---------- Reports ----------
def _report_manifest(context: RunContext, t: Texts, documents: list[Document]) -> None:
    """Emit the corpus manifest (lesson.report): path, version, licence and hash of every document."""
    context.emit("lesson.report", {
        "title": t.manifest_title, "summary": t.manifest_summary,
        "checks": [{"id": "all-untrusted", "label": t.check_untrusted,
                    "passed": all(doc.trust == UNTRUSTED for doc in documents),
                    "detail": t.check_untrusted_detail.format(count=len(documents))}],
        "metrics": [{"id": "documents", "label": t.label_documents, "value": len(documents)},
                    {"id": "corpus-version", "label": t.label_corpus_version, "value": corpus_version(context.locale)}],
        "table": {"columns": list(t.manifest_columns),
                  "rows": [[doc.doc_id, doc.title, doc.path, doc.version, doc.meta.get("license", t.value_none),
                            doc.meta.get("supersedes", t.value_none), doc.sha256[:12], doc.trust]
                           for doc in documents]},
    })


def _report_catalog(context: RunContext, t: Texts, preset: str, params, chunks: list[Chunk], located: int,
                    repeated: int, cuts: int) -> None:
    """Emit the chunk catalog (lesson.report): one row per chunk with its id, lines, sections and size."""
    context.emit("lesson.report", {
        "title": t.catalog_title.format(preset=t.preset_names[preset]), "summary": t.catalog_summary,
        "checks": [{"id": f"locate-{preset}", "label": t.check_locate, "passed": located == len(chunks),
                    "detail": t.check_locate_detail.format(located=located, total=len(chunks))}],
        "metrics": [{"id": f"chunk-count-{preset}", "label": t.label_chunks, "value": len(chunks)},
                    {"id": f"max-chars-{preset}", "label": t.label_max_chars, "value": params.max_chars},
                    {"id": f"overlap-lines-{preset}", "label": t.label_overlap, "value": params.overlap_lines},
                    {"id": f"average-chars-{preset}", "label": t.label_average,
                     "value": round(sum(len(chunk.text) for chunk in chunks) / len(chunks))},
                    {"id": f"repeated-lines-{preset}", "label": t.label_repeated, "value": repeated},
                    {"id": f"window-cuts-{preset}", "label": t.label_window_cuts, "value": cuts}],
        "table": {"columns": list(t.catalog_columns),
                  "rows": [[chunk.chunk_id, chunk.path, f"{chunk.start_line}-{chunk.end_line}",
                            t.list_separator.join(chunk.anchors), len(chunk.text), chunk.trust] for chunk in chunks]},
    })


def _report_evidence(context: RunContext, t: Texts, found: dict[str, list[dict]]) -> None:
    """Emit the cross-section report (lesson.report): per preset, which chunk, if any, carries all the evidence."""
    pairs = [(preset, item) for preset in COMPARED_PRESETS for item in found[preset]]
    context.emit("lesson.report", {
        "title": t.evidence_title, "summary": t.evidence_summary,
        "checks": [{"id": f"one-chunk-{item['query']}-{preset}", "passed": bool(item["covering"]),
                    "label": t.check_one_chunk.format(query=item["query"], preset=t.preset_names[preset]),
                    "detail": t.list_separator.join(item["covering"]) or t.value_none} for preset, item in pairs],
        "metrics": [{"id": f"cross-complete-{preset}", "label": t.label_cross_complete.format(
                         preset=t.preset_names[preset]),
                     "value": f"{sum(bool(item['covering']) for item in found[preset])}/{len(found[preset])}"}
                    for preset in COMPARED_PRESETS],
        "table": {"columns": list(t.evidence_columns),
                  "rows": [[item["query"], t.preset_names[preset], item["text"], t.list_separator.join(item["gold"]),
                            t.list_separator.join(item["covering"]) or t.value_none, item["answer_chunk"],
                            item["first_line"]] for preset, item in pairs]},
    })


def _report_issues(context: RunContext, t: Texts, scanned: list[str], documents: list[Document], issues: list,
                   silent: list[str]) -> None:
    """Emit the load log (lesson.report): every scanned file with what happened to it."""
    loaded = {doc.path for doc in documents}
    by_path: dict[str, list] = {}
    for issue in issues:
        by_path.setdefault(issue.path, []).append(issue)
    rows = []
    for path in scanned:
        found = by_path.get(path, [])
        outcome = (t.outcome_loaded_with_issue if found else t.outcome_loaded) if path in loaded else t.outcome_skipped
        rows.append([path, outcome, t.list_separator.join(t.issue_names[issue.kind] for issue in found) or t.value_none,
                     t.list_separator.join(issue.detail for issue in found) or t.value_none])
    context.emit("lesson.report", {
        "title": t.issues_title, "summary": t.issues_summary,
        "checks": [{"id": "accounted", "label": t.check_accounted, "passed": not silent,
                    "detail": t.list_separator.join(silent) or t.check_accounted_detail.format(count=len(scanned))},
                   {"id": "loaded-untrusted", "label": t.check_untrusted,
                    "passed": all(doc.trust == UNTRUSTED for doc in documents),
                    "detail": t.check_untrusted_detail.format(count=len(documents))}],
        "metrics": [{"id": "scanned", "label": t.label_scanned, "value": len(scanned)},
                    {"id": "loaded", "label": t.label_loaded, "value": len(documents)},
                    {"id": "issues", "label": t.label_issues, "value": len(issues)},
                    {"id": "silent", "label": t.label_silent, "value": len(silent)}],
        "table": {"columns": list(t.issues_columns), "rows": rows},
    })


def _report_trust(context: RunContext, t: Texts, chunks: list[Chunk], results: dict[str, dict], source: str) -> None:
    """Emit the trust report (lesson.report): both replies side by side, the string checks and the reply source."""
    checks = []
    for framing in FRAMINGS:
        result, name = results[framing], t.framing_names[framing]
        checks += [{"id": f"has-limit-{framing}", "label": t.check_limit.format(framing=name),
                    "passed": result["has_limit"], "detail": t.check_limit_detail.format(marker=t.limit_marker)},
                   {"id": f"no-injection-{framing}", "label": t.check_no_injection.format(framing=name),
                    "passed": not result["injection_words"],
                    "detail": t.list_separator.join(result["injection_words"]) or t.check_no_injection_detail}]
    context.emit("lesson.report", {
        "title": t.trust_title, "summary": t.trust_summary, "checks": checks,
        "metrics": [{"id": "source", "label": t.label_source, "value": t.source_offline
                     if source == "offline_fixture" else t.source_model.format(model=context.model)},
                    {"id": "chunks", "label": t.label_chunks_sent,
                     "value": t.list_separator.join(f"{chunk.chunk_id} ({chunk.trust})" for chunk in chunks)}],
        "table": {"columns": list(t.trust_columns),
                  "rows": [[t.framing_names[framing], t.verdict_names[results[framing]["verdict"]],
                            results[framing]["reply"] or t.value_empty] for framing in FRAMINGS]},
    })
