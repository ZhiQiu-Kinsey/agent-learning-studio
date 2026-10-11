"""Runtime text of reflection-revision: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The task and the two system prompts.
    spec: str
    writer_system: str
    self_review_system: str
    # User messages: first draft, self-review, revision.
    draft_request: str
    self_review_request: str
    revision_request: str
    # Test results that become review feedback.
    pattern_invalid: str
    pattern_not_compiled: str
    failure: str
    expected_words: dict[str, str]
    actual_words: dict[str, str]
    # Reading the model's JSON reply.
    no_json_object: str
    json_not_object: str
    missing_regex: str
    # Why the loop stopped, keyed by stop code.
    stop_reasons: dict[str, str]
    # Lab report.
    reviewer_names: dict[str, str]
    issue_separator: str
    report_titles: dict[str, str]
    report_summary: str
    check_final: str
    final_detail: str
    final_detail_error: str
    label_stop_reason: str
    label_iterations: str
    label_max_iters: str
    label_model_calls: str
    label_total_tokens: str
    label_final_regex: str
    label_note: str
    tokens_partly_reported: str
    value_not_reported: str
    value_empty: str
    table_columns: tuple[str, ...]
    # The final answer.
    answer_passed: str
    answer_failed: str


texts_for = catalog(__name__, Texts)
