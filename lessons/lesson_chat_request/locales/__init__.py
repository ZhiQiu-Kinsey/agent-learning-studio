"""Runtime text of chat-request: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The question used when the question box is empty.
    default_question: str
    # What each common finish_reason value means.
    finish_reasons: dict[str, str]
    # The answer when the response content is empty.
    empty_content: str
    # Error when the response has no choices[0].
    missing_choices: str
    # Lab report.
    report_title: str
    report_summary: str
    label_system: str
    label_max_tokens: str
    label_answer_length: str
    label_finish_reason: str
    label_reason_meaning: str
    label_prompt_tokens: str
    label_completion_tokens: str
    label_total_tokens: str
    label_reasoning_tokens: str
    label_reasoning_chars: str
    value_yes: str
    value_no: str
    value_not_set: str
    value_not_reported: str
    value_other_reason: str
    column_index: str


texts_for = catalog(__name__, Texts)
