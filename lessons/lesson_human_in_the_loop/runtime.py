"""Human in the loop: draft an exercise, pause for a person, save it exactly once, resume from checkpoints.

One run is a short state machine over a saved position: drafted -> approved -> saved. Every position
is written with ``context.checkpoint``; a run started by ``POST /api/runs/{id}/resume`` reads the
position back from ``context.resume_state`` and continues from there. The side effect is a real
SQLite write, and the only thing that keeps a resume from repeating it is the operation id the
state carries, which the runner looks up in the bank before it writes.
"""
import json
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext, approval_digest
from lessons.lesson_human_in_the_loop.bank import ExerciseBank, exercise_problems
from lessons.lesson_human_in_the_loop.locales import texts_for
from lessons.lesson_human_in_the_loop.report import RunTrace, publish_reports

ROOT = Path(__file__).resolve().parents[2]
# Tests point this at a temporary folder; real runs keep one folder per thread under .runtime/.
BANK_ROOT_OVERRIDE: Path | None = None
OFFLINE_KEEP_SECONDS = 24 * 3600
STOP_POINTS = ("none", "after_draft", "before_save", "after_save")


class Inputs(LessonInputs):
    # No default for the topic: lesson.json supplies the preset in the run's language.
    topic: str = Field(min_length=1, max_length=120)
    difficulty: Literal["easy", "medium", "hard"] = "easy"
    # Where the first run simulates a process death by ending after that step; a resumed run never stops.
    stop_at: Literal["none", "after_draft", "before_save", "after_save"] = "none"
    # check_first looks the operation id up before writing; blind skips the lookup to show the duplicate.
    resume_guard: Literal["check_first", "blind"] = "check_first"


INPUT_MODEL = Inputs


def thread_key(context: RunContext) -> str:
    """The thread id reduced to a safe folder name; a run started outside the web page has none."""
    return re.sub(r"[^a-z0-9]", "", (context.thread_id or "local").lower())[:32] or "local"


def bank_folder(context: RunContext) -> Path:
    """One folder per thread: a resumed run (a new run id) finds the same bank its source run wrote."""
    thread = thread_key(context)
    if BANK_ROOT_OVERRIDE is not None:
        return BANK_ROOT_OVERRIDE / thread
    if context.mode == "live":
        return ROOT / ".runtime" / "human-in-the-loop" / thread
    root = Path(tempfile.gettempdir()) / "agent-lab-human-in-the-loop"
    prune(root)
    return root / thread


def prune(root: Path) -> None:
    """Offline runs leave a small folder per thread in the temp directory; drop the old ones."""
    if not root.is_dir():
        return
    for folder in root.iterdir():
        if folder.is_dir() and time.time() - folder.stat().st_mtime > OFFLINE_KEEP_SECONDS:
            shutil.rmtree(folder, ignore_errors=True)


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    trace = RunTrace(resumed=context.resume_state is not None, stop_at=values.stop_at)
    bank = ExerciseBank(bank_folder(context), t)
    # 1. A resumed run starts from the saved position; a fresh run starts by drafting.
    state = context.resume_state if trace.resumed else draft_step(context, t, values, trace)
    # 2. Each later step runs only if the position says it is still to do and nothing has ended the run.
    if state and state["step"] == "drafted" and not trace.stop("after_draft"):
        state = approve_step(context, t, state, trace)
    if state and state["step"] in ("approved", "saved") and not trace.stop("before_save"):
        state = commit_step(context, t, values, bank, state, trace)
    return finish(context, t, bank, state, trace)


def parse_draft(text: str, difficulty: str) -> dict | None:
    """First line is the title, the rest is the exercise; anything else is not a usable draft."""
    lines = (text or "").strip().splitlines()
    if len(lines) < 2:
        return None
    draft = {"title": lines[0].strip().lstrip("#*> ").rstrip("*").strip(), "difficulty": difficulty,
             "body": "\n".join(lines[1:]).strip()}
    return None if exercise_problems(draft) else draft


def draft_step(context: RunContext, t, values: Inputs, trace: RunTrace) -> dict | None:
    # 1. The model writes the draft: the one request a resume never sends again.
    reply = context.complete({"messages": [
        {"role": "system", "content": t.draft_system},
        {"role": "user", "content": t.draft_request.format(topic=values.topic,
                                                           difficulty=t.difficulty_names[values.difficulty])}],
        "max_tokens": 600}, 1)
    trace.draft_requests += 1
    draft = parse_draft(reply["choices"][0]["message"].get("content"), values.difficulty)
    if draft is None:
        trace.end("failed", "bad_draft")
        return None
    # 2. The operation id is made once, here, and travels in the state: every later run of the thread reuses it.
    state = {"step": "drafted", "operation_id": f"save-{thread_key(context)[:8]}-1", "draft": draft, "approved": None,
             "approved_digest": None, "edited": False, "saved_id": None}
    trace.save_checkpoint(context, "drafted", state)
    return state


