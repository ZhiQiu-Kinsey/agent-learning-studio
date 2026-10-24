"""Text of the offline test model (fixtures.py) of the capstone, one file per run language.

Only what the scripted behavior puts into requests and events: the search query each case sends, the
markers that pick a line out of a retrieved chunk, and the sentences the scripted replies are written in.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The search query the scripted model sends for each case that searches.
    queries: dict[str, str]
    # A substring that picks the line to quote from the retrieved chunks, keyed by the script's own names.
    markers: dict[str, str]
    practice_questions: tuple[str, ...]
    conflict_topic: str
    conflict_resolution: str
    missing: str
    # The note each progress case asks to save (also written in the case's learner message).
    notes: dict[str, str]
    saved_message: str  # {lesson} {version}
    failed_message: str  # {error}
    recall_found: str  # {lessons}
    recall_none: str
    trace_summary: str  # {slowest} {hits} {usage}
    reject_note: str
    attack_note: str
    # Written into the recorded response of a scripted behavior, so the event says this is not a model's choice.
    attack_marker: str


texts_for = catalog(__name__, Texts)
