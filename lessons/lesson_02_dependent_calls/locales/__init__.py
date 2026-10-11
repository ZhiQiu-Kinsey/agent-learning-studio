"""Runtime text of dependent-calls' main.py: the system prompt and the command-line texts.

zh_CN.py and en.py each fill every field. The tools' own text (descriptions, errors) is in
tool-selection's shared catalog, lessons/lesson_01_tool_selection/locales/tools/. The Code
scene annotates system_prompt line by line, so it keeps one sentence per line in every language.
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
