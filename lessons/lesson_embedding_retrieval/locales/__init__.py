"""Runtime text of embedding-retrieval: every label, check and answer this lesson writes into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Embedding requests and reported usage.
    size_mismatch: str  # {asked}, {got}
    not_reported: str
    partly_reported: str  # {total}, {missing}
    # Why a saved index is refused.
    reason_field: str  # {field}, {old}, {new}
    reason_chunks: str  # {removed}, {added}
    reason_unreadable: str  # {error}
    # The index report.
    index_title: str
    index_summary: str  # {status}, {chunks}
    status_built: str
    status_reused: str
    status_rebuilt: str
    label_status: str
    label_model: str
    label_dimensions: str
    label_corpus_version: str
    label_chunks: str
    label_index_calls: str
    label_index_file: str
    label_vector_source: str
    label_stale_reasons: str
    location_project: str
    location_temporary: str
    location_memory: str
    source_live: str  # {model}
    source_test: str
    # Cost of the whole run.
    label_embedding_calls: str
    label_embedding_usage: str
    # Exercise: build the index and search it.
    search_title: str
    search_summary: str  # {query}, {count}
    label_doc_filter: str
    filter_all: str
    label_returned: str
    search_columns: tuple[str, ...]
    search_answer: str  # {count}, {first}, {score}
    search_answer_empty: str  # {doc}
    # Exercise: vector retrieval against the BM25 baseline.
    kinds: dict[str, str]
    compare_title: str
    compare_summary: str  # {total}, {answerable}
    label_query_set: str
    label_bm25_hits: str
    label_vector_hits: str
    label_bm25_complete: str
    label_vector_complete: str
    label_only_bm25: str
    label_only_vector: str
    label_no_answer_returned: str
    check_same_queries: str
    check_same_queries_detail: str  # {count}
    check_same_chunks: str
    check_same_chunks_detail: str  # {count}, {version}
    compare_columns: tuple[str, ...]
    outcome_complete: str  # {rank}
    outcome_partial: str  # {rank}
    outcome_miss: str
    outcome_no_gold: str  # {returned}
    verdicts: dict[str, str]  # key: BM25 hit then vector hit, "1" or "0"
    verdict_no_gold: str
    compare_answer: str  # {answerable}, {bm25}, {vector}, {only_bm25}, {only_vector}
    # Exercise: a stale index is refused.
    stale_title: str
    stale_summary: str  # {change}
    label_change: str
    change_dimensions: str  # {old}, {new}
    change_corpus: str  # {doc}
    check_stale: str
    check_stale_missed: str
    check_size_guard: str
    check_separate_files: str
    check_orphans: str
    check_old_leak: str
    check_new_clean: str
    none: str
    stale_columns_dimensions: tuple[str, ...]
    stale_columns_corpus: tuple[str, ...]
    stale_answer: str  # {change}, {reasons}


texts_for = catalog(__name__, Texts)
