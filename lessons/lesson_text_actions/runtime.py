"""One lookup task done three ways: the text action protocol (with / without stop) and native tool_calls.

The text format follows the stop-and-parse walkthrough in Hugging Face Agents Course Unit 1
(Apache-2.0); the prompts, parser and experiments are rewritten for this project.
"""
import json
import re
from functools import partial
from typing import Literal

from course.execution import LessonInputs, RunContext
from lessons.lesson_text_actions.locales import Texts, texts_for


class Inputs(LessonInputs):
    protocol: Literal["text_stop", "text_no_stop", "native"] = "text_stop"
    student_id: Literal["s-1042", "s-2077"] = "s-1042"


INPUT_MODEL = Inputs

# Local score table: the numbers follow no pattern, so the model cannot guess them and an
# invented Observation stands out next to the real result.
SCORES = {
    "s-1042": {"student_id": "s-1042", "score": 73, "attempts": 4, "updated": "2026-09-28"},
    "s-2077": {"student_id": "s-2077", "score": 58, "attempts": 2, "updated": "2026-09-30"},
}
PASS_LINE = 60


def lookup_quiz_score(t, /, student_id: str) -> dict:
    # t is positional-only: the model's arguments arrive by name and can never replace it.
    if student_id not in SCORES:
        raise ValueError(t.unknown_student.format(student_id=student_id))
    return SCORES[student_id]


def available_tools(locale: str) -> dict:
    """The allowlist: the tool bound to the error messages of the run's language."""
    return {"lookup_quiz_score": partial(lookup_quiz_score, texts_for(locale))}


def tool_definitions(locale: str) -> list[dict]:
    """The tool the native group sends in tools (also shown in the Tools panel). Names are code."""
    t = texts_for(locale)
    return [{"type": "function", "function": {
        "name": "lookup_quiz_score", "description": t.tool_description,
        "parameters": {"type": "object", "properties": {"student_id": {"type": "string", "description": t.tool_student_id}},
                       "required": ["student_id"], "additionalProperties": False}}}]


STOP = ["Observation:"]

ACTION = re.compile(r"Action:\s*([A-Za-z_][\w-]*)\s*\n\s*Action Input:\s*(.+)", re.S)
FINAL = re.compile(r"Final Answer:\s*(.+)", re.S)


def question_for(student_id: str, t: Texts) -> str:
    return t.question.format(student_id=student_id, pass_line=PASS_LINE)


def parse_step(content: str, t: Texts) -> dict:
    """Parse one piece of model text into one step, with no guessing repairs.

    kind is action / final / invalid. An Observation the model wrote itself is taken out
    separately and never enters the later context.
    """
    # Split at "Observation:" first: before it is what the model should write, after it is
    # what it should not write but may have written anyway.
    kept, marker, rest = content.partition("Observation:")
    fabricated = rest.strip() if marker else None
    naive_final = None
    if fabricated is not None:
        # Keep the conclusion the model wrote after its own result; the report compares it with
        # the real result. It is never used as the answer.
        found = FINAL.search(rest)
        naive_final = found.group(1).strip() if found else None
        fabricated = re.split(r"\n\s*(?:Thought:|Final Answer:|Action:)", fabricated, maxsplit=1)[0].strip()
    step = {"kept": kept.rstrip(), "fabricated": fabricated, "naive_final": naive_final}
    # An action wins over Final Answer: both in one output means the model concluded before
    # seeing the tool result, so the action runs first.
    action = ACTION.search(kept)
    if action:
        try:
            # raw_decode reads only the first JSON value and allows text after it; the parser's one leniency.
            arguments, _ = json.JSONDecoder().raw_decode(action.group(2).strip())
        except json.JSONDecodeError as error:
            return {**step, "kind": "invalid", "action": action.group(1), "error": t.invalid_json.format(error=error.msg)}
        if not isinstance(arguments, dict):
            return {**step, "kind": "invalid", "action": action.group(1), "error": t.not_an_object}
        return {**step, "kind": "action", "action": action.group(1), "arguments": arguments}
    final = FINAL.search(kept)
    if final:
        return {**step, "kind": "final", "answer": final.group(1).strip()}
    return {**step, "kind": "invalid", "error": t.no_action}


def _message(response: dict) -> tuple[dict, str | None]:
    choice = response["choices"][0]
    return choice.get("message", {}), choice.get("finish_reason")


