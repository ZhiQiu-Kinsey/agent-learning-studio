"""Paired experiments on prompts and tool descriptions: change one piece of text, keep everything else fixed, compare two real responses.

There is also a tool description matrix: the same add_numbers with a blank, a good and a
misleading description, each asked two probes. Valid proposals from the model go to the real
code, and the table puts "what the model expected" next to "what the code returned".
"""
import json
import re
from functools import partial
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_06_prompt_experiments.locales import texts_for


class Inputs(LessonInputs):
    scenario: Literal["tool_description", "flow_rule", "missing_input", "tool_matrix"] = "tool_description"
    # No default: the preset in lesson.json supplies the label in the run's language.
    sample_label: str = Field(min_length=1, max_length=40)


INPUT_MODEL = Inputs
# Paired scenarios; their (task, baseline, rewrite) texts are t.pair_tasks in the catalog.
PAIR_SCENARIOS = ("tool_description", "flow_rule", "missing_input")
# Matrix rows: the blank group has no description in the catalog and sends none.
MATRIX_GROUPS = ("blank", "good", "misleading")
# Matrix columns and the call each probe expects; the concatenation probe expects no call:
# does the model use the tool for something it cannot do?
PROBE_EXPECTED = {"sum": {"a": 19, "b": 23}, "concat": None}
PARAMETERS = {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
              "required": ["a", "b"], "additionalProperties": False}


def add_numbers(t, /, a: int, b: int) -> int:
    # The schema says integers: strings or floats come back as an error instead of "19" and "23" joined into 1923.
    # t holds the error message of the run's language; it is positional-only, so the model's arguments cannot replace it.
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in (a, b)):
        raise ValueError(t.not_integers)
    return a + b


def tool_spec(description: str | None) -> dict:
    """Build the tool definition: the parameter schema is always the same, the description is the only variable."""
    function = {"name": "add_numbers", "parameters": PARAMETERS}
    # The blank group leaves out the description field instead of sending an empty string.
    if description is not None:
        function["description"] = description
    return {"type": "function", "function": function}


def _content(response: dict, t) -> str:
    try:
        value = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(t.missing_content) from exc
    if not isinstance(value, str):
        raise ValueError(t.content_not_text)
    return value


def evaluate(scenario: str, answer: str, t) -> tuple[bool, str]:
    """A form screening of the answer text: a hit only means "looks like it"; a human still reads the original."""
    if scenario == "tool_description":
        return False, t.detail_tool_needs_calls
    if scenario == "missing_input":
        # The missing-input screening needs all three: it asks, it mentions addends or numbers, it writes no digit itself.
        passed = (bool(re.search(t.ask_pattern, answer, re.IGNORECASE))
                  and bool(re.search(t.number_word_pattern, answer, re.IGNORECASE))
                  and not bool(re.search(r"\d", answer)))
        return passed, (t.detail_missing_hit if passed else t.detail_missing_miss)
    # Process-rule screening: 42 must appear, and phrases like "not 42" are excluded to reduce false hits.
    passed = (bool(re.search(r"(?<!\d)42(?!\d)", answer))
              and not bool(re.search(t.negation_pattern, answer, re.IGNORECASE)))
    return passed, (t.detail_flow_hit if passed else t.detail_flow_miss)


def evaluate_tool_response(response: dict, t) -> tuple[str, bool, str]:
    """A structure screening of the tool proposal: name and arguments only; this call is not executed."""
    message = response.get("choices", [{}])[0].get("message", {})
    calls = message.get("tool_calls") or []
    # Exactly one proposal is expected; without one, keep the model's text answer on record.
    if len(calls) != 1:
        return _content(response, t) if isinstance(message.get("content"), str) else t.value_no_tool_call, False, t.detail_need_one_call
    function = calls[0].get("function", {})
    try:
        arguments = json.loads(function.get("arguments", ""))
    except (json.JSONDecodeError, TypeError):
        return str(function), False, t.detail_arguments_not_json
    passed = function.get("name") == "add_numbers" and arguments == {"a": 19, "b": 23}
    return json.dumps({"name": function.get("name"), "arguments": arguments}, ensure_ascii=False), passed, (
        t.detail_proposal_hit if passed else t.detail_proposal_miss)


