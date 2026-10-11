"""Context budget and the truncation window: real model comparisons of the full history, a window cut to a budget,
and a cut by count that splits a tool pair.

Lengths are always local JSON character counts, not tokens; tokens are only what the provider reports in usage.
"""
from functools import partial
from typing import Literal
import json

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_07_messages_context.runtime import rejection_status, validate_tool_history
from lessons.lesson_09_context_budget.locales import texts_for
from lessons.lesson_09_context_budget.locales.helpers import texts_for as helper_texts


class Inputs(LessonInputs):
    experiment: Literal["layouts", "broken_pair"] = "layouts"
    source_key: Literal["messages-context", "application-state"] = "messages-context"
    noise_repeats: int = Field(default=8, ge=2, le=25)
    char_budget: int = Field(default=600, ge=400, le=4000)


INPUT_MODEL = Inputs


def lookup_lesson(t, /, source_key: str) -> dict:
    """Local material, keyed by lesson slug; every call really reads one entry. t holds the run's language."""
    if source_key not in t.facts:
        raise ValueError(t.unknown_source.format(source_key=source_key))
    return {"source": source_key, "fact": t.facts[source_key]}


def lookup_tools(locale: str) -> dict:
    """The allowlist for context.call_tool: lookup_lesson with the material of the run's language."""
    return {"lookup_lesson": partial(lookup_lesson, helper_texts(locale))}


# ---------- Three ways to cut ----------

def message_groups(messages: list[dict]) -> list[list[dict]]:
    """Group the messages: a tool message follows its assistant call into the same group."""
    groups: list[list[dict]] = []
    for message in messages:
        if message.get("role") == "tool" and groups:
            groups[-1].append(message)
        else:
            groups.append([message])
    return groups


def fit_window(messages: list[dict], char_budget: int, t) -> list[dict]:
    """Truncation window: keep system and the current question, then fill from the newest messages back until one does not fit."""
    system, *history, question = messages
    # 1. system and the current question must stay; if even they do not fit, fail instead of sending a broken request.
    if message_chars([system, question]) > char_budget:
        raise ValueError(t.budget_too_small.format(budget=char_budget))
    kept: list[dict] = []
    # 2. Fill from the newest group back; a call and its tool result share a group, so they come in or go out together.
    for group in reversed(message_groups(history)):
        if message_chars([system, *group, *kept, question]) > char_budget:
            break  # 3. The window is the contiguous recent history: once a group does not fit, older ones are not tried
        kept = [*group, *kept]
    return [system, *kept, question]


def naive_tail(messages: list[dict], keep: int) -> list[dict]:
    """Cut by count: keep system and the last keep messages, without looking at whether calls and results pair up."""
    return [messages[0], *messages[1:][-keep:]]


def pair_aware_tail(messages: list[dict], keep: int) -> list[dict]:
    """Also cut by count, but when the cut falls inside a pair, keep the assistant call before it as well."""
    tail = messages[1:][-keep:]
    while tail and tail[0].get("role") == "tool" and keep < len(messages) - 1:
        keep += 1
        tail = messages[1:][-keep:]
    return [messages[0], *tail]


# ---------- Layout comparison: full history and truncation window ----------

def lookup_once(context: RunContext, source_key: str) -> dict:
    """The runner (not the model) reads once for real; stop if the result does not match the requested source."""
    result = context.call_tool("lookup_lesson", {"source_key": source_key},
                               lookup_tools(context.locale), call_id="budget_lookup")
    checked_fact(result, source_key, context.locale)
    return result


def build_layouts(t, locale: str, source_key: str, noise_repeats: int, char_budget: int, tool_result: dict,
                  question: str | None = None) -> dict[str, list[dict]]:
    # The tool exchange opens the history and side discussion follows: the window fills from the newest back, so it goes first.
    full = [{"role": "system", "content": t.system_prompt}, {"role": "user", "content": t.goal},
            *tool_pair("budget_lookup", source_key, tool_result), *side_talk(noise_repeats, locale),
            {"role": "user", "content": question or t.default_question}]
    window = fit_window(full, char_budget, t)
    for messages in (full, window):
        validate_tool_history(messages, locale)  # both layouts must pass the protocol check before sending
    return {"full": full, "window": window}


