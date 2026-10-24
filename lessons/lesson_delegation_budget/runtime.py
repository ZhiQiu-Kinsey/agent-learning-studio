"""Delegation, merging and a shared budget: a coordinator hands five subtasks to isolated contexts and merges the results.

The coordinator is this program. Each subtask gets a contract (contracts.py) and one model call on its own branch; all
of them draw on one budget of calls, reported tokens and time (budget.py). Subtasks go out by priority, at most
max_parallel at a time; a subtask past its deadline is cancelled and its late response is recorded but never merged.
The merge check runs as a registered tool and lists conflicts instead of settling them. Cancellation that passes from
parent to child, the verified settle point and per-subtask budgets follow ai-agent-book chapter 10 (Apache-2.0); the
shared team clock follows the claude-cookbooks latency notebook (MIT). Every text that reaches the model or an event
is in locales/, one catalog per run language.
"""
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from functools import partial
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from course.runner import RunCancelled
from lessons.lesson_delegation_budget.budget import Scope, SharedBudget, SubtaskCancelled
from lessons.lesson_delegation_budget.contracts import (DEFAULT_DEADLINE_MS, PLAN, REQUIRED_FIELDS, Contract,
                                                        build_contracts, merge_check, parse_reply, render)
from lessons.lesson_delegation_budget.locales import Texts, texts_for


class Inputs(LessonInputs):
    # no_evidence drops the evidence requirement from the contract; the merge check still demands evidence.
    contract: Literal["full", "no_evidence"] = "full"
    budget_calls: int = Field(5, ge=1, le=5)  # lesson.json allows 5 model calls per run
    budget_tokens: int = Field(8000, ge=100, le=50000)
    run_deadline_ms: int = Field(60000, ge=100, le=300000)
    max_parallel: int = Field(3, ge=1, le=5)
    tight_subtask: Literal["none", "deadline-syllabus", "team-size", "weight", "deadline-notice",
                           "late-policy"] = "none"
    tight_deadline_ms: int = Field(50, ge=1, le=DEFAULT_DEADLINE_MS)


INPUT_MODEL = Inputs


def ask(context: RunContext, contract: Contract, scope: Scope, messages: list[dict]):
    """One subtask: one request on its own branch, holding only its contract and documents."""
    scope.check()  # a subtask cancelled before it starts never sends its request
    response = context.complete({"messages": messages, "temperature": 0}, 1, branch=contract.id)
    return response, time.perf_counter()


def dispatch(context: RunContext, t: Texts, contracts: list[Contract], budget: SharedBudget, root: Scope,
             max_parallel: int):
    """Run the subtasks by priority under one budget; return each outcome and the futures that timed out."""
    queue = sorted(contracts, key=lambda item: item.priority)  # stable: plan order breaks ties
    running, outcomes, late = {}, {}, []
    pool = ThreadPoolExecutor(max_workers=len(contracts))
    try:
        while queue or running:
            context.check_cancelled()  # the Stop button reaches the coordinator even while it waits
            # 1. Fill free slots in priority order while the shared budget still grants a call.
            while queue and len(running) < max_parallel:
                refusal = "time" if root.reason else budget.grant()
                if refusal:
                    _stop_queue(context, t, queue, refusal, budget, outcomes)
                    break
                contract, scope = queue.pop(0), root.child()
                messages, started = render(t, contract), time.perf_counter()
                deadline = min(started + contract.deadline_ms / 1000, budget.ends_at)
                _announce(context, t, contract, budget, messages, round((deadline - started) * 1000))
                running[pool.submit(ask, context, contract, scope, messages)] = (contract, scope, started, deadline)
            if not running:
                break
            # 2. Wait for the first result or the nearest deadline, whichever comes first.
            nearest = min(item[3] for item in running.values())
            wait(running, timeout=max(nearest - time.perf_counter(), 0), return_when=FIRST_COMPLETED)
            if budget.remaining_ms() <= 0:
                root.cancel("run_deadline")  # one cancel at the root reaches every running subtask
            now = time.perf_counter()
            for future, (contract, scope, started, deadline) in list(running.items()):
                done = future.done()
                finished = (future.result()[1] if future.exception() is None else now) if done else None
                if done and finished <= deadline:
                    outcomes[contract.id] = _settle(future, budget, started)
                # 3. Late, cancelled from above or past its deadline: stop waiting. A sent request cannot be recalled.
                elif done or scope.reason or now >= deadline:
                    scope.cancel(scope.reason or "deadline")
                    outcomes[contract.id] = {"status": "timed_out", "reason": scope.reason,
                                             "after_ms": round((deadline - started) * 1000)}
                    late.append((contract, future))
                else:
                    continue
                del running[future]
                _record(context, contract, outcomes[contract.id])
    finally:
        pool.shutdown(wait=True)  # wait for requests already sent, so their usage reaches the books
    return outcomes, late


