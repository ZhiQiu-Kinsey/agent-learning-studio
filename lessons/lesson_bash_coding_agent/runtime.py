"""A coding agent with one bash tool, working in a throwaway copy of a fixture repository.

The agent proposes commands; course/sandbox.py decides whether and where they run (policy,
approval, runner) and the platform, not the agent, judges the result by re-running the tests.
The design follows mini-swe-agent (bash only, every command independent) and the safety notes
of chapter 5 of "Understanding AI Agents" (default no network, truncated output, structured
timeouts); the code and the experiments are written for this project.
"""
import json
import os
import re
from pathlib import Path
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from course.sandbox import CommandPolicy, CommandResult, Workspace, context_approver, run_guarded, select_runner
from lessons.lesson_bash_coding_agent.locales import Texts, texts_for

# A constant path, never browser input: the repository the agent repairs.
FIXTURE = Path(__file__).parent / "fixture_repo"
TEST_COMMAND = "python -m unittest discover -s tests"
PROBE_COMMAND = "python scripts/env_probe.py"
PROTECTED = ["tests/*"]
ACCEPTANCE_TIMEOUT_S = 60
DEFAULT_TIMEOUT_S = 20
WORKSPACE_LABEL = "<workspace>"  # the label the platform uses when it redacts the real path
SECRET_NAME = re.compile(r"(?i)(KEY|TOKEN|SECRET|PASSW|CREDENTIAL|AUTH|COOKIE|SESSION)")
STREAM_KEEP_BYTES = 8000  # head + tail the runner keeps per stream (OutputLimits defaults)


class Inputs(LessonInputs):
    task: Literal["fix_test", "get_green", "outside_doc", "slow_check"] = "fix_test"
    command_timeout_s: int = Field(default=DEFAULT_TIMEOUT_S, ge=2, le=60)


INPUT_MODEL = Inputs


def tool_definitions(locale: str, timeout_s: int = DEFAULT_TIMEOUT_S) -> list[dict]:
    """The one tool the model sees. The name and the argument are code; only the words are translated."""
    t = texts_for(locale)
    return [{"type": "function", "function": {
        "name": "bash", "description": t.tool_description.format(timeout=timeout_s),
        "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": t.tool_command}},
                       "required": ["command"], "additionalProperties": False}}}]


def command_record(result: CommandResult, isolated: bool, t: Texts) -> dict:
    """What the model and the run record both get back for one command: the facts of what happened."""
    if isinstance(result.detail.get("timeout_s"), float) and result.detail["timeout_s"].is_integer():
        result.detail["timeout_s"] = int(result.detail["timeout_s"])  # "3 seconds", not "3.0 seconds"
    data = result.to_dict(messages=t.sandbox_errors)
    if result.error_type == "approval_rejected" and not result.detail.get("note"):
        data["error"] = t.approval_rejected_no_note
    record = {key: data[key] for key in (
        "command", "backend", "shell", "policy", "approval", "ok", "exit_code", "stdout", "stderr", "truncated",
        "stdout_bytes", "stderr_bytes", "timed_out", "duration_ms", "escaped_processes_suspected",
        "error_type", "error", "detail")}
    record.update({"cwd": WORKSPACE_LABEL, "isolated": isolated})
    omitted = {name: size - STREAM_KEEP_BYTES for name, size in (("stdout", result.stdout_bytes),
                                                                  ("stderr", result.stderr_bytes))
               if size > STREAM_KEEP_BYTES}
    if omitted:
        # Present only when something was cut, so a selector on this key finds exactly those commands.
        record["omitted_bytes"] = omitted
    return record


def make_bash(context: RunContext, runner, policy: CommandPolicy, approve, t: Texts, ledger: list):
    def bash(command: str) -> dict:
        if not isinstance(command, str):
            raise ValueError(t.command_not_string)
        # Policy, then approval (restricted runner only), then the runner: the result says which step decided.
        result = run_guarded(command, runner=runner, policy=policy, approve=approve,
                             should_stop=context.cancelled, check_cancelled=context.check_cancelled)
        # A stop that killed the command ends the run; it is not a tool result for the model.
        context.check_cancelled()
        record = command_record(result, runner.isolated, t)
        ledger.append(record)
        return record
    return bash


def system_prompt(runner, timeout_s: int, t: Texts) -> str:
    shell = t.shell_posix if runner.shell_flavor == "posix" else t.shell_powershell
    approval = t.approval_none if runner.isolated else t.approval_restricted
    return t.system_prompt.format(shell=shell, timeout=timeout_s, approval=approval)


