"""Runtime text of this lesson; zh_CN.py and en.py each fill every field.

Strategy names (keyword, vector, hybrid), query kinds, filter reasons and update plan keys
are codes; these catalogs only translate how they are shown.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    rerank_system: str
    # Shared cells and separators
    separator: str
    value_none: str
    value_absent: str
    value_not_reported: str
    hit_item: str  # {chunk} {score}
    verdict_complete: str  # {rank}
    verdict_partial: str  # {rank} {missing}
    verdict_miss: str
    verdict_no_answer: str  # {count}
    kinds: dict[str, str]
    col_query: str
    col_kind: str
    col_verdict: str
    # Compare: one report per strategy
    strategy_titles: dict[str, str]
    strategy_summaries: dict[str, str]
    list_columns: dict[str, str]
    label_hit: str
    label_complete: str
    label_no_answer_returned: str
    # Compare: ranks-only comparison
    compare_title: str
    compare_summary: str
    check_same_source: str
    check_same_source_detail: str  # {version} {queries} {chunks} {count}
    label_hits_of: dict[str, str]
    label_keyword_only: str
    label_vector_only: str
    label_incomplete_all: str
    label_settings: str
    settings: str  # {top_k} {k}
    compare_columns: tuple[str, ...]
    rrf_title: str  # {query}
    rrf_summary: str  # {k} {text}
    rrf_columns: tuple[str, ...]
    label_rrf_k: str
    compare_answer: str  # {total} {keyword} {vector} {hybrid}
    # Rerank
    rerank_title: str  # {query}
    rerank_summary: str  # {text}
    candidate_cell: str  # {chunk} {mark}
    gold_mark: str
    check_reply_valid: str
    reply_clean: str
    reply_errors: dict[str, str]
    problem_labels: dict[str, str]  # {items}
    check_pool_covers: str
    label_before: str  # {k}
    label_after: str  # {k}
    label_extra_calls: str
    label_rerank_tokens: str
    label_rerank_ms: str
    label_prompt_chars: str
    label_candidates: str
    rerank_columns: tuple[str, ...]
    rerank_answer: str  # {k} {before} {after} {tokens}
    # Update: metadata filter
    filter_title: str
    filter_summary: str
    filter_off: str
    filter_on: str
    filter_reasons: dict[str, str]  # {by}: the newer doc_id, empty for doc_id_filter
    removed_item: str  # {chunk} {reason}
    label_filtered_out: str
    label_filtered_records: str
    label_old_hits: str
    label_candidates_left: str
    filter_columns: tuple[str, ...]
    # Update: changed corpus, stale index
    change_title: str
    change_summary: str
    change_actions: dict[str, str]
    change_columns: tuple[str, ...]
    check_index_stale: str
    versions_detail: str  # {index} {corpus}
    stale_reasons: dict[str, str]
    stale_item: str  # {query} {items}
    stale_entry: str  # {chunk} {reason}
    label_stale_hits: str
    # Update: after the incremental update
    update_title: str
    update_summary: str
    plan_labels: dict[str, str]
    label_embedded: str
    label_filter_after_delete: str
    label_index_version: str
    check_version_match: str
    check_ids_match: str
    ids_detail: str  # {index} {corpus}
    check_no_deleted: str
    check_no_stale: str
    check_edited_text: str
    update_columns: tuple[str, ...]
    update_answer: str  # {changed} {added} {removed} {embedded} {passed} {total}


texts_for = catalog(__name__, Texts)
