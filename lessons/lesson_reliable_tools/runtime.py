"""Reliable tools: real local tools, injected faults, bounded retries and idempotency. This lesson calls no model.

Every run works in a throwaway temporary store (SQLite plus an outbox folder): real runs and offline
tests run the same code, and the store starts from the same state every time. Tool calls are made
by the runner (context.call_tool), one tool_call/tool_result pair per attempt.
"""
import random
import tempfile
import uuid
from pathlib import Path
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_reliable_tools.faults import FaultInjector
from lessons.lesson_reliable_tools.locales import texts_for
from lessons.lesson_reliable_tools.retry import RealClock, RetryPolicy, call_with_retry
from lessons.lesson_reliable_tools.store import PracticeStore

LEARNER, EMPTY_LEARNER = "learner-a", "learner-b"
EXERCISE = "safe-divide"
# A fixed seed keeps the jitter reproducible from run to run; real clients each draw their own.
JITTER_SEED = 7
WRITE_MODES = ("blind_retry", "stop_when_unknown", "idempotency_key")


class Inputs(LessonInputs):
    scenario: Literal["read_timeout", "classify", "lost_response", "partial_write"] = "read_timeout"
    # read_timeout: how many of the first attempts find the database locked by another connection.
    locked_attempts: int = Field(default=2, ge=0, le=6)
    # partial_write: how many attempts find the outbox locked; at max_attempts or more, step 2 never succeeds.
    outbox_busy_attempts: int = Field(default=6, ge=0, le=6)
    max_attempts: int = Field(default=4, ge=1, le=6)
    timeout_ms: int = Field(default=200, ge=50, le=2000)
    base_delay_ms: int = Field(default=100, ge=0, le=1000)
    budget_ms: int = Field(default=3000, ge=200, le=20000)


INPUT_MODEL = Inputs


def policy_of(values: dict) -> RetryPolicy:
    return RetryPolicy(max_attempts=values["max_attempts"], timeout_s=values["timeout_ms"] / 1000,
                       base_delay_s=values["base_delay_ms"] / 1000, budget_s=values["budget_ms"] / 1000)


def open_store(context: RunContext, root: Path, values: dict, plan: dict):
    """A fresh store with two learners (3 credits and 0 credits), its fault injector and the wrapped tools."""
    t = texts_for(context.locale)
    store = PracticeStore(root, t, values["timeout_ms"] / 1000)
    store.seed(LEARNER, 3)
    store.seed(EMPTY_LEARNER, 0)
    faults = FaultInjector(store, plan, t)
    return store, faults, faults.tools(store.tools())


def new_key(operation: str) -> str:
    # Made once per logical operation, before the first attempt; every retry of it reuses the same key.
    return f"{operation}-{uuid.uuid4().hex[:8]}"


def read_timeout(context: RunContext, root: Path, values: dict, clock, rng) -> str:
    plan = {("read", n): "store_locked" for n in range(1, values["locked_attempts"] + 1)}
    store, faults, tools = open_store(context, root, values, plan)
    before = store.snapshot()
    # A read changes nothing, so repeating it is always safe: repeatable=True.
    outcome = call_with_retry(context, tools, faults, policy_of(values), clock, rng, operation="read",
                              name="read_account", arguments={"learner": LEARNER}, repeatable=True, writes=False,
                              round_number=1)
    unchanged = store.snapshot() == before
    _storage(context, store, "read", 1, unchanged=unchanged)
    return _report_read(context, values, outcome, unchanged)


