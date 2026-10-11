"""todo-planning runtime text: English."""
from lessons.lesson_todo_planning.locales import Texts

TEXTS = Texts(
    task=("Make me a review card: look up the review points of three lessons, messages-context (Context components "
          "and the message protocol), application-state (Application state and the run lifecycle) and context-budget "
          "(Context budget and the truncation window), save the three points with their point IDs on the review card, "
          "then tell me you are done."),
    base_system=("You are a teaching assistant. Call a tool when you need information; do not guess a point's text "
                 "or its ID. When everything is done, state the result in one or two sentences."),
    todo_rules=("Before you start, list the steps with todo_write. Each time you finish a step, call todo_write to "
                "update the statuses: pending means not started, in_progress means under way, done means finished; "
                "at most one item may be in_progress at a time."),
    system_with_rules="{base} {rules}",
    notes={
        "messages-context": "The model sees only the messages in this request; the program must resend the history.",
        "application-state": "Application state records the goal and the evidence; the message list does not update it.",
        "context-budget": "When compacting context, keep or drop a tool call and its tool result together.",
    },
    lookup_note_description="Look up the review point of one lesson and its point ID.",
    save_card_description=("Save points on the review card. Each point states the lesson (the lesson used with "
                           "lookup_note), the point ID and a one-sentence summary."),
    todo_write_description="Replace the current TODO list with a complete list.",
    todos_not_a_list="todos must be a list of 1–12 items.",
    todo_fields="Each item may only have the three fields id, content and status.",
    todo_id="Each item needs a unique, non-empty id.",
    todo_content="Each item needs a non-empty content.",
    todo_status="status must be pending, in_progress or done.",
    todo_one_in_progress="At most one item may be in_progress at a time.",
    unknown_lesson="There are only points for three lessons: messages-context, application-state and context-budget.",
    items_not_a_list="items must be a non-empty list.",
    item_fields="Each point needs the string fields lesson, note_id and summary.",
    reminder=("<reminder>The TODO list has not been updated for {rounds} rounds. Update the list with todo_write "
              "first, then continue.</reminder>"),
    check_card_saved="Review card saved",
    detail_card_saved="save_card returned successfully",
    detail_card_missing="No successful save_card",
    check_all_lessons="The card covers all three lessons",
    detail_card_lessons="Lessons on the card: {lessons}",
    check_note_ids="Every point ID comes from this run's lookups",
    detail_ids_match="All match this run's lookup_note results",
    detail_ids_wrong="Lessons that do not match: {lessons}",
    value_none="none",
    value_no_card="(no card)",
    list_separator=", ",
    change_separator="; ",
    timeline_added="added {ids}",
    timeline_unchanged="no change",
    condition_titles={"no_todo": "No TODO", "todo": "TODO, no reminder", "todo_reminder": "TODO, with reminder"},
    report_summary=("Acceptance looks only at the review card and this run's real lookup results; the model's claim "
                    "and the TODO statuses are self-reported and do not count."),
    label_verdict="Acceptance verdict",
    label_model_calls="Model calls",
    label_todo_writes="todo_write calls",
    label_reminders="Harness reminders",
    label_todo_done="TODO items self-reported done",
    label_last_claim="The model's last claim",
    label_note="Learner note",
    value_passed="passed",
    value_failed="failed",
    value_no_list="no list",
    value_unfinished="(call limit reached, not finished)",
    value_empty_note="(empty)",
    columns=("Round", "TODO version", "done", "Total", "Change"),
    verdict_passed="Acceptance passed",
    verdict_failed="Acceptance failed",
    answer_unfinished="{verdict}: not finished within {limit} calls.",
    answer_final="{verdict}. The model's last words: {answer}",
)
