"""Workflow patterns: prompt chaining (with gates), routing (with a fallback), parallel versus serial.

The split into three patterns follows claude-cookbooks patterns/agents/basic_workflows (MIT). That example's router
raises on an unknown label; this lesson records the raw reply and takes a fallback path instead. Tickets, gates,
timing and experiments are written by this project.
The file has one section per pattern (data, checks or parsing, the run function); report building is at the end.
Every text that reaches the model or an event is in locales/, one catalog per run language.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from course.execution import LessonInputs, RunContext
from lessons.lesson_workflow_patterns.locales import Texts, texts_for


class Inputs(LessonInputs):
    pattern: Literal["chain", "routing", "serial", "parallel"] = "routing"


INPUT_MODEL = Inputs


def _text(response: dict) -> str:
    content = response["choices"][0].get("message", {}).get("content")
    return content if isinstance(content, str) else ""


# ---------- Prompt chaining ----------
def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def gate(t: Texts, step: int, output: str) -> tuple[bool, str]:
    """The program check after each step; on failure the chain stops here and passes nothing bad on."""
    lines = _lines(output)
    if step == 0:
        ok = len(lines) == 3 and all(line.startswith("- ") for line in lines)
        return ok, (t.gate_lines_ok if ok else t.gate_lines_bad).format(count=len(lines))
    if step == 1:
        questions = [line for line in lines if line.startswith("Q: ")]
        answers = [line for line in lines if line.startswith("A: ")]
        ok = len(lines) == 6 and len(questions) == 3 and len(answers) == 3
        return ok, t.gate_qa.format(questions=len(questions), answers=len(answers), count=len(lines))
    try:
        titles = json.loads(output.strip())
    except json.JSONDecodeError:
        return False, t.gate_not_json
    limit = t.title_max_chars
    ok = isinstance(titles, list) and len(titles) == 3 and all(isinstance(x, str) and 0 < len(x) <= limit for x in titles)
    return ok, (t.gate_titles_ok if ok else t.gate_titles_bad).format(limit=limit)


def run_chain(context: RunContext, t: Texts) -> str:
    """Prompt chaining: three fixed steps; each output must pass its gate before it becomes the next input."""
    current, rows, stopped = t.chain_note, [], None
    for index, (name, instruction) in enumerate(t.chain):
        # 1. Send the request: its input is the previous step's checked output; the first step gets the raw note.
        response = context.complete({"messages": [{"role": "user", "content": f"{instruction}\n\n{current}"}],
                                     "temperature": 0}, index + 1)
        output = _text(response)
        # 2. Gate: the program checks the format; the result and the output are recorded as lesson.chain_step.
        passed, detail = gate(t, index, output)
        context.emit("lesson.chain_step", {"step": index + 1, "name": name, "gate_passed": passed,
                                           "gate_detail": detail, "output": output}, index + 1)
        rows.append([index + 1, name, t.value_passed if passed else t.value_failed, detail])
        # 3. Stop on failure; on success this step's output becomes the next step's input.
        if not passed:
            stopped = name
            break
        current = output
    _report_chain(context, t, rows, stopped)
    return t.chain_stopped.format(name=stopped) if stopped else t.chain_done.format(output=current)


# ---------- Routing ----------
LABELS = ("course", "account", "error", "other")
FALLBACK = "other"
# The author's label for each of the 20 tickets; the ticket texts are in t.tickets, one catalog per language.
GOLD = {"t01": "course", "t02": "account", "t03": "error", "t04": "other", "t05": "course",
        "t06": "account", "t07": "error", "t08": "other", "t09": "course", "t10": "account",
        "t11": "error", "t12": "other", "t13": "course", "t14": "account", "t15": "error",
        "t16": "other", "t17": "course", "t18": "account", "t19": "error", "t20": "course"}


def router_system(t: Texts) -> str:
    """The router prompt lists every label with its meaning; the labels themselves are the same in every language."""
    return t.router_system.format(labels=t.router_label_separator.join(
        t.router_label.format(key=key, name=t.label_names[key]) for key in LABELS))


def parse_label(content: str) -> tuple[str, bool]:
    """Take the label from the reply's first line; anything not in the list takes the fallback, flagged as such."""
    lines = (content or "").strip().splitlines()
    first = lines[0].strip().strip("`'\"。.").lower() if lines else ""
    return (first, False) if first in LABELS else (FALLBACK, True)


