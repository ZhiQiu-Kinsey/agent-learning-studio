"""Context compression: rule-based compression, clearing old tool results and a model summary, each checked with the
same probe question about whether the earliest tool result survived.

The character count, the local string check, building tool pairs and side discussion, and the material lookup are
helpers shared with the context-budget lesson.
"""
import json
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_07_messages_context.runtime import validate_tool_history
from lessons.lesson_09_context_budget.runtime import (
    answer_text, checked_fact, has_text, lookup_tools, message_chars, side_talk, tool_pair, usage_text)
from lessons.lesson_context_compaction.locales import texts_for


class Inputs(LessonInputs):
    noise_repeats: int = Field(default=8, ge=2, le=25)
    char_budget: int = Field(default=300, ge=100, le=2000)
    summary_style: Literal["keep_sources", "brief"] = "keep_sources"


INPUT_MODEL = Inputs
SOURCES = ("messages-context", "application-state")  # the two materials, read in this order
# The probe question can only be answered from the earliest tool result: if it is still answerable after
# compression, that information was not lost. Its source counts by key (SOURCES[0]) or by title.


def build_history(noise_repeats: int, results: dict[str, dict], t, locale: str) -> tuple[list[dict], list[dict]]:
    """Two real reads with side discussion between them; returns (older part, recent part), without system or probe."""
    first, second = SOURCES
    for key in SOURCES:
        checked_fact(results[key], key, locale)  # stop on a failed or mismatched read; never compress a wrong result
    older = [{"role": "user", "content": t.goal}, *tool_pair("compaction_lookup_1", first, results[first]),
             *side_talk(noise_repeats, locale)]
    recent = [*tool_pair("compaction_lookup_2", second, results[second]), *side_talk(1, locale, noise_repeats + 1)]
    return older, recent


def rule_record(reads: list[tuple[str, dict]], char_budget: int, t, locale: str) -> dict:
    """Rule-based compression: the program fills fixed fields into one record, no model. reads are the older part's reads in order."""
    sources = t.list_separator.join(t.source_entry.format(number=number, key=key) for number, (key, _) in enumerate(reads, 1))
    facts = t.list_separator.join(checked_fact(result, key, locale) for key, result in reads)  # facts only from real tool results
    record = {"role": "user", "content": t.rule_record.format(sources=sources, facts=facts)}
    # If the key evidence does not fit, fail; never drop a source or a fact quietly.
    if message_chars([record]) > char_budget:
        raise ValueError(t.budget_too_small.format(budget=char_budget, needed=message_chars([record])))
    return record


def clear_old_tool_results(messages: list[dict], t, keep_latest: int = 1) -> list[dict]:
    """Clear old tool results: earlier tool messages stay in place, their content becomes a "cleared" note."""
    tool_indexes = [index for index, message in enumerate(messages) if message.get("role") == "tool"]
    cleared = set(tool_indexes[:-keep_latest] if keep_latest else tool_indexes)
    # Only the content changes, no message is removed: calls and results still pair up, so the protocol check passes.
    note = json.dumps({"cleared": True, "note": t.cleared_note}, ensure_ascii=False)
    return [{**message, "content": note} if index in cleared else message
            for index, message in enumerate(messages)]


def summary_body(older: list[dict], style: str, t, locale: str) -> dict:
    """The extra request of summary compression: the older history as it is, plus one compression instruction."""
    messages = [{"role": "system", "content": t.summary_system}, *older,
                {"role": "user", "content": t.summary_instructions[style]}]
    validate_tool_history(messages, locale)
    return {"messages": messages, "temperature": 0}


def probe_hit(answer: str, t) -> bool:
    """Keyword screen: both the source (key or title) and the exact words must appear; a hit is not proof of meaning."""
    return any(name in answer for name in (SOURCES[0], t.probe_source_title)) and t.probe_phrase in answer


