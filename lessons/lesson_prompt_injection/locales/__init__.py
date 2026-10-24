"""Runtime text of prompt-injection: everything this lesson sends to the model or puts into events.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
Keys of the dict fields are codes from guard.py and runtime.py (rule codes, verdicts, probe ids).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The request: system prompts (plain, and with the warning), tool descriptions, argument descriptions.
    system_plain: str
    system_warned: str
    tool_descriptions: dict[str, str]  # keyed by tool name
    argument_descriptions: dict[str, str]  # keyed by argument name
    # Questions the runner asks.
    question_notice: str
    question_write: str
    question_fee: str
    question_direct: str  # {question}
    question_pickup: str
    # Strings that mark an answer: the true fee, the words of the demanded lie.
    fee_fact: tuple[str, ...]
    free_markers: tuple[str, ...]
    # What the model reads when a call is refused.
    denied: str  # {reason}
    needs_approval: str
    approval_refused: dict[str, str]  # rejected, timeout
    approval_mismatch: str
    approval_summary: str  # {path} {size}
    # Names for codes.
    rules: dict[str, str]
    verdicts: dict[str, str]  # allow, confirm, deny
    verdicts_answer: dict[str, str]  # held, followed, unclear, n/a
    origins: dict[str, str]
    approvals: dict[str, str]
    bases: dict[str, str]
    task_names: dict[str, str]
    scenario_names: dict[str, str]
    arm_names: dict[str, str]
    probe_labels: dict[str, str]
    decision_cell: str  # {verdict} {rule}
    source_cell: str  # {tool} {items} {planted}
    planted_mark: str  # {ids}
    clean_mark: str
    # Text the probes write or send.
    probe_overwrite: str
    probe_note: str
    probe_query: str
    # Normal-task report.
    report_normal_title: str
    report_normal_summary: str
    check_tasks_done: str
    check_no_false_refusal: str
    check_write_asked: str
    check_no_out_of_scope: str
    columns_normal: tuple[str, ...]
    label_tool_calls: str
    label_denied: str
    label_approvals: str
    # Attack report.
    report_attack_title: str
    report_attack_summary: str
    check_no_effect: str
    check_probes_blocked: str
    check_probes_allowed: str
    detail_effects: str  # {effects} {outbox} {changed}
    label_proposals: str
    label_violations: str
    label_blocked: str
    label_effects: str
    label_probes: str
    label_basis: str
    columns_calls: tuple[str, ...]
    # Model side against executor side.
    report_split_title: str
    report_split_summary: str
    columns_split: tuple[str, ...]
    # Probe report.
    report_probes_title: str
    report_probes_summary: str
    check_probe_verdicts: str
    label_probe_attacks: str
    label_probe_blocked: str
    label_probe_ran: str
    label_false_refusals: str
    columns_probes: tuple[str, ...]
    # Comparison report.
    report_compare_title: str
    report_compare_summary: str
    check_arm_clean: str  # {arm}
    detail_no_proposal: str
    columns_compare: tuple[str, ...]
    label_floor: str
    # Propagation report.
    report_propagation_title: str
    report_propagation_summary: str
    check_hop_one: str
    columns_chain: tuple[str, ...]
    # Shared labels and values.
    label_model_calls: str
    label_usage: str
    label_note: str
    detail_count: str  # {ok} {total}
    value_yes: str
    value_no: str
    value_none: str
    value_empty: str
    value_no_answer: str
    value_not_reported: str
    tokens_partly_reported: str  # {total} {missing}
    answer_block: str  # {task} {answer}


texts_for = catalog(__name__, Texts)
