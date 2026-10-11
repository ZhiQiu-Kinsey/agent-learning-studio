"""context-budget helpers runtime text: English."""
from lessons.lesson_09_context_budget.locales.helpers import Texts

TEXTS = Texts(
    facts={
        "messages-context": "The model sees only the messages in this request; the app resends history.",
        "application-state": "App state records the goal and evidence; the message list does not update state by itself.",
    },
    unknown_source="No such material: {source_key}",
    fact_mismatch="The actual tool result has no source and fact that match the request.",
    side_question="Side discussion {n}: briefly note this practice plan; it is unrelated to the question.",
    side_reply="Noted side discussion {n}.",
    missing_message="The model response has no choices[0].message.",
    content_not_text="The content of the model response is not text.",
    unknown_tool="unknown",
    proposed_calls="(No text answer: the model proposed calling {names}; the runner did not run them.)",
    name_separator=", ",
    usage_not_reported="not reported",
)
