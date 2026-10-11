"""Runtime text of prompt-caching's runtime.py: the rules, questions, dynamic line, report texts and the answer.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
The handbook the model reads is a per-language data file: locales/handbook/zh_CN.md and en.md.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # What the model reads: the rules before the handbook, the questions in order, the warmup request.
    rules: str
    questions: tuple[str, ...]
    warmup_question: str
    # The line that differs in every request, and how it follows the question in the stable-prefix layout.
    dynamic_line: str  # {number} {sent_at}
    question_with_dynamic: str  # {question} {dynamic}
    # The session tag at the top of the stable part; the fixed tag when runs are not isolated.
    session_tag: str  # {session}
    not_isolated: str
    # Purpose of a request (the purpose field of the cache events).
    purpose_warmup: str
    purpose_measure: str
    # Layout names, keyed by the layout code.
    layout_names: dict[str, str]
    answer: str  # {count} {layout}
    # Lab report.
    value_not_reported: str
    value_empty: str
    separator: str
    check_hash: str
    check_hash_detail: str  # {count} {distinct} {suffix}
    hash_suffix_warmup: str
    hash_suffix_plain: str
    check_reported: str
    check_reported_all: str
    check_reported_missing: str  # {rounds}
    check_explained: str
    check_explained_all: str
    unexplained_item: str  # {round} {cached}
    check_explained_detail: str  # {items}
    report_title: str  # {layout}
    report_summary: str
    report_summary_offline: str
    label_mode: str
    value_mode_offline: str
    value_mode_live: str
    label_layout: str
    label_model_calls: str
    label_reported: str
    label_hits: str
    label_ratio: str
    label_fields: str
    label_session: str
    label_note: str
    columns: tuple[str, ...]


texts_for = catalog(__name__, Texts)
