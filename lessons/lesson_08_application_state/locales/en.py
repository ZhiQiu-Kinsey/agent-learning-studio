"""application-state runtime text: English."""
from lessons.lesson_08_application_state.locales import Texts

TEXTS = Texts(
    source_excerpts={
        "messages-context": (
            "The context of one request consists of the system prompt, the earlier conversation, tool calls and "
            "tool results, and this turn's question; tool calls and tool results must come in pairs."
        ),
        "application-state": "Application state is updated by program events; model text cannot by itself prove a task complete.",
    },
    not_running="Steps can only run while the task is running.",
    illegal_transition="Illegal state transition: {current} → {target}",
    reason_required="A terminal state needs a reason.",
    completion_unproven="Without verified evidence and an actual result, the task cannot be marked completed.",
    step_read_index="Read the local material index",
    step_check_source="Check the material's source",
    step_summarize="Write the key points of the lesson material",
    action_created="Create an independent run",
    action_started="Start reading",
    action_waiting="Material missing; waiting",
    action_evidence="Source checked and evidence recorded",
    action_terminal="Record the terminal state",
    reason_missing="This preset has no material that can be verified, so the goal cannot be completed.",
    reason_budget_check="The step budget ran out before the material's source was checked.",
    reason_budget_summary="The step budget ran out before the key points were written.",
    reason_completed="The lesson-material summary flow finished; this does not mean an arbitrary free-form goal was achieved.",
    result="Key points of material {source_key}: {excerpt}",
    answer_completed=(
        "The lesson-material summary flow finished: {result}; the free-form goal \"{goal}\" was not checked separately."
    ),
    answer_failed="Not completed: {reason}",
    report_title="Application state versus messages",
    report_summary=(
        "This lesson runs only local Python and calls no model. The step budget is charged before each step, and "
        "the message list does not update the state by itself. The learner note does not change the task."
    ),
    check_reason="The terminal state has a reason",
    check_success="Success has evidence and a result",
    check_success_detail="The material comes from source_excerpts; result holds the key points actually written.",
    check_success_not_applicable="This run did not reach completed, so this check does not apply.",
    check_separate="Messages and state are kept apart",
    check_separate_detail="No local state update was disguised as an assistant or tool message.",
    label_status="Status",
    label_evidence="Evidence items",
    label_messages="Messages",
    label_step_budget="Step budget",
    label_used_steps="Steps run",
    label_note="Learner note",
    note_empty="none",
    columns=("Field", "Value in this run"),
)
