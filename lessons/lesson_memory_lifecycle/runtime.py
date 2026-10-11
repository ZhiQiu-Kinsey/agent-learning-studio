"""Updating, expiring and scoping memory: every run works in a throwaway temporary store; this lesson calls no model.

The store comes from persistent-memory's store.py; this lesson reads its put, expired, delete, recall and end_task.
"""
import re
import tempfile
import time
from pathlib import Path
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_10_persistent_memory.runtime import build_messages
from lessons.lesson_10_persistent_memory.store import MemoryStore, VersionConflict
from lessons.lesson_memory_lifecycle.locales import texts_for

NAMESPACE = "learner_demo"


class Inputs(LessonInputs):
    scenario: Literal["conflict", "expiry_delete", "scope_filter"] = "conflict"
    # Lifetime of the reminder in the expiry exercise (seconds): negative means already expired when written;
    # a positive value is the "not expired yet" comparison.
    expires_in_seconds: int = Field(default=-1, ge=-3600, le=3600)


INPUT_MODEL = Inputs


def conflict(context: RunContext, path: Path) -> str:
    t = texts_for(context.locale)
    seed = MemoryStore(path, locale=context.locale)
    try:
        first = seed.put(NAMESPACE, "study_plan", t.plan_first, t.plan_first_source, None)
    finally:
        seed.close()
    context.emit("lesson.memory", {"action": "saved", "writer": t.writer_initial, "record": first, "storage": "scratch"})
    # 1. Two writers each open a connection; both read version 1.
    writer_a, writer_b = MemoryStore(path, locale=context.locale), MemoryStore(path, locale=context.locale)
    try:
        seen_a = writer_a.get(NAMESPACE, "study_plan")["version"]
        seen_b = writer_b.get(NAMESPACE, "study_plan")["version"]
        # 2. A writes first with the version it read: it matches, the write succeeds, the version becomes 2.
        saved_a = writer_a.put(NAMESPACE, "study_plan", t.plan_a, t.plan_a_source, seen_a)
        context.emit("lesson.memory", {"action": "saved", "writer": "A", "expected_version": seen_a,
                                        "record": saved_a})
        context.check_cancelled()
        # 3. B writes later, still with old version 1: a stale write, rejected; A's value stays in the store.
        try:
            writer_b.put(NAMESPACE, "study_plan", t.plan_b, t.plan_b_source, seen_b)
            error = None
        except VersionConflict as conflict_error:
            error = str(conflict_error)
        kept = writer_b.get(NAMESPACE, "study_plan")
        # 4. B rereads version 2 and A's value, edits on top of the new value and writes with the new version.
        retried = writer_b.put(NAMESPACE, "study_plan", kept["value"] + t.plan_retry_suffix,
                               t.plan_retry_source, kept["version"])
        context.emit("lesson.memory", {"action": "conflict_and_update", "writer": "B", "expected_version": seen_b,
                                        "stale_rejected": error is not None, "error": error,
                                        "value_after_reject": kept["value"], "record": retried})
    finally:
        writer_a.close()
        writer_b.close()
    return _report_conflict(context, seen_b, saved_a, error, kept, retried)


def expiry_delete(context: RunContext, path: Path, expires_in: int) -> str:
    t = texts_for(context.locale)
    store = MemoryStore(path, locale=context.locale)
    try:
        # 1. Write a temporary reminder with an expiry time; with a negative expires_in it has expired when written.
        saved = store.put(NAMESPACE, "temporary_note", t.reminder_value, t.reminder_source, None,
                          expires_at=time.time() + expires_in)
        context.emit("lesson.memory", {"action": "saved", "record": saved, "storage": "scratch"})
        # 2. Expiry is a read rule: get cannot read it, yet the row is still in the table.
        visible = store.get(NAMESPACE, "temporary_note") is not None
        stored = store.stored(NAMESPACE, "temporary_note")
        if not visible:
            context.emit("lesson.memory", {"action": "expired", "version": saved["version"],
                                            "hidden": True, "stored": stored})
        context.check_cancelled()
        # 3. Deletion is a storage operation: an explicit DELETE of this row, expired or not.
        deleted = store.delete(NAMESPACE, "temporary_note")
    finally:
        store.close()
    # 4. Check on a new connection: the deleted row cannot be read back and is not in the table.
    reopened = MemoryStore(path, locale=context.locale)
    try:
        unreadable = reopened.get(NAMESPACE, "temporary_note") is None
        absent = unreadable and not reopened.stored(NAMESPACE, "temporary_note")
    finally:
        reopened.close()
    context.emit("lesson.memory", {"action": "deleted", "deleted": deleted, "absent": absent})
    return _report_expiry(context, expires_in, visible, stored, deleted, absent)


