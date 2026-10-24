"""Runtime text of keyword-retrieval's runtime.py: rewritten queries, report texts and answers built by code.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
Query wording itself is data in lesson_document_loading/corpus/queries.json, one text per language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The synonym queries asked again in the handbook's own words, keyed by query id.
    rewrites: dict[str, str]
    # Display names of the query kinds in queries.json, keyed by kind.
    kinds: dict[str, str]
    # Shared report pieces.
    label_note: str
    label_corpus_version: str
    label_query_set_version: str
    label_chunks: str
    label_params: str
    params_value: str  # {k1} {b} {top_k}
    label_model_calls: str
    value_none: str
    value_yes: str
    value_no: str
    value_not_applicable: str
    separator: str
    # Exercise "query-table".
    table_title: str
    table_summary: str
    check_traceable: str
    check_traceable_detail: str
    check_versions: str
    check_versions_detail: str  # {corpus} {queries}
    check_rerun: str
    check_rerun_detail: str
    label_hit_rate: str
    label_hit_count: str
    label_complete_rate: str
    label_mrr: str
    label_missed: str
    table_columns: tuple[str, ...]
    table_answer: str  # {hits} {graded} {complete} {missed}
    # Exercise "explain-score".
    explain_title: str
    explain_summary: str
    check_sum: str
    check_sum_detail: str  # {total} {score}
    label_chunk: str
    label_rank: str
    label_score: str
    label_length: str
    length_value: str  # {length} {avg}
    label_length_norm: str
    label_baseline_score: str
    label_baseline_rank: str
    explain_columns: tuple[str, ...]
    explain_answer: str  # {chunk_id} {score} {rank}
    check_found: str
    error_no_match: str
    error_unknown_chunk: str  # {chunk_id}
    explain_failed_summary: str
    explain_failed_answer: str  # {error}
    # Exercise "misses".
    misses_title: str
    misses_summary: str
    check_reasons: str
    check_reasons_detail: str
    check_rewrites: str
    check_rewrites_detail: str  # {hits} {total}
    check_no_answer: str
    check_no_answer_detail: str
    label_rewrites_hit: str
    label_no_answer_top: str
    misses_columns: tuple[str, ...]
    reasons: dict[str, str]
    value_hit: str
    reason_no_answer: str
    misses_answer: str  # {missed} {total} {rewrites} {no_answer}


texts_for = catalog(__name__, Texts)
