"""Runtime text of context-budget: prompts, layout and truncation names, and the two reports.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
The text of the helpers that context-compaction also imports is in locales/helpers/.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The system prompt, the goal message and the follow-up used when the question box is empty.
    system_prompt: str
    goal: str
    default_question: str
    # fit_window: the budget cannot even hold system and the current question.
    budget_too_small: str  # {budget}
    # Layout code -> name ("full", "window").
    layout_names: dict[str, str]
    # lesson.context_variant: who assembled the messages.
    variant_detail: str
    layouts_answer: str
    # Report of the layouts experiment.
    layouts_title: str
    layouts_summary: str
    check_protocol: str
    check_protocol_detail: str
    check_in_budget: str
    check_in_budget_detail: str  # {budget}, {chars}
    check_source_kept: str
    check_source_kept_detail: str
    label_model_calls: str
    label_char_budget: str
    label_usage_count: str
    label_question: str
    layouts_columns: tuple[str, ...]
    # Truncation code -> name ("naive", "pair_aware").
    truncation_names: dict[str, str]
    local_valid: str
    local_rejected: str  # {error}
    check_local: str  # {name}
    refused: str  # {status}
    refused_offline: str  # {status}
    no_answer: str
    accepted: str
    # The broken-pair answer depends on what the provider did in this run.
    pair_answer_accepted: str
    pair_answer_rejected: str  # {names}
    name_separator: str
    # Report of the broken-pair experiment.
    pair_title: str
    pair_summary: str
    label_history: str
    label_mode: str
    mode_offline: str
    mode_live: str
    pair_columns: tuple[str, ...]


texts_for = catalog(__name__, Texts)
