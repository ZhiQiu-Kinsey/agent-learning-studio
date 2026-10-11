"""structured-output runtime text: English."""
from lessons.lesson_05_structured_output.locales import Texts

TEXTS = Texts(
    facts_lesson_title="Task goals and acceptance",
    system_prompt=(
        "Output only one JSON object with the fields lesson_id, lesson_title, prerequisite and exercise. "
        "Do not invent or alter the given facts; exercise is a description of the exercise, 8 to 120 characters long."
    ),
    user_prompt=("Turn these trusted lesson facts into a study task card: {facts}. The exercise: use the fixed "
                 "input 19+23 to compare a run that finished with a run that passed acceptance."),
    inject_missing_field=" In this round, deliberately leave out the prerequisite field, so the validator can show a field error.",
    inject_wrong_fact=" In this round, deliberately write prerequisite as {wrong}, so the validator can show a fact error.",
    repair_prompt="The previous version failed: {reasons}. Output a complete JSON object based only on the original trusted facts.",
    non_json_constant="non-standard JSON constant: {value}",
    layer_json="JSON format",
    detail_json_ok="parses as JSON",
    layer_schema="Field schema",
    detail_schema_ok="required fields, types, lengths and extra fields all pass",
    layer_facts="Business facts",
    detail_facts_ok="matches the given lesson facts",
    detail_facts_mismatch="does not match the given facts: {fields}",
    missing_content="The model response has no readable message.content",
    content_not_text="The model response content must be text",
    stage_first="First draft",
    stage_repair="Repaired draft",
    report_title="{stage}: three-layer check of structured output",
    summary_passed="{stage} passed every check that ran",
    summary_failed="{stage} failed; a later layer is not judged when an earlier one fails",
    label_model_calls="Model calls",
    label_draft_verdict="Verdict for this draft",
    value_passed="passed",
    value_failed="failed",
    label_note="Learner note",
    value_empty="(empty)",
    columns=("Layer", "Result"),
    answer_passed="Accepted: {card}",
    answer_failed="The model output failed the checks; look at the responses and the three layers.",
)