def run_text(context: RunContext, protocol: str, student_id: str, max_steps: int) -> str:
    """Text protocol loop: the model writes the action as text; the program parses it, runs it and returns the real result as an Observation."""
    t = texts_for(context.locale)
    tools = available_tools(context.locale)
    messages = [{"role": "system", "content": t.text_system}, {"role": "user", "content": question_for(student_id, t)}]
    rows, parse_failures, fabrications = [], 0, []
    answer = None
    for step_number in range(1, max_steps + 1):
        # 1. Send the request: in the stop group the provider cuts the output when the model writes "Observation:".
        body = {"messages": messages, "temperature": 0}
        if protocol == "text_stop":
            body["stop"] = STOP
        message, finish_reason = _message(context.complete(body, step_number))
        content = message.get("content") if isinstance(message.get("content"), str) else ""
        # 2. Parse: every output is recorded as lesson.parse, with the raw text, the result and finish_reason.
        step = parse_step(content, t)
        context.emit("lesson.parse", {
            "protocol": protocol, "ok": step["kind"] != "invalid", "kind": step["kind"],
            "action": step.get("action"), "arguments": step.get("arguments"), "error": step.get("error"),
            "finish_reason": finish_reason, "model_wrote_observation": step["fabricated"] is not None,
            "raw": content}, step_number)
        rows.append([step_number, finish_reason or t.value_not_reported, step["kind"], step.get("error") or "—"])
        # 3. Decide whether to stop: a parse failure stops with no retry and no repair; so does a Final Answer.
        if step["kind"] == "invalid":
            parse_failures += 1
            break
        if step["kind"] == "final":
            answer = step["answer"]
            break
        # 4. Execute: the runner calls the tool from the parse result; the model only wrote down what it wants.
        result = context.call_tool(step["action"], step["arguments"], tools, round_number=step_number,
                                   call_id=f"text_action_{step_number}")
        if step["fabricated"] is not None:
            fabrications.append(step["fabricated"])
            context.emit("lesson.fabricated_observation", {
                "model_wrote": step["fabricated"], "real_result": result,
                "same_score": result.get("ok") is True and str(result["result"]["score"]) in step["fabricated"],
                "naive_final_answer": step["naive_final"]}, step_number)
        # 5. Hand back: only the text before Observation goes back, followed by the real result; the model's own part is dropped.
        messages += [{"role": "assistant", "content": step["kept"]},
                     {"role": "user", "content": "Observation: " + json.dumps(result, ensure_ascii=False)}]
    # Check against the final context: no Observation the model wrote may appear in a later message.
    leaked = any(text in str(message.get("content")) for text in fabrications for message in messages)
    _report_text(context, protocol, student_id, rows, parse_failures, fabrications, answer, leaked)
    if answer is None:
        return t.text_parse_failed if parse_failures else t.text_no_final.format(limit=max_steps)
    return answer


def run_native(context: RunContext, student_id: str, max_steps: int) -> str:
    """Native tool calling: the provider returns the action as structured tool_calls; the program parses no free text."""
    t = texts_for(context.locale)
    tools = available_tools(context.locale)
    messages = [{"role": "system", "content": t.native_system}, {"role": "user", "content": question_for(student_id, t)}]
    rows, answer = [], None
    for step_number in range(1, max_steps + 1):
        # 1. Send the request: the tool definition goes in tools; no text format to follow and no stop.
        response = context.complete({"messages": messages, "tools": tool_definitions(context.locale),
                                     "tool_choice": "auto", "temperature": 0}, step_number)
        message, finish_reason = _message(response)
        calls = message.get("tool_calls") or []
        rows.append([step_number, finish_reason or t.value_not_reported,
                     t.row_tool_calls.format(count=len(calls)) if calls else t.row_text_answer])
        # 2. Decide whether to stop: with no call proposal, content is the final answer.
        if not calls:
            answer = message.get("content") or ""
            break
        # 3. Execute and hand back: the assistant message with the proposals first, then one tool message per call id.
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
        for call in calls:
            result = context.execute_proposal(call, tools)
            messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": json.dumps(result, ensure_ascii=False)})
    _report_native(context, student_id, rows, answer, max_steps)
    return answer if answer is not None else t.native_no_answer.format(limit=max_steps)


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    if values.protocol == "native":
        return run_native(context, values.student_id, context.max_model_calls)
    return run_text(context, values.protocol, values.student_id, context.max_model_calls)


def _report_text(context: RunContext, protocol: str, student_id: str, rows: list[list], parse_failures: int,
                 fabrications: list[str], answer: str | None, leaked: bool) -> None:
    """Publish the text protocol report (lesson.report): two checks, parse counts and the step table."""
    t = texts_for(context.locale)
    context.emit("lesson.report", {
        "title": t.text_report_title_stop if protocol == "text_stop" else t.text_report_title_no_stop,
        "summary": t.text_report_summary,
        "checks": [
            {"label": t.check_not_leaked, "passed": not leaked,
             "detail": t.detail_fabricated.format(count=len(fabrications))},
            {"label": t.check_final_answer, "passed": answer is not None,
             "detail": t.detail_no_final if answer is None else t.detail_final_after_observation},
        ],
        "metrics": [{"label": t.label_protocol, "value": protocol}, {"label": t.label_model_calls, "value": len(rows)},
                    {"label": t.label_parse_failures, "value": parse_failures},
                    {"label": t.label_fabricated, "value": len(fabrications)},
                    {"label": t.label_student, "value": student_id},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.text_columns), "rows": rows},
    })


def _report_native(context: RunContext, student_id: str, rows: list[list], answer: str | None, max_steps: int) -> None:
    """Publish the native calling report (lesson.report)."""
    t = texts_for(context.locale)
    context.emit("lesson.report", {
        "title": t.native_report_title, "summary": t.native_report_summary,
        "checks": [{"label": t.check_native_answer, "passed": answer is not None,
                    "detail": t.detail_native_answer if answer is not None
                    else t.detail_native_unfinished.format(limit=max_steps)}],
        "metrics": [{"label": t.label_protocol, "value": "native"}, {"label": t.label_model_calls, "value": len(rows)},
                    {"label": t.label_student, "value": student_id},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.native_columns), "rows": rows},
    })
