"""Runtime text of memory-lifecycle's runtime.py: the memories it writes, report texts and answers built by code.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
store.py's messages and the rules in system come from persistent-memory's locales/shared/.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Exercise "conflict": the values and sources the writers put, and the writer name of the first write.
    writer_initial: str
    plan_first: str
    plan_first_source: str
    plan_a: str
    plan_a_source: str
    plan_b: str
    plan_b_source: str
    plan_retry_suffix: str
    plan_retry_source: str
    # Exercise "expiry_delete": the temporary reminder.
    reminder_value: str
    reminder_source: str
    # Exercise "scope_filter": value and source of each seeded memory, keyed by memory key, and the preview question.
    seed_values: dict[str, str]
    seed_sources: dict[str, str]
    preview_question: str
    # Shared report pieces.
    label_note: str
    label_model_calls: str
    label_storage: str
    storage_scratch: str
    value_none: str
    value_yes: str
    value_no: str
    value_success: str
    value_rejected: str
    separator: str
    # Report of "conflict".
    conflict_title: str
    conflict_summary: str
    conflict_check_rejected: str
    conflict_check_rejected_failed: str
    conflict_check_kept: str
    conflict_check_kept_detail: str  # {value} {version}
    conflict_check_retried: str
    conflict_check_retried_detail: str  # {version}
    label_final_version: str
    conflict_columns: tuple[str, ...]
    row_a_write: str
    row_b_write: str
    row_b_retry: str
    conflict_answer: str  # {outcome} {value} {version}
    outcome_rejected: str
    outcome_not_rejected: str
    # Report of "expiry_delete".
    expiry_title: str
    expiry_summary: str
    expiry_check_hidden: str
    expiry_check_hidden_detail: str
    expiry_check_live: str
    expiry_check_live_detail: str  # {seconds}
    expiry_check_deleted: str
    expiry_check_deleted_detail: str
    label_ttl: str
    expiry_columns: tuple[str, ...]
    row_after_write: str
    row_after_delete: str
    expiry_answer: str  # {visibility} {deletion}
    expiry_answer_hidden: str
    expiry_answer_live: str
    expiry_answer_deleted: str
    expiry_answer_not_deleted: str
    # Report of "scope_filter".
    scope_title: str
    scope_summary: str
    scope_check_recalled: str
    scope_check_recalled_detail: str  # {keys}
    scope_check_draft: str
    scope_check_draft_detail: str
    scope_check_flagged: str
    scope_check_flagged_detail: str
    scope_check_not_executed: str
    scope_check_not_executed_detail: str  # {count}
    scope_check_end_task: str
    scope_check_end_task_detail: str
    label_seeded: str
    label_recalled_now: str
    label_filtered: str
    label_ended: str
    scope_columns: tuple[str, ...]
    scope_answer: str  # {count}


texts_for = catalog(__name__, Texts)
