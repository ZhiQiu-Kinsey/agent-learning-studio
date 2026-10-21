"""Text of the offline test model (fixtures.py) for delegation-budget, one file per run language.

It holds only what the scripted replies put into events: the value each document states and the sentence quoted for it.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The value the script reports for each document.
    values: dict[str, str]
    # The sentence the script quotes from each document; each one is copied from the document text.
    quotes: dict[str, str]


texts_for = catalog(__name__, Texts)
