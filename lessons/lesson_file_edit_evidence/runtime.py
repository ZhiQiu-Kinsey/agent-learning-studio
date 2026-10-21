"""File tools, edit strategies and change evidence: one small repository, three ways to edit it, one journal of hashes and diffs.

Two scenarios share the file tools of file_tools.py:

- edit: the model fixes the failing tests in a throwaway copy of fixture_repo with ONE write tool per run
  (write_file, edit_file or edit_lines), so the three strategies are compared on the same task. The platform then
  checks the result itself: it reruns the tests, checks that the tests were not touched, which functions changed and
  whether the journal of hashes closes. The model's own final message is quoted, never trusted.
- guards: no model. The runner submits calls that a careless or hurried model could send, and the tools refuse them.

Commands only run in `edit`, and only the fixed test command, through course/sandbox.py: without a container the
restricted runner is NOT isolated, so every run goes past a human first. Every text that reaches the model or an
event is in locales/, one catalog per run language.
"""
import json
from pathlib import Path
from typing import Literal

from course.execution import LessonInputs, RunContext
from course.sandbox import CommandPolicy, Workspace, default_approval_mode, run_guarded, select_runner
from lessons.lesson_file_edit_evidence.evidence import symbol_changes, unittest_summary, verify_chain
from lessons.lesson_file_edit_evidence.file_tools import FileTools, split_lines
from lessons.lesson_file_edit_evidence.locales import Texts, texts_for

FIXTURE = Path(__file__).parent / "fixture_repo"
TEST_COMMAND = "python -m unittest discover -s tests"
PROTECTED = ("tests/*",)
# The task contract: which file and which functions the change may touch.
TASK_FILES = ("shop/pricing.py",)
TASK_SYMBOLS = ("discount_rate", "shipping")
WRITE_TOOLS = {"rewrite": "write_file", "replace": "edit_file", "lines": "edit_lines"}
MAX_ROUNDS = 10
CASES = ("read_first", "path_scope", "not_unique", "line_drift", "stale")
# Why a command that never ran did not run: these results say nothing about the code.
NOT_RUN = ("policy_denied", "approval_rejected", "approval_timeout", "approval_unavailable", "cancelled",
           "spawn_failed")


class Inputs(LessonInputs):
    scenario: Literal["edit", "guards"] = "edit"
    # scenario=edit: which write tool the model gets.
    strategy: Literal["rewrite", "replace", "lines"] = "replace"
    # scenario=guards: one case, or all five in a row.
    case: Literal["all", "read_first", "path_scope", "not_unique", "line_drift", "stale"] = "all"


INPUT_MODEL = Inputs


def tool_definitions(t: Texts, names: list[str]) -> list[dict]:
    """Tool definitions in the run's language; names and parameter names are code and stay the same."""
    def string(description):
        return {"type": "string", "description": description}

    def integer(description):
        return {"type": "integer", "description": description}

    specs = {
        "read_file": (t.desc_read_file, {"path": string(t.param_path), "start_line": integer(t.param_start_line),
                                         "end_line": integer(t.param_end_line)}, ["path"]),
        "write_file": (t.desc_write_file, {"path": string(t.param_path), "content": string(t.param_content)},
                       ["path", "content"]),
        "edit_file": (t.desc_edit_file, {"path": string(t.param_path), "old": string(t.param_old),
                                         "new": string(t.param_new)}, ["path", "old", "new"]),
        "edit_lines": (t.desc_edit_lines, {"path": string(t.param_path), "start_line": integer(t.param_first_line),
                                           "end_line": integer(t.param_last_line),
                                           "new_text": string(t.param_new_text)},
                       ["path", "start_line", "end_line", "new_text"]),
        "run_tests": (t.desc_run_tests, {}, []),
    }
    return [{"type": "function", "function": {
        "name": name, "description": specs[name][0],
        "parameters": {"type": "object", "properties": specs[name][1], "required": specs[name][2],
                       "additionalProperties": False}}} for name in names]


def read(path: Path) -> str:
    """Exact text of a file: no newline translation, so what the tools hashed is what the lesson compares."""
    return path.read_bytes().decode("utf-8")


def emit_change(context: RunContext):
    """The journal row of each write goes out as an event the moment the tool writes it."""
    return lambda row: context.emit("lesson.file_change", row)


