"""Agentic RAG with a bounded loop, next to a static baseline: the same question, the same search tool, counted calls.

The loop (search as a tool, the model decides what to look up next, one forced final answer once the search
budget is spent) follows agent.py and campaign.py in ai-agent-book chapter3/agentic-rag (Apache-2.0). Here every
limit is checked before a request, the attempt log is fed back to the model each round, and a program checks the
citations against this run's results and the human-labelled sections of the shared query set.
Every text that reaches the model or an event is in locales/, one catalog per run language.
"""
import json
import time
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_agentic_rag.locales import Texts, texts_for
from lessons.lesson_agentic_rag.search_tool import Handbook, cited_in_results, tool_definition
from lessons.lesson_keyword_retrieval.query_set import Query, judge, load_queries

STATUSES = ("answered", "partial", "insufficient")
# Tests replace the clock to reach the time limit without waiting.
clock = time.monotonic


class Inputs(LessonInputs):
    mode: Literal["static", "agentic"] = "agentic"
    # Multi-hop (q11, q12), synonym (q04), exact (q01) and no-answer (q07, q08) questions of the shared query set.
    question_id: Literal["q11", "q12", "q04", "q01", "q07", "q08"] = "q11"
    max_searches: int = Field(default=4, ge=1, le=6)
    max_model_calls: int = Field(default=5, ge=2, le=8)
    time_budget_s: int = Field(default=60, ge=5, le=300)
    top_k: int = Field(default=3, ge=1, le=5)


INPUT_MODEL = Inputs


class Ledger:
    """Every model call of the run, with the total_tokens the provider reported; None when not reported, never estimated.

    It also keeps the round of each search and how many tool calls were refused, for the report.
    """

    def __init__(self, context: RunContext):
        self.context = context
        self.tokens: list[int | None] = []
        self.search_rounds: dict[int, int] = {}
        self.refused = 0

    def complete(self, body: dict, round_number: int) -> dict:
        response = self.context.complete(body, round_number)
        usage = response.get("usage")
        total = usage.get("total_tokens") if isinstance(usage, dict) else None
        self.tokens.append(total if type(total) is int else None)
        return response

    @property
    def calls(self) -> int:
        return len(self.tokens)


def parse_final(content) -> dict:
    """Read the final JSON answer; anything that is not the agreed shape is status invalid, nothing is repaired."""
    text = content if isinstance(content, str) else ""
    try:
        value, _ = json.JSONDecoder().raw_decode(text[text.index("{"):])
    except ValueError:
        value = None
    valid = (isinstance(value, dict) and value.get("status") in STATUSES and isinstance(value.get("answer"), str)
             and isinstance(value.get("citations"), list) and all(isinstance(c, str) for c in value["citations"]))
    if not valid:
        return {"status": "invalid", "answer": text, "citations": [], "missing": ""}
    missing = value.get("missing")
    return {"status": value["status"], "answer": value["answer"], "citations": list(dict.fromkeys(value["citations"])),
            "missing": missing if isinstance(missing, str) else ""}


def stop_reason(values: Inputs, handbook: Handbook, ledger: Ledger, started: float) -> str | None:
    """The limits, checked before every request; the last model call is kept for the final answer."""
    if clock() - started >= values.time_budget_s:
        return "time_limit"
    if len(handbook.attempts) >= values.max_searches:
        return "search_limit"
    if ledger.calls >= values.max_model_calls - 1:
        return "call_limit"
    return None


def progress_note(context: RunContext, t: Texts, handbook: Handbook, ledger: Ledger, values: Inputs,
                  round_number: int) -> str:
    """The note the runner appends after a round of searches: the whole attempt log, with every repeat named."""
    lines = [t.progress_header.format(searches=len(handbook.attempts), max_searches=values.max_searches,
                                      calls=ledger.calls, max_calls=values.max_model_calls)]
    for attempt in handbook.attempts:
        lines.append(t.attempt_line.format(n=attempt.n, query=attempt.query, returned=len(attempt.returned),
                                           new=len(attempt.new), ids=t.id_separator.join(attempt.new) or t.value_none))
    repeats = [a for a in handbook.attempts if a.duplicate_of is not None]
    lines += [t.duplicate_line.format(n=a.n, first=a.duplicate_of) for a in repeats]
    lines.append(t.progress_footer)
    note = "\n".join(lines)
    context.emit("lesson.harness_injected", {"kind": "retrieval_progress", "source": "harness", "text": note,
                                             "searches_used": len(handbook.attempts),
                                             **({"repeats": [a.n for a in repeats]} if repeats else {})}, round_number)
    return note


