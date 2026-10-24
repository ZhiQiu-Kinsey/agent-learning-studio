"""Runtime text of long-running-tasks: prompts, tool descriptions and errors, injected messages, goal reasons, reports.

zh_CN.py and en.py each fill every field; runtime.py, goal.py, executor.py, jobs.py and scheduler.py read them with
texts_for(context.locale). Tool names, parameter names, job kinds, statuses and event names are code and stay the
same in every language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    list_separator: str
    # What the model is told: the system prompt, one fixed task per scenario, the quick policy lookups.
    system: str
    tasks: dict[str, str]  # nightly / late / deep
    policies: dict[str, str]  # pass_line / late_rule
    # Tool descriptions and notes in tool results.
    start_description: str
    check_description: str
    cancel_description: str
    policy_description: str
    report_description: str
    start_note: str
    result_pending: str
    # Tool and executor errors (structured errors to the model).
    unknown_kind: str  # {kind} {kinds}
    bad_timeout: str
    too_many_jobs: str  # {limit}
    unknown_job: str  # {job_id}
    already_finished: str  # {job_id} {status}
    unknown_topic: str  # {topic} {topics}
    report_shape: str
    report_kind: str  # {kind} {kinds}
    # What the jobs return (jobs.py).
    detail_checksum: str  # {files} {size} {digest}
    detail_grades: str  # {passed} {total} {line} {mean}
    bad_score: str  # {row} {value}
    detail_import: str  # {rows}
    detail_scan: str  # {shards} {duplicates}
    timeout_detail: str  # {seconds}
    cancel_detail: str  # {reason}
    cancel_reasons: dict[str, str]  # model_request / run_end
    # The injected message: header and one line per ended job, by status.
    injection_header: str  # {now}
    injection_items: dict[str, str]  # completed / failed / timed_out: {job_id} {kind} {exit_code} {finished_at} {value} {summary}
    feedback: str  # {round} {reason}
    # Goal check: reasons by code, and the text of each per-kind and report check.
    reasons: dict[str, str]
    goal_done: str  # {job}
    goal_running: str  # {job}
    goal_exhausted: str  # {attempts} {limit}
    goal_open: str  # {attempts} {limit}
    report_waiting: str
    report_missing: str
    report_lacks: str  # {kind}
    report_differs: str  # {kind}
    report_match: str
    # Task cards (lesson.task_card).
    card_goal: str  # {kinds}
    card_input_scope: str
    card_output: str  # {kinds}
    card_evidence: str
    card_failure: str  # {attempts}
    card_stop: str  # {rounds} {tick}
    schedule_goal: str  # {interval} {kind}
    schedule_input_scope: str
    schedule_output: str
    schedule_evidence: str
    schedule_failure: str  # {policy}
    schedule_stop: str  # {horizon}
    # Scheduler.
    policy_names: dict[str, str]  # skip / queue / parallel
    fire_details: dict[str, str]  # by action
    fire_actions: dict[str, str]
    fire_reasons: dict[str, str]
    # Lab report of the model scenarios.
    report_titles: dict[str, str]
    report_summary: str
    check_report: str
    check_goal_logged: str
    detail_goal_logged: str  # {rounds}
    check_not_early: str
    detail_not_early: str  # {count}
    detail_not_early_bad: str  # {jobs}
    check_no_orphans: str
    detail_no_orphans: str  # {count}
    label_outcome: str
    label_stop_reason: str
    label_rounds: str
    label_max_rounds: str
    label_jobs_started: str
    label_jobs_completed: str
    label_jobs_failed: str
    label_jobs_timed_out: str
    label_jobs_cancelled: str
    label_polls: str
    label_injections: str
    label_clock_end: str
    label_orphans: str
    label_note: str
    value_seconds: str  # {seconds}
    value_empty: str
    value_none: str
    outcomes: dict[str, str]
    status_names: dict[str, str]
    job_columns: tuple[str, ...]
    answers: dict[str, str]  # {reason} {rounds} {results}
    # Lab report of the scheduler scenario.
    schedule_report_title: str  # {policy}
    schedule_summary: str
    check_every_fire: str
    detail_every_fire: str  # {fires} {expected}
    check_every_run: str
    detail_every_run: str  # {runs}
    label_policy: str
    label_fires: str
    label_runs_started: str
    label_skipped: str
    label_queued: str
    label_dropped: str
    label_denied: str
    label_runs_finished: str
    label_cancelled_at_end: str
    label_waiting_at_end: str
    fire_columns: tuple[str, ...]
    schedule_answer: str  # {policy} {fires} {started} {skipped} {queued} {dropped} {denied} {cancelled}


texts_for = catalog(__name__, Texts)
