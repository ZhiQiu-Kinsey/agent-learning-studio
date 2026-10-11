"""A TODO list and a harness reminder: one multi-step task run under three conditions, judged by an independent acceptance check.

The todo_write rules (every item has content, at most one item in_progress at a time) and the
"remind after a few rounds without an update" approach follow learn-claude-code s03 (TodoWrite,
MIT); this lesson's tools, reminder text, acceptance check and experiments are written for this project.
"""
import json
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_todo_planning.locales import Texts, texts_for


class Inputs(LessonInputs):
    condition: Literal["no_todo", "todo", "todo_reminder"] = "todo_reminder"
    reminder_after: int = Field(default=2, ge=1, le=5)


INPUT_MODEL = Inputs
# Point ids of the three lessons, keyed by lesson slug: display numbers change when the curriculum
# grows, slugs do not. The ids follow no pattern, so an invented id never matches this run's lookup.
# The point text itself is in the catalog (t.notes), in the run's language.
NOTE_IDS = {"messages-context": "mc-31", "application-state": "as-12", "context-budget": "cb-47"}
REQUIRED = tuple(NOTE_IDS)
STATUSES = ("pending", "in_progress", "done")


class Workspace:
    """The local state of one run: the TODO list and the review card. New for every run, never kept across runs."""

    def __init__(self, t: Texts):
        # t holds the error messages of the run's language; the model cannot reach it through arguments.
        self.t = t
        self.todos: list[dict] = []
        self.version = 0
        self.card: list[dict] | None = None

    def todo_write(self, todos: list) -> dict:
        """Replace the whole list with a complete one; it takes effect only if every check passes, and the version goes up by one."""
        t = self.t
        if not isinstance(todos, list) or not 1 <= len(todos) <= 12:
            raise ValueError(t.todos_not_a_list)
        cleaned, ids = [], set()
        for item in todos:
            if not isinstance(item, dict) or set(item) - {"id", "content", "status"}:
                raise ValueError(t.todo_fields)
            todo_id, content, status = item.get("id"), item.get("content"), item.get("status")
            if not isinstance(todo_id, str) or not todo_id or todo_id in ids:
                raise ValueError(t.todo_id)
            if not isinstance(content, str) or not content.strip():
                raise ValueError(t.todo_content)
            if status not in STATUSES:
                raise ValueError(t.todo_status)
            ids.add(todo_id)
            cleaned.append({"id": todo_id, "content": content.strip(), "status": status})
        # At most one item in progress: the list should show "which step is under way now", not a pile of half-done work.
        if sum(item["status"] == "in_progress" for item in cleaned) > 1:
            raise ValueError(t.todo_one_in_progress)
        self.todos, self.version = cleaned, self.version + 1
        return {"version": self.version, "todos": cleaned}

    def lookup_note(self, lesson: str) -> dict:
        if lesson not in NOTE_IDS:
            raise ValueError(self.t.unknown_lesson)
        return {"lesson": lesson, "note_id": NOTE_IDS[lesson], "note": self.t.notes[lesson]}

    def save_card(self, items: list) -> dict:
        if not isinstance(items, list) or not items:
            raise ValueError(self.t.items_not_a_list)
        for item in items:
            if not isinstance(item, dict) or not all(isinstance(item.get(key), str) for key in ("lesson", "note_id", "summary")):
                raise ValueError(self.t.item_fields)
        self.card = [{key: item[key] for key in ("lesson", "note_id", "summary")} for item in items]
        return {"saved": len(self.card)}


def todo_diff(before: list[dict], after: list[dict]) -> dict:
    old = {item["id"]: item for item in before}
    new = {item["id"]: item for item in after}
    return {"added": [key for key in new if key not in old],
            "removed": [key for key in old if key not in new],
            "changed": [{"id": key, "from": old[key]["status"], "to": new[key]["status"]}
                        for key in new if key in old and old[key]["status"] != new[key]["status"]]}


def tool_definitions(locale: str, condition: str = "todo_reminder") -> list[dict]:
    """The tools of one condition; without a condition all three (the Tools panel). Names are code, descriptions follow the locale."""
    t = texts_for(locale)

    def spec(name, description, properties, required):
        return {"type": "function", "function": {"name": name, "description": description, "parameters": {
            "type": "object", "properties": properties, "required": required, "additionalProperties": False}}}
    specs = [
        spec("lookup_note", t.lookup_note_description, {"lesson": {"type": "string", "enum": list(REQUIRED)}}, ["lesson"]),
        spec("save_card", t.save_card_description, {"items": {"type": "array", "items": {
            "type": "object", "properties": {"lesson": {"type": "string"}, "note_id": {"type": "string"}, "summary": {"type": "string"}},
            "required": ["lesson", "note_id", "summary"], "additionalProperties": False}}}, ["items"]),
    ]
    if condition != "no_todo":
        specs.append(spec("todo_write", t.todo_write_description, {"todos": {"type": "array", "items": {
            "type": "object", "properties": {"id": {"type": "string"}, "content": {"type": "string"},
                                             "status": {"type": "string", "enum": list(STATUSES)}},
            "required": ["id", "content", "status"], "additionalProperties": False}}}, ["todos"]))
    return specs


def reminder_text(rounds: int, t: Texts) -> str:
    return t.reminder.format(rounds=rounds)


