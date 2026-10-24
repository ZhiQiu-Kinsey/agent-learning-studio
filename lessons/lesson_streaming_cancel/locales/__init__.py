"""Runtime text of streaming-cancel: the task sent to the model, the continuation requests, report labels, answers.

zh_CN.py and en.py each fill every field; runtime.py, reports.py and analysis.py read them with
texts_for(context.locale). Event names, field names, scenario names and statuses are code and stay the same
in every language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # What the model is told.
    system: str
    task: str  # {items} {length}
    lengths: dict[str, str]  # short / long
    continue_plain: str  # the bare "continue" that follows the cut text as an assistant message
    continue_marked: str  # {chunks} {kept_count} {kept} {next_item} {items}
    continue_marked_none: str  # {chunks} {next_item} {items}
    marked_phrase: str  # the words that tell the model the last answer is incomplete
    # Words used in values.
    value_empty: str
    value_none: str
    flag_yes: str
    flag_no: str
    not_reported: str
    not_received: str
    no_finish_marker: str
    usage_line: str  # {prompt} {completion} {total}
    statuses: dict[str, str]  # completed / stopped / cancelled / error
    # Report titles and summaries by scenario.
    report_titles: dict[str, str]
    report_summaries: dict[str, str]
    # Metric labels.
    label_status: str
    label_chunks: str
    label_first_chunk: str
    label_first_token: str
    label_stream_ms: str
    label_chars: str
    label_finish: str
    label_usage: str
    label_plain_ms: str
    label_only_plain: str
    label_only_streamed: str
    label_note: str
    label_stop_after: str
    label_items_seen: str
    label_kept: str
    label_next_item: str
    label_cut_line: str
    # Checks and their details.
    check_completed: str
    detail_completed: str  # {status} {reason}
    check_first_before_total: str
    detail_first_before_total: str  # {first} {total}
    check_shape: str
    detail_shape_ok: str
    detail_shape_bad: str  # {streamed} {plain}
    check_list: str
    detail_list: str  # {expected} {numbers}
    check_stop_reached: str
    detail_stop_reached: str  # {limit} {chunks} {status}
    check_finish_missing: str
    detail_finish_missing: str  # {reason}
    check_marked_request: str
    detail_marked_request: str  # {next_item}
    check_plain_merge: str
    check_marked_merge: str
    detail_merge: str  # {numbers} {verdict}
    verdict_ok: str
    verdict_bad: str  # {duplicates} {missing} {unfinished}
    # Tables.
    compare_columns: tuple[str, ...]
    row_first_chunk: str
    row_first_token: str
    row_total: str
    row_finish: str
    row_usage: str
    row_chars: str
    row_items: str
    continue_columns: tuple[str, ...]
    handling_plain: str
    handling_marked: str
    # The answer the runner writes itself, by scenario.
    answers: dict[str, str]


texts_for = catalog(__name__, Texts)
