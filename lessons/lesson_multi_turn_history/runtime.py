"""Ask several turns in a row: the program keeps each question and answer in history and sends them with the next request."""
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_multi_turn_history.locales import texts_for


def reply_text(response: dict, missing_choices: str) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError(missing_choices)
    return (choices[0].get("message") or {}).get("content") or ""


class Inputs(LessonInputs):
    # full: every turn carries all earlier messages; latest_only: only system and this turn's question.
    history: Literal["full", "latest_only"] = "full"
    turns: int = Field(default=2, ge=2, le=3)


INPUT_MODEL = Inputs


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    # 1. The message history lives only in this Python list; the model keeps nothing.
    history = [{"role": "system", "content": t.system_prompt}]
    turns = []
    for number, question in enumerate(t.turns[:values.turns], start=1):
        # 2. This turn's question goes into the history first.
        history.append({"role": "user", "content": question})
        # 3. Decide what to send: the whole history, or only system and this turn's question.
        messages = history if values.history == "full" else [history[0], history[-1]]
        response = context.complete({"messages": messages}, round_number=number)
        answer = reply_text(response, t.missing_choices)
        turns.append({"messages": list(messages), "response": response, "answer": answer})
        # 4. The answer goes back into the history as an assistant message; otherwise the next turn can't send it.
        history.append({"role": "assistant", "content": answer})
    _report(context, values, turns)
    return answer


def _report(context: RunContext, values: Inputs, turns: list[dict]) -> None:
    """Platform: turn each turn's message count and usage into the lab report."""
    t = texts_for(context.locale)

    def prompt_tokens(turn):
        return (turn["response"].get("usage") or {}).get("prompt_tokens")

    def completion_tokens(turn):
        return (turn["response"].get("usage") or {}).get("completion_tokens")

    def shown(value):
        return t.value_not_reported if value is None else value

    def has_fact(messages):
        return any(t.fact in message["content"] for message in messages)

    rows = [[number, len(turn["messages"]), t.value_yes if has_fact(turn["messages"]) else t.value_no,
             shown(prompt_tokens(turn)), shown(completion_tokens(turn)), turn["answer"]]
            for number, turn in enumerate(turns, start=1)]
    first, last = prompt_tokens(turns[0]), prompt_tokens(turns[-1])
    second = turns[1]
    context.emit("lesson.report", {
        "title": t.report_title,
        "summary": t.summary_full if values.history == "full" else t.summary_latest_only,
        "checks": [
            {"label": t.check_fact_sent, "passed": has_fact(second["messages"]),
             "detail": t.check_fact_sent_detail.format(fact=t.fact)},
            {"label": t.check_fact_answered, "passed": t.fact in second["answer"],
             "detail": t.check_fact_answered_detail},
        ],
        "metrics": [
            {"label": t.label_mode, "value": t.mode_values[values.history]},
            {"label": t.label_model_calls, "value": len(turns)},
            {"label": t.label_last_message_count, "value": len(turns[-1]["messages"])},
            {"label": t.label_prompt_growth,
             "value": t.value_not_reported if first is None or last is None else t.prompt_growth.format(first=first, last=last)},
            {"label": t.label_note, "value": context.question.strip() or t.value_empty},
        ],
        "table": {"columns": list(t.columns), "rows": rows},
    })
