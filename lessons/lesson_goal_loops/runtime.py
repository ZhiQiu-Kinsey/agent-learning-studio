"""Goal loops: after every round an independent goal evaluation decides whether to continue, finish or give up.

The worker is a model with one tool, read_note. Each round it reads the notes it wants and hands in
a notice card together with a completion claim (status). A program, evaluate_goal, judges the card
against the completion condition using only the notes read in this run; the claim is recorded and
compared, never trusted. Loop budgets (rounds, model calls, seconds) and abandon rules (unreachable,
no progress, repeated failure) end the loop with one of three outcomes: complete, abandoned or
budget_exhausted. The shape of the loop (a separate evaluator at the stop boundary, ok and impossible
verdicts, a cap on consecutive blocked turns) follows learn-claude-code s17_goal_loop (MIT); the task,
the program evaluator, the progress rules and the experiments are written by this project.
"""
import json
import re
import time
from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_goal_loops.locales import Texts, texts_for


class Inputs(LessonInputs):
    goal: Literal["notice", "notice_with_phone"] = "notice"
    worker_style: Literal["careful", "hasty"] = "careful"
    max_rounds: int = Field(default=5, ge=1, le=8)
    max_model_calls: int = Field(default=12, ge=3, le=20)
    max_seconds: int = Field(default=180, ge=10, le=600)
    max_stall: int = Field(default=2, ge=1, le=4)
    repeat_limit: int = Field(default=2, ge=2, le=4)


INPUT_MODEL = Inputs
# The material the worker may read; titles and texts are runtime text (t.note_titles, t.notes).
NOTES = ("schedule", "booking", "speaker", "minutes")
# Model calls one round may use: read, maybe read again, then hand in the card.
ROUND_STEPS = 3
# Tests replace the clock; the time budget only needs differences between two readings.
clock = time.monotonic


@dataclass(frozen=True)
class Criterion:
    """One checkable part of the goal: the field, the shape of a value, the notes that count as its source."""
    field: str
    pattern: str
    sources: tuple[str, ...]


# The completion condition, fixed before the run. The lookarounds keep "B204" from matching inside a longer code.
CRITERIA = {c.field: c for c in (
    Criterion("date", r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)", ("schedule",)),
    Criterion("room", r"(?<![A-Za-z0-9])[A-Z]\d{3}(?!\d)", ("booking",)),
    Criterion("start_time", r"(?<!\d)\d{2}:\d{2}(?!\d)", ("speaker",)),
    Criterion("contact_phone", r"(?<!\d)\d{3}-\d{4}-\d{4}(?!\d)", NOTES),  # any note may be the source
)}
GOALS = {"notice": ("date", "room", "start_time"),
         "notice_with_phone": ("date", "room", "start_time", "contact_phone")}
CLAIMS = ("done", "continue", "impossible")
# The verdict each claim would agree with; anything else is a disagreement worth recording.
AGREES = {"done": "complete", "continue": "continue", "impossible": "unreachable"}


def evaluate_goal(t: Texts, goal: str, card: dict, evidence: dict[str, str]) -> dict:
    """Judge the card by the completion condition; reads only the card and the notes read in this run."""
    checks = []
    for name in GOALS[goal]:
        criterion = CRITERIA[name]
        value = card.get(name, "")
        read = [note for note in criterion.sources if note in evidence]
        unread = [note for note in criterion.sources if note not in evidence]
        # Candidates: values of the right shape that really appear in a source note read so far.
        found = {match for note in read for match in re.findall(criterion.pattern, evidence[note])}
        suffix = t.detail_unread.format(notes=t.list_separator.join(unread)) if unread else ""
        if value and value in found:
            status, detail = "pass", t.detail_pass.format(value=value)
        elif not unread and not found:
            # Every allowed source has been read and none holds such a value: no round can fill this field.
            status, detail = "unreachable", t.detail_unreachable.format(count=len(read))
        elif not value:
            status, detail = "fail", t.detail_empty + suffix
        else:
            status, detail = "fail", t.detail_unsupported.format(value=value) + suffix
        checks.append({"id": name, "status": status, "value": value, "sources_read": read, "detail": detail})
    passed = sum(check["status"] == "pass" for check in checks)
    if passed == len(checks):
        verdict = "complete"
    elif any(check["status"] == "unreachable" for check in checks):
        verdict = "unreachable"
    else:
        verdict = "continue"
    return {"verdict": verdict, "passed": passed, "total": len(checks), "checks": checks}


