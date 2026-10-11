"""Runtime text of skills-disclosure's runtime.py: prompts, the tool description, tasks, report texts and answers.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
The skills themselves are per-language data files: locales/skills/<name>/zh_CN.md and en.md.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The vague description that replaces review-cards' description in the "vague" arms.
    vague_description: str
    # The user message of each task, keyed by the task code.
    task_messages: dict[str, str]
    # The two system prompts: the intro before all skill bodies, and the intro before the catalog.
    full_prompt: str
    catalog_prompt: str
    full_section: str  # {name} {description} {body}
    catalog_heading: str
    catalog_line: str  # {name} {description}
    # The load_skill tool the model reads, and its error.
    load_skill_description: str
    load_skill_name_description: str
    unknown_skill: str  # {name} {names}
    # Loading verdicts.
    loading_not_applicable: str
    loading_none_correct: str
    loading_missed: str
    loading_false: str  # {names}
    loading_correct: str  # {names}
    loading_wrong: str  # {names}
    # How a review card's question and answer lines start (the format screen counts them).
    card_question_prefixes: tuple[str, ...]
    card_answer_prefixes: tuple[str, ...]
    format_no_answer: str
    format_cards: str  # {asked} {answered}
    format_not_cards: str
    format_cards_written: str  # {asked}
    # Labels of the two modes and three tasks, keyed by code.
    mode_labels: dict[str, str]
    task_labels: dict[str, str]
    # Answers and shared report pieces.
    answer_section: str  # {mode} {answer}
    no_answer: str  # {limit}
    unparsable_arguments: str
    value_not_reported: str
    tokens_partly_reported: str  # {total} {missing}
    value_empty: str
    separator: str
    # Lab report.
    label_task: str
    label_description: str
    value_vague: str
    value_precise: str
    label_expected: str
    value_expect_none: str
    proposals: str  # {round} {names}
    proposals_separator: str
    value_all_resident: str
    value_no_proposal: str
    format_passed: str
    format_failed: str
    label_first_tokens: str  # {mode}
    check_full_bodies: str
    check_full_bodies_detail: str  # {count}
    check_catalog_only: str
    check_catalog_only_detail: str  # {chars}
    check_loading: str
    check_rejected: str
    check_rejected_detail: str  # {names}
    check_format: str  # {mode}
    check_format_detail: str  # {detail}
    label_model_calls: str
    label_note: str
    title_separator: str
    report_title: str  # {modes} {task}
    report_summary: str
    columns: tuple[str, ...]


texts_for = catalog(__name__, Texts)
