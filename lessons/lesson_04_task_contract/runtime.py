"""Task card and independent acceptance: check the executor's completion claim against the tool evidence recorded in this run.

This lesson does not call a model. The executor is a fixed script inside the runner, and
the runner injects every fault; the acceptance rule is the same in every scenario, only
the evidence changes.
"""
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_04_task_contract.locales import texts_for


class Inputs(LessonInputs):
    scenario: Literal["normal", "missing_evidence", "wrong_result", "claim_mismatch", "goal_loop"] = "normal"
    # No default: the preset in lesson.json supplies the claim in the run's language.
    claim: str = Field(min_length=1, max_length=120)
    max_attempts: int = Field(default=3, ge=1, le=3)


INPUT_MODEL = Inputs
# The task card (t.task_card) is written before the run; acceptance trusts only the card,
# and nothing the executor says afterwards can change it. These are its checkable values.
EXPECTED_ARGUMENTS = {"a": 19, "b": 23}
EXPECTED = 42


def add_numbers(a: int, b: int) -> int:
    return a + b


def verify(claim: dict, evidence: dict[str, dict], t) -> list[dict]:
    """Check the completion claim against the tool results recorded in this run; the claimed answer is only compared, never trusted."""
    # Look for evidence only through evidence_ref: a call not recorded in this run is no evidence.
    record = evidence.get(claim.get("evidence_ref") or "")
    result = record["result"] if record else None
    ok = bool(result and result.get("ok"))
    value = result.get("result") if ok else None
    # The task card's input_scope allows only 19 and 23: a call with other numbers that
    # happens to return 42 must not pass.
    arguments = record.get("arguments") if record else None
    shown = t.arguments_format.format(**arguments) if arguments else t.value_none
    return [
        {"label": t.check_ended, "passed": True, "detail": t.detail_ended},
        {"label": t.check_referenced, "passed": record is not None,
         "detail": t.detail_referenced if record else t.detail_not_referenced},
        {"label": t.check_tool_ok, "passed": ok, "detail": t.detail_tool_ok if ok else t.detail_tool_not_ok},
        {"label": t.check_arguments, "passed": arguments == EXPECTED_ARGUMENTS,
         "detail": t.detail_expected.format(expected=t.arguments_format.format(**EXPECTED_ARGUMENTS), actual=shown)},
        {"label": t.check_value, "passed": value == EXPECTED,
         "detail": t.detail_expected.format(expected=EXPECTED, actual=value if ok else t.value_none)},
        # Compare claim and evidence on their own: the reference and the evidence can be right
        # while the number in the claim was written separately.
        {"label": t.check_consistent, "passed": ok and claim.get("answer") == value,
         "detail": t.detail_consistent.format(claimed=claim.get("answer"), actual=value if ok else t.value_none)},
    ]


def accepted(checks: list[dict]) -> bool:
    # Skip the first check, "the run has finished": finishing and passing are two different things.
    return all(item["passed"] for item in checks[1:])


def _attempt(context: RunContext, scenario: str, attempt: int, evidence: dict[str, dict]) -> dict:
    """One attempt by the executor: a fixed script hands in the claim instead of an agent; faults come from the runner, not a model."""
    if scenario == "missing_evidence":
        # A claim without any tool call: the answer happens to be right, but there is nothing to check.
        return {"status": "done", "answer": EXPECTED, "evidence_ref": None, "summary": context.inputs["claim"]}
    # goal_loop fails only on attempt 1 and redoes the task card on retry; a real goal loop needs a model that reads the reasons.
    wrong = scenario in ("wrong_result", "claim_mismatch") or (scenario == "goal_loop" and attempt == 1)
    call_id = f"task_add_{attempt}"
    arguments = {"a": 19, "b": 22 if wrong else 23}
    result = context.call_tool("add_numbers", arguments, {"add_numbers": add_numbers},
                               round_number=attempt, call_id=call_id)
    evidence[call_id] = {"arguments": arguments, "result": result}
    # claim_mismatch: the executor reports 42 whatever the tool returned, a claim that only reports good news.
    answer = EXPECTED if scenario == "claim_mismatch" else result.get("result")
    return {"status": "done", "answer": answer, "evidence_ref": call_id, "summary": context.inputs["claim"]}


