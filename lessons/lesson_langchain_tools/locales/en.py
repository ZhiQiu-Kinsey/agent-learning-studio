"""Runtime text: English."""
from lessons.lesson_langchain_tools.locales import Texts

TEXTS = Texts(
    system_prompt=(
        "You are a study assistant. First call lookup_lesson to get the lesson facts, then produce a lesson card "
        "with TaskCard. The card's lesson_id, lesson_title and prerequisite must match the facts you looked up; "
        "exercise is one sentence describing a hands-on exercise. When a tool returns ok=false, read error "
        "before deciding what to do next, and never make facts up."
    ),
    user_prompt="Produce the lesson card for the lesson {lesson_id}.",
    injections={
        "missing_field": " (Experiment injection: the first time you produce the card, leave out the prerequisite "
                         "field on purpose; add it after you get the error.)",
        "wrong_fact": " (Experiment injection: the first time you produce the card, write prerequisite as "
                      "dependent-calls on purpose; correct it after you get the error.)",
        "tool_error": " (Experiment injection: in your first lookup, pass the directory name task_contract as "
                      "lesson_id on purpose; after the error, correct it as error says.)",
    },
    repair_instruction="Fix the lesson card as error says and call TaskCard exactly once.",
    reason_separator="; ",
    title_structured_output="Structured output and business validation",
    title_fail_safely="Error handling and safety boundaries",
    lookup_description=(
        "Look up the facts of a lesson by its slug: returns lesson_id, lesson_title and prerequisite. "
        "Accepts only a slug (such as task-contract), not a title, a lesson number or a directory name; "
        "raises an error when nothing matches."
    ),
    lookup_parameter="The lesson slug: lowercase letters and hyphens, for example task-contract",
    lookup_unknown="No lesson has the slug {lesson_id}. Available slugs: {known}",
    card_description="The card of one lesson: the fact fields must come from the lookup_lesson result; "
                     "exercise is one sentence.",
    check_business="Business check: facts match the trusted data",
    detail_business_skipped="Not run: the framework produced no card to check",
    detail_business_ok="lesson_id, lesson_title and prerequisite all match the trusted facts",
    detail_business_wrong="Field(s) {fields} do not match the trusted facts; expected {expected}",
    outcomes={
        "parsed": "The framework parsed a lesson card that fits the schema.",
        "schema_error": "Schema validation failed; parsing_error holds the Pydantic error:",
        "invalid_arguments": "The arguments are not a JSON object: parsed and parsing_error are both None, "
                             "and the framework raised nothing.",
        "no_structured_call": "The model did not call TaskCard: parsed and parsing_error are both None, "
                              "and the framework raised nothing.",
        "text_fallback": "The model ignored the forced tool call. Fallback: the JSON in the text was validated "
                         "with the same schema and passed.",
        "text_fallback_failed": "The model ignored the forced tool call, and the fallback check of the JSON in "
                                "the text failed too:",
    },
    check_parse="Framework parsing: with_structured_output returned a card",
    check_facts="Lookup: the target lesson's facts were found",
    detail_facts_found="lookup_lesson returned the target lesson's facts",
    detail_facts_missing="No successful lookup result, so the runner does not produce a card",
    answer_passed="The lesson card passed framework parsing and the business check: {card}",
    answer_no_facts="No lesson facts were found, so the runner does not produce a card. See error in the "
                    "tool results.",
    answer_failed="The lesson card did not pass the checks and the repair is used up. See the lab report of "
                  "each attempt.",
    definitions_title="Tool definition: generated from type hints vs written by hand",
    definitions_summary="The same tool, compared field by field: the definition the decorator generates from "
                        "type hints and the one written by hand. The card schema comes from the business model.",
    check_definition_match="The generated lookup_lesson definition matches the handwritten one",
    detail_same="Identical field by field",
    label_generated_parameters="Generated parameter schema",
    label_card_required="TaskCard required fields",
    label_card_extra="TaskCard additionalProperties",
    label_business_description="Tool description the business model brings",
    attempt_title="Lesson card, attempt {attempt}",
    label_outcome="Framework result",
    label_source="Data source",
    source_fixture="Offline test fixture (not a provider response)",
    source_provider="Provider response",
    layer_columns=("Layer", "Content"),
    layer_raw="Provider's raw response",
    layer_raw_where="See the response event of the same round: arguments is a JSON string",
    layer_framework="Tool call arguments in the framework's AIMessage",
    layer_parsed="Result of with_structured_output",
    layer_business="Business check",
    capabilities_title="Capability matrix",
    capabilities_summary="Only capabilities that showed up in this run are marked as observed; options this "
                         "lesson never sends are unverified.",
    capability_columns=("Capability", "Evidence in this run", "Status"),
    cap_tool_auto="Tool calling (bind_tools, tool_choice=auto)",
    cap_forced_tool="Forced tool call (with_structured_output sends tool_choice=required)",
    cap_call_ids="Provider sends call ids",
    cap_usage="Usage reporting",
    cap_parallel="Several tool calls in one response",
    cap_strict="strict schema",
    cap_json_schema="Provider-native JSON Schema output (response_format)",
    evidence_count="{count}/{total} responses contain tool calls",
    evidence_parallel="{count}/{total} responses contain several tool calls",
    evidence_synthesized="The adapter filled in {count} call id(s)",
    evidence_usage="{count}/{total} responses reported usage",
    evidence_not_sent="This lesson never sends this option",
    status_observed="Observed in this run",
    status_fixture="Offline fixture (not observed from a provider)",
    status_fallback="Adapter fallback",
    status_unverified="Unverified",
    final_title="Final verdict",
    stop_reasons={
        "accepted": "The lesson card passed framework parsing and the business check.",
        "no_facts": "The lookup did not succeed; the runner stopped without producing a card.",
        "repair_used_up": "Still failing after 1 repair; stopped at the limit.",
        "repair_off": "Repair is off; stopped after the first failed attempt.",
    },
    label_model_calls="Model calls",
    label_tool_failures="Tool failures (ok=false)",
    label_attempts="Card attempts",
    label_stop_reason="Stop reason",
    label_note="Learner note",
    value_empty="(empty)",
    value_none="(none)",
    value_not_reported="not reported",
)
