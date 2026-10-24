"""Runtime text of langchain-vs-native: report labels, the answers the runner writes, and the sample note.

zh_CN.py and en.py each fill every field. The system prompts and tool descriptions are not
here: both sides reuse the earlier lessons' runtime text (tool-selection, fail-safely), so
the two implementations send the same words.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Shared pieces of the reports.
    absent: str
    none: str
    list_separator: str
    outcome_ok: str  # {result}
    outcome_error: str  # {error_type} {error}
    stop_reasons: dict[str, str]  # answered, rounds
    verdicts: tuple[str, ...]  # index 0 = not accepted, 1 = accepted
    # Paired run (sum, divide-zero): the responsibility map.
    report_task_title: dict[str, str]  # sum, divide
    report_task_summary: str
    acceptance_rules: dict[str, str]  # sum, divide
    check_native_accepted: str
    check_langchain_accepted: str
    check_same_tools: str
    check_same_tools_detail: str
    label_native_calls: str
    label_langchain_calls: str
    label_native_rounds: str
    label_langchain_rounds: str
    label_framework_version: str
    columns_responsibility: tuple[str, ...]
    row_messages: str
    cell_native_messages: str  # {kinds}
    cell_langchain_messages: str  # {kinds}
    row_tools: str
    cell_native_tools: str  # {count}
    cell_langchain_tools: str  # {count}
    row_parsing: str
    cell_native_parsing: str  # {count}
    cell_langchain_parsing: str  # {valid} {invalid}
    row_feedback: str
    cell_native_feedback: str  # {count}
    cell_langchain_feedback: str  # {count}
    row_stop: str
    cell_stop: str  # {limit} {stop}
    row_errors: str
    cell_errors: str  # {count}
    row_acceptance: str
    # Paired run: the request diff.
    report_diff_title: str
    report_diff_summary: str
    label_diff_count: str  # {n}
    request_pair: str  # {n}
    columns_diff: tuple[str, ...]
    answer_task: str  # {native} {langchain}
    # Local exercise "arguments".
    report_arguments_title: str
    report_arguments_summary: str
    check_default_agrees: str
    check_strict_agrees: str
    agree_detail: str  # {ok} {total}
    label_masked: str
    label_masked_cases: str
    argument_cases: dict[str, str]  # valid, string, boolean, extra
    columns_arguments: tuple[str, ...]
    answer_arguments: str  # {masked} {total} {strict}
    # Local exercise "parsing".
    sample_note: str
    report_parsing_title: str
    report_parsing_summary: str
    check_all_answered: str
    answered_detail: str  # {answered} {total}
    check_same_order: str
    order_detail: str  # {provider} {framework}
    label_valid_calls: str
    label_invalid_calls: str
    label_synthesized: str
    place_valid: str
    place_invalid: str
    columns_parsing: tuple[str, ...]
    answer_parsing: str  # {valid} {invalid} {synthesized}


texts_for = catalog(__name__, Texts)
