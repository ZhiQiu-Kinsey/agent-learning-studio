"""Text of the offline test model and approver (fixtures.py) for human-in-the-loop, one file per run language."""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    draft: str  # {topic}: a title line, a blank line, then the exercise
    receipt: str  # {title}, {status}, {rows}
    edit_title_suffix: str
    edit_note: str


texts_for = catalog(__name__, Texts)
