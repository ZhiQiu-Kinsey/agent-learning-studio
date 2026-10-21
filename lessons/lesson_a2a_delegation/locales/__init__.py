"""Runtime text of a2a-delegation: everything the delegating side sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
The remote agent has its own catalog in locales/worker/, the offline test model in locales/fixture/.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The delegating agent's instructions and the tool built from the Agent Card.
    system_prompt: str
    tool_description: str  # {agent} {description} {skills}
    skill_id_description: str
    claims_description: str  # {max}
    delegation_text: str
    # Input and setup errors.
    empty_question: str
    needs_model: str
    worker_start_failed: str
    card_unusable: str  # {problem}
    card_problems: dict[str, str]
    # Errors the delegation tool returns to the model (structured errors).
    unknown_skill: str  # {skill_id}
    bad_claims: str  # {max}
    delegation_limit: str
    timeout_error: str  # {seconds} {state}
    no_task_id: str
    remote_failed: str  # {state} {message}
    remote_interrupted: str  # {state}
    stream_ended: str  # {state}
    remote_unavailable: str  # {error}
    incomplete_result: str  # {problems} {partial}
    problem_no_data: str
    problem_missing: str  # {claim_id}
    problem_no_evidence: str  # {claim_id}
    problem_unknown: str  # {claim_id}
    problem_separator: str
    # Answers the runner writes itself.
    empty_answer: str
    rounds_exhausted: str
    # Lab report.
    report_title: str
    report_summary: str  # {outcome} {states} {model_calls}
    outcomes: dict[str, str]
    faults: dict[str, str]
    check_card: str
    detail_card: str  # {name} {version} {skills} {streaming}
    check_endpoint: str
    detail_endpoint: str  # {card_url} {base_url}
    check_task_match: str
    detail_task_match: str  # {count} {task_id}
    check_bounded: str
    detail_bounded: dict[str, str]  # by outcome; {seconds} {state}
    check_result: str
    detail_result: dict[str, str]  # {problems}
    check_no_secret: str
    detail_env: str  # {names}
    check_stopped: str
    detail_stopped: dict[str, str]  # {port}
    label_outcome: str
    label_final_state: str
    label_states: str
    label_deadline: str
    label_model_calls: str
    label_a2a_messages: str
    label_worker_pid: str
    label_fault: str
    label_note: str
    value_none: str
    value_empty: str
    deadline_value: str  # {seconds}
    state_separator: str
    columns_timeline: tuple[str, ...]
    directions: dict[str, str]


texts_for = catalog(__name__, Texts)