def _settle(future, budget: SharedBudget, started: float) -> dict:
    """A subtask that answered in time: charge its reported usage and parse the reply; nothing is judged here."""
    try:
        response, finished = future.result()
    except RunCancelled:
        raise
    except Exception as error:  # the subtask fails alone; its siblings keep going
        budget.charge(None)
        return {"status": "failed", "error_type": type(error).__name__, "error": str(error)[:300],
                "elapsed_ms": round((time.perf_counter() - started) * 1000)}
    tokens = budget.charge(response)
    message = response["choices"][0].get("message", {}) if response.get("choices") else {}
    return {"status": "returned", "reply": parse_reply(message.get("content")), "tokens": tokens,
            "elapsed_ms": round((finished - started) * 1000)}


def settle_late(context: RunContext, t: Texts, late: list, budget: SharedBudget):
    """Responses that came back after their subtask timed out: charge them, record them, merge none of them."""
    for contract, future in late:
        error = future.exception()
        if isinstance(error, RunCancelled):
            raise error
        if isinstance(error, SubtaskCancelled):
            budget.refund()  # cancelled before the request went out: no call was made
            data = {"sent": False, "reason": "not_sent"}
        elif error is not None:
            budget.charge(None)
            data = {"discarded": True, "error_type": type(error).__name__, "error": str(error)[:300]}
        else:
            data = {"discarded": True, "total_tokens": budget.charge(future.result()[0])}
        context.emit("lesson.late_response", {"subtask": contract.id, **data, "detail": t.late_detail}, 1)


def finalize(contracts: list[Contract], outcomes: dict, merged: dict) -> dict:
    """Combine what came back with what the merge check said: the final status of every subtask and of the task."""
    verdicts = {item["id"]: item for item in merged["verdicts"]}
    statuses = {c.id: verdicts[c.id]["status"] if c.id in verdicts else outcomes[c.id]["status"] for c in contracts}
    covered = {field["id"] for field in merged["fields"]}
    missing = [field for field in REQUIRED_FIELDS if field not in covered]
    unfinished = [c.id for c in contracts if statuses[c.id] != "accepted"]
    status = ("incomplete" if missing else "needs_review" if merged["conflicts"]
              else "complete_with_gaps" if unfinished else "complete")
    return {"status": status, "statuses": statuses, "required_missing": missing, "unfinished": unfinished}


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    contracts = build_contracts(values.contract == "full", values.tight_subtask, values.tight_deadline_ms)
    budget, root = SharedBudget(values.budget_calls, values.budget_tokens, values.run_deadline_ms), Scope()
    context.emit("lesson.task_card", _card(t, values), 1)
    steps = [{"id": c.id, "status": "pending", "content": t.plan_step.format(
        id=c.id, field=t.field_names[c.field], priority=c.priority, docs=t.list_separator.join(c.docs))}
        for c in contracts]
    context.emit("lesson.plan", {"version": 1, "event": "created", "reason": t.plan_reason, "diff": {},
                                 "steps": steps}, 1)
    # 1. Delegate: isolated contexts, one shared budget, priority order.
    outcomes, late = dispatch(context, t, contracts, budget, root, values.max_parallel)
    settle_late(context, t, late, budget)
    # 2. Merge: the runner calls the merge check as a registered tool on every result that came back in time.
    returned = [{"id": c.id, "reply": outcomes[c.id]["reply"]} for c in contracts
                if outcomes[c.id]["status"] == "returned"]
    result = context.call_tool("merge_check", {"contracts": [c.as_json() for c in contracts], "results": returned},
                               {"merge_check": partial(merge_check, t)}, round_number=2)
    if not result.get("ok"):
        raise RuntimeError(result.get("error"))  # the arguments are built by this program: a failure here is a bug
    merged = result["result"]
    # 3. Settle: unfinished subtasks and conflicts decide the verdict; returning is not the same as succeeding.
    final = finalize(contracts, outcomes, merged)
    context.emit("lesson.merge", {"status": final["status"], "fields": merged["fields"],
                                  "conflicts": merged["conflicts"], "required_missing": final["required_missing"],
                                  "unfinished": [{"id": sid, "status": final["statuses"][sid]}
                                                 for sid in final["unfinished"]],
                                  "detail": t.merge_detail.format(accepted=sum(
                                      s == "accepted" for s in final["statuses"].values()),
                                      conflicts=len(merged["conflicts"]), unfinished=len(final["unfinished"]))}, 2)
    plan = {"accepted": "done", "not_started": "skipped"}
    for step in steps:
        step["status"] = plan.get(final["statuses"][step["id"]], "failed")
    context.emit("lesson.plan", {"version": 2, "event": "progress", "reason": t.plan_progress, "diff": {},
                                 "steps": steps}, 2)
    return _report(context, t, values, contracts, outcomes, merged, final, budget)


