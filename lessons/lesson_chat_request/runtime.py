"""One model request without tools: build the body, send it, read the answer, finish reason and usage."""
from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_chat_request.locales import texts_for


class Inputs(LessonInputs):
    # Empty means this request has no system message. No default here: the preset in
    # lesson.json supplies the system prompt in the run's language.
    system_prompt: str = Field(max_length=400)
    # 0 means no max_tokens in the body; the provider decides the output limit.
    max_tokens: int = Field(default=0, ge=0, le=1024)


INPUT_MODEL = Inputs


def build_request(question: str, system_prompt: str, max_tokens: int) -> dict:
    """The body holds only the fields this lesson is about; the platform adds model for the current connection."""
    messages = []
    if system_prompt.strip():
        # The system message carries the rules for the model; it goes first.
        messages.append({"role": "system", "content": system_prompt})
    # The user message is the question of this request.
    messages.append({"role": "user", "content": question})
    body = {"messages": messages}
    if max_tokens:
        # Output limit: generation stops after this many tokens and finish_reason is length.
        body["max_tokens"] = max_tokens
    return body


def read_reply(response: dict, missing_choices: str) -> dict:
    """Take the answer, finish reason and usage from the response; a number the provider did not report is None, not 0."""
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError(missing_choices)
    message = choices[0].get("message") or {}
    usage = response.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    return {
        "content": message.get("content") or "",
        # Some models reason before answering: the reasoning is in reasoning_content and is not the answer.
        "reasoning": message.get("reasoning_content"),
        "finish_reason": choices[0].get("finish_reason"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        # Reasoning tokens count toward completion_tokens; some providers cap them with max_tokens too.
        "reasoning_tokens": details.get("reasoning_tokens"),
    }


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    question = context.question.strip() or t.default_question
    # 1. Build the body: only messages, plus max_tokens when set. The key is not here.
    body = build_request(question, values.system_prompt, values.max_tokens)
    # 2. Send one request. context.complete records the request and response events unchanged.
    response = context.complete(body)
    # 3. Read the response: answer, finish reason, usage.
    reply = read_reply(response, t.missing_choices)
    _report(context, body, reply)
    return reply["content"] or t.empty_content


def _report(context: RunContext, body: dict, reply: dict) -> None:
    """Platform: turn the key fields of this request into the lab report."""
    t = texts_for(context.locale)

    def shown(value):
        return t.value_not_reported if value is None else value

    reason = reply["finish_reason"]
    metrics = [
        {"label": t.label_system, "value": t.value_yes if body["messages"][0]["role"] == "system" else t.value_no},
        {"label": t.label_max_tokens, "value": body.get("max_tokens", t.value_not_set)},
        {"label": t.label_answer_length, "value": len(reply["content"])},
        {"label": t.label_finish_reason, "value": shown(reason)},
        {"label": t.label_reason_meaning,
         "value": t.finish_reasons.get(reason, t.value_not_reported if reason is None else t.value_other_reason)},
        {"label": t.label_prompt_tokens, "value": shown(reply["prompt_tokens"])},
        {"label": t.label_completion_tokens, "value": shown(reply["completion_tokens"])},
        {"label": t.label_total_tokens, "value": shown(reply["total_tokens"])},
    ]
    if reply["reasoning_tokens"] is not None:
        metrics.append({"label": t.label_reasoning_tokens, "value": reply["reasoning_tokens"]})
    if reply["reasoning"] is not None:
        metrics.append({"label": t.label_reasoning_chars, "value": len(reply["reasoning"])})
    context.emit("lesson.report", {
        "title": t.report_title,
        "summary": t.report_summary,
        "metrics": metrics,
        "table": {"columns": [t.column_index, "role", "content"],
                  "rows": [[index, message["role"], message["content"]]
                           for index, message in enumerate(body["messages"])]},
    })
