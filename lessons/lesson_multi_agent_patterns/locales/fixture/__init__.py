"""Text of the offline test model (fixtures.py) for multi-agent-patterns, one file per run language.

It holds only what the scripted replies put into events: question stems and the exact quotes the script cites.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Question stem per topic.
    questions: dict[str, str]
    # The sentence the script quotes from each document; each one is copied from the document text.
    quotes: dict[str, str]


texts_for = catalog(__name__, Texts)
