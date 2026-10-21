"""Runtime text of delegation-budget: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py and contracts.py read them with texts_for(context.locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The evidence pack: five short documents keyed by id; d1 and d2 disagree on the deadline.
    docs: dict[str, str]
    doc_titles: dict[str, str]
    doc_block: str
    # One question per field, and the short name of each field in reports.
    questions: dict[str, str]
    field_names: dict[str, str]
    # The prompt a subtask receives: who it is, its question, its documents, the output and the stop rule.
    subtask_system: str
    contract_brief: str
    docs_header: str
    output_with_evidence: str
    output_without_evidence: str
    stop_rule: str
    # The coordinator's delegation contract as a task card (lesson.task_card).
    card_goal: str
    card_input_scope: str
    card_output_full: str
    card_output_plain: str
    card_evidence_full: str
    card_evidence_missing: str
    card_failure: str
    card_stop: str
    # Task graph (lesson.plan).
    plan_reason: str
    plan_progress: str
    plan_step: str
    # The merge check: its structured error and the text of each problem code.
    merge_not_list: str
    problem_labels: dict[str, str]
    # Subtask outcomes, stop reasons and the final verdict.
    status_names: dict[str, str]
    reason_names: dict[str, str]
    verdicts: dict[str, str]
    budget_stop_detail: str
    late_detail: str
    merge_detail: str
    # Lab report.
    report_title: str
    report_summary: str
    check_subtask: str
    check_accepted: str
    check_not_found: str
    check_not_run: str
    check_required: str
    check_required_ok: str
    check_required_missing: str
    label_verdict: str
    label_required: str
    value_required: str
    label_accepted: str
    value_accepted: str
    label_conflicts: str
    label_unfinished: str
    label_model_calls: str
    label_budget_calls: str
    value_budget: str
    label_total_tokens: str
    label_budget_tokens: str
    value_budget_tokens: str
    value_not_reported: str
    tokens_partly_reported: str
    label_wall_ms: str
    label_late: str
    label_note: str
    value_empty: str
    value_none: str
    value_yes: str
    value_no: str
    list_separator: str
    table_columns: tuple[str, ...]
    # The answer the coordinator writes from the merged results; no model writes it.
    answer_header: str
    answer_value: str
    answer_conflict: str
    answer_conflict_item: str
    answer_missing: str
    answer_unfinished: str
    answer_unfinished_item: str


texts_for = catalog(__name__, Texts)