def run_routing(context: RunContext, t: Texts) -> str:
    """Routing: the model outputs only a label per ticket and the program dispatches on it; accuracy is against the author's labels."""
    pairs, rows, fallbacks = [], [], 0
    system = router_system(t)
    for index, (ticket_id, gold) in enumerate(GOLD.items(), 1):
        text = t.tickets[ticket_id]
        # 1. One request per ticket with a fixed system message; the model outputs only a label.
        response = context.complete({"messages": [{"role": "system", "content": system},
                                                  {"role": "user", "content": text}], "temperature": 0}, index)
        raw = _text(response)
        # 2. Parse the label: anything not in the list takes the fallback and the raw reply is kept; only
        #    fallback records carry fallback_reason, only misrouted ones carry misrouted.
        predicted, fallback = parse_label(raw)
        fallbacks += fallback
        context.emit("lesson.route", {"ticket": ticket_id, "gold": gold, "predicted": predicted, "raw": raw,
                                      "fallback": fallback, "correct": predicted == gold,
                                      **({"fallback_reason": t.fallback_reason} if fallback else {}),
                                      **({"misrouted": True} if predicted != gold else {})}, index)
        pairs.append((gold, predicted))
        # 3. Misrouted or fallback tickets go into the report; a label can be debatable too, so a person reviews them.
        if predicted != gold or fallback:
            rows.append([ticket_id, text, t.label_names[gold], t.label_names[predicted], raw if fallback else "—"])
    correct = sum(g == p for g, p in pairs)
    _report_routing(context, t, pairs, rows, fallbacks, correct)
    return t.routing_done.format(correct=correct, total=len(GOLD), fallbacks=fallbacks)


# ---------- Parallel and serial ----------
# Three independent restating subtasks keyed by lesson slug (texts in t.topics); in parallel the slug is also the branch.
TOPICS = ("messages-context", "application-state", "context-budget")


def run_fanout(context: RunContext, t: Texts, parallel: bool) -> str:
    """The same three independent subtasks, sent one after another or all at once; time is measured with perf_counter on the backend."""
    origin = time.perf_counter()
    spans: dict[str, dict] = {}

    def one(index: int, lesson: str) -> str:
        started = time.perf_counter()
        # In parallel all three requests are in round 1 and pair by branch; serial requests take one round each, no branch.
        response = context.complete({"messages": [{"role": "system", "content": t.summary_system},
                                                  {"role": "user", "content": t.topics[lesson]}], "temperature": 0},
                                    1 if parallel else index, branch=lesson if parallel else None)
        ended = time.perf_counter()
        spans[lesson] = {"branch": lesson, "started_ms": round((started - origin) * 1000),
                         "ended_ms": round((ended - origin) * 1000)}
        return _text(response)

    # 1. Send: in parallel a thread pool sends all three at once on one shared call budget; serial sends them in turn.
    if parallel:
        with ThreadPoolExecutor(max_workers=len(TOPICS)) as pool:
            futures = {lesson: pool.submit(one, index, lesson) for index, lesson in enumerate(TOPICS, 1)}
            outputs = {lesson: future.result() for lesson, future in futures.items()}
    else:
        outputs = {lesson: one(index, lesson) for index, lesson in enumerate(TOPICS, 1)}
    # 2. Timing: both the wall-clock time and the sum of branch durations are backend measurements; their difference is the overlap.
    wall = round((time.perf_counter() - origin) * 1000)
    branches = [{**spans[lesson], "duration_ms": spans[lesson]["ended_ms"] - spans[lesson]["started_ms"]} for lesson in TOPICS]
    total = sum(item["duration_ms"] for item in branches)
    context.emit("lesson.parallel", {"mode": "parallel" if parallel else "serial", "wall_ms": wall,
                                     "sum_of_branches_ms": total, "branches": branches})
    _report_fanout(context, t, parallel, outputs, branches, wall, total)
    return t.fanout_done.format(mode=t.fanout_names["parallel" if parallel else "serial"], wall=wall, total=total)


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    pattern = Inputs.model_validate(context.inputs).pattern
    context.check_cancelled()
    if pattern == "chain":
        return run_chain(context, t)
    if pattern == "routing":
        return run_routing(context, t)
    return run_fanout(context, t, parallel=pattern == "parallel")


