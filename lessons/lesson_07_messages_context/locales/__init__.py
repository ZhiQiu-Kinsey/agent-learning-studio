"""Runtime text of messages-context: the five context messages, the variant names and the report.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
The protocol errors of validate_tool_history are in locales/protocol/, because other
lessons import that check.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The five context messages: the system prompt, the earlier conversation ({day}, {student_id})
    # and this turn's question.
    system_prompt: str
    conversation: str
    question: str
    # free_day code -> the day as written in the conversation and looked for in the answer.
    weekdays: dict[str, str]
    # The word that starts the basis line the system prompt asks for; the report screens for it.
    basis_keyword: str
    # VARIANTS code -> variant name, used in lesson.context and the report.
    variant_names: dict[str, str]
    # Tool error (lookup_score) and a failed lookup.
    unknown_student: str  # {student_id}
    lookup_failed: str
    # Protocol check outcome.
    protocol_passed: str
    protocol_rejected: str  # {error}
    # A response without a comparable text answer.
    missing_message: str
    no_text_answer: str
    # lesson.context: who wrote the five messages.
    parts_detail: str
    # The answer column of a variant that got no answer.
    outcome_not_sent: str
    outcome_provider_rejected: str
    # The run's answer.
    final_answer: str  # {sent}, {blocked}
    # Lab report.
    report_title: str
    report_summary: str
    check_protocol: str
    check_protocol_detail: str
    check_blocked: str
    check_blocked_none: str
    label_model_calls: str
    label_blocked: str
    label_tool_calls: str
    label_student_id: str
    label_free_day: str
    label_note: str
    note_empty: str
    columns: tuple[str, ...]


texts_for = catalog(__name__, Texts)
