"""Skills and progressive disclosure: the same task with every skill body in the system prompt, or only a catalog and loading on use.

locales/skills/<name>/<locale>.md are this lesson's own teaching material in SKILL.md format: name and description
between two --- lines, then the body. A run reads the files of its own language.
"""
import json
from functools import partial
from pathlib import Path
from typing import Literal

from course.execution import LessonInputs, RunContext
from course.i18n import localized_file
from lessons.lesson_skills_disclosure.locales import texts_for


class Inputs(LessonInputs):
    mode: Literal["both", "full", "on_demand"] = "both"
    task: Literal["make_cards", "chat", "review_question"] = "make_cards"
    description: Literal["precise", "vague"] = "precise"


INPUT_MODEL = Inputs

SKILLS_DIR = Path(__file__).with_name("locales") / "skills"
# Allowlist: only skills registered here enter the catalog and can be loaded; another file under skills/ does nothing.
SKILL_NAMES = ("review-cards", "error-question", "unit-test-checklist", "three-sentence-summary")


def read_skill(name: str, locale: str) -> dict:
    """Read one skill file: name and description between the two --- lines, the rest is the body."""
    text = localized_file(SKILLS_DIR / name, locale, ".md").read_text(encoding="utf-8").replace("\r\n", "\n")
    _, header, body = text.split("---\n", 2)
    fields = dict(line.split(":", 1) for line in header.strip().splitlines())
    if fields.get("name", "").strip() != name:
        raise ValueError(f"the name in skill file {name} does not match its registered name")
    return {"name": name, "description": fields["description"].strip(), "body": body.strip()}


def skill_list(description: str, locale: str) -> list[dict]:
    skills = [read_skill(name, locale) for name in SKILL_NAMES]
    if description == "vague":
        # The "vague" arms replace only review-cards' description; its body and the other skills stay.
        skills[0]["description"] = texts_for(locale).vague_description
    return skills


def load_skill(locale, /, name: str) -> dict:
    """The load_skill tool: the model's name is only looked up in the allowlist; only a hit reads the file."""
    if name not in SKILL_NAMES:
        # execute_tool turns the ValueError into a structured error with ok false and hands it back to the model.
        t = texts_for(locale)
        raise ValueError(t.unknown_skill.format(name=name, names=t.list_separator.join(SKILL_NAMES)))
    return {"name": name, "instructions": read_skill(name, locale)["body"]}


def available_tools(locale: str) -> dict:
    """The allowlist the runner executes from; locale is positional-only, so the model's arguments cannot replace it."""
    return {"load_skill": partial(load_skill, locale)}


# Which skill this lesson expects for each task (None: no skill should be loaded).
EXPECTED = {"make_cards": "review-cards", "chat": None, "review_question": None}
ON_DEMAND_LIMIT = 3  # on-demand loading sends at most 3 requests: propose a load, answer with the body, one spare


def run(context: RunContext) -> str:
    t, values = texts_for(context.locale), Inputs.model_validate(context.inputs)
    question, expected = t.task_messages[values.task], EXPECTED[values.task]
    skills = skill_list(values.description, context.locale)
    passes = []
    # With both modes, full injection goes first (request 1), then on-demand loading (from request 2).
    if values.mode in ("both", "full"):
        passes.append(run_full(context, skills, question, round_number=1))
    if values.mode in ("both", "on_demand"):
        passes.append(run_on_demand(context, skills, question, first_round=len(passes) + 1))
    _report(context, values, expected, passes)
    return "\n\n".join(t.answer_section.format(mode=t.mode_labels[item["mode"]], answer=_answer_text(t, item))
                       for item in passes)


def tool_definitions(locale: str) -> list[dict]:
    t = texts_for(locale)
    return [{"type": "function", "function": {
        "name": "load_skill",
        "description": t.load_skill_description,
        "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": t.load_skill_name_description}},
                       "required": ["name"], "additionalProperties": False}}}]


def full_prompt(t, skills: list[dict]) -> str:
    # Full injection: every skill's description and body go into the system prompt, carried by every request after.
    sections = [t.full_section.format(name=skill["name"], description=skill["description"], body=skill["body"])
                for skill in skills]
    return t.full_prompt + "\n\n" + "\n\n".join(sections)


