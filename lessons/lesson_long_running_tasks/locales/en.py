"""Runtime text of long-running-tasks (English)."""
from lessons.lesson_long_running_tasks.locales import Texts

TEXTS = Texts(
    list_separator=", ",
    system=(
        "You are the inspection assistant of a course. Put slow checks in the background with start_background_job: "
        "it returns a job id at once and does not wait for the job to finish. When a job has ended, the harness hands "
        "you its result in one separate message in a later round; the message opens with its source and is not "
        "something the user said. Do not guess a result before it arrives. When there is nothing else to do, say what "
        "you are waiting for; do not call check_job again and again. Once the required results are in, call "
        "submit_report; every value in the report must come from a background result, copied as is. When a background "
        "job fails, read the error first, then decide whether to retry."
    ),
    tasks={
        "nightly": (
            "Tonight's inspection: 1) verify the SHA-256 of the 6 submission packs with the background job "
            "checksum_pack; its value is the digest; 2) count how many of the 12 students passed with the background "
            "job grade_stats; its value is the number of passes. When both results have arrived, send the report with "
            "submit_report. While you wait you may read the rules with read_policy."
        ),
        "late": (
            "Late-score inspection: 1) verify the SHA-256 of the 6 submission packs with the background job "
            "checksum_pack; its value is the digest; 2) import the late-score sheet with the background job "
            "late_import; its value is the number of rows imported. When both results have arrived, send the report "
            "with submit_report."
        ),
        "deep": (
            "Full inspection before the finals: 1) verify the SHA-256 of the 6 submission packs with the background job "
            "checksum_pack; its value is the digest; 2) scan 8 shards for repeated content with the background job "
            "deep_scan; its value is the number of repeated shards. When both results have arrived, send the report "
            "with submit_report."
        ),
    },
    policies={
        "pass_line": "The pass line is 60 points; 60 and above passes.",
        "late_rule": "The late-score sheet is typed by the teaching assistant, one row per line as \"student,score\".",
    },
    start_description=(
        "Run a slow check in the background and return its job id at once, without waiting for it to finish. Kinds: "
        "checksum_pack verifies the submission packs, grade_stats counts passing scores, late_import imports the "
        "late-score sheet, deep_scan scans every shard. When the job has ended, the harness hands you the result "
        "in a separate message. timeout_seconds is the deadline in seconds (5 to 120); leave it out for the default."
    ),
    check_description=(
        "Look up the status and progress of one background job. Once a job has ended, its result is shown only after "
        "it has been delivered; do not use this in place of waiting."
    ),
    cancel_description="Cancel a background job that is still running and return its state after the cancel. A job that has ended cannot be cancelled.",
    policy_description="Read one inspection rule; topic is pass_line or late_rule. A synchronous tool that returns at once.",
    report_description=(
        "Submit the report: one kind and value for every required job, with value copied from the background "
        "result. Submitting again replaces the previous report."
    ),
    start_note=(
        "The job is running in the background. When it has ended, the harness will send you the result in a "
        "separate message; it will not appear in this tool result."
    ),
    result_pending="The job has ended; its result has not been delivered yet.",
    unknown_kind="There is no job kind {kind}; available: {kinds}.",
    bad_timeout="timeout_seconds must be an integer from 5 to 120.",
    too_many_jobs="The limit of {limit} background jobs at once is reached; wait for one to end or cancel one before starting another.",
    unknown_job="There is no job {job_id}.",
    already_finished="{job_id} has already ended ({status}) and cannot be cancelled.",
    unknown_topic="There is no rule {topic}; available: {topics}.",
    report_shape="results must be a non-empty array; every item has exactly the fields kind and value, and value is a string.",
    report_kind="kind cannot be {kind} or repeat; choose from: {kinds}.",
    detail_checksum="{files} files, {size} bytes in all, first 12 hex digits of the SHA-256: {digest}.",
    detail_grades="{passed} of {total} students passed ({line} points and above), mean {mean} points.",
    bad_score="The score {value} in row {row} is not an integer.",
    detail_import="Imported {rows} rows of scores.",
    detail_scan="Scanned {shards} shards and found {duplicates} repeated shards.",
    timeout_detail="It went past its deadline of {seconds} seconds and the background executor stopped it.",
    cancel_detail="Cancelled: {reason}.",
    cancel_reasons={"model_request": "the model asked to cancel", "run_end": "cancelled when the run ended"},
    injection_header=(
        "[Background job results · source: the harness's background executor, not something the user said] "
        "It is second {now} on the virtual clock. These jobs have ended:"
    ),
    injection_items={
        "completed": "- {job_id} {kind}: completed, exit code {exit_code}, ended at second {finished_at}. value={value}. {summary}",
        "failed": "- {job_id} {kind}: failed, exit code {exit_code}, ended at second {finished_at}. Error: {summary}",
        "timed_out": "- {job_id} {kind}: timed out, exit code {exit_code}, ended at second {finished_at}. {summary}",
    },
    feedback="[Harness · goal check] At the end of round {round} the goal is not met yet: {reason}",
    reasons={
        "goal_met": "Every required job has a delivered result and the values in the report match them.",
        "kind_exhausted": "{kind} was started {attempts} times (limit {limit}), none succeeded and none is running; running the same job again would fail the same way.",
        "waiting": "Background jobs are still running: {jobs}.",
        "open": "Still to start: {kinds}.",
        "report_missing": "All required results are delivered, but no report has been submitted yet.",
        "report_mismatch": "The report does not match the background results: {detail}",
        "budget": "The budget of {rounds} rounds is used up and the goal is not met. Last check: {state}",
    },
    goal_done="{job} completed and its result was delivered",
    goal_running="{job} is still running",
    goal_exhausted="started {attempts} times, limit {limit}, none succeeded",
    goal_open="started {attempts} times, limit {limit}; it can be started or retried",
    report_waiting="not every required result has been delivered, so the report is not compared yet",
    report_missing="no report has been submitted",
    report_lacks="the report lacks {kind}",
    report_differs="the value of {kind} differs from the background result",
    report_match="every value in the report equals the result of its job",
    card_goal="Finish {kinds} in the background, then submit a report from the results",
    card_input_scope="Only the results that background jobs return in this run; the jobs really run in the background executor, and time is a virtual clock",
    card_output="submit_report: one kind and value for each required job ({kinds})",
    card_evidence="Each value in the report must equal the delivered result of its job; the harness checks them one by one",
    card_failure="If one kind of job was started {attempts} times, failed every time and none is running, the goal is judged impossible and the run stops",
    card_stop="At most {rounds} model calls, about {tick} seconds (virtual) each; when they are used up the run stops and cancels the background jobs still running",
    schedule_goal="Trigger the background job {kind} every {interval} seconds and watch what the scheduler does when the previous run has not finished",
    schedule_input_scope="A fixed-interval trigger and no model; the jobs really run in the background executor, and time is a virtual clock",
    schedule_output="One record per trigger: when it was due, the decision, and the run it started",
    schedule_evidence="The number of triggers equals the number expected in the time range; every run that starts has its own record",
    schedule_failure="When the previous run has not finished, handle it by \"{policy}\" and state the reason",
    schedule_stop="Stop at second {horizon} and cancel the jobs still running",
    policy_names={"skip": "skip", "queue": "queue", "parallel": "parallel with a cap"},
    fire_details={
        "started": "It was due and nothing was running, so a run started.",
        "started_from_queue": "The previous run ended and the queued trigger started its run.",
        "skipped": "The previous run had not finished, so this trigger was skipped.",
        "queued": "The previous run had not finished, so this trigger joined the queue.",
        "dropped": "The queue was full, so this trigger was dropped.",
        "denied": "The cap on parallel runs was reached, so this trigger was refused.",
    },
    fire_actions={"started": "started", "started_from_queue": "started from queue", "skipped": "skipped",
                  "queued": "queued", "dropped": "dropped", "denied": "refused"},
    fire_reasons={"previous_running": "previous run not finished", "queue_full": "queue full",
                  "concurrency_limit": "parallel cap reached"},
    report_titles={"nightly": "Background jobs and result injection", "late": "A failing job and a retry",
                   "deep": "Budget, polling and cancelling"},
    report_summary=(
        "The jobs really run in the executor; time is in seconds on a virtual clock. The verdict comes from the "
        "harness's goal check and does not depend on what the model says."
    ),
    check_report="The report matches the background results",
    check_goal_logged="Every round's goal check is recorded with its reason",
    detail_goal_logged="{rounds} rounds, {rounds} records",
    check_not_early="No background result appeared in any request before it was injected",
    detail_not_early="{count} injected results; each first appeared in the request of the round that injected it",
    detail_not_early_bad="The results of these jobs appeared before injection: {jobs}",
    check_no_orphans="No background thread is alive when the run ends",
    detail_no_orphans="Jobs cancelled at the end: {count}; every thread was joined",
    label_outcome="Outcome",
    label_stop_reason="Stop reason",
    label_rounds="Rounds",
    label_max_rounds="Round budget",
    label_jobs_started="Jobs started",
    label_jobs_completed="Completed",
    label_jobs_failed="Failed",
    label_jobs_timed_out="Timed out",
    label_jobs_cancelled="Cancelled",
    label_polls="check_job calls",
    label_injections="Injections",
    label_clock_end="End time (virtual)",
    label_orphans="Live background threads",
    label_note="Learner note",
    value_seconds="{seconds} s",
    value_empty="none",
    value_none="none",
    outcomes={"completed": "Completed", "abandoned": "Given up: cannot be completed", "budget_exhausted": "Budget used up"},
    status_names={"running": "running", "completed": "completed", "failed": "failed", "timed_out": "timed out",
                  "cancelled": "cancelled"},
    job_columns=("Job", "Kind", "Started (s)", "Start round", "Ended (s)", "Status", "Exit code", "Injected in round",
                 "Ended to injected (s)"),
    answers={
        "completed": "Inspection complete ({rounds} rounds): report {results}, checked item by item against the background results.",
        "abandoned": "Cannot be completed ({rounds} rounds): {reason} Report submitted: {results}.",
        "budget_exhausted": "Goal not met. {reason} Report submitted: {results}.",
    },
    schedule_report_title="Scheduled trigger: {policy}",
    schedule_summary=(
        "Every trigger is decided and recorded the moment it is due; the runs that start are real jobs in the "
        "background executor. Time is in seconds on a virtual clock."
    ),
    check_every_fire="Every time a trigger was due there is a record",
    detail_every_fire="{fires} triggers fired, {expected} expected",
    check_every_run="Every run that started has its own record",
    detail_every_run="{runs} runs, one job record each",
    label_policy="Overlap policy",
    label_fires="Triggers fired",
    label_runs_started="Runs started",
    label_skipped="Skipped",
    label_queued="Queued",
    label_dropped="Dropped",
    label_denied="Refused",
    label_runs_finished="Runs finished",
    label_cancelled_at_end="Cancelled at the end",
    label_waiting_at_end="Still queued at the end",
    fire_columns=("Trigger", "Due (s)", "Decided at (s)", "Decision", "Run", "Reason"),
    schedule_answer=(
        "{fires} triggers fired under the policy \"{policy}\": {started} runs started, {skipped} skipped, "
        "{queued} queued, {dropped} dropped, {denied} refused; jobs cancelled at the end: {cancelled}."
    ),
)