def run(context: RunContext) -> str:
    """One task under three conditions: with or without todo_write, with or without a harness reminder; all end at the same acceptance check."""
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    condition, workspace = values.condition, Workspace(t)
    tools = {"lookup_note": workspace.lookup_note, "save_card": workspace.save_card}
    # The no-TODO group can neither see nor run todo_write: it is in neither the definitions nor the allowlist.
    if condition != "no_todo":
        tools["todo_write"] = workspace.todo_write
    system = t.base_system if condition == "no_todo" else t.system_with_rules.format(base=t.base_system, rules=t.todo_rules)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": t.task}]
    looked_up: dict[str, str] = {}
    timeline, answer, reminders, since_update, model_calls = [], None, 0, 0, 0
    for round_number in range(1, context.max_model_calls + 1):
        # 1. Send the request: every round carries the whole history and this group's tools.
        response = context.complete({"messages": messages, "tools": tool_definitions(context.locale, condition),
                                     "tool_choice": "auto", "temperature": 0}, round_number)
        model_calls += 1
        message = response["choices"][0].get("message", {})
        calls = message.get("tool_calls") or []
        # 2. No call proposal ends the loop. The model saying "done" is only a claim; acceptance comes later.
        if not calls:
            answer = message.get("content") or ""
            break
        # 3. Execute the proposals and write the results back; note whether the list was updated this round.
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
        updated = False
        for call in calls:
            name = call.get("function", {}).get("name")
            before = list(workspace.todos)
            result = context.execute_proposal(call, tools)
            messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": json.dumps(result, ensure_ascii=False)})
            if name == "lookup_note" and result.get("ok"):
                looked_up[result["result"]["lesson"]] = result["result"]["note_id"]
            if name == "todo_write" and result.get("ok"):
                updated = True
                _publish_todo(context, workspace, before, round_number, timeline)
        # 4. Harness reminder: after reminder_after rounds in a row without an update, append a user message.
        since_update = 0 if updated else since_update + 1
        if condition == "todo_reminder" and since_update >= values.reminder_after:
            # The reminder goes after every tool message of this round: OpenAI-compatible APIs require
            # tool messages to follow the assistant message with the calls directly.
            text = reminder_text(since_update, t)
            messages.append({"role": "user", "content": text})
            # The first reminder carries first, so replay can tell it apart from later ones.
            context.emit("lesson.harness_injected", {"kind": "todo_reminder", "source": "harness", "text": text,
                                                     "rounds_since_update": since_update,
                                                     **({} if reminders else {"first": True})}, round_number)
            reminders += 1
            since_update = 0
    # 5. Acceptance: only the review card and this run's real lookups count; the model's claim and the list's done do not.
    checks = verify_card(workspace.card, looked_up, t)
    return _report(context, condition, checks, workspace, timeline, reminders, model_calls, answer)


def verify_card(card: list[dict] | None, looked_up: dict[str, str], t: Texts) -> list[dict]:
    """Independent acceptance: only the review card and this run's real lookups, never what the model says or how the TODO is marked."""
    lessons = sorted(item["lesson"] for item in card) if card else []
    # An id must match what lookup_note returned in this run; for a lesson never looked up, no id counts.
    wrong = [item["lesson"] for item in card or [] if looked_up.get(item["lesson"]) != item["note_id"]]
    return [
        {"label": t.check_card_saved, "passed": card is not None,
         "detail": t.detail_card_saved if card is not None else t.detail_card_missing},
        {"label": t.check_all_lessons, "passed": lessons == sorted(REQUIRED),
         "detail": t.detail_card_lessons.format(lessons=t.list_separator.join(lessons) or t.value_none)},
        {"label": t.check_note_ids, "passed": card is not None and not wrong,
         "detail": t.detail_ids_match if card is not None and not wrong
         else t.detail_ids_wrong.format(lessons=t.list_separator.join(wrong) or t.value_no_card)},
    ]


def _publish_todo(context: RunContext, workspace: Workspace, before: list[dict], round_number: int,
                  timeline: list[list]) -> None:
    """Each change of the list publishes a snapshot and a diff (lesson.todo) and adds a row to the report's timeline."""
    t = workspace.t
    diff = todo_diff(before, workspace.todos)
    context.emit("lesson.todo", {"version": workspace.version, "todos": workspace.todos, "diff": diff}, round_number)
    timeline.append([round_number, workspace.version,
                     sum(item["status"] == "done" for item in workspace.todos), len(workspace.todos),
                     t.change_separator.join(f"{c['id']} {c['from']}→{c['to']}" for c in diff["changed"]) or
                     (t.timeline_added.format(ids=t.list_separator.join(diff["added"])) if diff["added"]
                      else t.timeline_unchanged)])


def _report(context: RunContext, condition: str, checks: list[dict], workspace: Workspace, timeline: list[list],
            reminders: int, model_calls: int, answer: str | None) -> str:
    """Publish the lab report (lesson.report) and return the final answer: the verdict first, the model's claim only as a record."""
    t = workspace.t
    accepted = all(check["passed"] for check in checks)
    done = sum(item["status"] == "done" for item in workspace.todos)
    context.emit("lesson.report", {
        "title": t.condition_titles[condition],
        "summary": t.report_summary,
        "checks": checks,
        "metrics": [{"label": t.label_verdict, "value": t.value_passed if accepted else t.value_failed},
                    {"label": t.label_model_calls, "value": model_calls},
                    {"label": t.label_todo_writes, "value": len(timeline)},
                    {"label": t.label_reminders, "value": reminders},
                    {"label": t.label_todo_done, "value": f"{done}/{len(workspace.todos)}" if workspace.todos else t.value_no_list},
                    {"id": "last_claim", "label": t.label_last_claim, "value":answer if answer is not None else t.value_unfinished},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.columns), "rows": timeline},
    })
    verdict = t.verdict_passed if accepted else t.verdict_failed
    if answer is None:
        return t.answer_unfinished.format(verdict=verdict, limit=context.max_model_calls)
    return t.answer_final.format(verdict=verdict, answer=answer)