def run_agentic(context: RunContext, t: Texts, values: Inputs, query: Query, handbook: Handbook,
                ledger: Ledger, started: float) -> tuple[dict | None, str]:
    """The model decides whether to search again or answer; the runner enforces every limit."""
    tools = {"search_handbook": handbook.search}
    messages = [{"role": "system", "content": t.agentic_system}, {"role": "user", "content": query.text}]
    round_number = 0
    while True:
        context.check_cancelled()
        # 1. Limits first: time, searches, model calls. Any one of them ends the loop.
        stop = stop_reason(values, handbook, ledger, started)
        if stop:
            break
        round_number += 1
        # 2. One request with the tool: the model either proposes searches or answers.
        response = ledger.complete({"messages": messages, "tools": [tool_definition(t)], "tool_choice": "auto",
                                    "temperature": 0}, round_number)
        message = response["choices"][0].get("message") or {}
        calls = message.get("tool_calls") or []
        if not calls:
            _emit_stop(context, t, "answered", handbook, ledger, round_number)
            return parse_final(message.get("content")), "answered"
        # 3. Every proposal runs through RunContext: real BM25, recorded as tool_call and tool_result.
        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": calls})
        for call in calls:
            before = len(handbook.attempts)
            result = context.execute_proposal(call, tools)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)})
            ledger.refused += not result["ok"]
            if len(handbook.attempts) > before:
                _emit_attempt(context, handbook, ledger, query, round_number)
        # 4. Feed the attempt log back, unless a limit was just reached (the final instruction says so instead).
        if stop_reason(values, handbook, ledger, started) is None:
            messages.append({"role": "user", "content": progress_note(context, t, handbook, ledger, values, round_number)})
    # 5. A limit ended the loop: record why; unless time ran out, one last request that may not search.
    _emit_stop(context, t, stop, handbook, ledger, round_number)
    if stop == "time_limit":
        return None, stop
    messages.append({"role": "user", "content": t.final_instruction.format(reason=t.stop_reasons[stop])})
    response = ledger.complete({"messages": messages, "tools": [tool_definition(t)], "tool_choice": "none",
                                "temperature": 0}, round_number + 1)
    return parse_final((response["choices"][0].get("message") or {}).get("content")), stop


def run_static(context: RunContext, t: Texts, values: Inputs, query: Query, handbook: Handbook,
               ledger: Ledger) -> tuple[dict, str]:
    """The baseline: the runner searches once with the question as written, the model answers once."""
    # 1. One search made by the runner, not the model; it is recorded as a runner-initiated call.
    result = context.call_tool("search_handbook", {"query": query.text, "top_k": values.top_k},
                               {"search_handbook": handbook.search})
    ledger.refused += not result["ok"]
    if handbook.attempts:
        _emit_attempt(context, handbook, ledger, query, 1)
    results = result["result"]["results"] if result.get("ok") else []
    # 2. One request with whatever came back; the model has no way to search again.
    user = t.static_request.format(question=query.text, results=json.dumps(results, ensure_ascii=False, indent=1))
    response = ledger.complete({"messages": [{"role": "system", "content": t.static_system},
                                             {"role": "user", "content": user}], "temperature": 0}, 1)
    _emit_stop(context, t, "static", handbook, ledger, 1)
    return parse_final((response["choices"][0].get("message") or {}).get("content")), "static"


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    query = next(item for item in load_queries(context.locale) if item.id == values.question_id)
    handbook = Handbook(t, context.locale, max_searches=1 if values.mode == "static" else values.max_searches,
                        default_top_k=values.top_k)
    ledger, started = Ledger(context), clock()
    if values.mode == "static":
        final, stop = run_static(context, t, values, query, handbook, ledger)
    else:
        final, stop = run_agentic(context, t, values, query, handbook, ledger, started)
    return _report(context, t, values, query, handbook, ledger, final, stop, clock() - started)


def _emit_attempt(context: RunContext, handbook: Handbook, ledger: Ledger, query: Query, round_number: int):
    """lesson.attempt: one search that ran. Gold coverage is for the learner only and never reaches the model."""
    attempt = handbook.attempts[-1]
    ledger.search_rounds[attempt.n] = round_number
    covered = judge([handbook.chunks[c] for c in handbook.seen], query)["matched"] if query.gold else []
    repeat = {} if attempt.duplicate_of is None else {"duplicate_of": attempt.duplicate_of}
    context.emit("lesson.attempt", {"n": attempt.n, "query": attempt.query, "terms": list(attempt.terms),
                                    "top_k": attempt.top_k, "returned": list(attempt.returned), "new": list(attempt.new),
                                    "gold_covered": covered, **repeat}, round_number)


def _emit_stop(context: RunContext, t: Texts, stop: str, handbook: Handbook, ledger: Ledger, round_number: int):
    context.emit("lesson.stop", {"reason": stop, "label": t.stop_reasons[stop], "searches_used": len(handbook.attempts),
                                 "model_calls": ledger.calls}, max(round_number, 1))


def _tokens(t: Texts, ledger: Ledger):
    reported = [value for value in ledger.tokens if value is not None]
    missing = len(ledger.tokens) - len(reported)
    if not reported:
        return t.value_not_reported
    return sum(reported) if not missing else t.tokens_partly_reported.format(total=sum(reported), missing=missing)