# ---------- scenario: edit ----------

class Meter:
    """What the model calls cost, counted from the recorded calls and results; usage only as the provider reported it."""

    def __init__(self, write_tool: str):
        self.write_tool = write_tool
        self.model_calls = 0
        self.usage: list[dict | None] = []
        self.calls: list[dict] = []

    def add_response(self, response: dict):
        self.model_calls += 1
        usage = response.get("usage")
        self.usage.append(usage if isinstance(usage, dict) else None)

    def add_call(self, call: dict, result: dict):
        self.calls.append({"name": call["function"]["name"], "ok": result.get("ok") is True,
                           "argument_chars": len(call["function"].get("arguments") or ""),
                           "result_chars": len(json.dumps(result, ensure_ascii=False))})

    def count(self, name: str, *, ok: bool | None = None) -> int:
        return sum(1 for call in self.calls if call["name"] == name and (ok is None or call["ok"] is ok))

    def chars(self, key: str, name: str | None = None) -> int:
        return sum(call[key] for call in self.calls if name is None or call["name"] == name)

    def tokens(self, field: str):
        """Sum of what the provider reported; None when it reported nothing, never an estimate."""
        reported = [usage[field] for usage in self.usage if usage and isinstance(usage.get(field), int)]
        return (sum(reported), len(self.usage) - len(reported)) if reported else None

    def last_write_then_tests(self) -> bool:
        """Did the model run the tests after its last accepted write?"""
        last_write = max((index for index, call in enumerate(self.calls)
                          if call["name"] == self.write_tool and call["ok"]), default=-1)
        return last_write >= 0 and any(call["name"] == "run_tests" for call in self.calls[last_write + 1:])


def task_tree(workspace: Workspace, t: Texts) -> str:
    lines = []
    for path in sorted(workspace.snapshot().hashes):
        text = read(workspace.root / path)
        lines.append(t.tree_line.format(path=path, lines=len(split_lines(text))))
    return "\n".join(lines)


