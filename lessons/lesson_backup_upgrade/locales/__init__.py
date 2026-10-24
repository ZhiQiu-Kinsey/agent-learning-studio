"""Runtime text of backup-upgrade: every label, detail and answer the exercises write into events and reports.

zh_CN.py and en.py each fill every field; the code reads them with texts_for(context.locale).
The demo data written into the teaching databases (memory_topics and friends) is in here too, so an English
run never puts Chinese into a file it later reads back.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Demo data written into the throwaway databases.
    event_note: str  # {n}
    memory_topics: tuple[str, ...]
    memory_value: str  # {topic} {n}; the plan-NNNN token is what the bit-flip fault changes
    memory_source: str
    # Shared report pieces.
    label_note: str
    label_model_calls: str
    value_none: str
    value_yes: str
    value_no: str
    value_not_applicable: str
    value_removed: str
    value_unreadable: str
    separator: str
    # Names of the choices shown in the report.
    method_names: dict[str, str]
    schedule_names: dict[str, str]
    scope_names: dict[str, str]
    damage_names: dict[str, str]
    failure_names: dict[str, str]
    safeguard_names: dict[str, str]
    recovery_names: dict[str, str]
    policy_names: dict[str, str]
    # Exercise online_backup.
    online_title: str  # {method}
    online_summary: str
    online_columns: tuple[str, ...]
    check_integrity: str  # {file}
    check_rows: str  # {file}
    rows_detail: str  # {rows} {missing} {broken}
    label_method: str
    label_writes: str
    label_committed_before: str
    label_schedule: str
    verdict_ok: str
    verdict_bad: str
    online_answer_ok: str  # {method}
    online_answer_bad: str  # {method}
    # Exercise restore_drill.
    restore_title: str
    restore_summary: str
    restore_columns: tuple[str, ...]
    check_no_secrets: str
    detail_no_secrets: str
    check_manifest: str
    detail_manifest_ok: str
    detail_manifest_bad: str  # {files}
    check_damage_caught: str
    detail_caught_by_manifest: str
    detail_caught_by_acceptance: str
    detail_not_caught: str
    check_runs_readable: str
    detail_runs: str  # {count}
    check_memory_recallable: str
    detail_memory: str  # {recalled} {stored}
    check_integrity_both: str
    check_digest: str
    detail_digest_ok: str
    detail_digest_bad: str
    label_scope: str
    label_damage: str
    label_verify: str
    label_runs_restored: str
    fault_note_backup: str
    restore_answer_refused: str
    restore_answer_ok: str
    restore_answer_bad: str
    restore_answer_secrets: str  # {answer} {files}
    # Exercise upgrade_rollback.
    upgrade_title: str
    upgrade_summary: str
    upgrade_columns: tuple[str, ...]
    check_upgrade: str
    detail_upgrade_ok: str
    detail_upgrade_error: str  # {error}
    detail_upgrade_check: str  # {before} {after}
    check_service: str  # {version}
    detail_service_ok: str  # {runs} {memories}
    problem_versions: str  # {runs} {memory} {version}
    problem_runs: str  # {error}
    problem_memory: str  # {error}
    problem_integrity: str
    check_data_unchanged: str
    label_failure: str
    label_safeguard: str
    label_final_versions: str
    label_recovery: str
    rollback_transaction_note: str
    rollback_committed_note: str
    fault_abort: str  # {file} {rows}
    fault_bug: str  # {file}
    answer_success: str  # {head} {state}
    answer_failure: str  # {head} {recovery} {state}
    upgrade_answer_ok: str
    upgrade_answer_failed: str
    recovery_answer_backup: str
    recovery_answer_transaction: str
    recovery_answer_committed: str
    recovery_answer_backup_failed: str
    recovery_answer_none: str
    final_answer_ok: str
    final_answer_bad: str
    # Exercise retention.
    retention_title: str
    retention_summary: str
    retention_columns: tuple[str, ...]
    check_restorable: str
    detail_restorable: str  # {backup}
    detail_not_restorable: str
    check_newest_verified: str
    detail_newest_verified: str
    detail_newest_damaged: str
    label_kept: str
    label_removed: str
    label_runs_lost: str
    label_policy: str
    retention_answer: str  # {backup} {lost}
    retention_answer_none: str


texts_for = catalog(__name__, Texts)