# ---------- Reports ----------
def _report_chain(context: RunContext, t: Texts, rows: list[list], stopped: str | None) -> None:
    """Emit the prompt chain report (lesson.report): the gate result of each step."""
    context.emit("lesson.report", {
        "title": t.chain_title, "summary": t.chain_summary,
        "checks": [{"label": t.chain_check.format(step=row[0], name=row[1]), "passed": row[2] == t.value_passed,
                    "detail": row[3]} for row in rows],
        "metrics": [{"label": t.label_model_calls, "value": len(rows)},
                    {"label": t.label_stopped_at, "value": stopped or t.value_all_done},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.chain_columns), "rows": rows},
    })


def confusion(t: Texts, rows: list[tuple[str, str]]) -> list[list]:
    """Confusion matrix: rows are the author's labels, columns the routing results; everything off the diagonal is misrouted."""
    table = []
    for gold in LABELS:
        counts = [sum(1 for g, p in rows if g == gold and p == predicted) for predicted in LABELS]
        table.append([t.label_names[gold], *counts])
    return table


def _report_routing(context: RunContext, t: Texts, pairs: list[tuple[str, str]], rows: list[list], fallbacks: int,
                    correct: int) -> None:
    """Emit the two routing reports (lesson.report): accuracy with the misrouted tickets, and the confusion matrix."""
    context.emit("lesson.report", {
        "title": t.routing_title, "summary": t.routing_summary,
        "checks": [{"label": t.routing_check, "passed": len(pairs) == len(GOLD),
                    "detail": t.routing_check_detail.format(done=len(pairs), total=len(GOLD), fallbacks=fallbacks)}],
        "metrics": [{"label": t.label_accuracy, "value": f"{correct}/{len(GOLD)}"},
                    {"label": t.label_fallbacks, "value": fallbacks},
                    {"label": t.label_model_calls, "value": len(pairs)},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.routing_columns), "rows": rows},
    })
    context.emit("lesson.report", {
        "title": t.confusion_title, "summary": t.confusion_summary,
        "table": {"columns": [t.confusion_corner, *(t.label_names[key] for key in LABELS)], "rows": confusion(t, pairs)},
    })


def _report_fanout(context: RunContext, t: Texts, parallel: bool, outputs: dict[str, str], branches: list[dict],
                   wall: int, total: int) -> None:
    """Emit the parallel or serial report (lesson.report): wall-clock time, branch durations and answers."""
    context.emit("lesson.report", {
        "title": t.fanout_names["parallel" if parallel else "serial"],
        "summary": t.fanout_summary,
        "checks": [{"label": t.fanout_check, "passed": all(outputs.values()),
                    "detail": t.list_separator.join(lesson for lesson, text in outputs.items() if text) or t.value_none}],
        "metrics": [{"label": t.label_wall_ms, "value": wall}, {"label": t.label_sum_ms, "value": total},
                    {"label": t.label_model_calls, "value": len(outputs)},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.fanout_columns),
                  "rows": [[b["branch"], b["started_ms"], b["ended_ms"], b["duration_ms"], outputs[lesson]]
                           for lesson, b in zip(TOPICS, branches)]},
    })
