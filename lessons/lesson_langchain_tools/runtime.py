"""Plug business contracts into LangChain components, then check that errors and evidence keep their meaning.

The framework looks the facts up (bind_tools + a decorated tool) and parses the task card
(with_structured_output). The program still decides: a tool failure stays ok=false, a
card the framework could not parse is a failure, and a parsed card must pass the business
check. Every model call goes through RunContext, so the provider's raw response sits in
the same run next to what the framework made of it.
"""
import json
import re
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from course.execution import LessonInputs, RunContext
from course.frameworks import RunContextChatModel, execute_tool_calls, local_tracing_only, tools_as_callables
from lessons.lesson_langchain_tools.components import (
    TARGET_LESSON,
    business_checks,
    card_schema,
    differing_paths,
    handwritten_definition,
    make_lookup_tool,
)
from lessons.lesson_langchain_tools.locales import texts_for

# Model calls allowed for the lookup; a second one lets the model correct a failed call.
LOOKUP_LIMIT = 2
# Extra structured attempts after a failed one: one repair, never an open-ended retry loop.
REPAIR_LIMIT = 1


class Inputs(LessonInputs):
    scenario: Literal["normal", "missing_field", "wrong_fact", "tool_error"] = "normal"
    repair: bool = True


INPUT_MODEL = Inputs


def look_up_facts(context: RunContext, model, lookup, history: list, log: dict) -> dict | None:
    """Let the model call the lookup tool until it gets the target lesson's facts, at most LOOKUP_LIMIT calls."""
    bound = model.bind_tools([lookup], tool_choice="auto")
    allowed = tools_as_callables([lookup])  # ToolException -> ok=false, not a crashed run
    for _ in range(LOOKUP_LIMIT):
        context.check_cancelled()
        # 1. The framework call: AIMessage.tool_calls holds parsed arguments, not the raw string.
        proposal = bound.invoke(history)
        history.append(proposal)
        log["lookup"].append(proposal)
        if not (proposal.tool_calls or proposal.invalid_tool_calls):
            return None  # the model answered without looking anything up
        # 2. Every call runs through RunContext; each ToolMessage carries ok, error_type and error.
        replies = execute_tool_calls(context, proposal, allowed)
        history.extend(replies)
        results = [json.loads(reply.content) for reply in replies]
        log["tool_results"].extend(results)
        # 3. Only a successful result for the target lesson counts as facts.
        for result in results:
            if result.get("ok") and result["result"].get("lesson_id") == TARGET_LESSON:
                return result["result"]
    return None


def generate_card(context: RunContext, model, schema, history: list, log: dict):
    """Ask for the card with with_structured_output, check it, and repair at most REPAIR_LIMIT times."""
    t = texts_for(context.locale)
    structured = model.with_structured_output(schema, include_raw=True)
    limit = 1 + (REPAIR_LIMIT if context.inputs["repair"] else 0)
    card, checks = None, []
    for attempt in range(1, limit + 1):
        context.check_cancelled()
        # 1. raw is the AIMessage, parsed the TaskCard or None, parsing_error the exception if one was raised.
        output = structured.invoke(history)
        raw, card, error = output["raw"], output["parsed"], output["parsing_error"]
        log["structured"].append(raw)
        outcome = classify(raw, card, error)
        # 2. Explicit fallback: the provider ignored the forced tool call and wrote text instead.
        if outcome == "no_structured_call" and _text(raw):
            card, error = parse_text_fallback(_text(raw), schema)
            outcome = "text_fallback" if card is not None else "text_fallback_failed"
            log["fallback"] = True
        # 3. The program's checks: parsing first, then the business rule on whatever was parsed.
        checks = [parse_check(outcome, error, t)] + business_checks(card, context.locale)
        reasons = [item["detail"] for item in checks if item.get("passed") is False]
        accepted = not reasons
        _report_attempt(context, attempt, raw, card, outcome, checks, _calls_so_far(log))
        if accepted or attempt == limit:
            return (card if accepted else None), checks, attempt
        # 4. Turn the failure into a message the model can act on, then try once more.
        history.extend([raw, *feedback_messages(raw, outcome, reasons, t)])
    return None, checks, limit


def classify(raw: AIMessage, card, error) -> str:
    """Name what with_structured_output did; two of these failures come back with no exception at all."""
    if card is not None:
        return "parsed"
    if error is not None:
        return "schema_error"  # raised by Pydantic, reported in parsing_error
    if raw.invalid_tool_calls:
        return "invalid_arguments"  # arguments were not a JSON object: parsed and parsing_error are both None
    return "no_structured_call"  # no tool call at all: parsed and parsing_error are both None


