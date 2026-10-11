"""Which parts make up the context of one request: remove one part at a time and see which part the answer depends on.

The full context is five messages: system prompt, earlier conversation, tool call, tool result, this turn's question.
The tool result comes from a real run of lookup_score; the runner writes the assistant message with tool_calls, the model does not.
"""
import json
from functools import partial
from typing import Literal

from course.execution import LessonInputs, RunContext
from lessons.lesson_07_messages_context.locales import texts_for
from lessons.lesson_07_messages_context.locales.protocol import texts_for as protocol_texts


class Inputs(LessonInputs):
    student_id: Literal["s-1042", "s-2077"] = "s-1042"
    free_day: Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"] = "thu"


INPUT_MODEL = Inputs
# Local score table: the scores follow no pattern, so the model cannot guess them. An answer
# that contains the score shows it used the tool result.
SCORES = {
    "s-1042": {"student_id": "s-1042", "score": 73, "pass_line": 60},
    "s-2077": {"student_id": "s-2077", "score": 58, "pass_line": 60},
}
CALL_ID = "lookup_score_1"


def lookup_score(t, /, student_id: str) -> dict:
    """The only tool of this lesson: the latest exercise score of a student. t holds the run's error text."""
    if student_id not in SCORES:
        raise ValueError(t.unknown_student.format(student_id=student_id))
    return SCORES[student_id]


ORDER = ("system", "conversation", "tool_call", "tool_result", "question")
# Each variant removes one part. A tool call and its result go together; the last variant removes only the result on purpose.
VARIANTS = {
    "full": (),
    "no_system": ("system",),
    "no_conversation": ("conversation",),
    "no_tool_pair": ("tool_call", "tool_result"),
    "no_tool_result": ("tool_result",),
}


def build_parts(t, values: Inputs, tool_result: dict) -> dict[str, dict]:
    """The five messages of the full context; joined in ORDER they are the messages of one request."""
    call = {"id": CALL_ID, "type": "function", "function": {
        "name": "lookup_score", "arguments": json.dumps({"student_id": values.student_id})}}
    return {
        "system": {"role": "system", "content": t.system_prompt},
        # The review day appears only in this earlier message.
        "conversation": {"role": "user", "content": t.conversation.format(
            day=t.weekdays[values.free_day], student_id=values.student_id)},
        # The runner writes this call; its id is the CALL_ID of the real execution.
        "tool_call": {"role": "assistant", "content": None, "tool_calls": [call]},
        # The score appears only in this tool result: what this run really returned.
        "tool_result": {"role": "tool", "tool_call_id": CALL_ID,
                        "content": json.dumps(tool_result, ensure_ascii=False)},
        "question": {"role": "user", "content": t.question},
    }


def assemble(parts: dict[str, dict], removed: tuple[str, ...]) -> list[dict]:
    """Join the messages in a fixed order, skipping only the removed parts; the others stay word for word."""
    return [parts[key] for key in ORDER if key not in removed]


def validate_tool_history(messages: list[dict], locale: str) -> None:
    """Protocol check: every tool call is followed by a tool message with the same id; otherwise ValueError."""
    t = protocol_texts(locale)
    outstanding: set[str] = set()  # ids of calls that were proposed and still wait for a result
    seen: set[str] = set()
    for message in messages:
        role = message.get("role")
        # While a call waits for its result, the next message can only be a tool message.
        if outstanding and role != "tool":
            raise ValueError(t.result_expected)
        if role == "assistant":
            for call in message.get("tool_calls", []):
                call_id = call.get("id")
                # The id is the only thing that pairs call and result, so it must be non-empty and unique.
                if not isinstance(call_id, str) or not call_id or call_id in seen:
                    raise ValueError(t.bad_call_id)
                outstanding.add(call_id)
                seen.add(call_id)
        elif role == "tool":
            call_id = message.get("tool_call_id")
            # A tool result can only answer a call that is still waiting.
            if call_id not in outstanding:
                raise ValueError(t.orphan_result)
            outstanding.remove(call_id)
        elif role not in {"system", "user"}:
            raise ValueError(t.unknown_role)
    # A call still without a result when the history ends is just as invalid.
    if outstanding:
        raise ValueError(t.result_missing)


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    # 1. Run the tool once for real. The runner makes this call; the model did not propose it.
    result = context.call_tool("lookup_score", {"student_id": values.student_id},
                               {"lookup_score": partial(lookup_score, t)}, call_id=CALL_ID)
    if not result.get("ok"):
        raise RuntimeError(t.lookup_failed)
    parts = build_parts(t, values, result)
    _describe(context, t, parts)
    rows, sent = [], 0
    for code, removed in VARIANTS.items():
        name = t.variant_names[code]
        # 2. Build this variant's context: the full context minus the parts in removed.
        messages = assemble(parts, removed)
        # 3. Check the protocol before sending; if it fails, send nothing and record why.
        try:
            validate_tool_history(messages, context.locale)
        except ValueError as error:
            _record(context, t, name, removed, messages, rejected=str(error))
            rows.append(_row(t, code, messages, None, values, rejected=str(error)))
            continue
        sent += 1
        _record(context, t, name, removed, messages, round_number=sent)
        # 4. Same question, temperature=0; record the answer as is, without judging it here.
        answer = _send(context, t, messages, sent)
        rows.append(_row(t, code, messages, answer, values))
    _report(context, t, values, rows, sent)
    return t.final_answer.format(sent=sent, blocked=len(VARIANTS) - sent)