def _checks(t: Texts, query: Query, handbook: Handbook, final: dict | None, calls: int, limits: tuple[int, int]) -> list:
    """Only checks that really ran are listed: citation checks need a final answer, gold checks need labels."""
    checks = []
    if final is not None:
        known, unknown = cited_in_results(final["citations"], handbook)
        checks.append({"id": "citations_from_results", "label": t.check_from_results, "passed": not unknown,
                       "detail": t.check_from_results_detail.format(cited=len(final["citations"]),
                                                                     unknown=t.id_separator.join(unknown) or t.value_none)})
        if query.gold:
            cover = judge([handbook.chunks[c] for c in known], query)
            checks.append({"id": "citations_cover_gold", "label": t.check_cover_gold,
                           "passed": bool(cover["complete"]) and not unknown,
                           "detail": t.check_cover_detail.format(matched=t.id_separator.join(cover["matched"]) or t.value_none,
                                                                 missing=t.id_separator.join(cover["missing"]) or t.value_none)})
        else:
            checks.append({"id": "declined", "label": t.check_declined,
                           "passed": final["status"] == "insufficient" and not final["citations"],
                           "detail": t.check_declined_detail.format(status=t.answer_statuses[final["status"]],
                                                                    cited=len(final["citations"]))})
    if query.gold:
        evidence = judge([handbook.chunks[c] for c in handbook.seen], query)
        checks.append({"id": "evidence_cover_gold", "label": t.check_evidence, "passed": bool(evidence["complete"]),
                       "detail": t.check_cover_detail.format(matched=t.id_separator.join(evidence["matched"]) or t.value_none,
                                                             missing=t.id_separator.join(evidence["missing"]) or t.value_none)})
    checks.append({"id": "within_limits", "label": t.check_within_limits,
                   "passed": len(handbook.attempts) <= limits[0] and calls <= limits[1],
                   "detail": t.check_within_detail.format(searches=len(handbook.attempts), max_searches=limits[0],
                                                          calls=calls, max_calls=limits[1])})
    return checks


def _report(context: RunContext, t: Texts, values: Inputs, query: Query, handbook: Handbook, ledger: Ledger,
            final: dict | None, stop: str, elapsed: float) -> str:
    """Emit the lab report (lesson.report) and return the final answer text."""
    limits = (1, 1) if values.mode == "static" else (values.max_searches, values.max_model_calls)
    status = final["status"] if final else "unfinished"
    seen_so_far, rows = set(), []
    for attempt in handbook.attempts:
        seen_so_far |= set(attempt.returned)
        covered = judge([handbook.chunks[c] for c in seen_so_far], query)["matched"] if query.gold else []
        rows.append([attempt.n, ledger.search_rounds.get(attempt.n, 1), attempt.query,
                     t.id_separator.join(attempt.returned) or t.value_none, t.id_separator.join(attempt.new) or t.value_none,
                     t.duplicate_cell.format(n=attempt.duplicate_of) if attempt.duplicate_of else "—",
                     t.id_separator.join(covered) or "—"])
    context.emit("lesson.report", {
        "title": t.report_titles[values.mode],
        "summary": t.report_summary,
        "checks": _checks(t, query, handbook, final, ledger.calls, limits),
        "metrics": [
            {"id": "question", "label": t.label_question, "value": f"{query.id} · {query.text}"},
            {"id": "stop_reason", "label": t.label_stop_reason, "value": t.stop_reasons[stop]},
            {"id": "answer_status", "label": t.label_answer_status, "value": t.answer_statuses[status]},
            {"id": "searches", "label": t.label_searches.format(limit=limits[0]), "value": len(handbook.attempts)},
            {"id": "model_calls", "label": t.label_model_calls.format(limit=limits[1]), "value": ledger.calls},
            {"id": "repeats", "label": t.label_duplicates,
             "value": sum(1 for a in handbook.attempts if a.duplicate_of is not None)},
            {"id": "refused", "label": t.label_rejected, "value": ledger.refused},
            {"id": "total_tokens", "label": t.label_total_tokens, "value": _tokens(t, ledger)},
            {"id": "elapsed", "label": t.label_elapsed.format(limit=values.time_budget_s), "value": round(elapsed, 2)},
            {"label": t.label_note, "value": context.question or t.value_empty},
        ],
        "table": {"columns": list(t.columns), "rows": rows},
    })
    if final is None:
        return t.unfinished_answer.format(stop=t.stop_reasons[stop], searches=len(handbook.attempts),
                                          ids=t.id_separator.join(handbook.seen) or t.value_none)
    return t.final_answer.format(answer=final["answer"], status=t.answer_statuses[status],
                                 citations=t.id_separator.join(final["citations"]) or t.value_none,
                                 missing=final["missing"] or t.value_none, stop=t.stop_reasons[stop])