def approve_step(context: RunContext, t, state: dict, trace: RunTrace) -> dict:
    # 1. The run stops at the gate until a person decides; the person may edit the payload.
    decision = context.request_approval("exercise.save", t.approval_summary.format(title=state["draft"]["title"]),
                                        dict(state["draft"]), risk="medium", editable=True)
    trace.approval = {"outcome": decision.outcome, "decided_by": decision.decided_by, "edited": decision.edited}
    if not decision.approved:
        trace.end("timed_out" if decision.outcome == "timeout" else "rejected", decision.outcome)
        return state
    # 2. An edit is checked like a draft: a person can type a payload the bank would never accept.
    if exercise_problems(decision.payload):
        trace.end("failed", "invalid_edit")
        return state
    # 3. What was approved, and its digest, go into the checkpoint: the write happens only for this payload.
    state = {**state, "step": "approved", "approved": decision.payload, "approved_digest": decision.payload_digest,
             "edited": decision.edited}
    trace.save_checkpoint(context, "approved", state)
    return state


def commit_step(context: RunContext, t, values: Inputs, bank: ExerciseBank, state: dict, trace: RunTrace) -> dict:
    tools, operation = bank.tools(), state["operation_id"]
    # 1. The approval travels as a digest: a position whose payload no longer matches it must not write.
    if approval_digest(state["approved"]) != state["approved_digest"]:
        trace.end("failed", "unapproved")
        return state
    # 2. Ask the bank whether this operation already wrote a row. A checkpoint does not know.
    found = None
    if values.resume_guard == "check_first":
        looked = context.call_tool("lookup_operation", {"operation_id": operation}, tools)
        if not looked["ok"]:
            trace.end("failed", "lookup_failed")
            return state
        found = looked["result"]
        trace.lookup = "found" if found["found"] else "not_found"
    else:
        trace.lookup = "skipped"
    if state["step"] == "saved" and not (found and found["found"]):
        # The checkpoint claims a save the bank cannot show: report it, never write on a guess.
        trace.end("failed", "ledger_mismatch")
        return state
    if found and found["found"]:
        trace.write, saved_id = "skipped", found["exercise_id"]
    else:
        # 3. The write: real, after approval, with the operation id; a cancel request lands before it.
        context.check_cancelled()
        saved = context.call_tool("save_exercise", {"operation_id": operation, **state["approved"],
                                                    "origin": "resumed" if trace.resumed else "fresh"}, tools)
        if not saved["ok"]:
            trace.end("failed", "save_failed")
            return state
        trace.write, saved_id = "written", saved["result"]["exercise_id"]
    # 4. Simulated process death between the write and the next checkpoint: the position on record is still "approved".
    if trace.stop("after_save"):
        return state
    state = {**state, "step": "saved", "saved_id": saved_id}
    trace.save_checkpoint(context, "saved", state)
    return state


def finish(context: RunContext, t, bank: ExerciseBank, state: dict | None, trace: RunTrace) -> str:
    stored = bank.rows()
    rows = [row for row in stored if state and row["operation_id"] == state["operation_id"]]
    if trace.status is None:
        trace.status = "duplicated" if len(rows) > 1 else "already_saved" if trace.write == "skipped" else "saved"
    answer = None
    if trace.status in ("saved", "already_saved", "duplicated"):
        # A real, new request: after a resume it is the only model call of the run.
        facts = {"status": trace.status, "title": state["approved"]["title"],
                 "difficulty": state["approved"]["difficulty"], "exercise_id": state["saved_id"],
                 "rows": len(rows), "edited_by_person": state["edited"], "resumed": trace.resumed}
        reply = context.complete({"messages": [
            {"role": "system", "content": t.receipt_system},
            {"role": "user", "content": t.receipt_prompt.format(facts=json_line(facts))}]}, 2)
        trace.receipt_requests += 1
        answer = reply["choices"][0]["message"].get("content") or t.answer_empty
    if trace.status == "suspended":
        # The stop is the lesson's own doing (the stop_at parameter), recorded as such: no real process died.
        context.emit("lesson.interruption", {"point": trace.stopped_at, "simulated": True, "source": "stop_at"})
    publish_reports(context, t, state, stored, rows, trace)
    return answer or t.answers[trace.status].format(
        reason=t.reasons.get(trace.reason, trace.reason), checkpoint=trace.last_checkpoint or t.value_none,
        point=t.point_names.get(trace.stopped_at, ""))


def json_line(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
