"""Runtime text of sampling-variance: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The question used when the question box is empty.
    default_question: str
    # The system message: one name only, so string comparison means something.
    system_prompt: str
    # Error when the response has no choices[0].
    missing_choices: str
    # The final answer: a one-line count.
    answer: str
    # Lab report.
    report_title: str
    report_summary: str
    label_temperature: str
    label_repeats: str
    label_distinct: str
    label_most_common: str
    label_prompt_total: str
    label_completion_total: str
    label_total_total: str
    value_times: str
    value_not_reported: str
    column_number: str
    column_answer: str
    column_completion_tokens: str


texts_for = catalog(__name__, Texts)
