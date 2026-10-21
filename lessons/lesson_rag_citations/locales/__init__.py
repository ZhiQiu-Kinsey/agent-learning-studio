"""Runtime text of rag-citations: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
Category, reason and query-kind keys are the codes from citations.py and query_set.py.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The request: rules in the system prompt, sources and question in the user message.
    system_prompt: str
    user_prompt: str  # {sources} {question}
    no_hits: str  # the program's own "missing" text when retrieval returned nothing
    # Names for codes, keyed by code.
    kinds: dict[str, str]
    categories: dict[str, str]
    reasons: dict[str, str]
    sources: dict[str, str]  # who wrote the answer: model, offline_fixture, program
    # Citation report.
    report_citations_title: str
    report_citations_summary: str
    check_format: str
    check_provided: str
    check_quotes: str
    check_numbers: str
    check_declined: str
    check_conflict: str
    detail_count: str  # {ok} {total}
    label_model_calls: str
    label_citations: str
    label_unprovided: str
    label_quote_missing: str
    label_usage: str
    label_note: str
    columns_citations: tuple[str, ...]
    # Triage report.
    report_triage_title: str
    report_triage_summary: str
    label_retrieval_failures: str
    label_generation_failures: str
    label_passed: str
    columns_triage: tuple[str, ...]
    retrieval_values: dict[str, str]  # hit, partial, miss, no_gold
    answer_values: dict[str, str]  # answered, declined, invalid
    # Values.
    value_yes: str
    value_no: str
    value_none: str
    value_not_reported: str
    tokens_partly_reported: str  # {total} {missing}
    value_empty: str
    separator: str
    # The final answer, assembled by the program from checked claims only.
    answer_heading: str  # {query_id} {question}
    answer_claim: str  # {text} {ids} {status}
    answer_conflict: str  # {topic} {docs} {current}
    answer_current_unknown: str
    answer_insufficient: str  # {missing}
    answer_invalid: str
    answer_category: str  # {category}
    status_checked: str
    status_failed: str


texts_for = catalog(__name__, Texts)