def run(context: RunContext) -> str:
    """Execute against the task card and accept; goal_loop retries on failure and stops on a pass or at the limit. The retry is a fixed script; reasons are only recorded."""
    t = texts_for(context.locale)
    scenario = context.inputs["scenario"]
    # Only the goal loop may try several times; every other scenario runs once, so each fault shows on its own.
    limit = context.inputs["max_attempts"] if scenario == "goal_loop" else 1
    # The stop condition is part of the contract: the goal loop writes its attempt limit into the stop field.
    card = {**t.task_card, "stop": t.stop_with_limit.format(limit=limit)} if scenario == "goal_loop" else t.task_card
    context.emit("lesson.task_card", card)
    evidence: dict[str, dict] = {}
    history, checks = [], []
    for attempt in range(1, limit + 1):
        context.check_cancelled()
        # 1. Execute: the executor hands in a completion claim; the tool results it produced go into evidence.
        claim = _attempt(context, scenario, attempt, evidence)
        context.emit("lesson.completion_claim", {"attempt": attempt, **claim}, attempt)
        # 2. Accept: the validator is independent of the executor and reads only the referenced evidence and the card.
        checks = verify(claim, evidence, t)
        passed = accepted(checks)
        reasons = [t.reason.format(label=item["label"], detail=item["detail"]) for item in checks[1:] if not item["passed"]]
        # 3. Decide the next step and record why: this executor is a fixed script and ignores the reasons; a real goal loop hands them back.
        if scenario == "goal_loop":
            context.emit("lesson.goal_check", {
                "attempt": attempt, "max_attempts": limit, "passed": passed, "reasons": reasons,
                "next": "stop" if passed or attempt == limit else "retry"}, attempt)
        history.append([attempt, claim["answer"], _evidence_value(evidence, claim, t),
                        t.verdict_passed if passed else t.verdict_failed,
                        t.reason_separator.join(reasons) or t.all_passed])
        # 4. Stop on a pass instead of using up the remaining attempts; otherwise go on until the limit.
        if passed:
            break
    ok = accepted(checks)
    _report(context, scenario, limit, checks, history, len(evidence))
    if ok:
        return t.answer_passed.format(attempts=len(history))
    if scenario == "goal_loop":
        return t.answer_limit.format(attempts=len(history))
    return t.answer_failed


def _evidence_value(evidence: dict[str, dict], claim: dict, t):
    record = evidence.get(claim.get("evidence_ref") or "")
    if not record or not record["result"].get("ok"):
        return t.value_none
    return record["result"].get("result")


def _report(context: RunContext, scenario: str, limit: int, checks: list[dict], history: list[list],
            tool_calls: int) -> None:
    """Publish the lab report (lesson.report): the checks, the metrics and one row per attempt."""
    t = texts_for(context.locale)
    ok = accepted(checks)
    metrics = [{"label": t.label_tool_calls, "value": tool_calls},
               {"label": t.label_scenario, "value": scenario},
               {"label": t.label_note, "value": context.question or t.value_empty}]
    if scenario == "goal_loop":
        metrics[1:1] = [{"label": t.label_attempts, "value": len(history)}, {"label": t.label_limit, "value": limit},
                        {"label": t.label_stop_reason, "value": t.stop_passed if ok else t.stop_limit}]
    context.emit("lesson.report", {
        "title": t.report_title, "summary": t.summary_passed if ok else t.summary_failed,
        "checks": checks,
        "metrics": metrics,
        "table": {"columns": list(t.columns), "rows": history},
    })
