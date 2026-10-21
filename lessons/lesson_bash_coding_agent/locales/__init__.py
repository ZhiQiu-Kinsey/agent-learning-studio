"""Runtime text of bash-coding-agent: prompts, the tool description, command errors, reports and answers.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
Tool names, argument names, error_type codes and policy rule ids are code and stay the same in
every language; only the sentences around them are translated.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # System prompt: {shell} is shell_posix or shell_powershell, {timeout} the per-command limit in
    # seconds, {approval} approval_restricted or approval_none.
    system_prompt: str  # {shell} {timeout} {approval}
    shell_posix: str
    shell_powershell: str
    approval_restricted: str
    approval_none: str
    # Tool definition (tool_definitions): the description and its one parameter.
    tool_description: str  # {timeout}
    tool_command: str
    command_not_string: str
    # The user message of each task preset (Inputs.task).
    tasks: dict[str, str]
    # Messages for CommandResult.to_dict(messages=...): key is error_type or error_type:rule.
    sandbox_errors: dict[str, str]
    approval_rejected_no_note: str
    # One-line summaries the approval card shows.
    approve_command: str  # {command}
    approve_acceptance: str  # {command}
    # Report 1: the execution environment, written before the model runs.
    env_title_unisolated: str
    env_title_isolated: str
    env_summary_unisolated: str
    env_summary_isolated: str
    check_isolation: str
    detail_isolation_no: str
    detail_isolation_yes: str
    check_no_secrets: str
    detail_no_secrets: str  # {parent} {child}
    detail_probe_failed: str
    label_backend: str
    label_isolation: str
    value_unisolated: str
    value_isolated: str
    label_selection: str
    label_selection_code: str
    selection_reasons: dict[str, str]  # keyed by BackendStatus.reason, plus "offline"
    label_shell: str
    label_approval_mode: str
    value_every_command: str
    value_no_approval: str
    label_timeout: str
    label_workspace_files: str
    label_protected: str
    col_env_name: str
    # Report 2: the command ledger.
    ledger_title: str
    ledger_summary: str
    label_commands: str
    label_policy_denied: str
    label_approval_refused: str
    label_timeouts: str
    label_truncated: str
    label_model_calls: str
    check_approved_before_run: str
    detail_approved_before_run: str
    detail_unapproved_run: str  # {count}
    check_process_tree: str
    detail_process_tree: str  # {count}
    detail_process_tree_escaped: str  # {count}
    ledger_columns: tuple[str, ...]
    cell_allow: str
    cell_deny: str  # {rule}
    cell_approved: str
    cell_rejected: str
    cell_approval_timeout: str
    cell_not_required: str
    cell_not_asked: str
    cell_none: str
    value_yes: str
    value_no: str
    # Report 3: the platform's acceptance.
    acceptance_title: str
    acceptance_summary: str
    check_tests_pass: str
    detail_tests_pass: str  # {exit_code} {run} {failed}
    detail_tests_not_run: str  # {reason}
    check_untouched: str
    detail_untouched_ok: str
    detail_untouched_changed: str  # {files}
    check_accepted: str
    detail_accepted: str
    detail_not_accepted: str
    label_tests_run: str
    label_tests_failed: str
    change_columns: tuple[str, ...]
    label_changed_files: str
    label_diff: str
    label_agent_claim: str
    label_rerun_output: str
    value_not_parsed: str
    value_no_diff: str
    value_no_claim: str
    reason_policy_denied: str  # {rule}
    reason_approval_refused: str
    reason_other: str  # {error_type}
    # The answer the runner writes: the platform's verdict first, then what the agent said.
    answer_accepted: str
    answer_tampered: str  # {files}
    answer_tests_failed: str
    answer_not_run: str  # {reason}
    answer_claim: str  # {claim}
    answer_no_claim: str  # {limit}
    # Used only by the offline fixture (fixtures.py): the scripted model's last reply per task, and the
    # note its stand-in approver writes when it rejects a command. No real model or learner is involved.
    script_claims: dict[str, str]
    script_reject_note: str


texts_for = catalog(__name__, Texts)