def rejection_status(error: Exception) -> int | None:
    """The HTTP status when the provider rejected these messages; None for any other failure, which the caller re-raises."""
    status = getattr(error, "status_code", None)
    # Only a 4xx is the provider's verdict on the request itself. Auth failures (401, 403), an unknown model (404),
    # timeouts (408) and rate limits (429) are about configuration or the provider's state at the time; 5xx is a
    # fault on the provider's side. None of them is a problem with these messages.
    if isinstance(status, int) and 400 <= status < 500 and status not in {401, 403, 404, 408, 429}:
        return status
    return None


def _send(context: RunContext, t, messages: list[dict], round_number: int) -> str | None:
    """Send one request and return the answer text; on a provider rejection record it and return None, no retry, no rewrite."""
    try:
        response = context.complete({"messages": messages, "temperature": 0}, round_number=round_number)
    except Exception as error:
        status = rejection_status(error)
        if status is None:
            raise  # Stop, network failure, timeout, rate limit and the call limit are not the provider's verdict on these messages.
        context.emit("lesson.provider_error", {"status": status, "error_type": type(error).__name__,
                                               "message": str(error)[:800]}, round_number)
        return None
    try:
        answer = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(t.missing_message) from error
    if not isinstance(answer, str):
        raise ValueError(t.no_text_answer)
    return answer


def _describe(context: RunContext, t, parts: dict[str, dict]) -> None:
    """Platform: say who wrote each of the five messages, as lesson.context."""
    context.emit("lesson.context", {
        "kind": "parts", "order": list(ORDER),
        "roles": {key: message["role"] for key, message in parts.items()},
        "detail": t.parts_detail})


def _record(context: RunContext, t, name: str, removed: tuple[str, ...], messages: list[dict],
            round_number: int | None = None, rejected: str | None = None) -> None:
    """Platform: record what this variant removed, how many messages are left and the protocol verdict."""
    data = {"variant": name, "removed": list(removed), "message_count": len(messages),
            "roles": [message["role"] for message in messages]}
    data.update({"rejected": rejected} if rejected else {"protocol": t.protocol_passed})
    context.emit("lesson.context", data, round_number)


def _row(t, code: str, messages: list[dict], answer: str | None, values: Inputs, rejected: str | None = None) -> list:
    """One row of the report table. The three "mentions" columns are a keyword screen; check them against the answer."""
    protocol = t.protocol_rejected.format(error=rejected) if rejected else t.protocol_passed
    name = t.variant_names[code]
    if answer is None:
        outcome = t.outcome_not_sent if rejected else t.outcome_provider_rejected
        return [name, len(messages), protocol, outcome, "—", "—", "—"]
    score = str(SCORES[values.student_id]["score"])
    return [name, len(messages), protocol, answer, score in answer, t.weekdays[values.free_day] in answer,
            t.basis_keyword in answer]


def _report(context: RunContext, t, values: Inputs, rows: list[list], sent: int) -> None:
    """Platform: assemble and publish lesson.report."""
    blocked = [row for row in rows if row[2] != t.protocol_passed]
    context.emit("lesson.report", {
        "title": t.report_title,
        "summary": t.report_summary,
        "checks": [
            {"label": t.check_protocol, "passed": all(row[2] == t.protocol_passed for row in rows if row not in blocked),
             "detail": t.check_protocol_detail},
            {"label": t.check_blocked, "passed": any(row[0] == t.variant_names["no_tool_result"] for row in blocked),
             "detail": blocked[0][2] if blocked else t.check_blocked_none},
        ],
        "metrics": [{"label": t.label_model_calls, "value": sent}, {"label": t.label_blocked, "value": len(blocked)},
                    {"label": t.label_tool_calls, "value": 1}, {"label": t.label_student_id, "value": values.student_id},
                    {"label": t.label_free_day, "value": t.weekdays[values.free_day]},
                    {"label": t.label_note, "value": context.question or t.note_empty}],
        "table": {"columns": list(t.columns), "rows": rows},
    })