def run_pair(context: RunContext, t) -> str:
    """Paired experiment: same model, same task, temperature=0, one piece of text changed, one request each."""
    # Half a pair cannot be compared: without budget for two calls, refuse instead of running half.
    if context.max_model_calls < 2:
        raise RuntimeError(t.pair_budget_error)
    scenario = context.inputs["scenario"]
    task, baseline, variant = t.pair_tasks[scenario]
    rows = []
    for index, (label, variable) in enumerate(((t.label_baseline, baseline), (t.label_variant, variant)), 1):
        # 1. Build the request: the two requests differ only in variable.
        system = t.pair_system if scenario == "tool_description" else variable
        body = {"messages": [{"role": "system", "content": system},
                             {"role": "user", "content": task}], "temperature": 0}
        if scenario == "tool_description":
            body["tools"] = [tool_spec(variable)]
        # 2. Send and screen: the tool scenario looks at the proposal, the others at the answer text.
        response = context.complete(body, index)
        if scenario == "tool_description":
            answer, passed, detail = evaluate_tool_response(response, t)
        else:
            answer = _content(response, t)
            passed, detail = evaluate(scenario, answer, t)
        # 3. Keep the original next to the screening verdict: screening only filters; judgment goes back to the text.
        rows.append({"label": label, "prompt": variable, "answer": answer, "passed": passed, "detail": detail})
    _report_pair(context, scenario, rows)
    return t.pair_answer


def proposed_call(response: dict) -> dict | None:
    """The first call proposal as {name, arguments, call}; arguments is None when they are not valid JSON."""
    message = response.get("choices", [{}])[0].get("message", {})
    calls = message.get("tool_calls") or []
    if not calls:
        return None
    function = calls[0].get("function", {})
    try:
        arguments = json.loads(function.get("arguments", ""))
    except (json.JSONDecodeError, TypeError):
        arguments = None
    return {"name": function.get("name"), "arguments": arguments, "call": calls[0]}


def judge_cell(expected_arguments: dict | None, proposal: dict | None, t) -> tuple[bool, str]:
    """Judge one cell: the sum probe must propose exactly add_numbers(19, 23), the concatenation probe no call."""
    if expected_arguments is None:
        return (proposal is None, t.cell_no_call_ok if proposal is None
                else t.cell_unneeded_call.format(name=proposal["name"]))
    if proposal is None:
        return False, t.cell_missing_call
    passed = proposal["name"] == "add_numbers" and proposal["arguments"] == expected_arguments
    return passed, t.cell_match if passed else t.cell_mismatch


def run_matrix(context: RunContext, t) -> str:
    """Description matrix: three descriptions x two probes, one request per cell; valid proposals run on the real code."""
    cells = len(MATRIX_GROUPS) * len(PROBE_EXPECTED)
    # A matrix missing a cell is no matrix: without enough budget, refuse before the first request.
    if context.max_model_calls < cells:
        raise RuntimeError(t.matrix_budget_error.format(cells=cells))
    checks, rows, index = [], [], 0
    for group in MATRIX_GROUPS:
        description = t.descriptions.get(group)
        label = t.group_labels[group]
        row = [t.group_blank_row.format(label=label) if description is None else label]
        for probe, expected in PROBE_EXPECTED.items():
            index += 1
            # 1. Send: system, probe and temperature are the same six times; tool_spec(description) is the only variable.
            body = {"messages": [{"role": "system", "content": t.matrix_system},
                                 {"role": "user", "content": t.probes[probe]}],
                    "tools": [tool_spec(description)], "temperature": 0}
            response = context.complete(body, index)
            proposal = proposed_call(response)
            # 2. Judge: call exactly when a call is needed, no call when it is not.
            passed, detail = judge_cell(expected, proposal, t)
            checks.append({"label": t.check_cell.format(group=label, probe=t.probe_labels[probe]),
                           "passed": passed, "detail": detail})
            # 3. Execute a valid proposal; the table shows the value the code really returned.
            cell = _matrix_cell(context, response, proposal, t)
            row.append(cell + (t.cell_expected if passed else t.cell_unexpected))
        rows.append(row)
    _report_matrix(context, checks, rows, index)
    return t.matrix_answer.format(calls=index)


