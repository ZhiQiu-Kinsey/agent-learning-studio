"""messages-context runtime text: English."""
from lessons.lesson_07_messages_context.locales import Texts

TEXTS = Texts(
    system_prompt=(
        "You are a course teaching assistant. Answer only from the messages in this request; "
        "if the basis is missing, say you cannot tell, and do not guess. "
        "End your answer with a separate line starting with \"Basis:\" that says which part of the "
        "conversation and which tool result you used."
    ),
    conversation=(
        "This week I can only review on {day} evening. "
        "First, look up the latest exercise for {student_id}."
    ),
    question="Did I pass that exercise? Which day should I review this week?",
    weekdays={"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday", "fri": "Friday",
              "sat": "Saturday", "sun": "Sunday"},
    basis_keyword="Basis",
    variant_names={
        "full": "Full context",
        "no_system": "Remove the system prompt",
        "no_conversation": "Remove the earlier conversation",
        "no_tool_pair": "Remove the tool call and result",
        "no_tool_result": "Remove only the tool result",
    },
    unknown_student="No record for student ID {student_id}.",
    lookup_failed="The local score lookup failed.",
    protocol_passed="passed",
    protocol_rejected="rejected: {error}",
    missing_message="The model response has no choices[0].message.",
    no_text_answer="The model returned no text answer to compare.",
    parts_detail=(
        "The runner assembles all five messages: the system message and the two user messages are samples "
        "written for this lesson; the runner writes the assistant message with tool_calls, the model did not "
        "propose it; the tool message holds what lookup_score really returned in this run."
    ),
    outcome_not_sent="not sent",
    outcome_provider_rejected="rejected by the provider; see lesson.provider_error",
    final_answer=(
        "{sent} variants were sent, and the protocol check blocked {blocked} before sending. "
        "Compare the report table with the messages of each request."
    ),
    report_title="Remove one part at a time",
    report_summary=(
        "Same question, same model; each variant has one part less than the full context. The program counts "
        "the messages and runs the protocol check. \"Mentions score\", \"Mentions review day\" and "
        "\"Has basis line\" are a keyword screen; check them against the answer text."
    ),
    check_protocol="Every variant that was sent passed the protocol check first",
    check_protocol_detail="validate_tool_history runs before every complete.",
    check_blocked="The variant that removes only the tool result was blocked and not sent",
    check_blocked_none="No variant was blocked in this run.",
    label_model_calls="Model calls",
    label_blocked="Blocked variants",
    label_tool_calls="Tool calls",
    label_student_id="Student ID",
    label_free_day="Review day",
    label_note="Learner note",
    note_empty="(empty)",
    columns=("Context", "Messages", "Protocol check", "Answer", "Mentions score", "Mentions review day",
             "Has basis line"),
)
