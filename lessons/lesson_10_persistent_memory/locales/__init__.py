"""Runtime text of persistent-memory's runtime.py: the question, report texts and answers built by code.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
store.py's messages and the rules in system are in locales/shared/, because memory-lifecycle imports them.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The question after the <memory> block in the recall exercises.
    question: str
    # The controlled sample the offline test seeds before the read-only exercises.
    seed_value: str
    seed_source: str
    # Error when the response has no text answer.
    no_text_answer: str
    # Shared report pieces.
    storage_temporary: str
    storage_local: str
    label_note: str
    label_model_calls: str
    label_storage: str
    value_none: str
    value_yes: str
    value_no: str
    separator: str
    columns_steps: tuple[str, ...]
    # Exercise "reopen".
    reopen_title: str
    reopen_summary: str
    reopen_check_value: str
    reopen_check_value_detail: str
    reopen_check_other: str
    reopen_check_other_detail: str  # {other}
    label_version_after: str
    row_first_write: str
    row_second_read: str
    row_other_namespace: str
    reopen_missing: str
    reopen_answer: str  # {value} {version}
    # Exercise "recall_only".
    recall_only_title: str
    recall_only_summary: str
    recall_only_check_writes: str
    recall_only_check_writes_detail: str  # {writes}
    recall_only_check_source: str
    recall_only_check_source_detail: str
    label_lookup: str
    value_found: str
    row_read_only: str
    recall_only_missing: str
    recall_only_answer: str  # {value} {source} {version}
    # Exercises "recall_answer" and "recall_other_namespace".
    recall_title: str
    recall_summary: str
    recall_check_writes: str
    recall_check_writes_detail: str  # {writes}
    recall_check_placed: str
    recall_check_placed_detail: str  # {count}
    recall_check_grounded: str
    recall_check_empty: str
    recall_cited_detail: str  # {keys}
    label_namespace: str
    label_recalled: str
    recall_columns: tuple[str, ...]
    recall_empty_row: str


texts_for = catalog(__name__, Texts)