def parse_text_fallback(text: str, schema):
    """Validate a JSON object written as text with the same schema; it is a fallback, so it is labelled as one."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        return schema.model_validate_json(match.group(0) if match else text), None
    except ValidationError as error:
        return None, error


def parse_check(outcome: str, error, t) -> dict:
    passed = outcome in ("parsed", "text_fallback")
    detail = t.outcomes[outcome]
    if isinstance(error, ValidationError):
        # Field paths and error types only: they read the same in every run language.
        detail += " " + "; ".join(".".join(map(str, item["loc"])) + ": " + item["type"] for item in error.errors())
    elif error is not None:
        detail += " " + type(error).__name__
    return {"id": "framework_parse", "label": t.check_parse, "passed": passed, "detail": detail[:300]}


def feedback_messages(raw: AIMessage, outcome: str, reasons: list[str], t) -> list:
    """Answer every call in the failed message: an assistant tool call without a tool message makes the next request invalid.

    These are messages the runner writes, not tool results: no tool ran, so no
    tool_call / tool_result events are recorded for them.
    """
    kind = "business_rule" if outcome in ("parsed", "text_fallback") else "schema_validation"
    payload = json.dumps({"ok": False, "error_type": kind, "error": t.reason_separator.join(reasons),
                          "next": t.repair_instruction}, ensure_ascii=False)
    ids = [call["id"] for call in raw.tool_calls] + [call.get("id") for call in raw.invalid_tool_calls]
    if ids:
        return [ToolMessage(content=payload, tool_call_id=call_id, status="error") for call_id in ids]
    return [HumanMessage(payload)]


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    scenario = context.inputs["scenario"]
    lookup = make_lookup_tool(context.locale)
    schema = card_schema(context.locale)
    _report_definitions(context, lookup, schema)
    model = RunContextChatModel(context=context, temperature=0)
    history = [SystemMessage(t.system_prompt),
               HumanMessage(t.user_prompt.format(lesson_id=TARGET_LESSON) + t.injections.get(scenario, ""))]
    log = {"lookup": [], "structured": [], "tool_results": [], "fallback": False}
    card, checks, attempts = None, [], 0
    # LangSmith stays off: framework inputs never leave this machine.
    with local_tracing_only():
        facts = look_up_facts(context, model, lookup, history, log)
        # No facts, no card: a failed lookup is not silently replaced by what the model remembers.
        if facts is not None:
            card, checks, attempts = generate_card(context, model, schema, history, log)
    _report_capabilities(context, log)
    stop = ("no_facts" if facts is None else "accepted" if card is not None
            else "repair_used_up" if context.inputs["repair"] else "repair_off")
    _report_final(context, facts, checks, attempts, log, stop)
    if card is not None:
        return t.answer_passed.format(card=card.model_dump_json())
    return t.answer_no_facts if facts is None else t.answer_failed


# ---------------------------------------------------------------------------
# Reports (lesson.report): assembled here so the flow above stays readable
# ---------------------------------------------------------------------------

def _calls_so_far(log: dict) -> int:
    # Reports sit on the round of the latest model call (the adapter numbers calls per run).
    return max(1, len(log["lookup"]) + len(log["structured"]))


def _text(message: AIMessage) -> str:
    return message.content if isinstance(message.content, str) else ""


def _source(context: RunContext, t) -> str:
    # Offline runs answer from the lesson's test fixture, never from a provider.
    return t.source_fixture if context.mode == "offline" else t.source_provider


def _report_definitions(context: RunContext, lookup, schema) -> None:
    t = texts_for(context.locale)
    generated = convert_to_openai_tool(lookup)
    paths = differing_paths(generated, handwritten_definition(context.locale))
    card_definition = convert_to_openai_tool(schema)["function"]
    business_doc = convert_to_openai_tool(schema.__mro__[1])["function"].get("description", "")
    context.emit("lesson.report", {
        "title": t.definitions_title, "summary": t.definitions_summary,
        "checks": [{"id": "definition_match", "label": t.check_definition_match, "passed": not paths,
                    "detail": t.detail_same if not paths else ", ".join(paths)}],
        "metrics": [{"id": "generated_parameters", "label": t.label_generated_parameters,
                     "value": json.dumps(generated["function"]["parameters"], ensure_ascii=False)},
                    {"id": "card_required", "label": t.label_card_required,
                     "value": ", ".join(card_definition["parameters"]["required"])},
                    {"id": "card_extra", "label": t.label_card_extra,
                     "value": str(card_definition["parameters"].get("additionalProperties"))},
                    {"id": "business_description", "label": t.label_business_description,
                     "value": business_doc or t.value_empty}],
    })


def _report_attempt(context: RunContext, attempt: int, raw: AIMessage, card, outcome: str, checks: list,
                    round_number: int) -> None:
    t = texts_for(context.locale)
    calls = raw.tool_calls or raw.invalid_tool_calls
    shown_args = (json.dumps(calls[0]["args"], ensure_ascii=False) if calls and isinstance(calls[0]["args"], dict)
                  else calls[0]["args"] if calls else t.value_none)
    context.emit("lesson.report", {
        "title": t.attempt_title.format(attempt=attempt), "summary": t.outcomes[outcome],
        "checks": checks,
        "metrics": [{"id": f"outcome_{attempt}", "label": t.label_outcome, "value": outcome},
                    {"label": t.label_source, "value": _source(context, t)}],
        "table": {"columns": list(t.layer_columns), "rows": [
            [t.layer_raw, t.layer_raw_where],
            [t.layer_framework, shown_args],
            [t.layer_parsed, card.model_dump_json() if card is not None else t.value_none],
            [t.layer_business, next((item["detail"] for item in checks if item["id"] == "business_facts"), "")],
        ]},
    }, round_number)


def _report_capabilities(context: RunContext, log: dict) -> None:
    t = texts_for(context.locale)
    seen = t.status_fixture if context.mode == "offline" else t.status_observed
    messages = log["lookup"] + log["structured"]
    lookup_calls = sum(1 for message in log["lookup"] if message.tool_calls or message.invalid_tool_calls)
    forced = sum(1 for message in log["structured"] if message.tool_calls or message.invalid_tool_calls)
    synthesized = sum(1 for message in messages for call in message.tool_calls + message.invalid_tool_calls
                      if str(call.get("id") or "").startswith("framework_call_"))
    reported = sum(1 for message in messages if message.usage_metadata is not None)
    parallel = sum(1 for message in messages if len(message.tool_calls) + len(message.invalid_tool_calls) > 1)
    rows = [
        [t.cap_tool_auto, t.evidence_count.format(count=lookup_calls, total=len(log["lookup"])),
         seen if lookup_calls else t.status_unverified],
        [t.cap_forced_tool, t.evidence_count.format(count=forced, total=len(log["structured"])),
         t.status_fallback if log["fallback"] else seen if forced else t.status_unverified],
        [t.cap_call_ids, t.evidence_synthesized.format(count=synthesized),
         t.status_fallback if synthesized else seen if messages else t.status_unverified],
        [t.cap_usage, t.evidence_usage.format(count=reported, total=len(messages)) if reported else t.value_not_reported,
         seen if messages else t.status_unverified],
        [t.cap_parallel, t.evidence_parallel.format(count=parallel, total=len(messages)),
         seen if parallel else t.status_unverified],
        [t.cap_strict, t.evidence_not_sent, t.status_unverified],
        [t.cap_json_schema, t.evidence_not_sent, t.status_unverified],
    ]
    context.emit("lesson.report", {
        "title": t.capabilities_title, "summary": t.capabilities_summary,
        "metrics": [{"id": "capability_source", "label": t.label_source, "value": _source(context, t)},
                    {"id": "cap_forced_tool", "label": t.cap_forced_tool, "value": rows[1][2]},
                    {"id": "cap_json_schema", "label": t.cap_json_schema, "value": rows[6][2]}],
        "table": {"columns": list(t.capability_columns), "rows": rows},
    }, _calls_so_far(log))


def _report_final(context: RunContext, facts, checks: list, attempts: int, log: dict, stop: str) -> None:
    t = texts_for(context.locale)
    failures = sum(1 for result in log["tool_results"] if not result.get("ok"))
    final_checks = [{"id": "facts_found", "label": t.check_facts, "passed": facts is not None,
                     "detail": t.detail_facts_found if facts is not None else t.detail_facts_missing}]
    context.emit("lesson.report", {
        "title": t.final_title, "summary": t.stop_reasons[stop],
        "checks": final_checks + checks,
        "metrics": [{"id": "model_calls", "label": t.label_model_calls,
                     "value": len(log["lookup"]) + len(log["structured"])},
                    {"id": "tool_failures", "label": t.label_tool_failures, "value": failures},
                    {"id": "structured_attempts", "label": t.label_attempts, "value": attempts},
                    {"id": "stop_reason", "label": t.label_stop_reason, "value": stop},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
    }, _calls_so_far(log))
