"""Runtime text of reliable-tools: tool error messages, the sample answer, report texts and answers built by code.

zh_CN.py and en.py each fill every field; store.py, faults.py and runtime.py read them with texts_for(locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Tool errors (store.py, faults.py): they travel in tool_result.error.
    store_timeout: str  # {seconds}
    unknown_learner: str  # {learner}
    unknown_exercise: str  # {exercise} {known}
    bad_answer: str
    key_conflict: str  # {key}
    no_credits: str  # {learner}
    outbox_busy: str
    unknown_submission: str  # {submission_id}
    response_lost: str
    # The answer every submission carries.
    sample_answer: str
    # Shared report pieces; dictionaries are keyed by the codes runtime.py and retry.py use.
    label_note: str
    label_model_calls: str
    label_attempts: str
    label_tool_calls: str
    value_none: str
    value_success: str
    separator: str
    reasons: dict[str, str]
    categories: dict[str, str]
    decisions: dict[str, str]
    statuses: dict[str, str]
    attempt_columns: tuple[str, ...]
    # Exercise "read-timeout".
    read_title: str
    read_summary: str
    read_check_bounded: str
    read_check_bounded_detail: str  # {attempts} {limit}
    read_check_unchanged: str
    read_check_unchanged_detail: str
    read_check_result: str
    read_check_result_ok: str  # {credits}
    read_check_result_failed: str  # {reason}
    label_waits: str
    label_stop_reason: str
    read_answer_ok: str  # {credits} {attempts}
    read_answer_failed: str  # {attempts} {reason}
    # Exercise "classify".
    operations: dict[str, str]
    classify_title: str
    classify_summary: str
    classify_check_no_retry: str
    classify_check_no_retry_detail: str
    classify_check_retried: str
    classify_check_retried_detail: str
    classify_check_once: str
    classify_check_once_detail: str  # {rows} {credits} {files}
    classify_columns: tuple[str, ...]
    classify_answer: str  # {calls}
    # Exercise "lost-response".
    modes: dict[str, str]
    lost_title: str
    lost_summary: str
    lost_check_once: str  # {mode}
    lost_check_detail: str  # {rows} {credits} {status}
    lost_check_key: str
    lost_check_key_detail: str  # {key}
    lost_columns: tuple[str, ...]
    lost_answer: str  # {blind} {stop} {keyed}
    # Exercise "partial-write".
    step_submit: str
    step_export: str
    step_compensate: str
    finals: dict[str, str]
    partial_title: str
    partial_summary: str
    partial_check_state: str
    partial_check_state_detail: str  # {status} {credits} {files}
    partial_check_history: str
    partial_check_history_detail: str
    label_final_status: str
    partial_columns: tuple[str, ...]
    partial_answers: dict[str, str]


texts_for = catalog(__name__, Texts)
