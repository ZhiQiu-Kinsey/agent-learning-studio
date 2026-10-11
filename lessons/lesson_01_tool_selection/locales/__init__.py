"""Runtime text of tool-selection's main.py: the system prompt and the command-line texts.

zh_CN.py and en.py each fill every field. The tools' own text (descriptions, errors)
is in locales/tools/, because tools.py is shared with other lessons.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The system prompt of the native loop.
    system_prompt: str
    # Command-line run.
    cli_title: str
    cli_examples: tuple[str, ...]


texts_for = catalog(__name__, Texts)