def _matrix_cell(context: RunContext, response: dict, proposal: dict | None, t) -> str:
    """Write one cell as table text; a valid add_numbers proposal is executed once on the real code."""
    if proposal is None:
        text = response.get("choices", [{}])[0].get("message", {}).get("content")
        return t.cell_no_call.format(text=text if isinstance(text, str) else t.value_no_text)
    cell = t.cell_call.format(name=proposal["name"], arguments=json.dumps(proposal["arguments"], ensure_ascii=False))
    # The allowlist holds this one pure function; a wrong name or non-object arguments are only recorded.
    if proposal["name"] == "add_numbers" and isinstance(proposal["arguments"], dict):
        # The model proposed this call: execute_proposal records it as the model's tool_call, with its own id.
        result = context.execute_proposal(proposal["call"], {"add_numbers": partial(add_numbers, t)})
        # The value the code returned, not the one the description promised: the misleading description shows here.
        cell += t.cell_returned.format(value=result.get("result") if result.get("ok") else result.get("error"))
    return cell


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    if context.inputs["scenario"] == "tool_matrix":
        return run_matrix(context, t)
    return run_pair(context, t)


def _report_pair(context: RunContext, scenario: str, rows: list[dict]) -> None:
    """Publish the paired report (lesson.report): two screenings, the fixed conditions and the raw outputs."""
    t = texts_for(context.locale)
    context.emit("lesson.report", {
        "title": t.pair_report_title, "summary": t.pair_report_summary,
        "checks": [{"label": t.check_screen.format(label=row["label"]), "passed": row["passed"], "detail": row["detail"]}
                   for row in rows],
        "metrics": [{"label": t.label_same_model, "value": context.model}, {"label": t.label_model_calls, "value": 2},
                    {"label": t.label_budget, "value": context.max_model_calls}, {"label": t.label_temperature, "value": 0},
                    {"label": t.label_sample, "value": context.inputs["sample_label"]},
                    {"label": t.label_note, "value": context.question or t.value_empty},
                    {"label": t.label_changed,
                     "value": "function.description" if scenario == "tool_description" else t.changed_system_rule}],
        "table": {"columns": list(t.pair_columns),
                  "rows": [[row["label"], row["prompt"], row["answer"], t.value_hit if row["passed"] else t.value_miss]
                           for row in rows]},
    })


def _report_matrix(context: RunContext, checks: list[dict], rows: list[list], calls: int) -> None:
    """Publish the matrix report (lesson.report): six verdicts and a table with proposals next to real return values."""
    t = texts_for(context.locale)
    context.emit("lesson.report", {
        "title": t.matrix_report_title, "summary": t.matrix_report_summary,
        "checks": checks,
        "metrics": [{"label": t.label_same_model, "value": context.model}, {"label": t.label_model_calls, "value": calls},
                    {"label": t.label_cells_passed, "value": sum(item["passed"] for item in checks)},
                    {"label": t.label_sample, "value": context.inputs["sample_label"]},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": [t.matrix_column_description,
                              *(t.matrix_column_probe.format(probe=t.probe_labels[probe], task=t.probes[probe])
                                for probe in PROBE_EXPECTED)],
                  "rows": rows},
    })
