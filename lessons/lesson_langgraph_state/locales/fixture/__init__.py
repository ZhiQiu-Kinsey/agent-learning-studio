"""Text of the offline test model (fixtures.py) for langgraph-state, one file per run language.

It holds only the answer template the scripted writer fills with the real tool result.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    answer: str  # {total_minutes}, {minutes_per_day}, {days}


texts_for = catalog(__name__, Texts)
