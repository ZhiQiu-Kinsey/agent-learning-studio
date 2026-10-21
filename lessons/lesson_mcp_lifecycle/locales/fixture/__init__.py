"""Scripted model text of the offline test model (fixtures.py): serves automated tests only."""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    query: str
    answer: str  # {book}


texts_for = catalog(__name__, Texts)
