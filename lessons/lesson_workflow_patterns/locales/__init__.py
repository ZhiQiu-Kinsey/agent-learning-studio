"""Runtime text of workflow-patterns: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Prompt chaining: the input note, the three steps (name, instruction) and the gate results.
    chain_note: str
    chain: tuple[tuple[str, str], ...]
    title_max_chars: int
    gate_lines_ok: str
    gate_lines_bad: str
    gate_qa: str
    gate_not_json: str
    gate_titles_ok: str
    gate_titles_bad: str
    chain_stopped: str
    chain_done: str
    # Routing: label names, the router prompt and the 20 tickets keyed by ticket id.
    label_names: dict[str, str]
    router_system: str
    router_label: str
    router_label_separator: str
    tickets: dict[str, str]
    fallback_reason: str
    routing_done: str
    # Fan-out: the three restating tasks keyed by lesson slug.
    topics: dict[str, str]
    summary_system: str
    fanout_names: dict[str, str]
    fanout_done: str
    # Lab reports.
    value_passed: str
    value_failed: str
    value_all_done: str
    value_empty: str
    value_none: str
    list_separator: str
    label_model_calls: str
    label_note: str
    chain_title: str
    chain_summary: str
    chain_check: str
    label_stopped_at: str
    chain_columns: tuple[str, ...]
    routing_title: str
    routing_summary: str
    routing_check: str
    routing_check_detail: str
    label_accuracy: str
    label_fallbacks: str
    routing_columns: tuple[str, ...]
    confusion_title: str
    confusion_summary: str
    confusion_corner: str
    fanout_summary: str
    fanout_check: str
    label_wall_ms: str
    label_sum_ms: str
    fanout_columns: tuple[str, ...]


texts_for = catalog(__name__, Texts)
