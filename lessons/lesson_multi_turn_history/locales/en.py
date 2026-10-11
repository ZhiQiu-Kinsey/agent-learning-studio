"""multi-turn-history runtime text: English."""
from lessons.lesson_multi_turn_history.locales import Texts

TEXTS = Texts(
    system_prompt="You are a concise assistant. Answer in one sentence each time.",
    turns=(
        "I have a cat named Tuanzi. It is three years old. Reply only with \"Got it\".",
        "What is my cat's name?",
        "How old is it this year?",
    ),
    fact="Tuanzi",
    missing_choices="The model response has no choices[0], so there is no answer to read.",
    report_title="Messages sent and usage per turn",
    summary_full=(
        "Every turn resends the whole history. The numbers come from usage in each turn's response; "
        "anything not reported says \"not reported\"."
    ),
    summary_latest_only=(
        "Every turn sends only system and that turn's question. The numbers come from usage in each turn's "
        "response; anything not reported says \"not reported\"."
    ),
    check_fact_sent="The turn 2 request contains the fact from turn 1",
    check_fact_sent_detail="Checks every message turn 2 actually sent for \"{fact}\".",
    check_fact_answered="The turn 2 answer mentions the fact",
    check_fact_answered_detail="Checks the content of the turn 2 response; it speaks only for this one answer.",
    label_mode="Mode",
    mode_values={"full": "whole history", "latest_only": "this turn's question only"},
    label_model_calls="Model calls",
    label_last_message_count="Messages sent in the last turn",
    label_prompt_growth="Prompt tokens from the first turn to the last",
    prompt_growth="{first} → {last}",
    label_note="Learner note",
    columns=("Turn", "Messages sent", "Contains the fact", "Prompt tokens", "Completion tokens", "Answer"),
    value_yes="yes",
    value_no="no",
    value_not_reported="not reported",
    value_empty="(empty)",
)