# ---------- Events, report and answer ----------
def _announce(context: RunContext, t: Texts, contract: Contract, budget: SharedBudget, messages: list[dict],
              deadline_ms: int):
    """lesson.delegate: the contract, the budget left after this grant, and what the context really holds."""
    text = "\n".join(message["content"] for message in messages)
    context.emit("lesson.delegate", {
        "subtask": contract.id, "field": contract.field, "priority": contract.priority,
        "required": contract.field in REQUIRED_FIELDS, "evidence_required": contract.evidence,
        "deadline_ms": deadline_ms, "budget": budget.snapshot(),
        "context": {"messages": len(messages), "input_chars": len(text),
                    "docs_seen": [doc for doc in t.docs if t.docs[doc] in text]}}, 1)


def _record(context: RunContext, contract: Contract, outcome: dict):
    """lesson.subtask: how a dispatched subtask ended; fields only appear on the outcome they describe."""
    data = {"subtask": contract.id, "field": contract.field, "status": outcome["status"]}
    if outcome["status"] == "timed_out":
        data.update(timed_out_after_ms=outcome["after_ms"], reason=outcome["reason"])
    elif outcome["status"] == "failed":
        data.update(error_type=outcome["error_type"], error=outcome["error"], elapsed_ms=outcome["elapsed_ms"])
    else:
        data.update(total_tokens=outcome["tokens"], elapsed_ms=outcome["elapsed_ms"], reply=outcome["reply"])
    context.emit("lesson.subtask", data, 1)


def _stop_queue(context: RunContext, t: Texts, queue: list, reason: str, budget: SharedBudget, outcomes: dict):
    """The budget refused: every subtask still queued stays unstarted, and the event says which and why."""
    for contract in queue:
        outcomes[contract.id] = {"status": "not_started", "reason": reason}
    context.emit("lesson.budget_stop", {
        "reason": reason, "not_started": [contract.id for contract in queue], "budget": budget.snapshot(),
        "detail": t.budget_stop_detail.format(reason=t.reason_names[reason], count=len(queue))}, 1)
    queue.clear()


def _card(t: Texts, values: Inputs) -> dict:
    full = values.contract == "full"
    return {"goal": t.card_goal, "input_scope": t.card_input_scope,
            "output": t.card_output_full if full else t.card_output_plain,
            "evidence": t.card_evidence_full if full else t.card_evidence_missing, "failure": t.card_failure,
            "stop": t.card_stop.format(calls=values.budget_calls, tokens=values.budget_tokens,
                                       run_ms=values.run_deadline_ms, deadline_ms=DEFAULT_DEADLINE_MS)}


def _outcome_text(t: Texts, outcome: dict, verdict: dict | None) -> str:
    if verdict and verdict["problems"]:
        return t.list_separator.join(t.problem_labels[code] for code in verdict["problems"])
    if outcome.get("reason"):
        return t.reason_names[outcome["reason"]]
    return outcome.get("error", "") or t.value_none


def _tokens_value(t: Texts, budget: SharedBudget):
    if budget.calls_used == 0:
        return t.value_none
    if budget.unreported >= budget.calls_used:
        return t.value_not_reported
    if budget.unreported:
        return t.tokens_partly_reported.format(total=budget.tokens_used, missing=budget.unreported)
    return budget.tokens_used