def classify(context: RunContext, root: Path, values: dict, clock, rng) -> str:
    t = texts_for(context.locale)
    plan = {("submit", 1): "store_locked", ("export", 1): "outbox_locked"}
    store, faults, tools = open_store(context, root, values, plan)
    common = dict(context=context, tools=tools, faults=faults, policy=policy_of(values), clock=clock, rng=rng)
    outcomes = []
    # 1. An exercise the tool never accepts, and a learner with no credits: both stop after one attempt.
    for number, (operation, learner, exercise) in enumerate(
            [("invalid", LEARNER, "speed-typing"), ("rejected", EMPTY_LEARNER, EXERCISE)], start=1):
        arguments = {"learner": learner, "exercise": exercise, "answer": t.sample_answer,
                     "idempotency_key": new_key(operation)}
        outcomes.append((operation, call_with_retry(**common, operation=operation, name="submit_practice",
                                                    arguments=arguments, repeatable=True, writes=True,
                                                    round_number=number)))
    # 2. A valid keyed write whose first attempt meets a locked database: retried, written once.
    arguments = {"learner": LEARNER, "exercise": EXERCISE, "answer": t.sample_answer,
                 "idempotency_key": new_key("submit")}
    submit = call_with_retry(**common, operation="submit", name="submit_practice", arguments=arguments,
                             repeatable=True, writes=True, round_number=3)
    outcomes.append(("submit", submit))
    # 3. The grader's file; its first attempt meets another writer's lock file.
    if submit.status == "ok":
        outcomes.append(("export", call_with_retry(
            **common, operation="export", name="write_outbox",
            arguments={"submission_id": submit.result["submission_id"]}, repeatable=True, writes=True,
            round_number=4)))
    storage = _storage(context, store, "classify", len(outcomes))
    return _report_classify(context, outcomes, storage)


def lost_response(context: RunContext, root: Path, values: dict, clock, rng) -> str:
    t = texts_for(context.locale)
    rows = []
    for number, mode in enumerate(WRITE_MODES, start=1):
        # Each mode gets its own fresh store, and the same fault: the first attempt commits, its result is lost.
        store, faults, tools = open_store(context, root / mode, values, {("submit", 1): "response_lost"})
        arguments = {"learner": LEARNER, "exercise": EXERCISE, "answer": t.sample_answer}
        if mode == "idempotency_key":
            arguments["idempotency_key"] = new_key("submit")
        outcome = call_with_retry(context, tools, faults, policy_of(values), clock, rng, operation="submit",
                                  name="submit_practice", arguments=arguments,
                                  repeatable=mode == "idempotency_key", writes=True, round_number=number,
                                  blind=mode == "blind_retry")
        rows.append((mode, outcome, _storage(context, store, mode, number)))
    return _report_lost(context, rows)


def partial_write(context: RunContext, root: Path, values: dict, clock, rng) -> str:
    t = texts_for(context.locale)
    plan = {("export", n): "outbox_locked" for n in range(1, values["outbox_busy_attempts"] + 1)}
    store, faults, tools = open_store(context, root, values, plan)
    common = dict(context=context, tools=tools, faults=faults, policy=policy_of(values), clock=clock, rng=rng)
    # 1. Step one: take a credit and record the submission (one transaction, keyed).
    submit = call_with_retry(**common, operation="submit", name="submit_practice", round_number=1,
                             arguments={"learner": LEARNER, "exercise": EXERCISE, "answer": t.sample_answer,
                                        "idempotency_key": new_key("submit")}, repeatable=True, writes=True)
    export = compensation = None
    if submit.status == "ok":
        submission = {"submission_id": submit.result["submission_id"]}
        # 2. Step two: the grader's file. The database and the folder share no transaction.
        export = call_with_retry(**common, operation="export", name="write_outbox", arguments=submission,
                                 repeatable=True, writes=True, round_number=2)
        # 3. Step two gave up: step one is already in effect, so undo it with its compensation.
        if export.status != "ok":
            context.check_cancelled()
            compensation = call_with_retry(**common, operation="compensate", name="cancel_submission",
                                           arguments=submission, repeatable=True, writes=True, round_number=3)
    storage = _storage(context, store, "partial", 3 if compensation else 2)
    return _report_partial(context, submit, export, compensation, storage)


SCENARIOS = {"read_timeout": read_timeout, "classify": classify, "lost_response": lost_response,
             "partial_write": partial_write}


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs).model_dump()
    with tempfile.TemporaryDirectory(prefix="reliable-tools-") as directory:
        return SCENARIOS[values["scenario"]](context, Path(directory), values, RealClock(),
                                             random.Random(JITTER_SEED))


# ---------- Evidence: these read the store and arrange reports; they never call a tool ----------

