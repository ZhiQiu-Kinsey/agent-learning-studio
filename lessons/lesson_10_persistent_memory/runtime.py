"""Persistent memory: save one explicitly given memory, reopen and read it back, then put the recall into one model request.

The store is store.py in this directory; memory-lifecycle uses it too.
"""
import json
import re
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_10_persistent_memory.locales import texts_for
from lessons.lesson_10_persistent_memory.locales.shared import texts_for as shared_texts_for
from lessons.lesson_10_persistent_memory.store import MemoryStore

# Real runs write a fixed teaching store under the project's .runtime, readable next run; offline tests use a temporary one.
DB_PATH = Path(__file__).resolve().parents[2] / ".runtime" / "persistent-memory.sqlite3"
NAME = r"^[A-Za-z][A-Za-z0-9_-]{0,31}$"


class Inputs(LessonInputs):
    scenario: Literal["reopen", "recall_only", "recall_answer"] = "reopen"
    namespace: str = Field(default="learner_demo", pattern=NAME)
    key: str = Field(default="learning_goal", pattern=NAME)
    # No default for value and source: lesson.json supplies them in the run's language.
    value: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=120)


INPUT_MODEL = Inputs
CITED = re.compile(r"\[([A-Za-z][A-Za-z0-9_-]{0,31})\]")


def save_and_reopen(context: RunContext, path: Path, values: Inputs) -> str:
    other = "other_learner" if values.namespace != "other_learner" else "learner_demo"
    # 1. First connection: read the current version, write the given value and source, then close.
    first = MemoryStore(path, locale=context.locale)
    try:
        before = first.get(values.namespace, values.key)
        other_before = first.get(other, values.key)
        # Pass the version just read, None for a new key; memory-lifecycle shows what this guards against.
        saved = first.put(values.namespace, values.key, values.value, values.source,
                          before["version"] if before else None)
    finally:
        first.close()
    context.emit("lesson.memory", {"action": "saved", "record": saved, "storage": _storage(context)})
    context.check_cancelled()
    # 2. Second connection: what it reads can only come from the SQLite file, not from the first connection's memory.
    second = MemoryStore(path, locale=context.locale)
    try:
        restored = second.get(values.namespace, values.key)
        # 3. Look up the same key in another namespace: this write must not have changed it.
        other_after = second.get(other, values.key)
    finally:
        second.close()
    return _report_reopen(context, values, saved, restored, other, other_before, other_after)


def open_for_reading(path: Path, locale: str) -> MemoryStore:
    """Open the store read-only; without a file, use an empty in-memory store, so reading never creates a file."""
    return MemoryStore(path, locale=locale, read_only=True) if path.exists() else MemoryStore(Path(":memory:"), locale=locale)


def recall_only(context: RunContext, path: Path, values: Inputs) -> str:
    store = open_for_reading(path, context.locale)
    try:
        record = store.get(values.namespace, values.key)
        writes = store.connection.total_changes  # rows this connection changed; 0 when it only read
    finally:
        store.close()
    context.emit("lesson.memory", {"action": "recall_only", "record": record, "storage": _storage(context)})
    return _report_recall_only(context, values, record, writes)


def build_messages(items: list[dict], question: str, locale: str) -> list[dict]:
    """Recalled memories go into the user message as data; system holds only rules, never memory content."""
    # Angle brackets become JSON escapes: a value containing </memory> cannot end the block; the parsed value is unchanged.
    payload = json.dumps(items, ensure_ascii=False, indent=2).replace("<", "\\u003c").replace(">", "\\u003e")
    return [{"role": "system", "content": shared_texts_for(locale).memory_rules},
            {"role": "user", "content": f"<memory>\n{payload}\n</memory>\n\n{question}"}]


def recall_answer(context: RunContext, path: Path, values: Inputs) -> str:
    # 1. Read-only recall: the memories of this namespace that belong in this request.
    store = open_for_reading(path, context.locale)
    try:
        records, _ = store.recall(values.namespace)
        writes = store.connection.total_changes
    finally:
        store.close()
    context.emit("lesson.memory", {"action": "recalled", "namespace": values.namespace,
                                    "included": [item["key"] for item in records], "storage": _storage(context)})
    # 2. Put them into the next request: only key, value and source per memory, the question after the data block.
    items = [{"key": item["key"], "value": item["value"], "source": item["source"]} for item in records]
    messages = build_messages(items, texts_for(context.locale).question, context.locale)
    answer = _content(context.complete({"messages": messages, "temperature": 0}), context.locale)
    # 3. What the answer relied on: every key in square brackets must be a record in this request's data block.
    cited = CITED.findall(answer)
    _report_recall_answer(context, values, records, messages, cited, writes)
    return answer


def seed(path: Path, locale: str) -> None:
    """The offline test's controlled sample: one learning goal in the default namespace."""
    t, fields = texts_for(locale), Inputs.model_fields
    store = MemoryStore(path, locale=locale)
    try:
        store.put(fields["namespace"].default, fields["key"].default, t.seed_value, t.seed_source, None)
    finally:
        store.close()


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    flow = {"reopen": save_and_reopen, "recall_only": recall_only, "recall_answer": recall_answer}[values.scenario]
    if context.mode != "offline":
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return flow(context, DB_PATH, values)
    # Offline tests use a throwaway store; the two read-only exercises get a controlled sample first, or nothing is there.
    with tempfile.TemporaryDirectory(prefix="persistent-memory-") as directory:
        path = Path(directory) / "memory.sqlite3"
        if values.scenario != "reopen":
            seed(path, context.locale)
        return flow(context, path, values)


