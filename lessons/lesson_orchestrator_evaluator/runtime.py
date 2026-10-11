"""Orchestrator-workers and evaluator-optimizer: one quiz-writing task, compared with a single call, counting the extra calls and usage.

The split into two patterns follows claude-cookbooks patterns/agents (MIT). There the orchestrator actually runs the workers
one after another and the revision loop has no limit; here the workers run in parallel and the loop must have a limit,
max_iters, and stops early when a revision comes back unchanged. The task, format checks and experiments are written by this project.
Every text that reaches the model or an event is in locales/, one catalog per run language.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_orchestrator_evaluator.locales import Texts, texts_for


class Inputs(LessonInputs):
    pattern: Literal["single", "orchestrator", "evaluator"] = "orchestrator"
    max_iters: int = Field(default=3, ge=1, le=3)


INPUT_MODEL = Inputs
# The three lessons, keyed by slug: displayed lesson numbers change when lessons are inserted, slugs do not.
# Their key points are in t.notes, the task in t.task.
LESSONS = ("messages-context", "application-state", "context-budget")
EVALUATED = "context-budget"  # evaluator-optimizer writes a question for this lesson only
MAX_WORKERS = 4


def extract_json(t: Texts, content: str):
    """Read the first JSON value in a reply; text or a code fence around it is allowed, nothing else is repaired."""
    starts = [index for index in (content.find("{"), content.find("[")) if index >= 0]
    if not starts:
        raise ValueError(t.no_json_found)
    value, _ = json.JSONDecoder().raw_decode(content[min(starts):])
    return value


def check_question(t: Texts, value) -> list[str]:
    """The format checks a program can decide; whether the question is good is left to the reviewer."""
    if not isinstance(value, dict):
        return [t.not_an_object]
    problems = []
    if not isinstance(value.get("question"), str) or not value["question"].strip():
        problems.append(t.missing_question)
    options = value.get("options")
    if not isinstance(options, list) or len(options) != 4 or not all(isinstance(o, str) and o.strip() for o in options):
        problems.append(t.options_invalid)
    elif len(set(options)) != 4:
        problems.append(t.options_duplicate)
    # bool is a subclass of int, hence type(...) is int: answer written as true is a format error too.
    if type(value.get("answer")) is not int or not 0 <= value["answer"] <= 3:
        problems.append(t.answer_invalid)
    if not isinstance(value.get("explanation"), str) or not value["explanation"].strip():
        problems.append(t.missing_explanation)
    return problems


def _parse_question(t: Texts, output: str) -> tuple[object, list[str]]:
    try:
        question = extract_json(t, output)
    except ValueError:
        question = None
    return question, check_question(t, question) if question is not None else [t.no_json]


class Ledger:
    """Call ledger: one row per model call with the role and the total_tokens the provider reported; None when not reported, never estimated."""

    def __init__(self, context: RunContext, t: Texts):
        self.context = context
        self.t = t
        self.rows: list[dict] = []

    def call(self, role: str, system: str, user: str, round_number: int, branch: str | None = None) -> str:
        started = time.perf_counter()
        response = self.context.complete({"messages": [{"role": "system", "content": system},
                                                       {"role": "user", "content": user}], "temperature": 0},
                                         round_number, branch=branch)
        usage = response.get("usage")
        tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
        self.rows.append({"role": self.t.roles[role], "branch": branch, "round": round_number,
                          "tokens": tokens if isinstance(tokens, int) else None,
                          "ms": round((time.perf_counter() - started) * 1000)})
        content = response["choices"][0].get("message", {}).get("content")
        return content if isinstance(content, str) else ""

    def total(self) -> str | int:
        reported = [row["tokens"] for row in self.rows if row["tokens"] is not None]
        missing = len(self.rows) - len(reported)
        if not reported:
            return self.t.value_not_reported
        return sum(reported) if not missing else self.t.tokens_partly_reported.format(total=sum(reported), missing=missing)


def run_single(context: RunContext, t: Texts, ledger: Ledger) -> tuple[dict, list]:
    """Baseline: one request writes all three questions, then each gets the same format check."""
    notes = json.dumps({lesson: t.notes[lesson] for lesson in LESSONS}, ensure_ascii=False)
    content = ledger.call("single", t.single_system, t.single_request.format(task=t.task, notes=notes), 1)
    try:
        value = extract_json(t, content)
        questions = value if isinstance(value, list) else []
    except ValueError:
        questions = []
    results = {}
    for index, lesson in enumerate(LESSONS):
        item = questions[index] if index < len(questions) else None
        results[lesson] = {"question": item, "problems": check_question(t, item) if item is not None else [t.missing_item]}
    return results, [[lesson, t.problem_separator.join(result["problems"]) or t.format_ok]
                     for lesson, result in results.items()]


def valid_subtasks(plan) -> list[dict] | None:
    """The orchestrator's subtasks pass a program check first: count, unique ids, lesson among the three, an instruction; None if not."""
    subtasks = plan.get("subtasks") if isinstance(plan, dict) else None
    valid = (isinstance(subtasks, list) and 0 < len(subtasks) <= MAX_WORKERS
             and all(isinstance(s, dict) and s.get("lesson") in LESSONS and isinstance(s.get("id"), str)
                     and isinstance(s.get("instruction"), str) for s in subtasks)
             and len({s["id"] for s in subtasks}) == len(subtasks))
    return subtasks if valid else None


