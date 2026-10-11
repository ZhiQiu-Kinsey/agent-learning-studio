"""chat-request runtime text: English."""
from lessons.lesson_chat_request.locales import Texts

TEXTS = Texts(
    default_question="Explain in one sentence what an agent is.",
    finish_reasons={"stop": "the model finished on its own", "length": "cut off at the output limit"},
    empty_content="(The content of this response is empty; look at finish_reason and usage.)",
    missing_choices="The model response has no choices[0], so there is no answer to read.",
    report_title="Key fields of one request",
    report_summary=(
        "Usage comes from usage in this run's response event; anything the provider did not report "
        "says \"not reported\". max_tokens and the system message come from the request."
    ),
    label_system="system message",
    label_max_tokens="max_tokens",
    label_answer_length="Answer length (characters)",
    label_finish_reason="finish_reason",
    label_reason_meaning="What the finish reason means",
    label_prompt_tokens="Prompt tokens",
    label_completion_tokens="Completion tokens",
    label_total_tokens="Total tokens",
    label_reasoning_tokens="Reasoning tokens (part of completion)",
    label_reasoning_chars="Reasoning content (characters)",
    value_yes="yes",
    value_no="no",
    value_not_set="not set",
    value_not_reported="not reported",
    value_other_reason="other; see the provider's docs",
    column_index="#",
)