def _report(context: RunContext, t: Texts, values: Inputs, contracts: list[Contract], outcomes: dict, merged: dict,
            final: dict, budget: SharedBudget) -> str:
    """Emit the lab report (lesson.report) and return the answer the coordinator writes from the merged results."""
    verdicts = {item["id"]: item for item in merged["verdicts"]}
    statuses = final["statuses"]
    checks = []
    for c in contracts:
        status, label = statuses[c.id], t.check_subtask.format(id=c.id, field=t.field_names[c.field])
        if c.id in verdicts:
            detail = (t.check_accepted if status == "accepted" else t.check_not_found if status == "not_found"
                      else _outcome_text(t, outcomes[c.id], verdicts[c.id]))
            checks.append({"id": c.id, "label": label, "passed": status == "accepted", "detail": detail})
        else:  # nothing came back, so no check ran: no passed flag
            checks.append({"id": c.id, "label": label, "detail": t.check_not_run.format(
                status=t.list_separator.join([t.status_names[status], _outcome_text(t, outcomes[c.id], None)]))})
    missing = [t.field_names[field] for field in final["required_missing"]]
    checks.append({"id": "required", "label": t.check_required, "passed": not missing,
                   "detail": t.check_required_missing.format(fields=t.list_separator.join(missing)) if missing
                   else t.check_required_ok})
    accepted = sum(status == "accepted" for status in statuses.values())
    late = sum(outcome["status"] == "timed_out" for outcome in outcomes.values())
    covered = len(REQUIRED_FIELDS) - len(missing)
    context.emit("lesson.report", {
        "title": t.report_title, "summary": t.report_summary, "checks": checks,
        "metrics": [
            {"id": "verdict", "label": t.label_verdict, "value": t.verdicts[final["status"]]},
            {"id": "required", "label": t.label_required,
             "value": t.value_required.format(covered=covered, total=len(REQUIRED_FIELDS))},
            {"id": "accepted", "label": t.label_accepted,
             "value": t.value_accepted.format(accepted=accepted, total=len(contracts))},
            {"id": "conflicts", "label": t.label_conflicts, "value": len(merged["conflicts"])},
            {"id": "unfinished", "label": t.label_unfinished,
             "value": t.list_separator.join(final["unfinished"]) or t.value_none},
            {"id": "model_calls", "label": t.label_model_calls, "value": budget.calls_used},
            {"id": "budget_calls", "label": t.label_budget_calls,
             "value": t.value_budget.format(used=budget.calls_used, limit=budget.calls)},
            {"id": "total_tokens", "label": t.label_total_tokens, "value": _tokens_value(t, budget)},
            {"id": "budget_tokens", "label": t.label_budget_tokens, "value": t.value_budget_tokens.format(
                used=budget.tokens_used, limit=budget.tokens, unreported=budget.unreported)},
            {"id": "wall_ms", "label": t.label_wall_ms, "value": round((time.perf_counter() - budget.started) * 1000)},
            {"id": "late", "label": t.label_late, "value": late},
            {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.table_columns), "rows": [
            [c.id, t.field_names[c.field], c.priority, t.list_separator.join(c.docs), t.status_names[statuses[c.id]],
             outcomes[c.id].get("elapsed_ms", "—"),
             (t.value_not_reported if outcomes[c.id].get("tokens") is None else outcomes[c.id]["tokens"])
             if outcomes[c.id]["status"] == "returned" else "—",
             _outcome_text(t, outcomes[c.id], verdicts.get(c.id))] for c in contracts]},
    }, 2)
    return _answer(t, contracts, merged, final)


def _answer(t: Texts, contracts: list[Contract], merged: dict, final: dict) -> str:
    """The coordinator's answer, written by this program from merged results only: conflicts stay visible."""
    fields = {item["id"]: item["values"] for item in merged["fields"]}
    conflicted = {item["id"] for item in merged["conflicts"]}
    lines = [t.answer_header.format(verdict=t.verdicts[final["status"]])]
    for field in dict.fromkeys(field for _, field, _, _ in PLAN):
        name, values = t.field_names[field], fields.get(field)
        if field in conflicted:
            lines.append(t.answer_conflict.format(field=name, items=t.list_separator.join(
                t.answer_conflict_item.format(doc=item["doc"], value=item["value"]) for item in values)))
        elif values:
            first = values[0]
            lines.append(t.answer_value.format(field=name, value=first["value"], doc=first["doc"], quote=first["quote"]))
        elif field in REQUIRED_FIELDS:
            lines.append(t.answer_missing.format(field=name))
    if final["unfinished"]:
        lines.append(t.answer_unfinished.format(items=t.list_separator.join(
            t.answer_unfinished_item.format(id=sid, status=t.status_names[final["statuses"][sid]])
            for sid in final["unfinished"])))
    return "\n".join(lines)
