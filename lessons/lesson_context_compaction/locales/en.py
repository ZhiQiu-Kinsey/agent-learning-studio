"""context-compaction runtime text: English."""
from lessons.lesson_context_compaction.locales import Texts

TEXTS = Texts(
    goal=(
        "Goal: read the \"Context components and the message protocol\" material and then the \"Application state "
        "and the run lifecycle\" material, then answer the question; constraint: do not treat an unsourced guess "
        "as fact."
    ),
    probe="Which item did the earliest material you read come from? What is its original wording?",
    probe_source_title="Context components and the message protocol",
    probe_phrase="the app resends history",
    system_prompt="Answer only from the messages in this request and do not call tools. If the basis is missing, say so; do not guess.",
    summary_system=(
        "You compress a conversation into a summary for continuing the work later. Write only the summary; "
        "do not call tools and do not continue the task."
    ),
    summary_instructions={
        "keep_sources": (
            "Compress the conversation above into one summary for continuing the work later. Keep the goal, the "
            "constraints, the source and the original result text of every tool call, and the open items. "
            "At most 120 words."
        ),
        "brief": "Summarize the conversation above in one or two sentences.",
    },
    cleared_note="Old tool result cleared; its original content is not in the context.",
    source_entry="read #{number}: {key}",
    list_separator="; ",
    rule_record=(
        "Record of earlier turns (built by rules)\nGoal: read two materials, then answer\n"
        "Constraint: no unsourced guess as fact\nSources: {sources}\nFacts: {facts}\nTo do: answer the user"
    ),
    budget_too_small="A character budget of {budget} is less than the {needed} characters needed to keep the key evidence.",
    layout_names={"none": "No compression", "rule": "Rule-based compression", "clear": "Clearing old tool results",
                  "summary": "Summary compression"},
    summary_prefix="Summary of the earlier conversation: ",
    final_answer=(
        "The summary request and the probe request of each arm are recorded. Compare each arm's context, "
        "its probe answer and the provider's usage."
    ),
    report_title="Three compressions and one probe question",
    report_summary=(
        "The runner assembled the history; the two tool results come from real reads in this run, and the current "
        "model wrote the summary. \"Original wording still in context\" is a local string check, \"Named source and "
        "original wording\" is a keyword screen; read them separately. Character counts are not tokens."
    ),
    check_protocol="Every arm's context passes the protocol check",
    check_protocol_detail="The protocol check ran on each arm before it was sent.",
    check_rule_fits="Rule-based compression kept the key evidence",
    check_rule_fits_detail="The record fits the character budget of {budget}.",
    check_probe="{name}: probe screen",
    probe_both="The answer contains both the source name and the original wording",
    probe_missing="The answer lacks the source name or the original wording; read the text to check",
    label_model_calls="Model calls",
    label_summary_usage="Usage of the summary request",
    label_summary_style="Summary instruction",
    label_summary_text="Summary text",
    label_probe="Probe question",
    label_note="Learner note",
    value_empty="(empty)",
    hit="hit",
    miss="miss",
    columns=("Method", "Messages", "JSON characters", "Original wording still in context", "Probe answer",
             "Named source and original wording (screen)", "Provider usage"),
)