TASK_EARLIER, TASK_NOW, TASK_NEXT = "task-earlier", "task-now", "task-next"
# Key, scope and task of the four seeded memories; their values and sources come in the run's language.
SEEDS = [("learning_goal", "persistent", None), ("draft_answer", "current_task", TASK_EARLIER),
         ("current_step", "current_task", TASK_NOW), ("pasted_note", "persistent", None)]
# A heuristic marker, only to prompt a human review: other wording slips through and normal sentences can match.
# It is not a security boundary. It knows a few Chinese and English phrasings, whatever the run language.
INSTRUCTION_LIKE = re.compile(r"忽略(之前|以上|前面)|删除(全部|所有)|ignore (all |the )?(previous|above)|system prompt",
                              re.I)


def package_memories(records: list[dict], question: str, locale: str) -> list[dict]:
    """The data block of persistent-memory, with each record's scope and the suspected-instruction flag added."""
    items = [{"key": item["key"], "value": item["value"], "source": item["source"], "scope": item["scope"],
              "instruction_like": bool(INSTRUCTION_LIKE.search(item["value"]))} for item in records]
    return build_messages(items, question, locale)


def scope_filter(context: RunContext, path: Path) -> str:
    t = texts_for(context.locale)
    store = MemoryStore(path, locale=context.locale)
    try:
        # 1. Seed four: two persistent, two current_task belonging to the previous task and to this task.
        for key, scope, task_id in SEEDS:
            store.put(NAMESPACE, key, t.seed_values[key], t.seed_sources[key], None, scope=scope, task_id=task_id)
        context.emit("lesson.memory", {"action": "seeded", "storage": "scratch",
                                        "records": [{"key": k, "scope": s, "task_id": i} for k, s, i in SEEDS]})
        # 2. Recall for task-now: every persistent record, current_task only with the same task_id.
        included, excluded = store.recall(NAMESPACE, TASK_NOW)
        context.emit("lesson.memory", _recalled(TASK_NOW, included, excluded))
        # 3. Package as data and count the rows: no code here acts on what a memory says.
        before = store.count(NAMESPACE)
        messages = package_memories(included, t.preview_question, context.locale)
        flagged = [item["key"] for item in included if INSTRUCTION_LIKE.search(item["value"])]
        context.emit("lesson.memory", {"action": "packaged", "sent_to_model": False, "messages": messages,
                                        "flagged": flagged})
        after = store.count(NAMESPACE)
        context.check_cancelled()
        # 4. This task ends: clear its current_task; the previous task never ended properly, its draft is only filtered.
        ended = store.end_task(NAMESPACE, TASK_NOW)
        context.emit("lesson.memory", {"action": "task_ended", "task_id": TASK_NOW, "deleted": ended})
        next_included, next_excluded = store.recall(NAMESPACE, TASK_NEXT)
        context.emit("lesson.memory", _recalled(TASK_NEXT, next_included, next_excluded))
    finally:
        store.close()
    return _report_scope(context, included, excluded, messages, flagged, before, after, ended, next_included)


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    # Real runs and offline tests alike work in a throwaway store and never touch persistent-memory's teaching store.
    with tempfile.TemporaryDirectory(prefix="memory-lifecycle-") as directory:
        path = Path(directory) / "memory.sqlite3"
        if values.scenario == "conflict":
            return conflict(context, path)
        if values.scenario == "expiry_delete":
            return expiry_delete(context, path, values.expires_in_seconds)
        return scope_filter(context, path)


# ---------- Reports: they only arrange the evidence, they do not read or write ----------

def _recalled(task_id: str, included: list[dict], excluded: list[dict]) -> dict:
    return {"action": "recalled", "task_id": task_id, "included": [item["key"] for item in included],
            "excluded": [{"key": item["key"], "reason": item["reason"]} for item in excluded]}


def _note(context: RunContext) -> dict:
    t = texts_for(context.locale)
    return {"label": t.label_note, "value": context.question or t.value_none}