def run_orchestrator(context: RunContext, t: Texts, ledger: Ledger) -> tuple[dict, list]:
    """Orchestrator-workers: one request splits the task, then one worker per subtask runs in parallel, 1 + N calls in total."""
    # 1. Orchestrate: the orchestrator only splits the task and writes no questions.
    content = ledger.call("orchestrator", t.orchestrator_system, t.task, 1)
    try:
        subtasks = valid_subtasks(extract_json(t, content))
    except ValueError:
        subtasks = None
    # 2. Validate: a malformed subtask list dispatches no workers; the raw reply is recorded.
    if subtasks is None:
        context.emit("lesson.plan_error", {"error": t.plan_error, "raw": content}, 1)
        return {}, [[t.roles["orchestrator"], t.no_workers]]
    steps = [{"id": s["id"], "content": t.plan_step.format(lesson=s["lesson"], instruction=s["instruction"]),
              "status": "in_progress"} for s in subtasks]
    context.emit("lesson.plan", {"version": 1, "event": "created", "reason": t.plan_reason, "diff": {}, "steps": steps}, 1)

    def work(subtask: dict) -> tuple[dict, str]:
        # A worker gets only its own instruction and that lesson's key point: not the whole task, not the other subtasks.
        user = t.worker_request.format(instruction=subtask["instruction"], note=t.notes[subtask["lesson"]])
        return subtask, ledger.call("worker", t.worker_system, user, 2, branch=subtask["id"])

    # 3. Dispatch: workers run in parallel, each request with a branch, on one shared call budget.
    with ThreadPoolExecutor(max_workers=len(subtasks)) as pool:
        outputs = list(pool.map(work, subtasks))
    # 4. Collect: each question gets the format check; each plan item is marked done or failed.
    results, rows = _collect(context, t, outputs, steps)
    context.emit("lesson.plan", {"version": 1, "event": "progress", "reason": "", "diff": {}, "steps": steps}, 2)
    return results, rows


def _collect(context: RunContext, t: Texts, outputs: list[tuple[dict, str]], steps: list[dict]) -> tuple[dict, list]:
    """Check each returned question, emit lesson.worker, and mark the matching plan item done or failed."""
    results, rows = {}, []
    for subtask, output in outputs:
        question, problems = _parse_question(t, output)
        # When two workers got the same lesson, only the first question counts.
        results.setdefault(subtask["lesson"], {"question": question, "problems": problems})
        context.emit("lesson.worker", {"id": subtask["id"], "lesson": subtask["lesson"], "problems": problems,
                                       "output": output}, 2)
        for step in steps:
            if step["id"] == subtask["id"]:
                step["status"] = "done" if not problems else "failed"
        rows.append([subtask["id"], t.problem_separator.join(problems) or t.format_ok])
    return results, rows


def review(ledger: Ledger, lesson: str, output: str) -> tuple[str, list[str]]:
    """Ask the evaluator to grade one question by the rubric; only pass or revise is a verdict, anything else is malformed."""
    t = ledger.t
    content = ledger.call("evaluator", t.evaluator_system, t.review_request.format(note=t.notes[lesson], output=output),
                          len(ledger.rows) + 1)
    try:
        parsed = extract_json(t, content)
    except ValueError:
        return "invalid", []
    if not isinstance(parsed, dict):
        return "invalid", []
    verdict = parsed.get("verdict") if parsed.get("verdict") in ("pass", "revise") else "invalid"
    feedback = [str(item) for item in parsed.get("feedback", [])] if isinstance(parsed.get("feedback"), list) else []
    return verdict, feedback