def catalog_prompt(t, skills: list[dict]) -> str:
    # Progressive disclosure: one line per skill in the system prompt; the body comes only when the model calls load_skill.
    lines = [t.catalog_line.format(name=skill["name"], description=skill["description"]) for skill in skills]
    return t.catalog_prompt + "\n\n" + t.catalog_heading + "\n" + "\n".join(lines)


def run_full(context: RunContext, skills: list[dict], question: str, round_number: int) -> dict:
    t = texts_for(context.locale)
    messages = [{"role": "system", "content": full_prompt(t, skills)}, {"role": "user", "content": question}]
    # Full injection sends one request: every procedure is already in the system prompt, no tool needed.
    response = context.complete({"messages": messages, "temperature": 0}, round_number)
    record = _record(context, "full", round_number, messages, response, skills)
    return {"mode": "full", "answer": _content(response), "requests": [record], "loaded": None}


def run_on_demand(context: RunContext, skills: list[dict], question: str, first_round: int) -> dict:
    t = texts_for(context.locale)
    # 1. The system prompt holds only the catalog; a skill body can enter the history only as a load_skill tool result.
    messages = [{"role": "system", "content": catalog_prompt(t, skills)}, {"role": "user", "content": question}]
    requests, loaded = [], []
    for round_number in range(first_round, first_round + ON_DEMAND_LIMIT):
        context.check_cancelled()
        # 2. Every request carries load_skill: whether to load, and which, is the model's decision.
        response = context.complete({"messages": messages, "tools": tool_definitions(context.locale),
                                     "tool_choice": "auto", "temperature": 0}, round_number)
        requests.append(_record(context, "on_demand", round_number, messages, response, skills))
        message = response["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        # 3. No call proposed: content is the answer.
        if not calls:
            return {"mode": "on_demand", "answer": message.get("content") or "", "requests": requests,
                    "loaded": loaded}
        # 4. Run the proposed load_skill; the body goes back into the history as a tool result, seen by the next request.
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
        for call in calls:
            result = context.execute_proposal(call, available_tools(context.locale))
            if result["ok"]:
                loaded.append(result["result"]["name"])
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    # The request limit is used up and the model still wants skills: no more requests, honestly recorded as no answer.
    return {"mode": "on_demand", "answer": None, "requests": requests, "loaded": loaded}


def judge_loading(t, expected: str | None, loaded: list[str] | None) -> tuple[bool | None, str]:
    """Compare "the skill this lesson expects" with the skills the events show were really loaded."""
    if loaded is None:
        return None, t.loading_not_applicable
    if not loaded:
        return (True, t.loading_none_correct) if expected is None else (False, t.loading_missed)
    names = t.list_separator.join(dict.fromkeys(loaded))
    if expected is None:
        return False, t.loading_false.format(names=names)
    return (True, t.loading_correct.format(names=names)) if set(loaded) == {expected} else (
        False, t.loading_wrong.format(names=names))


def count_cards(t, answer: str) -> tuple[int, int]:
    """Count lines starting with the question and answer prefixes, after removing Markdown asterisks and leading numbers."""
    asked = answered = 0
    for line in answer.splitlines():
        text = line.replace("*", "").strip().lstrip("-#>0123456789.、 ")
        asked += text.startswith(t.card_question_prefixes)
        answered += text.startswith(t.card_answer_prefixes)
    return asked, answered


def format_screen(t, expected: str | None, answer: str | None) -> tuple[bool, str]:
    """Format screen: only whether the answer looks like review cards, not whether it is right."""
    if answer is None:
        return False, t.format_no_answer
    asked, answered = count_cards(t, answer)
    if expected == "review-cards":
        return 3 <= asked <= 5 and asked == answered, t.format_cards.format(asked=asked, answered=answered)
    return asked == 0, t.format_not_cards if asked == 0 else t.format_cards_written.format(asked=asked)


# ---------- Platform: record each request, publish the report ----------

def _content(response: dict) -> str:
    content = response["choices"][0]["message"].get("content")
    return content if isinstance(content, str) else ""


def _answer_text(t, item: dict) -> str:
    return item["answer"] if item["answer"] is not None else t.no_answer.format(limit=ON_DEMAND_LIMIT)


def _proposed_name(t, call: dict) -> str:
    try:
        name = json.loads(call["function"].get("arguments") or "{}").get("name")
    except (json.JSONDecodeError, AttributeError):
        name = None
    return name if isinstance(name, str) else t.unparsable_arguments


def _record(context: RunContext, mode: str, round_number: int, messages: list[dict], response: dict,
            skills: list[dict]) -> dict:
    """Evidence of one request: the prompt tokens the provider reported, which skill bodies were in the messages sent,
    which skills the response proposed to load."""
    t = texts_for(context.locale)
    usage = response.get("usage")
    tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    sent = "\n".join(str(message.get("content") or "") for message in messages)
    # With full injection a body appears verbatim in the system prompt; with on-demand loading it is in a tool result,
    # escaped as JSON.
    in_context = [skill["name"] for skill in skills
                  if skill["body"] in sent or json.dumps(skill["body"], ensure_ascii=False)[1:-1] in sent]
    calls = response["choices"][0]["message"].get("tool_calls") or []
    record = {"mode": mode, "round": round_number,
              "prompt_tokens": tokens if type(tokens) is int else None,
              "system_chars": len(messages[0]["content"]), "skills_in_context": in_context,
              "proposed_loads": [_proposed_name(t, call) for call in calls]}
    context.emit("lesson.skill_request", record, round_number)
    return record


def _tokens(t, values: list[int | None]) -> tuple[str, int | str]:
    shown = " → ".join(t.value_not_reported if value is None else str(value) for value in values)
    missing = sum(value is None for value in values)
    total = sum(value for value in values if value is not None)
    return shown, total if not missing else (
        t.value_not_reported if missing == len(values) else t.tokens_partly_reported.format(total=total, missing=missing))


def _report(context: RunContext, values: Inputs, expected: str | None, passes: list[dict]) -> None:
    t = texts_for(context.locale)
    rows, checks = [], []
    metrics = [{"label": t.label_task, "value": t.task_labels[values.task]},
               {"label": t.label_description, "value": t.value_vague if values.description == "vague" else t.value_precise},
               {"label": t.label_expected, "value": expected or t.value_expect_none}]
    for item in passes:
        label, first = t.mode_labels[item["mode"]], item["requests"][0]
        shown, total = _tokens(t, [record["prompt_tokens"] for record in item["requests"]])
        loading_ok, loading = judge_loading(t, expected, item["loaded"])
        format_ok, format_detail = format_screen(t, expected, item["answer"])
        proposals = t.proposals_separator.join(
            t.proposals.format(round=record["round"], names=t.list_separator.join(record["proposed_loads"]))
            for record in item["requests"] if record["proposed_loads"])
        rows.append([label, len(item["requests"]), shown, total,
                     proposals or (t.value_all_resident if item["loaded"] is None else t.value_no_proposal),
                     loading, (t.format_passed if format_ok else t.format_failed) + format_detail])
        metrics.append({"label": t.label_first_tokens.format(mode=label),
                        "value": t.value_not_reported if first["prompt_tokens"] is None else first["prompt_tokens"]})
        if item["mode"] == "full":
            checks.append({"label": t.check_full_bodies,
                           "passed": len(first["skills_in_context"]) == len(SKILL_NAMES),
                           "detail": t.check_full_bodies_detail.format(count=len(first["skills_in_context"]))})
        else:
            checks.append({"label": t.check_catalog_only,
                           "passed": not first["skills_in_context"],
                           "detail": t.check_catalog_only_detail.format(chars=first["system_chars"])})
            checks.append({"label": t.check_loading, "passed": loading_ok, "detail": loading})
            rejected = [name for record in item["requests"] for name in record["proposed_loads"]
                        if name not in SKILL_NAMES]
            if rejected:
                checks.append({"label": t.check_rejected, "passed": True,
                               "detail": t.check_rejected_detail.format(names=t.list_separator.join(rejected))})
        checks.append({"label": t.check_format.format(mode=label), "passed": format_ok,
                       "detail": t.check_format_detail.format(detail=format_detail)})
    metrics += [{"label": t.label_model_calls, "value": sum(len(item["requests"]) for item in passes)},
                {"label": t.label_note, "value": context.question or t.value_empty}]
    context.emit("lesson.report", {
        "title": t.report_title.format(modes=t.title_separator.join(t.mode_labels[item["mode"]] for item in passes),
                                       task=t.task_labels[values.task]),
        "summary": t.report_summary,
        "checks": checks, "metrics": metrics,
        "table": {"columns": list(t.columns), "rows": rows},
    })
