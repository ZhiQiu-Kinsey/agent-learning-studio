"""Runtime text of this lesson; zh_CN.py and en.py each fill every field."""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Prompts sent to the model
    system_prompt: str
    user_prompt: str  # {lesson_id}
    injections: dict  # fault scenario -> extra instruction appended to the user prompt (normal has none)
    repair_instruction: str
    reason_separator: str
    # Business table, tool and schema descriptions (components.py)
    title_structured_output: str
    title_fail_safely: str
    lookup_description: str
    lookup_parameter: str
    lookup_unknown: str  # {lesson_id} {known}
    card_description: str
    check_business: str
    detail_business_skipped: str
    detail_business_ok: str
    detail_business_wrong: str  # {fields} {expected}
    # Structured output outcomes and checks
    outcomes: dict  # outcome -> what with_structured_output gave back
    check_parse: str
    check_facts: str
    detail_facts_found: str
    detail_facts_missing: str
    # Answers
    answer_passed: str  # {card}
    answer_no_facts: str
    answer_failed: str
    # Report: tool definitions
    definitions_title: str
    definitions_summary: str
    check_definition_match: str
    detail_same: str
    label_generated_parameters: str
    label_card_required: str
    label_card_extra: str
    label_business_description: str
    # Report: one structured attempt
    attempt_title: str  # {attempt}
    label_outcome: str
    label_source: str
    source_fixture: str
    source_provider: str
    layer_columns: tuple
    layer_raw: str
    layer_raw_where: str
    layer_framework: str
    layer_parsed: str
    layer_business: str
    # Report: capability matrix
    capabilities_title: str
    capabilities_summary: str
    capability_columns: tuple
    cap_tool_auto: str
    cap_forced_tool: str
    cap_call_ids: str
    cap_usage: str
    cap_parallel: str
    cap_strict: str
    cap_json_schema: str
    evidence_count: str  # {count} {total}
    evidence_parallel: str  # {count} {total}
    evidence_synthesized: str  # {count}
    evidence_usage: str  # {count} {total}
    evidence_not_sent: str
    status_observed: str
    status_fixture: str
    status_fallback: str
    status_unverified: str
    # Report: final verdict
    final_title: str
    stop_reasons: dict  # stop reason -> summary
    label_model_calls: str
    label_tool_failures: str
    label_attempts: str
    label_stop_reason: str
    label_note: str
    value_empty: str
    value_none: str
    value_not_reported: str


texts_for = catalog(__name__, Texts)