# ---------- Reports and helpers: they only arrange the evidence, they do not read or write ----------

def memory_block(content: str) -> list:
    """The JSON of the <memory> block in a user message; brackets are escaped, so the first </memory> ends the block."""
    return json.loads(content.split("<memory>\n", 1)[1].split("\n</memory>", 1)[0])


def _storage(context: RunContext) -> str:
    return "temporary" if context.mode == "offline" else "local-persistent"


def _storage_label(context: RunContext) -> str:
    t = texts_for(context.locale)
    return t.storage_temporary if context.mode == "offline" else t.storage_local


def _note(context: RunContext) -> dict:
    t = texts_for(context.locale)
    return {"label": t.label_note, "value": context.question or t.value_none}


def _content(response: dict, locale: str) -> str:
    choices = response.get("choices")
    message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ValueError(texts_for(locale).no_text_answer)
    return message["content"]


def _row(t, label: str, namespace: str, record: dict | None) -> list:
    if record is None:
        return [label, namespace, t.value_none, t.value_none, 0]
    return [label, namespace, record["value"], record["source"], record["version"]]


def _report_reopen(context, values, saved, restored, other, other_before, other_after) -> str:
    t = texts_for(context.locale)
    context.emit("lesson.report", {
        "title": t.reopen_title,
        "summary": t.reopen_summary,
        "checks": [
            {"label": t.reopen_check_value,
             "passed": restored is not None and restored["value"] == values.value
             and restored["version"] == saved["version"],
             "detail": t.reopen_check_value_detail},
            {"label": t.reopen_check_other, "passed": other_before == other_after,
             "detail": t.reopen_check_other_detail.format(other=other)},
        ],
        "metrics": [{"label": t.label_version_after, "value": saved["version"]},
                    {"label": t.label_model_calls, "value": 0},
                    {"label": t.label_storage, "value": _storage_label(context)}, _note(context)],
        "table": {"columns": list(t.columns_steps),
                  "rows": [_row(t, t.row_first_write, values.namespace, saved),
                           _row(t, t.row_second_read, values.namespace, restored),
                           _row(t, t.row_other_namespace, other, other_after)]},
    })
    if restored is None:
        return t.reopen_missing
    return t.reopen_answer.format(value=restored["value"], version=restored["version"])


def _report_recall_only(context, values, record, writes) -> str:
    t = texts_for(context.locale)
    context.emit("lesson.report", {
        "title": t.recall_only_title,
        "summary": t.recall_only_summary,
        "checks": [{"label": t.recall_only_check_writes, "passed": writes == 0,
                    "detail": t.recall_only_check_writes_detail.format(writes=writes)},
                   {"label": t.recall_only_check_source, "passed": record is None or bool(record["source"]),
                    "detail": t.recall_only_check_source_detail}],
        "metrics": [{"label": t.label_lookup, "value": t.value_found if record else t.value_none},
                    {"label": t.label_model_calls, "value": 0},
                    {"label": t.label_storage, "value": _storage_label(context)}, _note(context)],
        "table": {"columns": list(t.columns_steps),
                  "rows": [_row(t, t.row_read_only, values.namespace, record)]},
    })
    if record is None:
        return t.recall_only_missing
    return t.recall_only_answer.format(value=record["value"], source=record["source"], version=record["version"])


def _report_recall_answer(context, values, records, messages, cited, writes):
    t = texts_for(context.locale)
    system, user = messages[0]["content"], messages[1]["content"]
    keys = {item["key"] for item in records}
    sent = [item["value"] for item in memory_block(user)]
    # system must equal the written rules exactly: comparing whole texts, a short value that happens to be a word
    # of the rules is not mistaken for a leak.
    placed = sent == [item["value"] for item in records] and system == shared_texts_for(context.locale).memory_rules
    cited_detail = t.recall_cited_detail.format(keys=t.separator.join(cited) if cited else t.value_none)
    if records:
        grounded = {"label": t.recall_check_grounded, "passed": bool(cited) and set(cited) <= keys,
                    "detail": cited_detail}
    else:
        grounded = {"label": t.recall_check_empty, "passed": not cited, "detail": cited_detail}
    context.emit("lesson.report", {
        "title": t.recall_title,
        "summary": t.recall_summary,
        "checks": [
            {"label": t.recall_check_writes, "passed": writes == 0,
             "detail": t.recall_check_writes_detail.format(writes=writes)},
            {"label": t.recall_check_placed, "passed": placed,
             "detail": t.recall_check_placed_detail.format(count=len(records))},
            grounded,
        ],
        "metrics": [{"label": t.label_namespace, "value": values.namespace},
                    {"label": t.label_recalled, "value": len(records)},
                    {"label": t.label_model_calls, "value": 1},
                    {"label": t.label_storage, "value": _storage_label(context)},
                    _note(context)],
        "table": {"columns": list(t.recall_columns),
                  "rows": [[item["key"], item["value"], item["source"], item["version"],
                            t.value_yes if item["key"] in cited else t.value_no] for item in records]
                  or [[t.recall_empty_row, "—", "—", "—", "—"]]},
    })
