"""Runtime text shared with memory-lifecycle: store.py's messages and the rules build_messages puts in system.

store.py and build_messages are imported by memory-lifecycle, so their text has its own
catalog. Column names, scope codes and event fields are code and stay the same in every
language; only what reaches the model or an event is translated.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The system message of build_messages: rules only, never memory content.
    memory_rules: str
    # Errors MemoryStore raises; they reach events (VersionConflict) or input errors.
    bad_identifier: str
    bad_scope: str
    version_conflict: str  # {expected} {current}
    # Why recall skipped a record (the reason field of excluded records).
    reason_expired: str
    reason_other_task: str


texts_for = catalog(__name__, Texts)
