"""Runtime text of context-compaction: prompts, the probe question, the rule record and the report.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
The material, the side discussion and the helpers' wording come from context-budget
(lessons/lesson_09_context_budget/locales/helpers/).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The goal message, the probe question, and what counts as answering it: the title of the
    # earliest source (its key also counts) and a phrase from its fact.
    goal: str
    probe: str
    probe_source_title: str
    probe_phrase: str
    # System prompts of the probe requests and of the summary request.
    system_prompt: str
    summary_system: str
    # summary_style code -> compression instruction.
    summary_instructions: dict[str, str]
    # What a cleared tool result says instead of its content.
    cleared_note: str
    # Rule-based record: one entry per read, joined by list_separator, and the whole record.
    source_entry: str  # {number}, {key}
    list_separator: str
    rule_record: str  # {sources}, {facts}
    budget_too_small: str  # {budget}, {needed}
    # Layout code -> name ("none", "rule", "clear", "summary").
    layout_names: dict[str, str]
    summary_prefix: str
    final_answer: str
    # Lab report.
    report_title: str
    report_summary: str
    check_protocol: str
    check_protocol_detail: str
    check_rule_fits: str
    check_rule_fits_detail: str  # {budget}
    check_probe: str  # {name}
    probe_both: str
    probe_missing: str
    label_model_calls: str
    label_summary_usage: str
    label_summary_style: str
    label_summary_text: str
    label_probe: str
    label_note: str
    note_empty: str
    hit: str
    miss: str
    columns: tuple[str, ...]


texts_for = catalog(__name__, Texts)
