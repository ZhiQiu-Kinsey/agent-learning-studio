"""Send the same request several times unchanged: count the distinct answers and see that output comes from sampling."""
from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_sampling_variance.locales import texts_for


class Inputs(LessonInputs):
    # The experimental condition: the two arms change only this number.
    temperature: float = Field(default=0, ge=0, le=2)
    # How often the same request is sent; max_rounds in lesson.json is 5, so the platform allows at most 5 requests.
    repeats: int = Field(default=5, ge=2, le=5)


INPUT_MODEL = Inputs


def reply_text(response: dict, missing_choices: str) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError(missing_choices)
    return (choices[0].get("message") or {}).get("content") or ""


def count_distinct(answers: list[str]) -> int:
    """Compare character by character after trimming: one extra punctuation mark makes another answer; similar meanings are not merged."""
    return len({answer.strip() for answer in answers})


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    question = context.question.strip() or t.default_question
    # 1. Build the body once, so every request sends exactly the same messages.
    body = {"messages": [{"role": "system", "content": t.system_prompt}, {"role": "user", "content": question}],
            "temperature": values.temperature}
    responses = []
    for number in range(1, values.repeats + 1):
        # 2. Send it again unchanged. Each request stands alone; earlier answers are not carried over.
        responses.append(context.complete(body, round_number=number))
    answers = [reply_text(response, t.missing_choices) for response in responses]
    # 3. The program counts the distinct answers; nobody judges them by eye.
    distinct = count_distinct(answers)
    _report(context, values, answers, responses, distinct)
    return t.answer.format(repeats=values.repeats, distinct=distinct)


def _report(context: RunContext, values: Inputs, answers: list[str], responses: list[dict], distinct: int) -> None:
    """Platform: put each answer and the usage into the lab report; if one response lacks usage, the total is "not reported"."""
    t = texts_for(context.locale)
    usages = [response.get("usage") or {} for response in responses]

    def total(key):
        numbers = [usage.get(key) for usage in usages]
        return t.value_not_reported if any(number is None for number in numbers) else sum(numbers)

    counts = {}
    for answer in answers:
        counts[answer.strip()] = counts.get(answer.strip(), 0) + 1
    context.emit("lesson.report", {
        "title": t.report_title.format(temperature=f"{values.temperature:g}", repeats=values.repeats),
        "summary": t.report_summary,
        "metrics": [
            {"label": t.label_temperature, "value": values.temperature},
            {"label": t.label_repeats, "value": values.repeats},
            {"label": t.label_distinct, "value": distinct},
            {"label": t.label_most_common, "value": t.value_times.format(count=max(counts.values()))},
            {"label": t.label_prompt_total, "value": total("prompt_tokens")},
            {"label": t.label_completion_total, "value": total("completion_tokens")},
            {"label": t.label_total_total, "value": total("total_tokens")},
        ],
        "table": {"columns": [t.column_number, t.column_answer, t.column_completion_tokens],
                  "rows": [[number, answer, t.value_not_reported if usage.get("completion_tokens") is None
                            else usage["completion_tokens"]]
                           for number, (answer, usage) in enumerate(zip(answers, usages), start=1)]},
    })
