"""human-in-the-loop runtime text: English."""
from lessons.lesson_human_in_the_loop.locales import Texts

TEXTS = Texts(
    draft_system=("You write practice exercises. Write exactly one exercise: the first line is the title "
                  "(at most 60 characters, no # and no quotes), then a blank line, then the exercise text "
                  "(at most 300 words, no answer)."),
    draft_request="Topic: {topic}. Difficulty: {difficulty}.",
    difficulty_names={"easy": "Beginner", "medium": "Intermediate", "hard": "Challenge"},
    approval_summary="Save the exercise \"{title}\" to the local exercise bank",
    receipt_system=("You are the exercise bank assistant. Using only the facts given, tell the learner in one or "
                    "two sentences what was saved, and name the exercise title. If status is already_saved, say "
                    "nothing was saved again this time; if duplicated, say the same operation was saved more than "
                    "once; if edited_by_person is true, mention that the saved version is the one a person edited. "
                    "Do not add anything the facts do not say."),
    receipt_prompt="Facts: {facts}",
    answer_empty="(The model returned no text.)",
    bank_bad_operation="operation_id must look like save-<letters or digits>-<number>.",
    bank_bad_origin="origin must be fresh or resumed.",
    bank_bad_exercise="The exercise is not acceptable; fields with a problem: {fields}.",
    answers={
        "suspended": ("The run ended right after the {point} step with business status suspended: that is neither a failure "
                      "nor a completion. The last checkpoint is {checkpoint}. To continue, open it in the events "
                      "and press its “Resume from” button."),
        "rejected": "The person approving rejected this draft and nothing was written. The last checkpoint is {checkpoint}.",
        "timed_out": "Waiting for the approval timed out and nothing was written. The last checkpoint is {checkpoint}.",
        "failed": "Not finished: {reason}",
    },
    reasons={
        "bad_draft": ("The model's draft is not usable (it needs a title line and a body, a title of at most 80 "
                      "characters and a body of at most 1500), so it never reached approval."),
        "invalid_edit": ("The person's edit is not acceptable (a missing field, or a wrong difficulty or length). "
                         "Nothing was saved and no approved checkpoint was written."),
        "unapproved": "The content in the checkpoint no longer matches the digest it was approved with, so nothing is written.",
        "lookup_failed": "Looking up the operation id failed, so nothing was written.",
        "save_failed": "The write failed and the bank gained no row. The checkpoint is still at approved, so you can resume again.",
        "ledger_mismatch": ("The checkpoint says the exercise was saved, but the bank has no row for this operation id. "
                            "Nothing was rewritten on a guess; a person has to check."),
    },
    point_names={"after_draft": "drafting", "before_save": "approval", "after_save": "write"},
    ledger_title="What the exercise bank holds",
    ledger_summary=("Rows read straight from the database, not a retelling of a tool result. As many rows as an "
                    "operation id has, that many times it was written."),
    ledger_empty="The exercise bank has no rows yet: nothing was written by the end of this run.",
    ledger_columns=("Row", "Operation id", "Title", "Difficulty", "Written by"),
    origin_names={"fresh": "the first run", "resumed": "a resumed run"},
    label_rows_operation="Rows for this operation",
    label_rows_total="Rows in the bank",
    run_title="This run",
    status_summaries={
        "saved": "The bank has one row for this operation id. saved only says one write happened; it says nothing about how good the exercise is.",
        "already_saved": "After the resume, the lookup found this operation id already written, so nothing was written again; the bank still has one row.",
        "duplicated": "The bank has more than one row for the same operation id: the resume did not look first, so one save was executed twice.",
        "suspended": "By its parameters the run ends here to simulate a process dying. The checkpoint is still there and you can resume from it. suspended is neither a failure nor a completion.",
        "rejected": "The person approving rejected the draft and nothing was written.",
        "timed_out": "Waiting for the approval timed out and nothing was written.",
        "failed": "Nothing was written, or the write was not completed; the answer gives the reason.",
    },
    check_gate="No approval, no write",
    detail_gate="Approved: {approved}; rows in the bank for this operation: {rows}.",
    check_once="One operation id is written once",
    detail_once="Operation id {operation} has {rows} row(s) in the bank.",
    check_draft="The draft request was not sent again",
    detail_draft="This run sent {count} draft request(s) ({kind}). A first run should send 1 and a resumed run 0.",
    check_edit="The person's edit left a trail",
    detail_edit="The approved content differs from the draft and the state keeps both; the bank already has a row for this operation: {saved}, and if so it matches the approved content.",
    kind_names={"fresh": "first run", "resumed": "resumed run"},
    label_status="Business status",
    label_kind="Run kind",
    label_thread="Thread ID (first 8)",
    label_resumed_from="Resumed from (run / checkpoint)",
    label_operation="Operation id",
    label_checkpoints="Checkpoints saved by this run",
    label_approval="Approval (outcome / decided by / edited)",
    label_lookup="Operation id lookup before the write",
    label_write="Write",
    label_model_calls="Model calls",
    label_note="Learner notes",
    approval_carried="Carried by the digest in the checkpoint; no new approval this run",
    lookup_names={"not_asked": "not run", "found": "found: this operation is already done",
                  "not_found": "not found: free to write", "skipped": "skipped (blind resume)"},
    write_names={"not_asked": "not run", "written": "written", "skipped": "not written (operation id already done)"},
    edited_yes="edited",
    edited_no="not edited",
    yes_text="yes",
    no_text="no",
    value_none="—",
    diff_columns=("Field", "The model's draft", "What was approved", "Row in the bank"),
    field_title="Title",
    field_difficulty="Difficulty",
    field_body="Body (first 40 characters)",
)