def agent_loop(context: RunContext, bash, tools: list[dict], system: str, task: str) -> tuple[str | None, int]:
    """The whole agent: ask the model, run the commands it proposes, hand the results back, until it stops asking.

    Returns its last reply (None when the model-call budget ran out first) and the number of model calls.
    """
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task}]
    for step_number in range(1, context.max_model_calls + 1):
        # 1. Every request carries the full history and the one tool.
        response = context.complete({"messages": messages, "tools": tools, "tool_choice": "auto",
                                     "temperature": 0}, step_number)
        message = response["choices"][0].get("message", {})
        calls = message.get("tool_calls") or []
        # 2. No command proposed: the content is the agent's last reply, which is a claim, not a result.
        if not calls:
            return message.get("content") or "", step_number
        # 3. The assistant message with the proposals goes back first, so each tool message can pair by id.
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
        for call in calls:
            result = context.execute_proposal(call, {"bash": bash})
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    return None, context.max_model_calls


def accept(context: RunContext, workspace: Workspace, runner, policy, approve, t: Texts) -> dict:
    """The platform's verdict: re-run the tests and look at the protected files, ignoring what the agent said."""
    # The re-run executes code the agent wrote into the project, so it asks for approval like any command.
    rerun = run_guarded(TEST_COMMAND, runner=runner, policy=policy, approve=approve,
                        timeout=ACCEPTANCE_TIMEOUT_S, should_stop=context.cancelled,
                        check_cancelled=context.check_cancelled)
    context.check_cancelled()
    # Did it run at all? "Ran and failed" and "never ran" are different verdicts.
    ran = rerun.error_type not in ("policy_denied", "approval_rejected", "approval_timeout",
                                   "approval_unavailable", "spawn_failed", "cancelled")
    tests_ok = ran and rerun.ok
    tampered = [change.path for change in workspace.protected_changes(PROTECTED)]
    return {"rerun": rerun, "ran": ran, "tests_ok": tests_ok, "tampered": tampered,
            "accepted": tests_ok and not tampered}


def probe_environment(runner) -> tuple[list[str] | None, int]:
    """Names of the variables a command started by the platform sees, and how many of the parent's look secret."""
    # A trusted script of the fixture, run before the agent has touched anything: no approval needed.
    probe = runner.run(PROBE_COMMAND, timeout=30)
    parent = sum(1 for name in os.environ if SECRET_NAME.search(name))
    if not probe.ok:
        return None, parent
    try:
        return [str(name) for name in json.loads(probe.stdout)["names"]], parent
    except (ValueError, KeyError, TypeError):
        return None, parent


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    t = texts_for(context.locale)
    context.check_cancelled()
    with Workspace(FIXTURE) as workspace:
        # Offline tests always use the restricted runner, so they do not depend on this machine having a container.
        runner, status = select_runner(workspace, prefer="restricted" if context.mode == "offline" else "auto",
                                       timeout=values.command_timeout_s)
        policy = CommandPolicy.for_runner(runner)
        names, parent_secrets = probe_environment(runner)
        _report_environment(context, runner, status, values, workspace, names, parent_secrets)
        approve = context_approver(context, lambda request: t.approve_command.format(command=_clip(request.command, 300)))
        approve_acceptance = context_approver(
            context, lambda request: t.approve_acceptance.format(command=_clip(request.command, 300)), kind="acceptance")
        ledger: list[dict] = []
        claim, model_calls = agent_loop(context, make_bash(context, runner, policy, approve, t, ledger),
                                        tool_definitions(context.locale, values.command_timeout_s),
                                        system_prompt(runner, values.command_timeout_s, t), t.tasks[values.task])
        _report_ledger(context, ledger, runner.isolated, model_calls)
        verdict = accept(context, workspace, runner, policy, approve_acceptance, t)
        _report_acceptance(context, workspace, verdict, claim)
    return _answer(verdict, claim, context.max_model_calls, t)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


def _tests_summary(rerun: CommandResult) -> tuple[int | None, int | None]:
    """Tests run and failed, read from the unittest summary lines; None when they are not there."""
    text = rerun.stderr + "\n" + rerun.stdout
    ran = re.search(r"^Ran (\d+) tests? in", text, re.M)
    failed = re.search(r"^FAILED \((.*?)\)", text, re.M)
    if not ran:
        return None, None
    count = sum(int(number) for number in re.findall(r"(?:failures|errors)=(\d+)", failed.group(1))) if failed else 0
    return int(ran.group(1)), count