def agent_loop(context: RunContext, t: Texts, workspace: Workspace, tools: list[dict], available: dict,
               meter: Meter) -> tuple[str, str]:
    """The tool-call loop of course/runner.py, with two differences: it keeps a meter and it ends with a stop reason
    instead of an exception, so a run that used up its rounds still gets its evidence report."""
    messages = [{"role": "system", "content": t.system_prompt},
                {"role": "user", "content": t.task.format(tree=task_tree(workspace, t), command=TEST_COMMAND)}]
    for round_number in range(1, MAX_ROUNDS + 1):
        response = context.complete({"messages": messages, "tools": tools, "tool_choice": "auto"}, round_number)
        meter.add_response(response)
        message = response["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        if not calls:
            return "answered", message.get("content") or ""
        messages.append(message)
        for call in calls:
            result = context.execute_proposal(call, available)
            meter.add_call(call, result)
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    return "rounds", ""


def run_edit(context: RunContext, t: Texts, values: dict) -> str:
    strategy = values["strategy"]
    write_tool = WRITE_TOOLS[strategy]
    with Workspace(FIXTURE) as workspace:
        before_texts = {path: read(workspace.root / path) for path in TASK_FILES}
        # Offline tests must not depend on whether this machine has a container engine: they always take the
        # restricted runner, so the approval step is part of every deterministic run.
        runner, status = select_runner(workspace, prefer="restricted" if context.mode == "offline" else "auto",
                                       timeout=30)
        policy, mode = CommandPolicy.for_runner(runner), default_approval_mode(runner)
        context.emit("lesson.sandbox", {
            "backend": runner.backend, "isolated": runner.isolated, "approval": mode,
            "container": status.reason, "command": TEST_COMMAND,
            "label": t.label_isolated if runner.isolated else t.label_unisolated})
        context.emit("lesson.task_card", t.task_card)

        def guarded(purpose: str, timeout: float) -> dict:
            def approve(request):
                changed = [{"path": change.path, "status": change.status} for change in workspace.changes()]
                payload = {**request.to_dict(), "tool": purpose, "changed_files": changed}
                summary = (t.approve_tests if purpose == "run_tests" else t.approve_acceptance).format(
                    command=request.command, label=t.label_unisolated, files=len(changed))
                return context.request_approval("command", summary, payload, timeout_s=300, risk="high")
            result = run_guarded(TEST_COMMAND, runner=runner, policy=policy, approve=approve, timeout=timeout,
                                 should_stop=context.cancelled, check_cancelled=context.check_cancelled)
            return result.to_dict(messages=t.sandbox_errors)

        def run_tests() -> dict:
            data = guarded("run_tests", 30)
            # The model sees the command's own words and the result codes; timings stay out of its context.
            return {key: data[key] for key in ("ok", "exit_code", "stdout", "stderr", "truncated", "timed_out",
                                               "error_type", "error")}

        file_tools = FileTools(workspace, t, protected=PROTECTED, record=emit_change(context))
        meter = Meter(write_tool)
        available = {"read_file": file_tools.read_file, write_tool: getattr(file_tools, write_tool),
                     "run_tests": run_tests}
        stop, claim = agent_loop(context, t, workspace, tool_definitions(t, list(available)), available, meter)
        # The platform's own run: a command of the platform, but it still executes code the model edited, so it
        # goes past the same human as the model's own test runs.
        context.check_cancelled()
        verdict = guarded("acceptance", 60)
        return _report_edit(context, t, strategy, workspace, file_tools, meter, verdict, stop, claim, runner,
                            before_texts)


def _short(digest: str | None) -> str:
    return digest[:12] if digest else "—"


def _report_edit(context, t: Texts, strategy: str, workspace: Workspace, file_tools: FileTools, meter: Meter,
                 verdict: dict, stop: str, claim: str, runner, before_texts: dict[str, str]) -> str:
    snapshot = workspace.snapshot()
    changes = workspace.changes(snapshot)
    chain = verify_chain(file_tools.journal, workspace.baseline.hashes, snapshot.hashes)
    tampered = workspace.protected_changes(PROTECTED, snapshot)
    written = [row for row in file_tools.journal if row["ok"] and row["changed"]]
    rejected = [row for row in file_tools.journal if not row["ok"]]
    added, removed = sum(row["added"] for row in written), sum(row["removed"] for row in written)
    # 1. Which files and which functions changed, from the files themselves.
    outside = [change.path for change in changes if change.path not in TASK_FILES]
    touched, unexpected, unparsable = [], [], False
    for path in TASK_FILES:
        if any(change.path == path for change in changes):
            current = read(workspace.root / path) if (workspace.root / path).exists() else ""
            found = symbol_changes(before_texts[path], current)
            if found is None:
                unparsable = True
                continue
            touched += found["changed"] + found["removed"] + found["added"]
            # A function the task does not name must not change or vanish; a helper the model adds is allowed.
            unexpected += [name for name in found["changed"] + found["removed"] if name not in TASK_SYMBOLS]
    scope_ok = not outside and not unexpected and not unparsable
    # 2. The platform's own test run: a command that never ran says nothing about the code.
    ran = verdict.get("error_type") not in NOT_RUN
    summary = unittest_summary((verdict.get("stderr") or "") + (verdict.get("stdout") or "")) if ran else {}
    tests = {"id": "tests_pass", "label": t.check_tests}
    if ran:
        tests["passed"] = bool(verdict.get("ok"))
        # unittest words it as "FAILED (failures=2)"; keep its own wording in both run languages.
        outcome = (summary["outcome"] or "?") + (f" ({summary['detail']})" if summary["detail"] else "")
        tests["detail"] = t.check_tests_detail.format(ran=summary["ran"] if summary["ran"] is not None else "?",
                                                      outcome=outcome)
    else:
        tests["detail"] = t.check_tests_not_run.format(reason=verdict.get("error") or verdict.get("error_type"))
    chain_text = t.separator.join(f"{item['path']}: {t.chain_reasons[item['reason']]}" for item in chain)
    final_pricing = snapshot.hashes.get(TASK_FILES[0])
    base_pricing = workspace.baseline.hashes.get(TASK_FILES[0])
    context.emit("lesson.report", {
        "title": t.edit_titles[strategy],
        "summary": t.edit_summary,
        "checks": [
            tests,
            {"id": "tests_untouched", "label": t.check_untouched, "passed": not tampered,
             "detail": t.check_untouched_detail.format(files=t.separator.join(c.path for c in tampered) or t.value_none)},
            {"id": "scope", "label": t.check_scope, "passed": scope_ok,
             "detail": (t.check_scope_unparsable if unparsable else t.check_scope_detail).format(
                 files=t.separator.join(c.path for c in changes) or t.value_none,
                 symbols=t.separator.join(sorted(set(touched))) or t.value_none,
                 unexpected=t.separator.join(sorted(set(unexpected)) + outside) or t.value_none)},
            {"id": "evidence_chain", "label": t.check_chain, "passed": not chain,
             "detail": t.check_chain_ok.format(rows=len(written)) if not chain
             else t.check_chain_broken.format(problems=chain_text)},
        ],
        "metrics": [
            {"id": "environment", "label": t.label_environment,
             "value": t.environment_text.format(label=t.label_isolated if runner.isolated else t.label_unisolated,
                                                approval=t.approvals[default_approval_mode(runner)])},
            {"id": "model_calls", "label": t.label_model_calls, "value": meter.model_calls},
            {"id": "write_calls", "label": t.label_write_calls.format(tool=meter.write_tool),
             "value": t.write_calls_value.format(ok=meter.count(meter.write_tool, ok=True),
                                                 rejected=meter.count(meter.write_tool, ok=False))},
            {"id": "read_calls", "label": t.label_read_calls, "value": meter.count("read_file")},
            {"id": "test_runs", "label": t.label_test_runs, "value": meter.count("run_tests")},
            {"id": "write_arg_chars", "label": t.label_write_chars, "value": meter.chars("argument_chars", meter.write_tool)},
            {"id": "result_chars", "label": t.label_result_chars, "value": meter.chars("result_chars")},
            {"id": "completion_tokens", "label": t.label_completion_tokens, "value": _tokens(t, meter, "completion_tokens")},
            {"id": "total_tokens", "label": t.label_total_tokens, "value": _tokens(t, meter, "total_tokens")},
            {"id": "lines_changed", "label": t.label_lines, "value": t.lines_value.format(added=added, removed=removed)},
            {"id": "self_check", "label": t.label_self_check,
             "value": t.value_yes if meter.last_write_then_tests() else t.value_no},
            {"id": "base_sha256", "label": t.label_base_hash.format(path=TASK_FILES[0]), "value": _short(base_pricing)},
            {"id": "final_sha256", "label": t.label_final_hash.format(path=TASK_FILES[0]), "value": _short(final_pricing)},
            {"id": "diff", "label": t.label_diff, "value": workspace.diff() or t.value_none},
            {"id": "note", "label": t.label_note, "value": context.question or t.value_none},
        ],
        "table": {"columns": list(t.journal_columns), "rows": [_journal_row(t, row) for row in file_tools.journal]},
    })
    verdict_line = (t.verdict_ok if verdict.get("ok") else t.verdict_failed) if ran else t.verdict_not_run
    if stop == "rounds":
        claim_line = t.claim_rounds.format(limit=MAX_ROUNDS)
    else:
        claim_line = t.claim_quote.format(claim=claim.strip() or t.value_none)
    return t.edit_answer.format(strategy=t.strategies[strategy], writes=len(written), rejected=len(rejected),
                                files=len(changes), added=added, removed=removed, tests=verdict_line,
                                chain=t.chain_ok if not chain else t.chain_broken, claim=claim_line)


def _tokens(t: Texts, meter: Meter, field: str):
    found = meter.tokens(field)
    if found is None:
        return t.value_not_reported
    total, missing = found
    return total if not missing else t.tokens_partly_reported.format(total=total, missing=missing)


def _journal_row(t: Texts, row: dict) -> list:
    if row["ok"]:
        outcome = t.outcome_written if row["changed"] else t.outcome_unchanged
    else:
        outcome = row["error_type"]
    return [row["seq"], row["tool"], row["path"], outcome, _short(row["before_sha256"]),
            _short(row["after_sha256"]), f"+{row['added']} / -{row['removed']}"]


# ---------- scenario: guards ----------

class Scenario:
    """One case: calls submitted by the runner (not the model), each with the outcome the lesson declares for it."""

    def __init__(self, context: RunContext, t: Texts, workspace: Workspace, tools: FileTools, case: str,
                 round_number: int):
        self.context, self.t, self.workspace, self.tools, self.case = context, t, workspace, tools, case
        self.round = round_number
        self.steps: list[dict] = []
        self.extras: list[tuple[str, bool]] = []

    def call(self, name: str, arguments: dict, expect: str = "ok") -> dict:
        before = self.workspace.snapshot().hashes
        result = self.context.call_tool(name, arguments, self.tools.tools(), self.round)
        actual = "ok" if result["ok"] else result["error_type"]
        unchanged = self.workspace.snapshot().hashes == before
        self.steps.append({"case": self.t.cases[self.case], "tool": name, "path": arguments.get("path", "—"),
                           "expect": expect, "actual": actual, "unchanged": unchanged,
                           # A refused call must leave every file as it was; an accepted one is not judged on it.
                           "passed": actual == expect and (unchanged or actual == "ok")})
        return result

    def text(self, path: str) -> str:
        return read(self.workspace.root / path)


def locate(text: str, needle: str) -> int:
    """1-based number of the first line that contains ``needle``: the cases find their lines, they never hard-code them."""
    return next(number for number, line in enumerate(split_lines(text), 1) if needle in line)


def case_read_first(s: Scenario):
    path = "shop/pricing.py"
    whole = s.text(path)
    s.call("edit_file", {"path": path, "old": "if amount > FREE_SHIPPING_FROM:",
                         "new": "if amount >= FREE_SHIPPING_FROM:"}, "NotReadYet")
    s.call("write_file", {"path": path, "content": ""}, "NotReadYet")
    s.call("read_file", {"path": path, "start_line": 1, "end_line": 10})
    s.call("write_file", {"path": path, "content": whole}, "PartialRead")


def case_path_scope(s: Scenario):
    s.call("read_file", {"path": "../outside.txt"}, "PathOutsideWorkspace")
    s.call("read_file", {"path": "/etc/passwd"}, "PathOutsideWorkspace")
    s.call("write_file", {"path": "../escape.txt", "content": "x"}, "PathOutsideWorkspace")
    s.extras.append(("escape_absent", not (s.workspace.base / "escape.txt").exists()))
    s.call("read_file", {"path": "tests/test_pricing.py"})
    # The cheat a hurried agent might try: make the failing expectation say what the code does.
    s.call("edit_file", {"path": "tests/test_pricing.py", "old": "self.assertEqual(shipping(50.0), 0.0)",
                         "new": "self.assertEqual(shipping(50.0), 4.5)"}, "ProtectedPath")


def case_not_unique(s: Scenario):
    path = "shop/pricing.py"
    s.call("read_file", {"path": path})
    s.call("edit_file", {"path": path, "old": "return 0.0", "new": "return 0.5"}, "OldStringNotUnique")
    s.call("edit_file", {"path": path, "old": "return 0.7", "new": "return 0.5"}, "OldStringNotFound")
    s.call("edit_file", {"path": path, "old": "if amount > FREE_SHIPPING_FROM:",
                         "new": "if amount >= FREE_SHIPPING_FROM:"})


def case_line_drift(s: Scenario):
    path = "shop/pricing.py"
    s.call("read_file", {"path": path})
    original = s.text(path)
    tier, shipping = locate(original, "if amount >= 200:"), locate(original, "if amount > FREE_SHIPPING_FROM:")
    shipping_line = split_lines(original)[shipping - 1]
    s.call("edit_lines", {"path": path, "start_line": tier, "end_line": tier + 1,
                          "new_text": "    if amount >= 300:\n        return 0.20\n    if amount >= 200:\n        return 0.15"})
    # The second edit still uses the numbers of the first read: after the first edit they point two lines too high.
    s.extras.append(("numbers_shifted", split_lines(s.text(path))[shipping - 1] != shipping_line))
    s.call("edit_lines", {"path": path, "start_line": shipping, "end_line": shipping,
                          "new_text": "    if amount >= FREE_SHIPPING_FROM:"}, "LineNumbersStale")
    s.call("read_file", {"path": path})
    s.call("edit_lines", {"path": path, "start_line": locate(s.text(path), "if amount > FREE_SHIPPING_FROM:"),
                          "end_line": locate(s.text(path), "if amount > FREE_SHIPPING_FROM:"),
                          "new_text": "    if amount >= FREE_SHIPPING_FROM:"})


def case_stale(s: Scenario):
    path = "shop/report.py"
    old = '"""One line per charge, ending with the total the customer pays."""'
    new = '"""One line per charge; the last line is the total the customer pays."""'
    s.call("read_file", {"path": path})
    # The runner plays "another process": it writes the file directly, past the tools. The event says so.
    target = s.workspace.resolve(path)
    before = s.workspace.snapshot().hashes[path]
    target.write_bytes((s.text(path) + "# edited elsewhere\n").encode("utf-8"))
    after = s.workspace.snapshot().hashes[path]
    s.context.emit("lesson.external_change", {"path": path, "before_sha256": before, "after_sha256": after,
                                              "by": "course_program", "simulated": True,
                                              "note": s.t.external_note}, s.round)
    s.call("edit_file", {"path": path, "old": old, "new": new}, "StaleRead")
    s.call("read_file", {"path": path})
    s.call("edit_file", {"path": path, "old": old, "new": new})
    s.extras.append(("external_kept", "# edited elsewhere" in s.text(path)))


CASE_FUNCTIONS = {"read_first": case_read_first, "path_scope": case_path_scope, "not_unique": case_not_unique,
                  "line_drift": case_line_drift, "stale": case_stale}


def run_guards(context: RunContext, t: Texts, values: dict) -> str:
    names = CASES if values["case"] == "all" else (values["case"],)
    steps, checks, journal_rows, applied = [], [], 0, 0
    for number, name in enumerate(names, start=1):
        context.check_cancelled()
        # A fresh workspace per case, so one case's edits never explain another case's evidence.
        with Workspace(FIXTURE) as workspace:
            file_tools = FileTools(workspace, t, protected=PROTECTED, record=emit_change(context))
            scenario = Scenario(context, t, workspace, file_tools, name, number)
            CASE_FUNCTIONS[name](scenario)
            chain = verify_chain(file_tools.journal, workspace.baseline.hashes, workspace.snapshot().hashes)
            # Only the stale case may break the chain, and it must break it exactly once, at the file the runner
            # changed behind the tools' back; everywhere else the chain must close.
            expected = [("shop/report.py", "broken_chain")] if name == "stale" else []
            scenario.extras.append(("chain", [(item["path"], item["reason"]) for item in chain] == expected))
        steps += scenario.steps
        journal_rows += len(file_tools.journal)
        applied += sum(1 for row in file_tools.journal if row["ok"] and row["changed"])
        extras = dict(scenario.extras)
        matched = sum(1 for step in scenario.steps if step["passed"])
        checks.append({"id": f"case_{name}", "label": t.case_titles[name],
                       "passed": matched == len(scenario.steps) and all(extras.values()),
                       "detail": t.case_detail.format(steps=len(scenario.steps), matched=matched,
                                                      extras=t.separator.join(t.extras[key] + (t.mark_ok if ok else t.mark_bad)
                                                                              for key, ok in scenario.extras))})
    rejected = sum(1 for step in steps if step["actual"] != "ok")
    context.emit("lesson.report", {
        "title": t.guards_title,
        "summary": t.guards_summary,
        "checks": checks,
        "metrics": [{"id": "tool_calls", "label": t.label_tool_calls, "value": len(steps)},
                    {"id": "rejected", "label": t.label_rejected, "value": rejected},
                    {"id": "writes_applied", "label": t.label_writes_applied, "value": applied},
                    {"id": "commands_run", "label": t.label_commands_run, "value": 0},
                    {"id": "model_calls", "label": t.label_model_calls, "value": 0},
                    {"id": "note", "label": t.label_note, "value": context.question or t.value_none}],
        "table": {"columns": list(t.guards_columns),
                  "rows": [[step["case"], step["tool"], step["path"], step["expect"], step["actual"],
                            t.value_yes if step["unchanged"] else t.value_no] for step in steps]},
    })
    return t.guards_answer.format(cases=len(names), calls=len(steps), rejected=rejected)


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs).model_dump()
    context.check_cancelled()
    return run_edit(context, t, values) if values["scenario"] == "edit" else run_guards(context, t, values)
