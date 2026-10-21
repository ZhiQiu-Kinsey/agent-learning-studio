"""The execution-side permission gate: a call is judged by program rules, before anything runs.

The gate reads three things and nothing else: the task contract (contract.TASK_TOOLS), the
identity the runner bound to the session, and the call's own arguments. It never reads the
retrieved material or the model's prose, so text inside a note cannot widen what a task may
do. Security comes first, then input validation: a call that names another learner is
refused as a permission problem before its other arguments are even looked at.
"""
from dataclasses import dataclass

from lessons.lesson_capstone_study_assistant.contract import (KNOWN_LESSONS, NOTE_MAX_CHARS, STATUSES, TASK_TOOLS,
                                                              WRITE)
from lessons.lesson_capstone_study_assistant.notes import MAX_TOP_K

# Argument names are code, the same in every language; the model's definitions list exactly these.
ARGUMENTS = {
    "search_notes": {"required": {"query"}, "optional": {"top_k"}},
    "read_progress": {"required": {"learner"}, "optional": set()},
    "save_progress": {"required": {"learner", "lesson", "status", "note"}, "optional": set()},
}
# Rules that refuse for security reasons; every other refusal is a plain input error.
PERMISSION_RULES = ("not_authorized_for_task", "other_learner", "approval_rejected", "approval_timeout",
                    "payload_changed")
INPUT_RULES = ("bad_arguments", "unknown_lesson", "bad_status", "bad_note", "bad_query")


class PermissionDenied(ValueError):
    """A security refusal. A ValueError, so the tool loop turns it into a structured error result."""

    def __init__(self, rule: str, message: str):
        super().__init__(message)
        self.rule = rule


class InvalidArguments(ValueError):
    """The call was allowed in principle, but its arguments cannot be used."""

    def __init__(self, rule: str, message: str):
        super().__init__(message)
        self.rule = rule


class ApprovalRejected(PermissionDenied):
    """A person said no (or did not answer in time): the write must not happen."""


@dataclass(frozen=True)
class Decision:
    verdict: str  # "allow" | "deny" | "invalid"
    rule: str  # "ok" or a code from PERMISSION_RULES / INPUT_RULES
    mode: str | None  # "read" | "write" when the task knows the tool

    def raise_for(self, messages: dict) -> None:
        if self.verdict == "deny":
            raise PermissionDenied(self.rule, messages[self.rule])
        if self.verdict == "invalid":
            raise InvalidArguments(self.rule, messages[self.rule])


def decide(task: str, learner: str, name: str, arguments) -> Decision:
    """Judge one call. Pure: no model, no store, no events; the same inputs always give the same decision."""
    allowed = TASK_TOOLS[task]
    # 1. Is this tool part of what the task may do at all? A write tool is simply absent from a read-only task.
    if name not in allowed:
        return Decision("deny", "not_authorized_for_task", None)
    mode = allowed[name]
    shape = ARGUMENTS[name]
    # 2. The argument names must be exactly the declared ones; a stray name is never forwarded to the tool.
    if not isinstance(arguments, dict) or not shape["required"] <= set(arguments) <= shape["required"] | shape["optional"]:
        return Decision("invalid", "bad_arguments", mode)
    # 3. Identity: whoever the call names, the session is bound to one learner.
    if "learner" in arguments and arguments["learner"] != learner:
        return Decision("deny", "other_learner", mode)
    if name == "search_notes":
        query, top_k = arguments["query"], arguments.get("top_k", 5)
        if not isinstance(query, str) or not query.strip() or len(query) > 200:
            return Decision("invalid", "bad_query", mode)
        if type(top_k) is not int or not 1 <= top_k <= MAX_TOP_K:
            return Decision("invalid", "bad_arguments", mode)
    if name == "save_progress":
        # 4. Values last, each with its own rule, so a report can say which input was wrong.
        if arguments["lesson"] not in KNOWN_LESSONS:
            return Decision("invalid", "unknown_lesson", mode)
        if arguments["status"] not in STATUSES:
            return Decision("invalid", "bad_status", mode)
        note = arguments["note"]
        if not isinstance(note, str) or not note.strip() or len(note) > NOTE_MAX_CHARS:
            return Decision("invalid", "bad_note", mode)
    return Decision("allow", "ok", mode)


def needs_approval(task: str, name: str) -> bool:
    """Only a write needs a person; the contract says which tools write."""
    return TASK_TOOLS[task].get(name) == WRITE
