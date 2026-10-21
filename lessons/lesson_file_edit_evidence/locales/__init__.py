"""Runtime text of file-edit-evidence: the prompts and tool texts the model reads, tool errors, report texts and answers.

zh_CN.py and en.py each fill every field; file_tools.py and runtime.py read them with texts_for(locale).
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Prompt and task (sent to the model).
    system_prompt: str
    task: str  # {tree} {command}
    tree_line: str  # {path} {lines}
    task_card: dict[str, str]
    # Tool definitions: descriptions are language, names and parameter names are code.
    desc_read_file: str
    desc_write_file: str
    desc_edit_file: str
    desc_edit_lines: str
    desc_run_tests: str
    param_path: str
    param_start_line: str
    param_end_line: str
    param_content: str
    param_old: str
    param_new: str
    param_first_line: str
    param_last_line: str
    param_new_text: str
    # Tool errors (file_tools.py): they travel in tool_result.error.
    path_outside: str  # {path}
    protected_path: str  # {path}
    file_not_found: str  # {path}
    not_a_file: str  # {path}
    not_text: str  # {path}
    file_too_large: str  # {path} {limit}
    not_read_yet: str  # {path}
    stale_read: str  # {path}
    partial_read: str  # {path}
    line_numbers_stale: str  # {path}
    invalid_range: str  # {start} {end} {total}
    invalid_argument: str  # {name}
    old_empty: str
    old_not_found: str  # {path}
    old_not_unique: str  # {count} {lines}
    no_op_edit: str
    write_failed: str  # {path}
    # Sandbox: labels, approval texts and the sandbox error codes the model and the learner read.
    label_isolated: str
    label_unisolated: str
    approvals: dict[str, str]
    environment_text: str  # {label} {approval}
    approve_tests: str  # {command} {label} {files}
    approve_acceptance: str  # {command} {label} {files}
    sandbox_errors: dict[str, str]
    # Report pieces shared by both scenarios.
    separator: str
    value_yes: str
    value_no: str
    value_none: str
    value_not_reported: str
    tokens_partly_reported: str  # {total} {missing}
    label_note: str
    label_model_calls: str
    label_tool_calls: str
    # Scenario edit.
    strategies: dict[str, str]
    edit_titles: dict[str, str]
    edit_summary: str
    check_tests: str
    check_tests_detail: str  # {ran} {outcome}
    check_tests_not_run: str  # {reason}
    check_untouched: str
    check_untouched_detail: str  # {files}
    check_scope: str
    check_scope_detail: str  # {files} {symbols} {unexpected}
    check_scope_unparsable: str  # {files} {symbols} {unexpected}
    check_chain: str
    check_chain_ok: str  # {rows}
    check_chain_broken: str  # {problems}
    chain_reasons: dict[str, str]
    label_environment: str
    label_write_calls: str  # {tool}
    write_calls_value: str  # {ok} {rejected}
    label_read_calls: str
    label_test_runs: str
    label_write_chars: str
    label_result_chars: str
    label_completion_tokens: str
    label_total_tokens: str
    label_lines: str
    lines_value: str  # {added} {removed}
    label_self_check: str
    label_base_hash: str  # {path}
    label_final_hash: str  # {path}
    label_diff: str
    journal_columns: tuple[str, ...]
    outcome_written: str
    outcome_unchanged: str
    verdict_ok: str
    verdict_failed: str
    verdict_not_run: str
    chain_ok: str
    chain_broken: str
    claim_quote: str  # {claim}
    claim_rounds: str  # {limit}
    edit_answer: str  # {strategy} {writes} {rejected} {files} {added} {removed} {tests} {chain} {claim}
    # Scenario guards.
    cases: dict[str, str]
    case_titles: dict[str, str]
    extras: dict[str, str]
    mark_ok: str
    mark_bad: str
    case_detail: str  # {steps} {matched} {extras}
    external_note: str
    guards_title: str
    guards_summary: str
    guards_columns: tuple[str, ...]
    label_rejected: str
    label_writes_applied: str
    label_commands_run: str
    guards_answer: str  # {cases} {calls} {rejected}


texts_for = catalog(__name__, Texts)