def run_layouts(context: RunContext, t, values: Inputs) -> str:
    # 1. The runner really reads one entry; both layouts use the same tool result.
    result = lookup_once(context, values.source_key)
    question = context.question.strip() or t.default_question
    # 2. Assemble the full history, then cut a window to the character budget.
    layouts = build_layouts(t, context.locale, values.source_key, values.noise_repeats, values.char_budget,
                            result, question)
    full, window = layouts["full"], layouts["window"]
    context.emit("lesson.context_variant", {
        "kind": "window", "char_budget": values.char_budget, "full_messages": len(full),
        "kept_messages": len(window), "dropped_messages": len(full) - len(window),
        "tool_result_kept": any(message.get("role") == "tool" for message in window),
        "detail": t.variant_detail})
    # 3. The same follow-up, one request per layout.
    rows = []
    for index, (code, messages) in enumerate(layouts.items(), 1):
        context.check_cancelled()
        response = context.complete({"messages": messages, "temperature": 0}, round_number=index)
        rows.append({"name": t.layout_names[code], "messages": messages,
                     "answer": answer_text(response, context.locale),
                     "usage": usage_text(response, context.locale),
                     "has_usage": isinstance(response.get("usage"), dict)})
    context.emit("lesson.report", _layout_report(t, values, result["result"], question, rows))
    return t.layouts_answer


def _layout_report(t, values: Inputs, observed: dict, question: str, rows: list[dict]) -> dict:
    window = rows[1]["messages"]
    return {
        "title": t.layouts_title,
        "summary": t.layouts_summary,
        "checks": [
            {"label": t.check_protocol, "passed": True, "detail": t.check_protocol_detail},
            {"label": t.check_in_budget, "passed": message_chars(window) <= values.char_budget,
             "detail": t.check_in_budget_detail.format(budget=values.char_budget, chars=message_chars(window))},
            {"label": t.check_source_kept, "passed": has_text(window, observed["source"]),
             "detail": t.check_source_kept_detail},
        ],
        "metrics": [{"label": t.label_model_calls, "value": len(rows)},
                    {"label": t.label_char_budget, "value": values.char_budget},
                    {"label": t.label_usage_count, "value": sum(row["has_usage"] for row in rows)},
                    {"label": t.label_question, "value": question}],
        "table": {"columns": list(t.layouts_columns),
                  "rows": [[row["name"], len(row["messages"]), message_chars(row["messages"]),
                            message_chars(row["messages"]) <= values.char_budget,
                            has_text(row["messages"], observed["source"]), has_text(row["messages"], observed["fact"]),
                            row["answer"], row["usage"]] for row in rows]},
    }


# ---------- Splitting a pair: cut by count and send as is ----------

def run_broken_pair(context: RunContext, t, values: Inputs) -> str:
    result = lookup_once(context, values.source_key)
    question = context.question.strip() or t.default_question
    # 1. The tool exchange goes last: keeping only the last 2 messages cuts right between the call and its result.
    history = [{"role": "system", "content": t.system_prompt}, {"role": "user", "content": t.goal},
               *side_talk(values.noise_repeats, context.locale), *tool_pair("budget_lookup", values.source_key, result),
               {"role": "user", "content": question}]
    attempts = {"naive": naive_tail(history, 2),
                "pair_aware": pair_aware_tail(history, 2)}
    rows, checks = [], []
    for index, (code, messages) in enumerate(attempts.items(), 1):
        name = t.truncation_names[code]
        context.check_cancelled()
        # 2. Run the local protocol check and record its verdict, but do not block: send as is and see what the provider does.
        try:
            validate_tool_history(messages, context.locale)
            local = t.local_valid
        except ValueError as error:
            local = t.local_rejected.format(error=error)
        checks.append({"id": f"local_{code}", "label": t.check_local.format(name=name), "passed": local == t.local_valid, "detail": local})
        try:
            response = context.complete({"messages": messages, "temperature": 0}, round_number=index)
        except Exception as error:  # 3. Record a provider rejection as it is; no retry, no rewrite
            status = rejection_status(error)
            if status is None:
                raise  # Stop, timeout, rate limit and network failures are not the provider's verdict on these messages
            source = "offline_fixture" if context.mode == "offline" else "provider"
            context.emit("lesson.provider_error", {
                "status": status, "error_type": type(error).__name__, "message": str(error)[:800],
                "source": source, "layout": name}, index)
            rows.append([name, len(messages), local, _refusal(t, status, source), t.no_answer])
            continue
        rows.append([name, len(messages), local, t.accepted, answer_text(response, context.locale)])
    context.emit("lesson.report", _pair_report(context, t, history, checks, rows))
    return _pair_answer(t, rows)


