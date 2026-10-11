"""tool-proposals runtime text: English."""
from lessons.lesson_tool_proposals.locales import Texts

TEXTS = Texts(
    default_question="Add 19 and 23 for me.",
    system_prompt=(
        "You are a teaching assistant. To add two numbers, call add_numbers; "
        "when asked for the current time or date, call get_current_time; answer other questions directly."
    ),
    missing_choices="The model response has no choices[0], so there are no call proposals to read.",
    empty_content="(The model proposed no call, and content is empty too.)",
    proposals_answer=(
        "The model proposed {count} call(s): {calls}. "
        "This lesson does not execute tools, so there is no tool result."
    ),
    call_separator="; ",
    report_title="What the model proposed",
    report_summary=(
        "The table lists only the tool_calls in the response. This lesson executes no tool, "
        "so the events have no tool_call and no tool_result."
    ),
    label_finish_reason="finish_reason",
    label_proposal_count="Call proposals",
    label_content_length="content length (characters)",
    columns=("Call id", "Tool name", "arguments (JSON string)", "Parses as a JSON object"),
    value_not_reported="not reported",
    value_none="(none)",
    value_empty="(empty)",
)
