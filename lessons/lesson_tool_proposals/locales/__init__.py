"""Runtime text of tool-proposals: the system prompt, the answer the runner writes and the lab report.

zh_CN.py and en.py each fill every field. The tool descriptions are not here: they come
from tool-selection's shared catalog (lessons/lesson_01_tool_selection/locales/tools/).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The question used when the question box is empty.
    default_question: str
    # The system prompt: which question goes to which tool.
    system_prompt: str
    # Error when the response has no choices[0].
    missing_choices: str
    # Answers the runner writes.
    empty_content: str
    proposals_answer: str  # {count} {calls}
    call_separator: str
    # Lab report.
    report_title: str
    report_summary: str
    label_finish_reason: str
    label_proposal_count: str
    label_content_length: str
    columns: tuple[str, ...]
    value_not_reported: str
    value_none: str
    value_empty: str


texts_for = catalog(__name__, Texts)