@dataclass
class Progress:
    """What the abandon rules remember between rounds: best score so far, rounds without gain, the last failure."""
    best: int = 0
    stall: int = 0
    repeats: int = 0
    last_failure: tuple | None = None

    def update(self, evaluation: dict) -> None:
        # Progress means more checks pass than ever before; a different wrong value is not progress.
        if evaluation["passed"] > self.best:
            self.best, self.stall = evaluation["passed"], 0
        else:
            self.stall += 1
        # A failure is the same when the same checks fail with the same status and the same value.
        failure = tuple((c["id"], c["status"], c["value"]) for c in evaluation["checks"] if c["status"] != "pass")
        self.repeats = self.repeats + 1 if failure and failure == self.last_failure else 1
        self.last_failure = failure


@dataclass
class Budget:
    """What one loop has spent; the limits live in Inputs."""
    started: float
    rounds: int = 0
    calls: int = 0

    def seconds(self) -> float:
        return round(clock() - self.started, 1)


def decide(evaluation: dict, progress: Progress, budget: Budget, values: Inputs) -> tuple[str, str]:
    """The next step after a round, as (decision, reason code): goal verdicts first, then abandon rules, then budgets."""
    if evaluation["verdict"] == "complete":
        return "complete", "goal_met"
    if evaluation["verdict"] == "unreachable":
        return "abandoned", "unreachable"
    if progress.repeats >= values.repeat_limit:
        return "abandoned", "repeated_failure"
    if progress.stall >= values.max_stall:
        return "abandoned", "no_progress"
    # Budgets are checked before a round starts, never in the middle of one: a round needs up to ROUND_STEPS calls.
    if budget.rounds >= values.max_rounds:
        return "budget_exhausted", "max_rounds"
    if values.max_model_calls - budget.calls < ROUND_STEPS:
        return "budget_exhausted", "max_model_calls"
    if budget.seconds() >= values.max_seconds:
        return "budget_exhausted", "max_seconds"
    return "continue", "keep_going"


def tool_definition(t: Texts) -> dict:
    """The only tool. Names are code; descriptions come in the run's language."""
    return {"type": "function", "function": {
        "name": "read_note", "description": t.tool_description,
        "parameters": {"type": "object", "properties": {
            "note_id": {"type": "string", "enum": list(NOTES), "description": t.tool_note_id}},
            "required": ["note_id"], "additionalProperties": False}}}


def make_reader(t: Texts):
    def read_note(note_id):
        if note_id not in NOTES:
            raise ValueError(t.unknown_note.format(note_id=note_id, notes=t.list_separator.join(NOTES)))
        return {"note_id": note_id, "title": t.note_titles[note_id], "text": t.notes[note_id]}
    return {"read_note": read_note}


def extract_json(t: Texts, content: str) -> dict:
    """Read the first JSON object in a reply; text or a code fence around it is allowed, nothing else is repaired."""
    start = content.find("{")
    if start < 0:
        raise ValueError(t.no_json_object)
    value, _ = json.JSONDecoder().raw_decode(content[start:])
    if not isinstance(value, dict):
        raise ValueError(t.no_json_object)
    return value


def read_submission(t: Texts, goal: str, content: str | None, card: dict) -> dict:
    """The worker's card and claim. A broken reply keeps the previous card and records the claim as invalid."""
    if content is None:
        return {"card": card, "status": "invalid", "note": "", "parse_error": t.no_submission.format(steps=ROUND_STEPS)}
    try:
        value = extract_json(t, content)
        submitted = value.get("card")
        if not isinstance(submitted, dict):
            raise ValueError(t.card_not_object)
    except ValueError as error:
        return {"card": card, "status": "invalid", "note": "", "parse_error": str(error)}
    # Only the goal's fields count; values are compared as trimmed text, never repaired.
    new_card = {name: str(submitted.get(name) or "").strip() for name in GOALS[goal]}
    status = value.get("status") if value.get("status") in CLAIMS else "invalid"
    note = value.get("note") if isinstance(value.get("note"), str) else ""
    return {"card": new_card, "status": status, "note": note, "parse_error": None}


