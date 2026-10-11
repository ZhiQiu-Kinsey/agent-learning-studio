"""Runtime text of structured-output: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The trusted title of task-contract, as the catalog writes it in this language.
    facts_lesson_title: str
    # The request: system rule, user task, and the deliberate first-draft faults.
    system_prompt: str
    user_prompt: str
    inject_missing_field: str
    inject_wrong_fact: str
    # The repair request: the reasons of the layers that failed.
    repair_prompt: str
    # Layer 1: JSON format.
    non_json_constant: str
    layer_json: str
    detail_json_ok: str
    # Layer 2: field schema.
    layer_schema: str
    detail_schema_ok: str
    # Layer 3: business facts.
    layer_facts: str
    detail_facts_ok: str
    detail_facts_mismatch: str
    # Errors when the response carries no readable text.
    missing_content: str
    content_not_text: str
    # Lab report, one per draft.
    stage_first: str
    stage_repair: str
    report_title: str
    summary_passed: str
    summary_failed: str
    label_model_calls: str
    label_draft_verdict: str
    value_passed: str
    value_failed: str
    label_note: str
    value_empty: str
    columns: tuple[str, ...]
    # The final answer.
    answer_passed: str
    answer_failed: str


texts_for = catalog(__name__, Texts)