def _refusal(t, status: int, source: str) -> str:
    return (t.refused_offline if source == "offline_fixture" else t.refused).format(status=status)


def _pair_answer(t, rows: list) -> str:
    # A provider may accept both cuts; only point to lesson.provider_error when this run actually recorded one.
    rejected = [row[0] for row in rows if row[3] != t.accepted]
    if not rejected:
        return t.pair_answer_accepted
    return t.pair_answer_rejected.format(names=t.name_separator.join(rejected))


def _pair_report(context: RunContext, t, history: list[dict], checks: list[dict], rows: list) -> dict:
    return {
        "title": t.pair_title,
        "summary": t.pair_summary,
        "checks": checks,
        "metrics": [{"label": t.label_model_calls, "value": len(rows)}, {"label": t.label_history, "value": len(history)},
                    {"label": t.label_mode, "value": t.mode_offline if context.mode == "offline" else t.mode_live}],
        "table": {"columns": list(t.pair_columns), "rows": rows},
    }


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    if values.experiment == "broken_pair":
        return run_broken_pair(context, t, values)
    return run_layouts(context, t, values)


# ---------- Shared helpers: the context-compaction lesson imports them too ----------

def message_chars(messages: list[dict]) -> int:
    """This lesson's unit of length: characters of compact JSON. Only for comparing sizes; not tokens."""
    return len(json.dumps(messages, ensure_ascii=False, separators=(",", ":")))


def has_text(messages: list[dict], text: str) -> bool:
    """Local string check: does this text appear verbatim in the content of some message?"""
    return any(isinstance(message.get("content"), str) and text in message["content"]
               for message in messages)


def answer_text(response: dict, locale: str) -> str:
    """The answer text. When the model wrote no text and proposed tool calls instead, say so: these requests carry no
    tools and the runner does not run the calls."""
    t = helper_texts(locale)
    try:
        message = response["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(t.missing_message) from error
    content = message.get("content")
    if content is not None and not isinstance(content, str):
        raise ValueError(t.content_not_text)
    calls = [call.get("function", {}).get("name", t.unknown_tool) for call in message.get("tool_calls") or []]
    if calls and not (content or "").strip():
        return t.proposed_calls.format(names=t.name_separator.join(calls))
    return content or ""


def usage_text(response: dict, locale: str) -> str:
    """Show the usage the provider reported as it is; when it reported none, say "not reported", never zero."""
    usage = response.get("usage")
    return json.dumps(usage, ensure_ascii=False) if isinstance(usage, dict) else helper_texts(locale).usage_not_reported


def tool_pair(call_id: str, source_key: str, tool_result: dict) -> list[dict]:
    """One tool call and its result: the runner assembles the assistant message; the result comes from a real run."""
    call = {"role": "assistant", "content": None, "tool_calls": [{"id": call_id, "type": "function", "function": {
        "name": "lookup_lesson", "arguments": json.dumps({"source_key": source_key})}}]}
    result = {"role": "tool", "tool_call_id": call_id, "content": json.dumps(tool_result, ensure_ascii=False)}
    return [call, result]


def side_talk(count: int, locale: str, start: int = 1) -> list[dict]:
    """Side discussion: filler turns unrelated to the question; they only make the history longer."""
    t = helper_texts(locale)
    talk = []
    for n in range(start, start + count):
        talk += [{"role": "user", "content": t.side_question.format(n=n)},
                 {"role": "assistant", "content": t.side_reply.format(n=n)}]
    return talk


def checked_fact(tool_result: dict, source_key: str, locale: str) -> str:
    """The tool result must have succeeded and match the requested source; otherwise it is not used to build context."""
    observed = tool_result.get("result")
    if not isinstance(observed, dict) or observed.get("source") != source_key or not isinstance(observed.get("fact"), str):
        raise ValueError(helper_texts(locale).fact_mismatch)
    return observed["fact"]
