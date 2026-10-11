"""Runtime text of text-actions: prompts, the tool's description and error, parser errors, reports and answers.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
The protocol keywords (Thought, Action, Action Input, Observation, Final Answer) are part of
the format the parser reads, so they stay the same in every language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # System prompt of the text protocol: the format the parser expects.
    text_system: str
    # System prompt of the native group.
    native_system: str
    # The question sent to the model.
    question: str  # {student_id} {pass_line}
    # Tool description and its parameter (tool_definitions).
    tool_description: str
    tool_student_id: str
    # Tool error; it reaches the model as a structured error.
    unknown_student: str  # {student_id}
    # Parser errors, recorded in lesson.parse.
    invalid_json: str  # {error}
    not_an_object: str
    no_action: str
    # Rows of the step table.
    value_not_reported: str
    row_tool_calls: str  # {count}
    row_text_answer: str
    # Answers written by the runner when the model gave none.
    text_parse_failed: str
    text_no_final: str  # {limit}
    native_no_answer: str  # {limit}
    # Lab report of the text protocol.
    text_report_title_stop: str
    text_report_title_no_stop: str
    text_report_summary: str
    check_not_leaked: str
    detail_fabricated: str  # {count}
    check_final_answer: str
    detail_no_final: str
    detail_final_after_observation: str
    # Lab report of the native group.
    native_report_title: str
    native_report_summary: str
    check_native_answer: str
    detail_native_answer: str
    detail_native_unfinished: str  # {limit}
    # Shared report labels and values.
    label_protocol: str
    label_model_calls: str
    label_parse_failures: str
    label_fabricated: str
    label_student: str
    label_note: str
    value_empty_note: str
    text_columns: tuple[str, ...]
    native_columns: tuple[str, ...]


texts_for = catalog(__name__, Texts)