def _not_run_reason(rerun: CommandResult, t: Texts) -> str:
    if rerun.error_type == "policy_denied":
        return t.reason_policy_denied.format(rule=(rerun.policy or {}).get("rule", ""))
    if rerun.error_type in ("approval_rejected", "approval_timeout", "approval_unavailable"):
        return t.reason_approval_refused
    return t.reason_other.format(error_type=rerun.error_type)


def _answer(verdict: dict, claim: str | None, limit: int, t: Texts) -> str:
    if not verdict["ran"]:
        head = t.answer_not_run.format(reason=_not_run_reason(verdict["rerun"], t))
    elif verdict["tampered"]:
        head = t.answer_tampered.format(files=", ".join(verdict["tampered"]))
    elif not verdict["tests_ok"]:
        head = t.answer_tests_failed
    else:
        head = t.answer_accepted
    tail = t.answer_claim.format(claim=_clip(claim, 600)) if claim is not None else t.answer_no_claim.format(limit=limit)
    return head + "\n\n" + tail


def _report_environment(context: RunContext, runner, status, values: Inputs, workspace: Workspace,
                        names: list[str] | None, parent_secrets: int) -> None:
    """Publish report 1: which backend runs the commands, whether it isolates, and why."""
    t = texts_for(context.locale)
    reason = "offline" if context.mode == "offline" else status.reason
    checks = [{"id": "isolation", "label": t.check_isolation, "passed": runner.isolated,
               "detail": t.detail_isolation_yes if runner.isolated else t.detail_isolation_no}]
    if names is None:
        checks.append({"id": "no-secrets", "label": t.check_no_secrets, "detail": t.detail_probe_failed})
    else:
        # Same name in the parent and in the child means the variable crossed over. Names only, never values.
        parent_names = {key.upper() for key in os.environ}
        crossed = [name for name in names if SECRET_NAME.search(name) and name.upper() in parent_names]
        checks.append({"id": "no-secrets", "label": t.check_no_secrets, "passed": not crossed,
                       "detail": t.detail_no_secrets.format(parent=parent_secrets, child=len(crossed))})
    context.emit("lesson.report", {
        "title": t.env_title_isolated if runner.isolated else t.env_title_unisolated,
        "summary": t.env_summary_isolated if runner.isolated else t.env_summary_unisolated,
        "checks": checks,
        "metrics": [
            {"id": "backend", "label": t.label_backend, "value": runner.backend},
            {"id": "isolation", "label": t.label_isolation,
             "value": t.value_isolated if runner.isolated else t.value_unisolated},
            {"id": "selection", "label": t.label_selection,
             "value": t.selection_reasons.get(reason, status.reason)},
            {"id": "selection-code", "label": t.label_selection_code, "value": reason},
            {"id": "shell", "label": t.label_shell, "value": runner.shell_flavor},
            {"id": "approval-mode", "label": t.label_approval_mode,
             "value": t.value_no_approval if runner.isolated else t.value_every_command},
            {"id": "timeout", "label": t.label_timeout, "value": values.command_timeout_s},
            {"id": "workspace-files", "label": t.label_workspace_files, "value": len(workspace.baseline.hashes)},
            {"id": "protected", "label": t.label_protected, "value": ", ".join(PROTECTED)},
        ],
        "table": {"columns": [t.col_env_name], "rows": [[name] for name in (names or [])]},
    })


def _approval_cell(record: dict, t: Texts) -> str:
    approval = record["approval"]
    if approval is None:
        return t.cell_not_asked
    if not approval.get("required"):
        return t.cell_not_required
    if record["error_type"] == "approval_timeout":
        return t.cell_approval_timeout
    return t.cell_approved if approval.get("approved") else t.cell_rejected


