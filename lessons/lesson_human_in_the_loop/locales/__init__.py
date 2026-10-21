"""Runtime text of human-in-the-loop: prompts, tool errors, answers and the two reports.

zh_CN.py and en.py each fill every field. Status codes, step and checkpoint names, tool names, event
names and field names are code and stay the same in every language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The draft request.
    draft_system: str
    draft_request: str  # {topic}, {difficulty}
    difficulty_names: dict[str, str]
    # The approval card and the receipt request.
    approval_summary: str  # {title}
    receipt_system: str
    receipt_prompt: str  # {facts}
    answer_empty: str
    # Tool errors of the bank.
    bank_bad_operation: str
    bank_bad_origin: str
    bank_bad_exercise: str  # {fields}
    # The run's answer when the model wrote none: status -> template ({reason}, {checkpoint}, {point}).
    answers: dict[str, str]
    reasons: dict[str, str]
    point_names: dict[str, str]
    # Report 1: what the bank holds.
    ledger_title: str
    ledger_summary: str
    ledger_empty: str
    ledger_columns: tuple[str, ...]
    origin_names: dict[str, str]
    label_rows_operation: str
    label_rows_total: str
    # Report 2: what this run did.
    run_title: str
    status_summaries: dict[str, str]
    check_gate: str
    detail_gate: str  # {approved}, {rows}
    check_once: str
    detail_once: str  # {operation}, {rows}
    check_draft: str
    detail_draft: str  # {count}, {kind}
    check_edit: str
    detail_edit: str  # {saved}
    kind_names: dict[str, str]
    label_status: str
    label_kind: str
    label_thread: str
    label_resumed_from: str
    label_operation: str
    label_checkpoints: str
    label_approval: str
    label_lookup: str
    label_write: str
    label_model_calls: str
    label_note: str
    approval_carried: str
    lookup_names: dict[str, str]
    write_names: dict[str, str]
    edited_yes: str
    edited_no: str
    yes_text: str
    no_text: str
    value_none: str
    diff_columns: tuple[str, ...]
    field_title: str
    field_difficulty: str
    field_body: str


texts_for = catalog(__name__, Texts)