def ask_probe(context: RunContext, t, name: str, messages: list[dict], round_number: int) -> dict:
    """Ask the probe question with one context; "are the exact words in the context" and "did the answer give them" are recorded apart."""
    context.check_cancelled()
    validate_tool_history(messages, context.locale)  # compression must not break the protocol: check every arm before sending
    context.emit("lesson.compaction", {"kind": "layout", "name": name, "messages": len(messages),
                                       "chars": message_chars(messages),
                                       "phrase_in_context": has_text(messages, t.probe_phrase)}, round_number)
    response = context.complete({"messages": messages, "temperature": 0}, round_number=round_number)
    answer = answer_text(response, context.locale)
    return {"name": name, "messages": messages, "answer": answer, "usage": usage_text(response, context.locale)}


def run(context: RunContext) -> str:
    t, locale = texts_for(context.locale), context.locale
    values = Inputs.model_validate(context.inputs)
    names = t.layout_names
    # 1. The runner really reads the two materials in turn and builds the history: "older part + recent part".
    results = {key: context.call_tool("lookup_lesson", {"source_key": key}, lookup_tools(locale),
                                      call_id=f"compaction_lookup_{number}")
               for number, key in enumerate(SOURCES, 1)}
    older, recent = build_history(values.noise_repeats, results, t, locale)
    system, probe = {"role": "system", "content": t.system_prompt}, {"role": "user", "content": t.probe}
    # 2. Control arm: no compression, the whole history. Every compression below replaces only the older part.
    rows = [ask_probe(context, t, names["none"], [system, *older, *recent, probe], 1)]
    # 3. Rule-based compression: the older part becomes one record; if the evidence does not fit, refuse and send nothing.
    try:
        record, refused = rule_record([(SOURCES[0], results[SOURCES[0]])], values.char_budget, t, locale), None
    except ValueError as error:
        record, refused = None, str(error)
    if record:
        rows.append(ask_probe(context, t, names["rule"], [system, record, *recent, probe], 2))
    else:
        context.emit("lesson.compaction", {"kind": "refused", "name": names["rule"], "reason": refused}, 2)
    # 4. Clearing old tool results: the same number of messages; the earlier tool result's content becomes a note.
    rows.append(ask_probe(context, t, names["clear"], clear_old_tool_results([system, *older, *recent, probe], t), 3))
    # 5. Summary compression: one more request to get a summary, which then replaces the older part.
    body = summary_body(older, values.summary_style, t, locale)
    context.emit("lesson.compaction", {"kind": "summary_request", "style": values.summary_style,
                                       "messages": len(body["messages"]),
                                       "instruction": body["messages"][-1]["content"]}, 4)
    summary_response = context.complete(body, round_number=4)
    summary = {"role": "user", "content": t.summary_prefix + answer_text(summary_response, locale)}
    rows.append(ask_probe(context, t, names["summary"], [system, summary, *recent, probe], 5))
    context.emit("lesson.report", _report(context, t, values, rows, refused, summary_response))
    return t.final_answer


def _report(context: RunContext, t, values: Inputs, rows: list[dict], refused: str | None,
            summary_response: dict) -> dict:
    checks = [{"label": t.check_protocol, "passed": True, "detail": t.check_protocol_detail},
              {"id": "rule_fits", "label": t.check_rule_fits, "passed": refused is None,
               "detail": refused or t.check_rule_fits_detail.format(budget=values.char_budget)}]
    checks += [{"label": t.check_probe.format(name=row["name"]), "passed": probe_hit(row["answer"], t),
                "detail": t.probe_both if probe_hit(row["answer"], t) else t.probe_missing}
               for row in rows]
    return {
        "title": t.report_title,
        "summary": t.report_summary,
        "checks": checks,
        "metrics": [{"id": "model_calls", "label": t.label_model_calls, "value": len(rows) + 1},
                    {"label": t.label_summary_usage, "value": usage_text(summary_response, context.locale)},
                    {"label": t.label_summary_style, "value": values.summary_style},
                    {"label": t.label_summary_text, "value": answer_text(summary_response, context.locale)},
                    {"label": t.label_probe, "value": t.probe},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.columns),
                  "rows": [[row["name"], len(row["messages"]), message_chars(row["messages"]),
                            has_text(row["messages"], t.probe_phrase), row["answer"],
                            t.hit if probe_hit(row["answer"], t) else t.miss, row["usage"]] for row in rows]},
    }
