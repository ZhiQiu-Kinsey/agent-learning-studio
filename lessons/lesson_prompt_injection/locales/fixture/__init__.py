"""Text of the offline test model (fixtures.py) for prompt-injection, one file per run language.

Only what the scripted responses put into events: answers, the text it writes or sends, and the notes
that mark a scripted response as the fixture's, not a model's.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    answers: dict[str, str]  # keyed by the script's own names
    tip_failed: str  # {error}
    secret_suffix: str  # {key}
    tip_content: str
    overwrite_content: str
    post_nothing: str  # body sent when the key was never read
    post_conversation: str
    note_follows: str  # marks a call the script proposes because the material asked for it
    note_answer: str  # marks an answer the script writes because the material demanded it


texts_for = catalog(__name__, Texts)
