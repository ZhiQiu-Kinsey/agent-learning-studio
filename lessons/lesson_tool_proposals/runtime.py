"""Send the tool definitions with the request and only record the calls the model proposes; this lesson executes no tool."""
import json

from course.execution import RunContext
from lessons.lesson_01_tool_selection.tools import tool_definitions
from lessons.lesson_tool_proposals.locales import texts_for


def read_proposals(message: dict) -> list[dict]:
    """Turn tool_calls into a list of call proposals: read fields only, look up no function, execute nothing."""
    proposals = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        arguments = function.get("arguments")
        try:
            # arguments is a JSON string. Only check whether it parses to an object; the result calls nothing.
            valid = isinstance(json.loads(arguments or "{}"), dict)
        except (TypeError, json.JSONDecodeError):
            valid = False
        proposals.append({"id": call.get("id"), "name": function.get("name"),
                          "arguments": arguments, "valid_json": valid})
    return proposals


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    question = context.question.strip() or t.default_question
    # 1. Compared with a plain request, the body adds tools and tool_choice: the tool definitions travel with it.
    body = {"messages": [{"role": "system", "content": t.system_prompt}, {"role": "user", "content": question}],
            "tools": tool_definitions(context.locale), "tool_choice": "auto"}
    # 2. Send this one request only.
    response = context.complete(body)
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError(t.missing_choices)
    message = choices[0].get("message") or {}
    # 3. Only read the call proposals. No function is registered for execution, so there is no tool result.
    proposals = read_proposals(message)
    _report(context, choices[0].get("finish_reason"), message, proposals)
    if not proposals:
        return message.get("content") or t.empty_content
    calls = t.call_separator.join(f"{item['name']}({item['arguments']})" for item in proposals)
    return t.proposals_answer.format(count=len(proposals), calls=calls)


def _report(context: RunContext, finish_reason: str | None, message: dict, proposals: list[dict]) -> None:
    """Platform: turn the call proposals into the lab report."""
    t = texts_for(context.locale)
    context.emit("lesson.report", {
        "title": t.report_title,
        "summary": t.report_summary,
        "metrics": [
            {"label": t.label_finish_reason, "value": t.value_not_reported if finish_reason is None else finish_reason},
            {"label": t.label_proposal_count, "value": len(proposals)},
            {"label": t.label_content_length, "value": len(message.get("content") or "")},
        ],
        "table": {"columns": list(t.columns),
                  "rows": [[item["id"] or t.value_none, item["name"] or t.value_none, item["arguments"] or t.value_empty,
                            item["valid_json"]] for item in proposals]},
    })
