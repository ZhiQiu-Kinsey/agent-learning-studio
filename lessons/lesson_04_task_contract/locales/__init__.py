"""Runtime text of task-contract: everything this lesson puts into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The task card, written before the run: goal, input_scope, output, evidence, failure, stop.
    task_card: dict[str, str]
    # The stop field of the goal loop, with the attempt limit.
    stop_with_limit: str
    # Acceptance checks: label, then the detail for each outcome.
    check_ended: str
    detail_ended: str
    check_referenced: str
    detail_referenced: str
    detail_not_referenced: str
    check_tool_ok: str
    detail_tool_ok: str
    detail_tool_not_ok: str
    check_arguments: str
    check_value: str
    detail_expected: str
    check_consistent: str
    detail_consistent: str
    # How call arguments appear in a detail, and the value when there is no evidence.
    arguments_format: str
    value_none: str
    # A failed check as one reason: "label: detail".
    reason: str
    reason_separator: str
    all_passed: str
    verdict_passed: str
    verdict_failed: str
    # The final answer.
    answer_passed: str
    answer_limit: str
    answer_failed: str
    # Lab report.
    report_title: str
    summary_passed: str
    summary_failed: str
    label_tool_calls: str
    label_scenario: str
    label_note: str
    value_empty: str
    label_attempts: str
    label_limit: str
    label_stop_reason: str
    stop_passed: str
    stop_limit: str
    columns: tuple[str, ...]


texts_for = catalog(__name__, Texts)