def _report_conflict(context, seen_b, saved_a, error, kept, retried) -> str:
    t = texts_for(context.locale)
    rejected = error is not None
    context.emit("lesson.report", {
        "title": t.conflict_title,
        "summary": t.conflict_summary,
        "checks": [
            {"label": t.conflict_check_rejected, "passed": rejected, "detail": error or t.conflict_check_rejected_failed},
            {"label": t.conflict_check_kept, "passed": kept["value"] == saved_a["value"]
             and kept["version"] == saved_a["version"],
             "detail": t.conflict_check_kept_detail.format(value=kept["value"], version=kept["version"])},
            {"label": t.conflict_check_retried, "passed": retried["version"] == kept["version"] + 1,
             "detail": t.conflict_check_retried_detail.format(version=retried["version"])},
        ],
        "metrics": [{"label": t.label_final_version, "value": retried["version"]},
                    {"label": t.label_model_calls, "value": 0},
                    {"label": t.label_storage, "value": t.storage_scratch}, _note(context)],
        "table": {"columns": list(t.conflict_columns),
                  "rows": [[t.row_a_write, "A", saved_a["version"] - 1, t.value_success, saved_a["value"]],
                           [t.row_b_write, "B", seen_b, t.value_rejected if rejected else t.value_success,
                            kept["value"]],
                           [t.row_b_retry, "B", kept["version"], t.value_success, retried["value"]]]},
    })
    return t.conflict_answer.format(outcome=t.outcome_rejected if rejected else t.outcome_not_rejected,
                                    value=retried["value"], version=retried["version"])


def _report_expiry(context, expires_in, visible, stored, deleted, absent) -> str:
    t = texts_for(context.locale)
    if expires_in <= 0:
        hidden_check = {"id": "expiry_visibility", "label": t.expiry_check_hidden, "passed": not visible and stored,
                        "detail": t.expiry_check_hidden_detail}
    else:
        hidden_check = {"id": "expiry_visibility", "label": t.expiry_check_live, "passed": visible and stored,
                        "detail": t.expiry_check_live_detail.format(seconds=expires_in)}
    context.emit("lesson.report", {
        "title": t.expiry_title,
        "summary": t.expiry_summary,
        "checks": [hidden_check,
                   {"label": t.expiry_check_deleted, "passed": deleted and absent,
                    "detail": t.expiry_check_deleted_detail}],
        "metrics": [{"label": t.label_ttl, "value": expires_in}, {"label": t.label_model_calls, "value": 0},
                    {"label": t.label_storage, "value": t.storage_scratch}, _note(context)],
        "table": {"columns": list(t.expiry_columns),
                  "rows": [[t.row_after_write, visible, stored], [t.row_after_delete, not absent, not absent]]},
    })
    return t.expiry_answer.format(
        visibility=t.expiry_answer_hidden if not visible else t.expiry_answer_live,
        deletion=t.expiry_answer_deleted if deleted and absent else t.expiry_answer_not_deleted)


def _report_scope(context, included, excluded, messages, flagged, before, after, ended, next_included) -> str:
    t = texts_for(context.locale)
    keys = {item["key"] for item in included}
    next_keys = {item["key"] for item in next_included}
    user = messages[1]["content"]
    injected = t.seed_values["pasted_note"]
    context.emit("lesson.report", {
        "title": t.scope_title,
        "summary": t.scope_summary,
        "checks": [
            {"label": t.scope_check_recalled, "passed": keys == {"learning_goal", "current_step", "pasted_note"},
             "detail": t.scope_check_recalled_detail.format(keys=t.separator.join(sorted(keys)))},
            {"label": t.scope_check_draft, "passed": any(item["key"] == "draft_answer" for item in excluded),
             "detail": t.scope_check_draft_detail},
            {"label": t.scope_check_flagged, "passed": flagged == ["pasted_note"]
             and injected in user and injected not in messages[0]["content"], "detail": t.scope_check_flagged_detail},
            {"id": "not_executed", "label": t.scope_check_not_executed, "passed": before == after == len(SEEDS),
             "detail": t.scope_check_not_executed_detail.format(count=after)},
            {"label": t.scope_check_end_task, "passed": ended == 1
             and next_keys == {"learning_goal", "pasted_note"}, "detail": t.scope_check_end_task_detail},
        ],
        "metrics": [{"label": t.label_seeded, "value": len(SEEDS)}, {"label": t.label_recalled_now, "value": len(included)},
                    {"label": t.label_filtered, "value": len(excluded)}, {"label": t.label_ended, "value": ended},
                    {"label": t.label_model_calls, "value": 0}, _note(context)],
        "table": {"columns": list(t.scope_columns),
                  "rows": [[key, scope, task_id or "—", t.value_yes if key in keys else t.value_no,
                            t.value_yes if key in next_keys else t.value_no]
                           for key, scope, task_id in SEEDS]},
    })
    return t.scope_answer.format(count=len(included))
