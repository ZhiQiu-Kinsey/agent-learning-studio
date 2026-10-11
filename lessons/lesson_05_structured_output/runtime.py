"""Parse, type-check, then independently verify a model-generated task card."""
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from course.execution import LessonInputs, RunContext
from lessons.lesson_05_structured_output.locales import texts_for

# The wrong prerequisite the "wrong fact" exercise asks the model to write.
WRONG_PREREQUISITE = "dependent-calls"


def trusted_facts(t) -> dict:
    """The facts this lesson trusts. Lessons are identified by slug: the displayed lesson number moves when lessons are inserted, so it cannot be a trusted fact."""
    return {"lesson_id": "task-contract", "lesson_title": t.facts_lesson_title, "prerequisite": "fail-safely"}


class Inputs(LessonInputs):
    scenario: Literal["normal", "missing_field", "wrong_fact"] = "normal"
    repair: bool = True


INPUT_MODEL = Inputs


class TaskCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lesson_id: str = Field(min_length=1, max_length=48)
    lesson_title: str = Field(min_length=1, max_length=60)
    prerequisite: str = Field(min_length=1, max_length=48)
    exercise: str = Field(min_length=8, max_length=120)


def inspect_output(raw: str, t) -> tuple[TaskCard | None, list[dict]]:
    def reject_non_json_constant(value: str):
        raise ValueError(t.non_json_constant.format(value=value))

    checks = []
    try:
        parsed = json.loads(raw, parse_constant=reject_non_json_constant)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return None, [{"label": t.layer_json, "passed": False, "detail": str(exc)}]
    checks.append({"label": t.layer_json, "passed": True, "detail": t.detail_json_ok})
    try:
        card = TaskCard.model_validate(parsed)
    except ValidationError as exc:
        checks.append({"label": t.layer_schema, "passed": False,
                       "detail": "; ".join(".".join(map(str, e["loc"])) + ": " + e["type"] for e in exc.errors())[:300]})
        return None, checks
    checks.append({"label": t.layer_schema, "passed": True, "detail": t.detail_schema_ok})
    mismatches = [key for key, expected in trusted_facts(t).items() if getattr(card, key) != expected]
    checks.append({"label": t.layer_facts, "passed": not mismatches,
                   "detail": t.detail_facts_ok if not mismatches else t.detail_facts_mismatch.format(fields=", ".join(mismatches))})
    return card, checks


def _content(response: dict, t) -> str:
    try:
        value = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(t.missing_content) from exc
    if not isinstance(value, str):
        raise ValueError(t.content_not_text)
    return value


def _report(context: RunContext, checks: list[dict], attempt: int) -> None:
    t = texts_for(context.locale)
    accepted = len(checks) == 3 and all(c["passed"] for c in checks)
    stage = t.stage_first if attempt == 1 else t.stage_repair
    context.emit("lesson.report", {
        "title": t.report_title.format(stage=stage),
        "summary": (t.summary_passed if accepted else t.summary_failed).format(stage=stage),
        "checks": checks,
        "metrics": [{"label": t.label_model_calls, "value": attempt},
                    {"label": t.label_draft_verdict, "value": t.value_passed if accepted else t.value_failed},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.columns),
                  "rows": [[c["label"], t.value_passed if c["passed"] else c["detail"]] for c in checks]},
    }, attempt)


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    scenario = context.inputs["scenario"]
    facts_text = json.dumps(trusted_facts(t), ensure_ascii=False)
    user = t.user_prompt.format(facts=facts_text)
    if scenario == "missing_field":
        user += t.inject_missing_field
    elif scenario == "wrong_fact":
        user += t.inject_wrong_fact.format(wrong=WRONG_PREREQUISITE)
    messages = [{"role": "system", "content": t.system_prompt}, {"role": "user", "content": user}]
    raw = _content(context.complete({"messages": messages, "temperature": 0}, 1), t)
    card, checks = inspect_output(raw, t)
    attempts = 1
    _report(context, checks, attempts)
    if (not all(item["passed"] for item in checks) and context.inputs["repair"]
            and context.max_model_calls >= 2):
        context.check_cancelled()
        reasons = "; ".join(c["detail"] for c in checks if not c["passed"])
        messages.extend([{"role": "assistant", "content": raw},
                         {"role": "user", "content": t.repair_prompt.format(reasons=reasons)}])
        raw = _content(context.complete({"messages": messages, "temperature": 0}, 2), t)
        card, checks = inspect_output(raw, t)
        attempts = 2
        _report(context, checks, attempts)
    accepted = len(checks) == 3 and all(c["passed"] for c in checks)
    return t.answer_passed.format(card=card.model_dump_json()) if accepted else t.answer_failed
