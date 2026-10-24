"""Runtime text of agentic-rag: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; search_tool.py and runtime.py read them with texts_for(context.locale).
The questions themselves are data in lessons/lesson_document_loading/corpus/queries.json, one text per language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Tool definition of search_handbook: the name and parameter names are code, only descriptions are translated.
    tool_description: str
    tool_query: str
    tool_top_k: str
    # Structured errors of search_handbook.
    query_not_text: str
    query_too_long: str  # {limit}
    query_no_terms: str
    top_k_invalid: str  # {limit}
    search_budget_exhausted: str  # {limit}
    # System prompts and the static request.
    agentic_system: str
    static_system: str
    static_request: str  # {question} {results}
    # The progress note the runner inserts after each round of searches.
    progress_header: str  # {searches} {max_searches} {calls} {max_calls}
    attempt_line: str  # {n} {query} {returned} {new} {ids}
    duplicate_line: str  # {n} {first}
    progress_footer: str
    id_separator: str
    value_none: str
    # The last request after a limit, without searching.
    final_instruction: str  # {reason}
    # Why the run stopped and what the answer says, keyed by code.
    stop_reasons: dict[str, str]
    answer_statuses: dict[str, str]
    # Lab report.
    report_titles: dict[str, str]
    report_summary: str
    check_from_results: str
    check_from_results_detail: str  # {cited} {unknown}
    check_cover_gold: str
    check_cover_detail: str  # {matched} {missing}
    check_declined: str
    check_declined_detail: str  # {status} {cited}
    check_evidence: str
    check_within_limits: str
    check_within_detail: str  # {searches} {max_searches} {calls} {max_calls}
    label_question: str
    label_stop_reason: str
    label_answer_status: str
    label_searches: str  # {limit}
    label_model_calls: str  # {limit}
    label_duplicates: str
    label_rejected: str
    label_total_tokens: str
    label_elapsed: str  # {limit}
    label_note: str
    value_not_reported: str
    tokens_partly_reported: str  # {total} {missing}
    value_empty: str
    duplicate_cell: str  # {n}
    columns: tuple[str, ...]
    # The final answer the runner returns.
    final_answer: str  # {answer} {status} {citations} {missing} {stop}
    unfinished_answer: str  # {stop} {searches} {ids}


texts_for = catalog(__name__, Texts)