def run_evaluator(context: RunContext, t: Texts, ledger: Ledger, max_iters: int) -> tuple[dict, list, str]:
    """Evaluator-optimizer: the generator writes, the evaluator grades by the rubric, the generator revises; at most max_iters rounds."""
    lesson, rows, feedback, previous, previous_question = EVALUATED, [], [], None, None
    stop, question = "limit", None
    for iteration in range(1, max_iters + 1):
        # 1. Generate: round 1 gets only the key point; later rounds also get the previous version and the feedback.
        if previous is None:
            user = t.generator_request.format(lesson=lesson, note=t.notes[lesson])
        else:
            user = t.revision_request.format(lesson=lesson, note=t.notes[lesson], previous=previous,
                                             feedback=json.dumps(feedback, ensure_ascii=False))
        output = ledger.call("generator", t.worker_system, user, len(ledger.rows) + 1)
        question, problems = _parse_question(t, output)
        # Unchanged: the same question again (compared as parsed JSON; as raw text when it does not parse).
        unchanged = previous is not None and (question == previous_question if question is not None else output == previous)
        # A revision also carries revises, the version it revises; the first version has none, so no such field.
        revises = {} if previous is None else {"revises": iteration - 2}
        context.emit("lesson.draft", {"version": iteration - 1, "question": question, "previous": previous,
                                      "unchanged": unchanged, "format_problems": problems, **revises}, len(ledger.rows))
        # 2. Stop before reviewing an unchanged revision: the same input would get the same verdict again.
        if unchanged:
            stop = "unchanged"
            break
        # 3. Review: a format problem goes straight back, saving an evaluator request; only a well-formed question is graded.
        if problems:
            verdict, feedback, source = "revise", problems, "format-check"
        else:
            verdict, feedback = review(ledger, lesson, output)
            source = "evaluator"
        context.emit("lesson.review", {"iteration": iteration, "source": source, "verdict": verdict, "issues": feedback},
                     len(ledger.rows))
        rows.append([iteration, source, verdict, t.problem_separator.join(feedback) or "—"])
        # 4. Stop: the review passed, the review output was malformed, or the loop reaches max_iters by itself.
        if verdict == "pass":
            stop = "passed"
            break
        if verdict == "invalid":
            stop = "invalid"
            break
        previous, previous_question = output, question
    final = {"question": question, "problems": check_question(t, question) if question is not None else [t.no_json]}
    return {lesson: final}, rows, t.stop_reasons[stop]


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    ledger = Ledger(context, t)
    stop_reason = None
    if values.pattern == "single":
        results, rows = run_single(context, t, ledger)
        columns = t.columns_single
    elif values.pattern == "orchestrator":
        results, rows = run_orchestrator(context, t, ledger)
        columns = t.columns_orchestrator
    else:
        results, rows, stop_reason = run_evaluator(context, t, ledger, values.max_iters)
        columns = t.columns_evaluator
    expected = [EVALUATED] if values.pattern == "evaluator" else list(LESSONS)
    ok = [lesson for lesson in expected if lesson in results and not results[lesson]["problems"]]
    return _report(context, t, values.pattern, ledger, rows, list(columns), expected, ok, stop_reason)


def _report(context: RunContext, t: Texts, pattern: str, ledger: Ledger, rows: list, columns: list[str],
            expected: list[str], ok: list[str], stop_reason: str | None) -> str:
    """Emit the lab report (lesson.report) and the call ledger (lesson.cost), and return the final answer."""
    roles = dict.fromkeys(r["role"] for r in ledger.rows)
    context.emit("lesson.report", {
        "title": t.report_titles[pattern],
        "summary": t.report_summary,
        "checks": [{"label": t.check_format, "passed": len(ok) == len(expected),
                    "detail": t.check_format_detail.format(ok=len(ok), total=len(expected))}],
        "metrics": [{"id": "model_calls", "label": t.label_model_calls, "value": len(ledger.rows)},
                    {"id": "total_tokens", "label": t.label_total_tokens, "value": ledger.total()},
                    {"label": t.label_role_calls, "value": t.role_separator.join(
                        t.role_count.format(role=role, count=sum(r["role"] == role for r in ledger.rows)) for role in roles)},
                    *([{"id": "stop_reason", "label": t.label_stop_reason, "value": stop_reason}] if stop_reason else []),
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": columns, "rows": rows},
    })
    context.emit("lesson.cost", {"calls": ledger.rows, "total_tokens": ledger.total()})
    if stop_reason:
        return t.answer_with_stop.format(calls=len(ledger.rows), ok=len(ok), total=len(expected), reason=stop_reason)
    return t.answer.format(calls=len(ledger.rows), ok=len(ok), total=len(expected))
