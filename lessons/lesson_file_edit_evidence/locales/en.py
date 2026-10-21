"""file-edit-evidence runtime text: English."""
from lessons.lesson_file_edit_evidence.locales import Texts

TEXTS = Texts(
    system_prompt=(
        "You are a coding agent working in a small Python repository. You can only read and write files and run the tests "
        "through the tools you are given. Rules:\n"
        "1. Read a file with read_file before you change it. The tools refuse a file you have not read, and a file that "
        "was changed by someone else after you read it; when refused, read it again and edit from the new content.\n"
        "2. Paths are relative to the repository root. Files under tests/ are read-only.\n"
        "3. The \"line number|\" at the start of each line in a read_file result is for display; it is not part of the file.\n"
        "4. After editing, call run_tests and judge from its output whether you are done.\n"
        "5. Finish with one or two sentences on what you changed and how the tests went; do not claim anything you did not do."
    ),
    task=(
        "Two tests in the repository fail:\n"
        "1. An order of 300 or more should get a 20% discount (today the top tier is 15%, from 200).\n"
        "2. An order of exactly 50 should ship free (today it must be more than 50).\n"
        "Change only shop/pricing.py so that all tests pass, and do not touch any file under tests/; the docstring of "
        "discount_rate must match the new rule.\n\n"
        "Files in the repository:\n{tree}\n\n"
        "Test command (the run_tests tool runs it): {command}"
    ),
    tree_line="{path} ({lines} lines)",
    task_card={
        "goal": "Make every test under tests/ pass: 20% off from 300, free shipping at exactly 50",
        "input_scope": "Change only shop/pricing.py; every file in the repository can be read, tests/ is read-only",
        "output": "The change to shop/pricing.py, plus one or two sentences of explanation",
        "evidence": "The platform reruns the tests itself and they pass; the before and after hash and the unified diff of every write add up",
        "failure": "Write without reading, file changed after the read, old not unique, stale line numbers, path outside the workspace, editing a test: the tool refuses with a structured error and the file stays as it was",
        "stop": "The model stops proposing calls, or uses up the round limit of 10",
    },
    desc_read_file=(
        "Read one text file in the workspace and return its content with line numbers; the \"line number|\" at the start "
        "of each line is for display and is not part of the file. Use start_line and end_line to read one range "
        "(1-based, both ends included); without them it reads from line 1, at most 400 lines. Read a file before you change it."
    ),
    desc_write_file=(
        "Write the whole file as content; a missing file is created. An existing file must first be read in full with "
        "read_file and must not have been changed by anyone else since, otherwise the call is refused. Files under tests/ cannot be written."
    ),
    desc_edit_file=(
        "Exact replace: replace old with new in the file. old must be identical to the file text (without the line-number "
        "prefix) and must occur exactly once; a missing or repeated match is an error and the file stays as it was. "
        "Read the file first; if someone else changed it after your read, the call is refused. Files under tests/ cannot be changed."
    ),
    desc_edit_lines=(
        "Line replace: replace lines start_line to end_line (both included) with new_text. The numbers must come from "
        "the latest read_file; every write makes line numbers void, so read again first. If someone else changed the "
        "file after your read, the call is refused. Files under tests/ cannot be changed."
    ),
    desc_run_tests=(
        "Run the tests in the workspace (python -m unittest discover -s tests) and return the exit code and the output. "
        "Without container isolation every run needs a human's approval first; when it is rejected the command does not run."
    ),
    param_path="Path relative to the repository root, for example shop/pricing.py",
    param_start_line="First line to read, 1-based, default 1",
    param_end_line="Last line to read (included); default is 400 lines after the first line, or the end of the file",
    param_content="The complete new content of the file",
    param_old="The text to replace: identical to the file text and occurring exactly once in the file",
    param_new="The replacement text",
    param_first_line="Number of the first line to replace (included)",
    param_last_line="Number of the last line to replace (included)",
    param_new_text="The new text for these lines, possibly several lines; an empty string deletes the lines",
    path_outside="The path {path} is not inside the workspace: use a path relative to the repository root, not an absolute path, .. or ~.",
    protected_path="{path} is protected and cannot be written: files under tests/ are read-only; the task is to change the code, not the tests that check it.",
    file_not_found="File {path} not found.",
    not_a_file="{path} is not a file.",
    not_text="{path} is not a UTF-8 text file and cannot be read or written.",
    file_too_large="{path} is larger than {limit} bytes; the tool does not handle it.",
    not_read_yet="You have not read {path} yet, nothing was written. Read it with read_file first, then edit.",
    stale_read="{path} was changed after you read it, so what you hold is out of date; nothing was written. Call read_file again and edit from the new content.",
    partial_read="You read only part of {path}; writing the whole file would overwrite what you did not see, so nothing was written. Read all of it first, or use a local edit instead.",
    line_numbers_stale="{path} was written since your last read_file, so its line numbers are void; nothing was written. Call read_file again and use the new line numbers.",
    invalid_range="The line range is wrong: start_line={start}, end_line={end}, the file has {total} lines. It needs 1 <= start_line <= end_line <= total lines.",
    invalid_argument="The argument {name} has the wrong type.",
    old_empty="old must be a non-empty string.",
    old_not_found="old was not found in {path}. It must be identical to the file text and must not include the line-number prefix that read_file shows; read the file again and copy from it.",
    old_not_unique="old occurs {count} times in the file (lines {lines}), so it is unclear which one to change; nothing was written. Include the surrounding lines in old so it occurs once.",
    no_op_edit="This edit would not change the file, so nothing was written.",
    write_failed="The operating system refused to write {path}; the file is as it was.",
    label_isolated="Isolated · commands run in a container",
    label_unisolated="Not isolated · commands run on your machine",
    approvals={"every_command": "every command needs your approval first", "none": "runs in a container, no per-command approval"},
    environment_text="{label}; {approval}",
    approve_tests="Run the tests: {command}. {label}. This executes code the agent changed; {files} files are changed so far.",
    approve_acceptance="Platform acceptance, rerun the tests: {command}. {label}. This executes code the agent changed; {files} files are changed so far.",
    sandbox_errors={
        "policy_denied": "The command was refused by the policy (rule {rule}) and did not run.",
        "approval_rejected": "A human rejected the command; it did not run.",
        "approval_timeout": "Nobody decided in time; the command did not run.",
        "approval_unavailable": "The command needs a human's approval and there is no approval channel; it did not run.",
        "timeout": "The tests ran longer than {timeout_s} seconds and were terminated.",
        "output_limit": "The tests wrote too much output and were terminated.",
        "cancelled": "The run was stopped and the command was terminated.",
        "nonzero_exit": "The test command ended with exit code {exit_code}; see stdout and stderr for the reason.",
        "spawn_failed": "The command could not be started.",
    },
    separator=", ",
    value_yes="yes",
    value_no="no",
    value_none="none",
    value_not_reported="not reported",
    tokens_partly_reported="{total} ({missing} responses not reported)",
    label_note="Learner note",
    label_model_calls="Model calls",
    label_tool_calls="Tool calls",
    strategies={"rewrite": "Whole-file rewrite", "replace": "Exact replace", "lines": "Line replace"},
    edit_titles={"rewrite": "Whole-file rewrite: write_file", "replace": "Exact replace: edit_file", "lines": "Line replace: edit_lines"},
    edit_summary=(
        "One change task, one write tool for the model. The platform reruns the tests itself and checks whether the tests "
        "were touched, which functions changed and whether the before and after hashes link up. The checks below come "
        "from the files and the command, not from what the model says."
    ),
    check_tests="The platform reruns the tests",
    check_tests_detail="Ran {ran} tests, result {outcome}.",
    check_tests_not_run="The tests did not run: {reason}. This item is not judged as passed.",
    check_untouched="Files under tests/ were not changed",
    check_untouched_detail="Protected files changed: {files}.",
    check_scope="The change stays inside what the task allows",
    check_scope_detail="Files changed: {files}; functions changed, removed or added: {symbols}; outside the task: {unexpected}.",
    check_scope_unparsable="The changed file does not parse as Python, so the scope cannot be compared (files: {files}).",
    check_chain="Every write has a before and after hash, and they link up",
    check_chain_ok="Writes that took effect: {rows}; each before hash equals the previous after hash, and the last one equals the file's hash now.",
    check_chain_broken="The hash chain does not add up: {problems}.",
    chain_reasons={
        "broken_chain": "this row does not start at the file's hash at that moment",
        "unexplained_change": "the file changed but no write record explains it",
        "final_mismatch": "the last row does not end at the file's hash now",
    },
    label_environment="Execution environment",
    label_write_calls="{tool} calls (accepted / refused)",
    write_calls_value="{ok} / {rejected}",
    label_read_calls="read_file calls",
    label_test_runs="Test runs the model made itself",
    label_write_chars="Argument characters of write calls (as sent)",
    label_result_chars="Tool result characters (returned to the model)",
    label_completion_tokens="Completion tokens (provider reported)",
    label_total_tokens="Total tokens (provider reported)",
    label_lines="Lines added / removed by writes that took effect",
    lines_value="+{added} / -{removed}",
    label_self_check="The model ran the tests after its last write",
    label_base_hash="{path} start hash (first 12)",
    label_final_hash="{path} final hash (first 12)",
    label_diff="Unified diff (against the start version, all files)",
    journal_columns=("#", "Tool", "Path", "Outcome", "Before hash", "After hash", "Added / removed"),
    outcome_written="written",
    outcome_unchanged="no change",
    verdict_ok="passed",
    verdict_failed="failed",
    verdict_not_run="did not run",
    chain_ok="closed",
    chain_broken="broken",
    claim_quote="The model says: {claim}",
    claim_rounds="The model used up the round limit of {limit} and gave no conclusion.",
    edit_answer=(
        "{strategy}: writes that took effect {writes}, refused {rejected}; files changed {files}, lines added {added}, removed {removed}. "
        "The platform reran the tests: {tests}. Hash chain: {chain}. {claim}"
    ),
    cases={"read_first": "Read before write", "path_scope": "Path and scope", "not_unique": "Unique match",
           "line_drift": "Line drift", "stale": "Stale detection"},
    case_titles={
        "read_first": "Read before write: unread or partly read, the tool refuses",
        "path_scope": "Path and scope: escaping and editing tests, the tool refuses",
        "not_unique": "Unique match: not found or found several times, the tool refuses",
        "line_drift": "Line drift: old line numbers die after a write",
        "stale": "Stale detection: changed after the read, refuse to overwrite",
    },
    extras={
        "escape_absent": "escape.txt did not appear outside the workspace",
        "numbers_shifted": "the old line number really pointed at another line",
        "external_kept": "the externally added line was not overwritten",
        "chain": "the hash chain is as expected",
    },
    mark_ok=": yes",
    mark_bad=": no",
    case_detail="{matched} of {steps} steps matched the declared outcome; {extras}.",
    external_note="An external change simulated by the runner: it wrote this file directly, past the tools, and the tools were not told.",
    guards_title="Five guards: read before write, path, unique match, line numbers, stale read",
    guards_summary=(
        "This group calls no model. The runner submits calls the way a careless or hurried model might, declares the "
        "expected outcome of each step first, then compares it with the error_type the tool really returns and the file "
        "hashes. A refused call must leave every file as it was."
    ),
    guards_columns=("Case", "Tool", "Path", "Expected", "Actual", "Files unchanged"),
    label_rejected="Refused calls",
    label_writes_applied="Writes that took effect",
    label_commands_run="Commands run",
    guards_answer="Ran {cases} cases and submitted {calls} calls; the tools refused {rejected} of them. The report table compares every step.",
)
