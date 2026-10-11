"""Runtime text of prompt-experiments: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
The prompt fields at the top are annotated line by line in the Code scene, so every
language keeps the same number of lines per field.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Paired scenarios: scenario code -> (user task, baseline text, rewritten text).
    pair_tasks: dict[str, tuple[str, ...]]
    # The fixed system message of the tool-description pair; there the variable is the description.
    pair_system: str
    # Matrix descriptions by group code; the blank group has no entry and sends no description.
    descriptions: dict[str, str]
    # Matrix probes by code: the sum probe needs the tool, the concatenation probe does not.
    probes: dict[str, str]
    matrix_system: str
    # Text heuristics of the paired screening (regular expressions, matched case-insensitively).
    ask_pattern: str
    number_word_pattern: str
    negation_pattern: str
    # Tool error; it ends up in the tool result.
    not_integers: str
    # Errors when the response carries no readable text.
    missing_content: str
    content_not_text: str
    # Screening details of the paired experiment.
    detail_tool_needs_calls: str
    detail_missing_hit: str
    detail_missing_miss: str
    detail_flow_hit: str
    detail_flow_miss: str
    value_no_tool_call: str
    detail_need_one_call: str
    detail_arguments_not_json: str
    detail_proposal_hit: str
    detail_proposal_miss: str
    label_baseline: str
    label_variant: str
    pair_budget_error: str
    pair_answer: str
    # Matrix cells.
    group_labels: dict[str, str]
    probe_labels: dict[str, str]
    group_blank_row: str
    check_cell: str
    cell_no_call_ok: str
    cell_unneeded_call: str
    cell_missing_call: str
    cell_match: str
    cell_mismatch: str
    cell_no_call: str
    value_no_text: str
    cell_call: str
    cell_returned: str
    cell_expected: str
    cell_unexpected: str
    matrix_budget_error: str
    matrix_answer: str
    # Lab reports.
    pair_report_title: str
    pair_report_summary: str
    check_screen: str
    label_same_model: str
    label_model_calls: str
    label_budget: str
    label_temperature: str
    label_sample: str
    label_note: str
    value_empty: str
    label_changed: str
    changed_system_rule: str
    pair_columns: tuple[str, ...]
    value_hit: str
    value_miss: str
    matrix_report_title: str
    matrix_report_summary: str
    label_cells_passed: str
    matrix_column_description: str
    matrix_column_probe: str


texts_for = catalog(__name__, Texts)