def _storage(context: RunContext, store: PracticeStore, label: str, round_number: int, **extra) -> dict:
    snapshot = store.snapshot()
    context.emit("lesson.storage", {"label": label, **snapshot, **extra}, round_number)
    return snapshot


def _note(context: RunContext) -> dict:
    t = texts_for(context.locale)
    return {"id": "note", "label": t.label_note, "value": context.question or t.value_none}


def _attempt_count(outcome) -> int:
    return len(outcome.attempts)


def _report_read(context, values, outcome, unchanged) -> str:
    t = texts_for(context.locale)
    retries = [item for item in outcome.attempts if not item["ok"]]
    waits = [item["wait_ms"] for item in retries if item["decision"] == "retry"]
    context.emit("lesson.report", {
        "title": t.read_title,
        "summary": t.read_summary,
        "checks": [
            {"id": "read_bounded", "label": t.read_check_bounded,
             "passed": _attempt_count(outcome) <= values["max_attempts"],
             "detail": t.read_check_bounded_detail.format(attempts=_attempt_count(outcome),
                                                          limit=values["max_attempts"])},
            {"id": "read_unchanged", "label": t.read_check_unchanged, "passed": unchanged,
             "detail": t.read_check_unchanged_detail},
            {"id": "read_result", "label": t.read_check_result, "passed": outcome.status == "ok",
             "detail": t.read_check_result_ok.format(credits=outcome.result["credits"]) if outcome.status == "ok"
             else t.read_check_result_failed.format(reason=t.reasons[outcome.reason])},
        ],
        "metrics": [{"id": "attempts", "label": t.label_attempts, "value": _attempt_count(outcome)},
                    {"id": "waits", "label": t.label_waits, "value": t.separator.join(f"{w} ms" for w in waits)
                     or t.value_none},
                    {"id": "stop_reason", "label": t.label_stop_reason, "value": t.reasons[outcome.reason]},
                    {"id": "model_calls", "label": t.label_model_calls, "value": 0}, _note(context)],
        "table": _attempt_table(t, outcome.attempts),
    })
    if outcome.status == "ok":
        return t.read_answer_ok.format(credits=outcome.result["credits"], attempts=_attempt_count(outcome))
    return t.read_answer_failed.format(attempts=_attempt_count(outcome), reason=t.reasons[outcome.reason])


def _attempt_table(t, attempts) -> dict:
    rows = []
    for item in attempts:
        if item["ok"]:
            rows.append([item["attempt"], t.value_success, "—", "—", "—", item["took_ms"]])
        else:
            rows.append([item["attempt"], item["error_type"], t.categories[item["category"]],
                         t.decisions[item["decision"]], item["wait_ms"], item["took_ms"]])
    return {"columns": list(t.attempt_columns), "rows": rows}


def _report_classify(context, outcomes, storage) -> str:
    t = texts_for(context.locale)
    by_name = dict(outcomes)
    rows = []
    for operation, outcome in outcomes:
        last = outcome.attempts[-1]
        rows.append([t.operations[operation], _attempt_count(outcome),
                     last.get("error_type", "—") if not last["ok"] else "—",
                     t.categories[last["category"]] if not last["ok"] else "—", t.statuses[outcome.status]])
    single = [name for name in ("invalid", "rejected") if _attempt_count(by_name[name]) == 1
              and by_name[name].status == "failed"]
    submissions = [item for item in storage["submissions"] if item["status"] == "active"]
    context.emit("lesson.report", {
        "title": t.classify_title,
        "summary": t.classify_summary,
        "checks": [
            {"id": "no_pointless_retry", "label": t.classify_check_no_retry, "passed": len(single) == 2,
             "detail": t.classify_check_no_retry_detail},
            {"id": "transient_retried", "label": t.classify_check_retried,
             "passed": "export" in by_name and by_name["submit"].status == "ok"
             and by_name["export"].status == "ok" and _attempt_count(by_name["submit"]) == 2,
             "detail": t.classify_check_retried_detail},
            {"id": "written_once", "label": t.classify_check_once, "passed": len(submissions) == 1
             and storage["accounts"][LEARNER] == 2 and len(storage["outbox"]) == 1,
             "detail": t.classify_check_once_detail.format(rows=len(submissions),
                                                           credits=storage["accounts"][LEARNER],
                                                           files=len(storage["outbox"]))},
        ],
        "metrics": [{"id": "tool_calls", "label": t.label_tool_calls,
                     "value": sum(_attempt_count(outcome) for _, outcome in outcomes)},
                    {"id": "model_calls", "label": t.label_model_calls, "value": 0}, _note(context)],
        "table": {"columns": list(t.classify_columns), "rows": rows},
    })
    return t.classify_answer.format(calls=sum(_attempt_count(outcome) for _, outcome in outcomes))


