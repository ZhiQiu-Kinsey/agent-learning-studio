"""Runtime text of todo-planning: the task, prompts, tool descriptions and errors, the reminder, the report.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
Tool names, parameter names, statuses (pending / in_progress / done) and note ids are code
and stay the same in every language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The fixed task (the user message) and the system prompt: the base prompt for every group,
    # plus the TODO rules for the two groups that get todo_write.
    task: str
    base_system: str
    todo_rules: str
    system_with_rules: str  # {base} {rules}
    # The review point text of each lesson, keyed by lesson slug (lookup_note returns it).
    notes: dict[str, str]
    # Tool descriptions (tool_definitions).
    lookup_note_description: str
    save_card_description: str
    todo_write_description: str
    # Tool errors; they reach the model as structured errors.
    todos_not_a_list: str
    todo_fields: str
    todo_id: str
    todo_content: str
    todo_status: str
    todo_one_in_progress: str
    unknown_lesson: str
    items_not_a_list: str
    item_fields: str
    # The reminder the harness appends.
    reminder: str  # {rounds}
    # Acceptance checks (verify_card).
    check_card_saved: str
    detail_card_saved: str
    detail_card_missing: str
    check_all_lessons: str
    detail_card_lessons: str  # {lessons}
    check_note_ids: str
    detail_ids_match: str
    detail_ids_wrong: str  # {lessons}
    value_none: str
    value_no_card: str
    list_separator: str
    # Timeline rows of the report.
    change_separator: str
    timeline_added: str  # {ids}
    timeline_unchanged: str
    # Lab report.
    condition_titles: dict[str, str]
    report_summary: str
    label_verdict: str
    label_model_calls: str
    label_todo_writes: str
    label_reminders: str
    label_todo_done: str
    label_last_claim: str
    label_note: str
    value_passed: str
    value_failed: str
    value_no_list: str
    value_unfinished: str
    value_empty: str
    columns: tuple[str, ...]
    # The final answer written by the runner.
    verdict_passed: str
    verdict_failed: str
    answer_unfinished: str  # {verdict} {limit}
    answer_final: str  # {verdict} {answer}


texts_for = catalog(__name__, Texts)