class Worker:
    """The executor: one conversation across all rounds, the way a goal loop keeps working in the same session."""

    def __init__(self, context: RunContext, t: Texts, values: Inputs, budget: Budget):
        self.context, self.t, self.budget = context, t, budget
        self.tools = make_reader(t)
        self.usage: list[int | None] = []
        self.messages = [{"role": "system", "content": t.worker_system[values.worker_style]},
                         {"role": "user", "content": task_message(t, values.goal)}]

    def ask(self) -> dict:
        self.budget.calls += 1
        response = self.context.complete({"messages": self.messages, "tools": [tool_definition(self.t)],
                                          "tool_choice": "auto", "temperature": 0}, self.budget.calls)
        usage = response.get("usage")
        total = usage.get("total_tokens") if isinstance(usage, dict) else None
        self.usage.append(total if isinstance(total, int) else None)
        return response["choices"][0].get("message") or {}

    def work_round(self, evidence: dict[str, str], read_order: list[str]) -> str | None:
        """One turn: read notes until the model answers without a tool call; None if it never hands in."""
        for _ in range(ROUND_STEPS):
            message = self.ask()
            calls = message.get("tool_calls") or []
            if not calls:
                content = message.get("content") if isinstance(message.get("content"), str) else ""
                self.messages.append({"role": "assistant", "content": content})
                return content
            self.messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": calls})
            for call in calls:
                result = self.context.execute_proposal(call, self.tools)
                # Evidence is exactly what the tool returned in this run; the evaluator reads nothing else.
                if result.get("ok"):
                    note = result["result"]
                    evidence[note["note_id"]] = note["text"]
                    if note["note_id"] not in read_order:
                        read_order.append(note["note_id"])
                self.messages.append({"role": "tool", "tool_call_id": call["id"],
                                      "content": json.dumps(result, ensure_ascii=False)})
        return None


def task_message(t: Texts, goal: str) -> str:
    """The first user message: the goal, its completion condition and the list of notes."""
    condition = "\n".join(t.condition_line.format(
        field=name, label=t.field_labels[name],
        sources=t.any_note if CRITERIA[name].sources == NOTES else t.list_separator.join(CRITERIA[name].sources))
        for name in GOALS[goal])
    notes = "\n".join(t.note_line.format(id=note, title=t.note_titles[note]) for note in NOTES)
    return t.task.format(goal=t.goal_names[goal], fields=", ".join(GOALS[goal]), condition=condition, notes=notes)


def run(context: RunContext) -> str:
    """The goal loop: work one round, evaluate, record why, then continue or stop with one of three outcomes."""
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    budget = Budget(started=clock())
    context.emit("lesson.task_card", task_card(t, values))
    worker, progress = Worker(context, t, values, budget), Progress()
    evidence, read_order, card, history, claims = {}, [], {}, [], []
    decision, reason_code = "continue", "keep_going"
    while decision == "continue":
        context.check_cancelled()
        budget.rounds += 1
        # 1. Work: the worker reads notes and hands in a card with its own claim.
        before = len(read_order)
        submission = read_submission(t, values.goal, worker.work_round(evidence, read_order), card)
        card = submission["card"]
        context.emit("lesson.completion_claim", {"loop_round": budget.rounds, **submission}, budget.calls)
        # 2. Evaluate: the program reads the card and the notes read so far, never the claim.
        evaluation = evaluate_goal(t, values.goal, card, evidence)
        progress.update(evaluation)
        # 3. Decide: goal verdict, abandon rules, budgets, in that order.
        decision, reason_code = decide(evaluation, progress, budget, values)
        reason = reason_text(t, reason_code, evaluation, progress, budget, values)
        claims.append((submission["status"], AGREES.get(submission["status"]) == evaluation["verdict"]))
        # 4. Record: the evaluation record says what was read, what was judged, and why the loop goes on or stops.
        context.emit("lesson.goal_evaluation", record(budget, values, evaluation, progress, submission,
                                                      read_order, decision, reason_code, reason), budget.calls)
        history.append([budget.rounds, t.list_separator.join(read_order[before:]) or "—", submission["status"],
                        f"{evaluation['passed']}/{evaluation['total']}", t.verdicts[evaluation["verdict"]],
                        t.decisions[decision], reason])
        # 5. Continue: the evaluator's reasons go back into the same conversation as the next user message.
        if decision == "continue":
            worker.messages.append({"role": "user", "content": feedback(t, budget.rounds, evaluation, submission)})
    return _report(context, t, values, decision, reason, evaluation, history, claims, read_order, budget, worker)


def reason_text(t: Texts, code: str, evaluation: dict, progress: Progress, budget: Budget, values: Inputs) -> str:
    unreachable = [c["id"] for c in evaluation["checks"] if c["status"] == "unreachable"]
    return t.reasons[code].format(
        fields=t.list_separator.join(unreachable), count=progress.repeats, stall=progress.stall,
        limit_rounds=values.max_rounds, left=values.max_model_calls - budget.calls, need=ROUND_STEPS,
        seconds=budget.seconds(), limit_seconds=values.max_seconds,
        passed=evaluation["passed"], total=evaluation["total"])


