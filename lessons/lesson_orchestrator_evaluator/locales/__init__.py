"""Runtime text of orchestrator-evaluator: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The task: the key point of each lesson (keyed by slug) and the task statement.
    notes: dict[str, str]
    task: str
    # System prompts of the four roles.
    single_system: str
    orchestrator_system: str
    worker_system: str
    evaluator_system: str
    # User messages.
    single_request: str
    worker_request: str
    generator_request: str
    revision_request: str
    review_request: str
    # Format check problems and JSON reading.
    no_json: str
    not_an_object: str
    missing_question: str
    options_invalid: str
    options_duplicate: str
    answer_invalid: str
    missing_explanation: str
    no_json_found: str
    missing_item: str
    format_ok: str
    problem_separator: str
    # The orchestrator's plan.
    plan_error: str
    plan_reason: str
    plan_step: str
    no_workers: str
    # Roles in the call ledger, keyed by role code.
    roles: dict[str, str]
    # Why the revision loop stopped, keyed by stop code.
    stop_reasons: dict[str, str]
    # Lab report.
    report_titles: dict[str, str]
    report_summary: str
    check_format: str
    check_format_detail: str
    label_model_calls: str
    label_total_tokens: str
    label_role_calls: str
    label_stop_reason: str
    label_note: str
    role_count: str
    role_separator: str
    tokens_partly_reported: str
    value_not_reported: str
    value_empty: str
    columns_single: tuple[str, ...]
    columns_orchestrator: tuple[str, ...]
    columns_evaluator: tuple[str, ...]
    # The final answer.
    answer: str
    answer_with_stop: str


texts_for = catalog(__name__, Texts)
