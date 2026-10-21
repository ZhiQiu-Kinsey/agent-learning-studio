"""Runtime text of goal-loops: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
Field names, note ids, statuses and reason codes are code and stay the same in every language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The material: four short notes, keyed by note id.
    note_titles: dict[str, str]
    notes: dict[str, str]
    # The goal and the card fields.
    goal_names: dict[str, str]
    field_labels: dict[str, str]
    # What the worker gets: system prompts by worker style, the task, the feedback after a round.
    worker_system: dict[str, str]
    task: str  # {goal} {fields} {condition} {notes}
    condition_line: str  # {field} {label} {sources}
    any_note: str
    note_line: str  # {id} {title}
    feedback: str  # {loop_round} {passed} {total} {issues}
    feedback_claim: str  # {claim} {verdict}
    issue_line: str  # {field} {detail}
    list_separator: str
    # The read_note tool.
    tool_description: str
    tool_note_id: str
    unknown_note: str  # {note_id} {notes}
    # Reading the worker's reply.
    no_json_object: str
    card_not_object: str
    no_submission: str  # {steps}
    # What the evaluator writes for each check.
    detail_pass: str  # {value}
    detail_empty: str
    detail_unsupported: str  # {value}
    detail_unread: str  # {notes}
    detail_unreachable: str  # {count}
    # Verdicts, decisions and reasons, keyed by code.
    verdicts: dict[str, str]
    decisions: dict[str, str]
    reasons: dict[str, str]
    # The task card emitted before the first round.
    card_goal: str  # {goal}
    card_input_scope: str
    card_output: str  # {fields}
    card_evidence: str
    card_failure: str  # {stall} {repeats}
    card_stop: str  # {rounds} {calls} {seconds}
    # The lab report.
    report_title: str
    report_summary: str
    label_outcome: str
    label_stop_reason: str
    label_progress: str
    label_rounds: str
    label_max_rounds: str
    label_model_calls: str
    label_total_tokens: str
    label_claims_done: str
    label_claims_disagree: str
    label_notes_read: str
    label_seconds: str
    label_note: str
    tokens_partly_reported: str  # {total} {missing}
    value_not_reported: str
    value_none: str
    value_empty: str
    table_columns: tuple[str, ...]
    # The final answer, keyed by decision.
    answers: dict[str, str]  # {reason} {passed} {total} {rounds} {card}
    # One-sentence notes the offline test model writes into its replies; only fixtures.py reads them.
    fixture_notes: dict[str, str]


texts_for = catalog(__name__, Texts)