def record(budget: Budget, values: Inputs, evaluation: dict, progress: Progress, submission: dict,
           read_order: list[str], decision: str, reason_code: str, reason: str) -> dict:
    """The evaluation record of one round (lesson.goal_evaluation)."""
    return {
        "loop_round": budget.rounds,
        "evidence": {"notes_read": list(read_order), "card": dict(submission["card"])},
        "claim": submission["status"],
        "verdict": evaluation["verdict"], "passed": evaluation["passed"], "total": evaluation["total"],
        "checks": evaluation["checks"],
        "claim_agrees": AGREES.get(submission["status"]) == evaluation["verdict"],
        "progress": {"best": progress.best, "stall": progress.stall, "repeats": progress.repeats},
        "budget": {"rounds": budget.rounds, "max_rounds": values.max_rounds, "model_calls": budget.calls,
                   "max_model_calls": values.max_model_calls, "seconds": budget.seconds(),
                   "max_seconds": values.max_seconds},
        "decision": decision, "reason_code": reason_code, "reason": reason,
    }


def feedback(t: Texts, loop_round: int, evaluation: dict, submission: dict) -> str:
    issues = "\n".join(t.issue_line.format(field=c["id"], detail=c["detail"])
                       for c in evaluation["checks"] if c["status"] != "pass")
    text = t.feedback.format(loop_round=loop_round, passed=evaluation["passed"], total=evaluation["total"],
                             issues=issues)
    if submission["status"] in ("done", "impossible"):
        text += t.feedback_claim.format(claim=submission["status"], verdict=t.verdicts[evaluation["verdict"]])
    return text


def task_card(t: Texts, values: Inputs) -> dict:
    return {"goal": t.card_goal.format(goal=t.goal_names[values.goal]),
            "input_scope": t.card_input_scope,
            "output": t.card_output.format(fields=", ".join(GOALS[values.goal])),
            "evidence": t.card_evidence,
            "failure": t.card_failure.format(stall=values.max_stall, repeats=values.repeat_limit),
            "stop": t.card_stop.format(rounds=values.max_rounds, calls=values.max_model_calls,
                                       seconds=values.max_seconds)}


def _tokens(t: Texts, usage: list[int | None]):
    reported = [value for value in usage if value is not None]
    if not reported:
        return t.value_not_reported
    missing = len(usage) - len(reported)
    return sum(reported) if not missing else t.tokens_partly_reported.format(total=sum(reported), missing=missing)


def _report(context: RunContext, t: Texts, values: Inputs, decision: str, reason: str, evaluation: dict,
            history: list[list], claims: list[tuple[str, bool]], read_order: list[str], budget: Budget,
            worker: Worker) -> str:
    """Emit the lab report (lesson.report) and return the final answer; the outcome is the decision, never the claim."""
    checks = [{"id": f"field_{c['id']}", "label": t.field_labels[c["id"]], "passed": c["status"] == "pass",
               "detail": c["detail"]} for c in evaluation["checks"]]
    context.emit("lesson.report", {
        "title": t.report_title, "summary": t.report_summary, "checks": checks,
        "metrics": [{"id": "outcome", "label": t.label_outcome, "value": t.decisions[decision]},
                    {"id": "stop_reason", "label": t.label_stop_reason, "value": reason},
                    {"id": "progress", "label": t.label_progress,
                     "value": f"{evaluation['passed']}/{evaluation['total']}"},
                    {"id": "rounds", "label": t.label_rounds, "value": budget.rounds},
                    {"label": t.label_max_rounds, "value": values.max_rounds},
                    {"id": "model_calls", "label": t.label_model_calls, "value": budget.calls},
                    {"id": "total_tokens", "label": t.label_total_tokens, "value": _tokens(t, worker.usage)},
                    {"id": "claims_done", "label": t.label_claims_done,
                     "value": sum(status == "done" for status, _ in claims)},
                    {"id": "claims_disagree", "label": t.label_claims_disagree,
                     "value": sum(not agrees for _, agrees in claims)},
                    {"label": t.label_notes_read, "value": t.list_separator.join(read_order) or t.value_none},
                    {"label": t.label_seconds, "value": budget.seconds()},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.table_columns), "rows": history},
    })
    card = json.dumps({c["id"]: c["value"] for c in evaluation["checks"]}, ensure_ascii=False)
    return t.answers[decision].format(reason=reason, passed=evaluation["passed"], total=evaluation["total"],
                                      rounds=budget.rounds, card=card)
