"""Runtime text of document-loading: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
Developer-facing details (LoadIssue.detail) stay in English in loader.py; learners read the explanations here.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Shared values.
    value_none: str
    value_empty: str
    list_separator: str
    preset_names: dict[str, str]
    check_untrusted: str
    check_untrusted_detail: str  # {count}
    # Exercise 1: corpus manifest, chunk catalog and cross-section evidence.
    manifest_title: str
    manifest_summary: str
    label_documents: str
    label_corpus_version: str
    manifest_columns: tuple[str, ...]
    catalog_title: str  # {preset}
    catalog_summary: str
    check_locate: str
    check_locate_detail: str  # {located} {total}
    label_chunks: str
    label_max_chars: str
    label_overlap: str
    label_average: str
    label_repeated: str
    label_window_cuts: str
    catalog_columns: tuple[str, ...]
    evidence_title: str
    evidence_summary: str
    check_one_chunk: str  # {query} {preset}
    label_cross_complete: str  # {preset}
    evidence_columns: tuple[str, ...]
    chunk_done: str  # {preset} {chunks} {located} {complete} {total}
    # Exercise 2: the load log; issue kinds are code, their names and explanations are text.
    issue_names: dict[str, str]
    issue_explanations: dict[str, str]
    outcome_loaded: str
    outcome_loaded_with_issue: str
    outcome_skipped: str
    issues_title: str
    issues_summary: str
    check_accounted: str
    check_accounted_detail: str  # {count}
    label_scanned: str
    label_loaded: str
    label_issues: str
    label_silent: str
    issues_columns: tuple[str, ...]
    issues_done: str  # {scanned} {loaded} {issues} {silent}
    # Exercise 3: the two framings, the string checks on the reply, and the report.
    mixed_system: str  # {material}
    tagged_system: str
    tagged_user: str  # {documents} {question}
    limit_marker: str
    injection_markers: tuple[str, ...]
    framing_names: dict[str, str]
    verdict_names: dict[str, str]
    trust_title: str
    trust_summary: str
    check_limit: str  # {framing}
    check_limit_detail: str  # {marker}
    check_no_injection: str  # {framing}
    check_no_injection_detail: str
    label_source: str
    source_offline: str
    source_model: str  # {model}
    label_chunks_sent: str
    trust_columns: tuple[str, ...]
    trust_done: str  # {framing} {verdict}


texts_for = catalog(__name__, Texts)
