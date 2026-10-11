"""Runtime text of application-state: the material, step labels, snapshot actions, terminal reasons and the report.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
State names (ready, running, ...) and source keys are code and stay the same in every language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The two local materials: source key -> excerpt. "missing" is deliberately absent.
    source_excerpts: dict[str, str]
    # State machine errors (TaskState).
    not_running: str
    illegal_transition: str  # {current}, {target}
    reason_required: str
    completion_unproven: str
    # Step labels recorded in state.steps.
    step_read_index: str
    step_check_source: str
    step_summarize: str
    # Snapshot actions (lesson.state).
    action_created: str
    action_started: str
    action_waiting: str
    action_evidence: str
    action_terminal: str
    # Terminal reasons and the result.
    reason_missing: str
    reason_budget_check: str
    reason_budget_summary: str
    reason_completed: str
    result: str  # {source_key}, {excerpt}
    # The run's answer.
    answer_completed: str  # {result}, {goal}
    answer_failed: str  # {reason}
    # Lab report.
    report_title: str
    report_summary: str
    check_reason: str
    check_success: str
    check_success_detail: str
    check_success_not_applicable: str
    check_separate: str
    check_separate_detail: str
    label_status: str
    label_evidence: str
    label_messages: str
    label_step_budget: str
    label_used_steps: str
    label_note: str
    value_empty: str
    columns: tuple[str, ...]


texts_for = catalog(__name__, Texts)
