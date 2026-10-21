"""Runtime text of hooks-approval: prompts, tool descriptions, refusal messages, reports and answers.

zh_CN.py and en.py each fill every field; runtime.py and gate.py read them with texts_for(context.locale).
Tool names, argument names, error_type codes, hook names and event names are code and stay the same in
every language; only the sentences around them are translated.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # What the model reads: the system prompt, the four tool definitions and the task of each preset.
    system_prompt: str
    tool_descriptions: dict[str, str]  # keyed by tool name
    param_descriptions: dict[str, str]  # keyed by argument name
    tasks: dict[str, str]  # keyed by Inputs.task
    record_titles: dict[str, str]  # titles of the seeded tickets, keyed by ticket id
    # What the model reads back when the gate refuses a call or a tool fails.
    refusals: dict[str, str]  # keyed by error_type; may use {fields} {hook} {reason_text} {note}
    hook_reasons: dict[str, str]  # keyed by the reason code a deny hook returns
    desk_errors: dict[str, str]  # keyed by DeskError code; {record_id} / {owner}
    no_note: str
    # The one-line summary on an approval card; the facts it states are checked against the payload.
    approve_summary: dict[str, str]  # update_record {record_id} {field} {value}; send_notice {recipient} {subject} {chars}
    # Report 1: the hooks and settings of this run.
    hooks_title: str
    hooks_summary: str  # {domain}
    hook_columns: tuple[str, ...]
    phase_pre: str
    phase_post: str
    hook_roles: dict[str, str]  # keyed by hook name
    hook_rules: dict[str, str]  # keyed by hook name
    label_pre_hooks: str
    label_post_hooks: str
    label_timeout: str
    label_editable: str
    label_late_rewrite: str
    value_yes: str
    value_no: str
    # Report 2: the ledger of calls.
    gate_title: str
    gate_summary: str
    gate_columns: tuple[str, ...]
    risk_labels: dict[str, str]
    verdict_labels: dict[str, str]
    approval_labels: dict[str, str]  # approved, rejected, timeout, not_asked
    refusal_labels: dict[str, str]  # keyed by error_type; may use {hook}
    cell_executed: str
    cell_edited: str
    cell_none: str
    check_no_early_effect: str
    detail_no_early_effect: str  # {count}
    detail_early_effect: str
    check_args_match: str
    detail_args_match: str  # {count}
    detail_args_differ: str
    detail_nothing_gated_ran: str
    check_refused_not_run: str
    detail_refused_not_run: str  # {count}
    detail_refused_ran: str
    detail_nothing_refused: str
    check_summary_covers: str
    detail_summary_covers: str  # {count}
    detail_summary_misses: str
    detail_no_approvals: str
    check_redacted: str
    detail_redacted: str  # {count}
    detail_leaked: str
    detail_no_reads: str
    label_tool_calls: str
    label_ran_plain: str
    label_approved: str
    label_rejected: str
    label_timeouts: str
    label_hook_denied: str
    label_guard_blocked: str
    label_edited: str
    # Report 3: the desk after the run.
    effects_title: str
    effects_summary: str
    effects_columns: tuple[str, ...]
    kind_record: str
    kind_notice: str
    check_effects_match: str
    detail_effects_match: str  # {records} {notices}
    detail_effects_differ: str  # {records} {notices} {ledger_records} {ledger_notices}
    label_records_changed: str
    label_notices_written: str
    label_agent_claim: str
    value_no_claim: str
    # The answer the runner writes: the ledger and the desk first, then what the model said.
    answer_summary: str  # {calls} {plain} {approved} {refused}
    answer_refused_head: str
    answer_refused_line: str  # {n} {tool} {reason}
    answer_effects: str  # {records} {notices}
    answer_claim: str  # {claim}
    answer_no_claim: str  # {limit}
    # Used only by the offline fixture (fixtures.py): the scripted model's notices and last reply, and the
    # note its stand-in approver writes when it rejects a card. No real model or learner is involved.
    script_notice_subject: str  # {record_id}
    script_notice_body: str  # {record_id}
    script_broadcast_subject: str  # {record_id}
    script_done: dict[str, str]  # keyed by Inputs.task: the last reply when nothing was refused
    script_partial: str  # {reasons}
    script_reject_note: str


texts_for = catalog(__name__, Texts)