def _report_lost(context, rows) -> str:
    t = texts_for(context.locale)
    table, checks = [], []
    for mode, outcome, storage in rows:
        written = len(storage["submissions"])
        table.append([t.modes[mode], _attempt_count(outcome), t.statuses[outcome.status], written,
                      storage["accounts"][LEARNER], len(storage["operations"])])
        detail = t.lost_check_detail.format(rows=written, credits=storage["accounts"][LEARNER],
                                            status=t.statuses[outcome.status])
        checks.append({"id": f"{mode}_written_once", "label": t.lost_check_once.format(mode=t.modes[mode]),
                       "passed": written == 1, "detail": detail})
    keyed = rows[-1][2]
    checks.append({"id": "key_in_store", "label": t.lost_check_key,
                   "passed": len(keyed["operations"]) == 1 and len(keyed["submissions"]) == 1,
                   "detail": t.lost_check_key_detail.format(
                       key=keyed["operations"][0]["idempotency_key"] if keyed["operations"] else t.value_none)})
    context.emit("lesson.report", {
        "title": t.lost_title,
        "summary": t.lost_summary,
        "checks": checks,
        "metrics": [{"id": "model_calls", "label": t.label_model_calls, "value": 0}, _note(context)],
        "table": {"columns": list(t.lost_columns), "rows": table},
    })
    counts = {mode: len(storage["submissions"]) for mode, _, storage in rows}
    return t.lost_answer.format(blind=counts["blind_retry"], stop=counts["stop_when_unknown"],
                                keyed=counts["idempotency_key"])


def _report_partial(context, submit, export, compensation, storage) -> str:
    t = texts_for(context.locale)
    submission = storage["submissions"][0] if storage["submissions"] else None
    credits = storage["accounts"][LEARNER]
    if submit.status != "ok":
        final = "failed"
    elif export is not None and export.status == "ok":
        final = "completed"
    elif compensation is not None and compensation.status == "ok":
        final = "compensated"
    else:
        final = "partial"
    steps = [[t.step_submit, t.statuses[submit.status], _attempt_count(submit)]]
    if export is not None:
        steps.append([t.step_export, t.statuses[export.status], _attempt_count(export)])
    if compensation is not None:
        steps.append([t.step_compensate, t.statuses[compensation.status], _attempt_count(compensation)])
    if final == "failed":
        consistent = not storage["submissions"] and credits == 3
    elif final == "completed":
        consistent = submission is not None and submission["status"] == "active" and credits == 2 \
            and storage["outbox"] == [f"outbox/{submission['id']}.json"]
    else:
        consistent = submission is not None and submission["status"] == "cancelled" and credits == 3 \
            and storage["outbox"] == []
    context.emit("lesson.report", {
        "title": t.partial_title,
        "summary": t.partial_summary,
        "checks": [
            {"id": "final_state", "label": t.partial_check_state, "passed": consistent,
             "detail": t.partial_check_state_detail.format(
                 status=submission["status"] if submission else t.value_none, credits=credits,
                 files=t.separator.join(storage["outbox"]) or t.value_none)},
            {"id": "history_kept", "label": t.partial_check_history,
             "passed": len(storage["submissions"]) == 1 and len(storage["operations"]) == 1,
             "detail": t.partial_check_history_detail},
        ],
        "metrics": [{"id": "final_status", "label": t.label_final_status, "value": t.finals[final]},
                    {"id": "model_calls", "label": t.label_model_calls, "value": 0}, _note(context)],
        "table": {"columns": list(t.partial_columns), "rows": steps},
    })
    return t.partial_answers[final]