def _report_ledger(context: RunContext, ledger: list[dict], isolated: bool, model_calls: int) -> None:
    """Publish report 2: every command with its policy decision, approval, exit code and duration."""
    t = texts_for(context.locale)
    denied = [r for r in ledger if r["error_type"] == "policy_denied"]
    refused = [r for r in ledger if r["error_type"] in ("approval_rejected", "approval_timeout", "approval_unavailable")]
    timed_out = [r for r in ledger if r["timed_out"]]
    ran = [r for r in ledger if r["exit_code"] is not None or r["timed_out"]]
    unapproved = [r for r in ran if not (r["approval"] or {}).get("approved")]
    checks = []
    if not isolated:
        checks.append({"id": "approved-before-run", "label": t.check_approved_before_run, "passed": not unapproved,
                       "detail": t.detail_unapproved_run.format(count=len(unapproved)) if unapproved
                       else t.detail_approved_before_run})
    if timed_out:
        escaped = [r for r in timed_out if r["escaped_processes_suspected"]]
        checks.append({"id": "process-tree", "label": t.check_process_tree, "passed": not escaped,
                       "detail": (t.detail_process_tree_escaped if escaped else t.detail_process_tree).format(
                           count=len(timed_out))})
    rows = []
    for number, record in enumerate(ledger, 1):
        policy = record["policy"] or {}
        rows.append([number, _clip(record["command"], 80),
                     t.cell_deny.format(rule=policy.get("rule")) if policy.get("action") == "deny" else t.cell_allow,
                     _approval_cell(record, t),
                     record["exit_code"] if record["exit_code"] is not None else t.cell_none,
                     record["duration_ms"], t.value_yes if record["truncated"] else t.value_no])
    context.emit("lesson.report", {
        "title": t.ledger_title, "summary": t.ledger_summary, "checks": checks,
        "metrics": [
            {"id": "commands", "label": t.label_commands, "value": len(ledger)},
            {"id": "policy-denied", "label": t.label_policy_denied, "value": len(denied)},
            {"id": "approval-refused", "label": t.label_approval_refused, "value": len(refused)},
            {"id": "timeouts", "label": t.label_timeouts, "value": len(timed_out)},
            {"id": "truncated", "label": t.label_truncated, "value": sum(1 for r in ledger if r["truncated"])},
            {"id": "model-calls", "label": t.label_model_calls, "value": model_calls},
        ],
        "table": {"columns": list(t.ledger_columns), "rows": rows},
    })


def _report_acceptance(context: RunContext, workspace: Workspace, verdict: dict, claim: str | None) -> None:
    """Publish report 3: the platform's acceptance, the diff, and what the agent claimed (shown last, never trusted)."""
    t = texts_for(context.locale)
    rerun: CommandResult = verdict["rerun"]
    tests_run, tests_failed = _tests_summary(rerun) if verdict["ran"] else (None, None)
    changes = workspace.changes()
    if verdict["ran"]:
        pass_check = {"id": "tests-pass", "label": t.check_tests_pass, "passed": verdict["tests_ok"],
                      "detail": t.detail_tests_pass.format(
                          exit_code=rerun.exit_code, run=tests_run if tests_run is not None else t.value_not_parsed,
                          failed=tests_failed if tests_failed is not None else t.value_not_parsed)}
    else:
        # A check that did not run carries no verdict.
        pass_check = {"id": "tests-pass", "label": t.check_tests_pass,
                      "detail": t.detail_tests_not_run.format(reason=_not_run_reason(rerun, t))}
    context.emit("lesson.report", {
        "title": t.acceptance_title, "summary": t.acceptance_summary,
        "checks": [
            pass_check,
            {"id": "tests-untouched", "label": t.check_untouched, "passed": not verdict["tampered"],
             "detail": t.detail_untouched_changed.format(files=", ".join(verdict["tampered"]))
             if verdict["tampered"] else t.detail_untouched_ok},
            {"id": "accepted", "label": t.check_accepted, "passed": verdict["accepted"],
             "detail": t.detail_accepted if verdict["accepted"] else t.detail_not_accepted},
        ],
        "metrics": [
            {"id": "tests-run", "label": t.label_tests_run, "value": tests_run if tests_run is not None else t.value_not_parsed},
            {"id": "tests-failed", "label": t.label_tests_failed,
             "value": tests_failed if tests_failed is not None else t.value_not_parsed},
            {"id": "changed-files", "label": t.label_changed_files, "value": len(changes)},
            {"id": "diff", "label": t.label_diff, "value": workspace.diff(max_chars=6000) or t.value_no_diff},
            {"id": "rerun-output", "label": t.label_rerun_output, "value": _clip(rerun.stderr[-600:] or rerun.stdout[-600:], 600)},
            {"id": "agent-claim", "label": t.label_agent_claim, "value": _clip(claim, 600) if claim else t.value_no_claim},
        ],
        "table": {"columns": list(t.change_columns),
                  "rows": [[change.path, change.status, t.value_yes if change.path in verdict["tampered"] else t.value_no]
                           for change in changes]},
    })
