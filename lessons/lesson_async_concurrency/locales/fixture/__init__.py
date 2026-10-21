"""Text of the offline test model (fixtures.py) for async-concurrency, one file per run language.

It holds only what the scripted replies put into events: one summary sentence per lesson note.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The one-sentence summary the script gives for each note, keyed by lesson slug.
    summaries: dict[str, str]


texts_for = catalog(__name__, Texts)
