"""Text of the offline test script (fixtures.py): the searches it proposes and the answers it gives, per run language.

It serves automated tests only. The texts live here, not in fixtures.py, so that file holds no language of its own.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    hop_one: str
    hop_two: str
    no_answer_queries: tuple[str, ...]
    answer_complete: str
    answer_first_hop: str
    missing_first_hop: str
    answer_none: str
    missing_none: str


texts_for = catalog(__name__, Texts)
