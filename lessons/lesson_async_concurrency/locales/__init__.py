"""Runtime text of async-concurrency: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py, tools.py and scheduler.py read them with texts_for(context.locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The four lesson notes the job reads, keyed by lesson slug, and the summary request built from one of them.
    notes: dict[str, str]
    summary_system: str
    summary_request: str  # {lesson} {note}
    # Tool errors (structured errors: error_type is the exception class, error is this text).
    unknown_note: str  # {lesson}
    note_locked: str  # {lesson}
    task_stopped: str  # {ms}
    sheet_bad_arguments: str
    sheet_bad_entry: str
    sheet_missing_input: str  # {missing}
    sheet_line: str  # {lesson} {text}
    summary_missing_input: str  # {lesson}
    empty_reply: str
    needs_model: str
    list_separator: str
    # The dependency graph of one variant.
    graph_detail: str  # {variant} {count} {levels}
    # Names: scenarios, variants, task kinds, task end states (as a cell and as a metric label), verdicts.
    scenario_names: dict[str, str]
    variant_names: dict[str, str]
    kind_names: dict[str, str]
    status_names: dict[str, str]
    status_labels: dict[str, str]
    verdicts: dict[str, str]
    # Why a task ended as it did: {error} {error_type} {blocked} {origin} {timeout_ms}.
    reason_texts: dict[str, str]
    # The stop event: {origin} {deadline_ms} {running}.
    stop_details: dict[str, str]
    # One variant's report.
    variant_title: str  # {variant}
    variant_summary: str
    check_dependencies: str
    detail_dependencies_ok: str
    detail_dependencies_bad: str  # {task} {need} {started} {ended} {status}
    check_limit: str
    detail_limit: str  # {peak} {limit}
    check_orphans: str
    detail_orphans: str  # {alive} {late} {late_ms}
    check_complete: str
    detail_complete_ok: str
    detail_complete_missing: str  # {missing}
    label_verdict: str
    label_wall_ms: str
    label_serial_ms: str
    label_critical_ms: str
    label_limit: str
    label_peak: str
    label_peak_threads: str
    label_model_calls: str
    label_tool_calls: str
    label_late: str
    label_sheet: str
    sheet_complete: str
    sheet_partial: str  # {missing}
    sheet_not_built: str
    label_note: str
    value_empty: str
    value_none: str
    table_columns: tuple[str, ...]
    # The comparison report at the end of the run.
    total_title: str  # {scenario}
    total_summary: str
    total_columns: tuple[str, ...]
    total_check_dependencies: str  # {variant}
    total_check_complete: str  # {variant}
    total_metric: str  # {variant} {label}
    total_check_limit: str
    total_detail_limit: str  # {peaks}
    total_check_orphans: str
    total_detail_orphans: str  # {alive}
    # The answer the runner writes from what really finished.
    answer_header: str  # {scenario}
    answer_variant: str  # {variant} {verdict} {wall} {done} {total}
    answer_missing: str  # {items}
    answer_missing_item: str  # {id} {status}


texts_for = catalog(__name__, Texts)
