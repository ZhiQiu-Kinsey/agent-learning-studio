"""Text of the offline test model (fixtures.py) for rag-citations, one file per run language.

Only what the scripted answers put into events: claim sentences, quotes copied verbatim from
the handbook chunks, and the notes that mark a deliberate fixture error.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Claim sentences, keyed by the script's own names.
    claims: dict[str, str]
    # Quotes, each copied verbatim from the handbook chunk the script cites.
    quotes: dict[str, str]
    conflict_topic: str
    conflict_resolution: str
    missing: str
    # Why a triage answer is wrong, keyed by query id; written into the recorded response.
    error_notes: dict[str, str]
    # The edit that turns the q10 quote into one that is not in the chunk: (before, after).
    quote_edit: tuple[str, str]


texts_for = catalog(__name__, Texts)
