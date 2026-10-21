"""Text of the offline test model (fixtures.py) for streaming-cancel, one file per run language.

Twelve scripted items about one round of an Agent loop, three sentences each. A short answer uses the first
sentence of every item, a long one all three.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    items: tuple[tuple[str, str, str], ...]


texts_for = catalog(__name__, Texts)
