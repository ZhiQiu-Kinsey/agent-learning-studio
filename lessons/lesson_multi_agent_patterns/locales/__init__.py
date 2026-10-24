"""Runtime text of multi-agent-patterns: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py and verifier.py read them with texts_for(context.locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The evidence pack: four documents keyed by id. Only the brief says d4 is an old draft.
    docs: dict[str, str]
    doc_titles: dict[str, str]
    doc_block: str
    topic_names: dict[str, str]
    # The task every mode gets, the rule a handoff may leave out, and each step's instruction.
    task_brief: str
    outdated_rule: str
    research_instruction: str
    write_instruction: str
    review_instruction: str
    single_instruction: str
    docs_header: str
    facts_header: str
    questions_header: str
    single_system: str
    role_prompts: dict[str, str]
    # The verifier: the structured error and the text of each problem code.
    verifier_not_list: str
    problem_labels: dict[str, str]
    # Task graph (lesson.plan).
    plan_reason: str
    plan_step: str
    plan_details: dict[str, str]
    # Run identity and lab report.
    mode_names: dict[str, str]
    role_names: dict[str, str]
    handoff_names: dict[str, str]
    handoff_not_used: str
    report_summary: str
    check_topic: str
    check_ok: str
    check_verifier: str
    label_task: str
    value_task: str
    label_model_calls: str
    label_total_tokens: str
    value_not_reported: str
    tokens_partly_reported: str
    label_wall_ms: str
    label_identities: str
    value_identities: str
    label_input_chars: str
    label_conflicts: str
    label_duplicates: str
    label_handoff: str
    label_note: str
    value_empty: str
    value_yes: str
    value_no: str
    value_none: str
    list_separator: str
    ledger_columns: tuple[str, ...]
    merge_detail: str
    answer: str


texts_for = catalog(__name__, Texts)
