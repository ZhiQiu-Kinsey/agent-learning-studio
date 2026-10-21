"""Behavior tests for bash-coding-agent: scripted model data, real commands in a real workspace copy.

Nothing here talks to a model. The "model" follows a script and the approvals come from a stand-in
policy (decided_by: offline_fixture); the commands the script proposes really run in a throwaway
copy of fixture_repo through course/sandbox.py, so policy, approval, timeout, truncation, process
cleanup and the platform's acceptance are all exercised for real. POSIX-only checks are skipped on Windows.
"""
import json
import os
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from course.sandbox import BackendStatus, CommandResult, ContainerRunner, RestrictedRunner, Workspace
from lessons.lesson_bash_coding_agent import runtime
from lessons.lesson_bash_coding_agent.fixtures import FIX, RUN_TESTS, create_approval_policy, create_completion
from lessons.lesson_bash_coding_agent.locales import texts_for
from server.offline import tool_call

ZH = texts_for("zh-CN")
EN = texts_for("en")
APPROVE = lambda request: {"decision": "approve"}  # noqa: E731 - a stand-in for the learner


def reply(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}


def scripted(commands, claim="done"):
    """A model that proposes `commands` one by one and then replies `claim`."""
    def complete(body, api_key):
        step = sum(1 for message in body["messages"] if message["role"] == "tool")
        if step >= len(commands):
            return reply(claim)
        message = {"role": "assistant", "content": None, "tool_calls": [tool_call("bash", {"command": commands[step]}, step + 1)]}
        return {"choices": [{"message": message, "finish_reason": "tool_calls"}]}
    return complete


def run_case(exercise_id, inputs, completion=None, approval=None, budget=12, cancelled=lambda: False,
             locale="zh-CN", mode="offline"):
    events, workspaces = [], []

    class Recorded(Workspace):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            workspaces.append(self)

    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="bash-coding-agent", exercise_id=exercise_id, question="", mode=mode, model="fixture-model",
        representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
        approval_policy=approval or create_approval_policy(exercise_id, values, locale),
    )
    with patch.object(runtime, "Workspace", Recorded):
        try:
            answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
        finally:
            run_case.workspaces = workspaces
            run_case.events = events
    return answer, events


def process_is_running(pid):
    """True while the process exists and is not a zombie (a killed child nobody has reaped yet is already dead)."""
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
            return handle.read().rsplit(") ", 1)[1][0] != "Z"
    except FileNotFoundError:
        return False
    except OSError:
        pass  # no /proc here (macOS): fall back to signal 0
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def results(events):
    """The bash results (the dict inside tool_result) in order."""
    return [data["result"]["result"] for data in of(events, "tool_result")]


def report(events, title_key, locale="zh-CN"):
    """The lesson.report whose first metric or check id matches title_key's marker id."""
    marker = {"environment": "backend", "ledger": "commands", "acceptance": "tests-run"}[title_key]
    for data in of(events, "lesson.report"):
        if any(item.get("id") == marker for item in data.get("metrics", [])):
            return data
    raise AssertionError(f"no {title_key} report")


def item(data, kind, item_id):
    return next(entry for entry in data[kind] if entry["id"] == item_id)


class InputTests(unittest.TestCase):
    def test_defaults_and_bounds(self):
        values = validate_inputs(runtime, {})
        self.assertEqual(values, {"task": "fix_test", "command_timeout_s": 20})
        for bad in ({"task": "rm_rf"}, {"command_timeout_s": 1}, {"command_timeout_s": 61}, {"unknown": 1},
                    {"command_timeout_s": "x"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)

    def test_every_task_has_text_in_both_languages(self):
        for texts in (ZH, EN):
            self.assertEqual(set(texts.tasks), {"fix_test", "get_green", "outside_doc", "slow_check"})
        self.assertEqual(set(ZH.sandbox_errors), set(EN.sandbox_errors))


class FixtureRepoTests(unittest.TestCase):
    """The fixture is what the lesson promises: one failing test, and a one-line fix that makes all of them pass."""

    def test_the_fixture_fails_until_the_fix_is_applied(self):
        with Workspace(runtime.FIXTURE) as workspace:
            runner = RestrictedRunner(workspace, timeout=20)
            before = runner.run(RUN_TESTS)
            self.assertEqual((before.ok, before.exit_code), (False, 1))
            self.assertIn("FAILED (failures=1)", before.stderr)
            self.assertEqual(runtime._tests_summary(before), (7, 1))
            fixed = runner.run(FIX)
            self.assertTrue(fixed.ok, fixed.stderr)
            after = runner.run(RUN_TESTS)
            self.assertTrue(after.ok, after.stderr)
            self.assertEqual(runtime._tests_summary(after), (7, 0))
            self.assertEqual([change.path for change in workspace.changes()], ["gradebook/grades.py"])

    def test_the_summary_reads_failures_and_errors(self):
        make = lambda stderr: SimpleNamespace(stderr=stderr, stdout="")  # noqa: E731
        self.assertEqual(runtime._tests_summary(make("Ran 7 tests in 0.1s\n\nFAILED (failures=2, errors=1)")), (7, 3))
        self.assertEqual(runtime._tests_summary(make("Ran 1 test in 0.0s\n\nOK")), (1, 0))
        self.assertEqual(runtime._tests_summary(make("Traceback...")), (None, None))


class FixAndAcceptTests(unittest.TestCase):
    def test_fixing_the_source_is_accepted_in_both_languages(self):
        for locale in ("zh-CN", "en"):
            texts = texts_for(locale)
            with self.subTest(locale=locale):
                answer, events = run_case("fix-test", {"task": "fix_test"}, locale=locale)
                commands = [data["command"] for data in results(events)]
                self.assertEqual(commands[0], RUN_TESTS)
                self.assertEqual(commands[-1], RUN_TESTS)
                first = results(events)[0]
                self.assertEqual((first["ok"], first["exit_code"], first["error_type"]), (False, 1, "nonzero_exit"))
                self.assertEqual(first["error"], texts.sandbox_errors["nonzero_exit"].format(exit_code=1))
                self.assertTrue(results(events)[-1]["ok"])
                acceptance = report(events, "acceptance")
                self.assertTrue(item(acceptance, "checks", "tests-pass")["passed"])
                self.assertTrue(item(acceptance, "checks", "tests-untouched")["passed"])
                self.assertTrue(item(acceptance, "checks", "accepted")["passed"])
                self.assertIn("score >= 90", item(acceptance, "metrics", "diff")["value"])
                self.assertEqual(item(acceptance, "metrics", "changed-files")["value"], 1)
                self.assertEqual(item(acceptance, "metrics", "tests-run")["value"], 7)
                self.assertTrue(answer.startswith(texts.answer_accepted))
                self.assertIn(texts.script_claims["fix_test"], answer)

    def test_event_order_is_call_then_approval_then_result(self):
        _, events = run_case("fix-test", {"task": "fix_test"})
        kinds = [kind for kind, _, _ in events]
        calls = [index for index, kind in enumerate(kinds) if kind == "tool_call"]
        self.assertEqual(len(calls), 4)
        for index in calls:
            self.assertEqual(kinds[index:index + 4], ["tool_call", "approval_requested", "approval_resolved", "tool_result"])
        approvals = of(events, "approval_requested")
        self.assertEqual([data["kind"] for data in approvals], ["command"] * 4 + ["acceptance"])
        for data in approvals:
            self.assertEqual((data["payload"]["isolated"], data["payload"]["backend"], data["payload"]["cwd"]),
                             (False, "restricted", "<workspace>"))
            self.assertEqual(data["risk"], "high")
        self.assertTrue(all(data["decided_by"] == "offline_fixture" for data in of(events, "approval_resolved")))
        # The acceptance asks last, after the model's last response.
        self.assertLess(max(index for index, kind in enumerate(kinds) if kind == "response"),
                        max(index for index, kind in enumerate(kinds) if kind == "approval_requested"))
        self.assertEqual(of(events, "request")[0]["body"]["tools"][0]["function"]["name"], "bash")

    def test_results_are_the_facts_of_each_command(self):
        _, events = run_case("fix-test", {"task": "fix_test"})
        for record in results(events):
            self.assertEqual((record["cwd"], record["isolated"], record["backend"]), ("<workspace>", False, "restricted"))
            self.assertEqual(record["policy"]["action"], "allow")
            self.assertEqual(record["approval"]["outcome"], "approved")
            self.assertIsInstance(record["duration_ms"], int)
            self.assertNotIn("omitted_bytes", record)
        # The model gets exactly this record back as the tool message.
        second = of(events, "request")[1]["body"]["messages"][-1]
        self.assertEqual(second["role"], "tool")
        self.assertEqual(json.loads(second["content"])["result"]["command"], RUN_TESTS)

    def test_the_workspace_is_a_copy_that_is_removed_afterwards(self):
        source_before = (runtime.FIXTURE / "gradebook" / "grades.py").read_bytes()
        _, events = run_case("fix-test", {"task": "fix_test"})
        self.assertEqual((runtime.FIXTURE / "gradebook" / "grades.py").read_bytes(), source_before)
        workspace = run_case.workspaces[0]
        self.assertTrue(workspace.closed)
        self.assertFalse(workspace.base.exists())
        text = json.dumps(events, ensure_ascii=False)
        self.assertNotIn(str(workspace.base), text)
        self.assertNotIn(str(runtime.FIXTURE), text)


class TamperTests(unittest.TestCase):
    def test_green_tests_on_edited_tests_are_not_accepted(self):
        for locale in ("zh-CN", "en"):
            texts = texts_for(locale)
            with self.subTest(locale=locale):
                answer, events = run_case("tamper", {"task": "get_green"}, locale=locale)
                self.assertTrue(results(events)[-1]["ok"])  # the agent's own test run is green
                acceptance = report(events, "acceptance")
                self.assertTrue(item(acceptance, "checks", "tests-pass")["passed"])
                untouched = item(acceptance, "checks", "tests-untouched")
                self.assertFalse(untouched["passed"])
                self.assertIn("tests/test_grades.py", untouched["detail"])
                self.assertFalse(item(acceptance, "checks", "accepted")["passed"])
                self.assertIn("tests/test_grades.py", item(acceptance, "metrics", "diff")["value"])
                self.assertEqual(acceptance["table"]["rows"], [["tests/test_grades.py", "modified", texts.value_yes]])
                self.assertTrue(answer.startswith(texts.answer_tampered.format(files="tests/test_grades.py")))

    def test_adding_or_deleting_a_test_counts_as_touching_the_tests(self):
        for command, status in (("python -c \"open('tests/test_extra.py', 'w').write('')\"", "added"),
                                ("python -c \"import os; os.remove('tests/test_report.py')\"", "removed")):
            with self.subTest(status=status):
                answer, events = run_case("tamper", {"task": "get_green"}, completion=scripted([command]), approval=APPROVE)
                acceptance = report(events, "acceptance")
                self.assertEqual(acceptance["table"]["rows"][0][1], status)
                self.assertFalse(item(acceptance, "checks", "accepted")["passed"])

    def test_the_tests_still_failing_is_a_different_verdict(self):
        answer, events = run_case("fix-test", {"task": "fix_test"}, completion=scripted([]), approval=APPROVE)
        acceptance = report(events, "acceptance")
        self.assertFalse(item(acceptance, "checks", "tests-pass")["passed"])
        self.assertTrue(item(acceptance, "checks", "tests-untouched")["passed"])
        self.assertIn("1", item(acceptance, "checks", "tests-pass")["detail"])
        self.assertTrue(answer.startswith(ZH.answer_tests_failed))
        self.assertEqual(item(acceptance, "metrics", "diff")["value"], ZH.value_no_diff)

    def test_an_edit_to_the_source_that_is_not_a_fix_is_not_accepted(self):
        command = "python -c \"import pathlib; p = pathlib.Path('gradebook/grades.py'); p.write_text('')\""
        answer, events = run_case("fix-test", {"task": "fix_test"}, completion=scripted([command]), approval=APPROVE)
        self.assertFalse(item(report(events, "acceptance"), "checks", "tests-pass")["passed"])
        self.assertTrue(answer.startswith(ZH.answer_tests_failed))


class PolicyAndApprovalTests(unittest.TestCase):
    def test_a_path_outside_the_project_is_refused_before_any_approval(self):
        for locale in ("zh-CN", "en"):
            texts = texts_for(locale)
            with self.subTest(locale=locale):
                answer, events = run_case("outside-doc", {"task": "outside_doc"}, locale=locale)
                first = results(events)[0]
                self.assertEqual((first["ok"], first["exit_code"], first["error_type"]), (False, None, "policy_denied"))
                self.assertEqual(first["policy"]["rule"], "parent_traversal")
                self.assertEqual(first["detail"]["matched"], "..")
                self.assertIsNone(first["approval"])
                self.assertEqual(first["error"], texts.sandbox_errors["policy_denied:parent_traversal"].format(matched=".."))
                # Refused by the policy: no approval was asked for that command. The four that passed, plus the
                # acceptance, make as many approvals as there are commands.
                self.assertEqual(len(results(events)), 5)
                self.assertEqual(len(of(events, "approval_requested")), 5)
                # What the model sees next is this same structured refusal.
                tool_message = of(events, "request")[1]["body"]["messages"][-1]
                self.assertEqual(json.loads(tool_message["content"])["result"]["error_type"], "policy_denied")

    def test_a_rejected_command_does_not_run_and_the_note_reaches_the_model(self):
        ran_marker = "python -c \"import pathlib; pathlib.Path('ran.txt').write_text('x')\""
        calls = []

        def policy(request):
            calls.append(request["payload"]["command"])
            return {"decision": "reject", "note": "no"} if "ran.txt" in request["payload"]["command"] else {"decision": "approve"}

        answer, events = run_case("fix-test", {"task": "fix_test"}, completion=scripted([ran_marker, RUN_TESTS]), approval=policy)
        rejected = results(events)[0]
        self.assertEqual((rejected["error_type"], rejected["exit_code"], rejected["approval"]["approved"]),
                         ("approval_rejected", None, False))
        self.assertEqual(rejected["detail"], {"note": "no"})
        self.assertIn("no", rejected["error"])
        resolved = of(events, "approval_resolved")[0]
        self.assertEqual((resolved["outcome"], resolved["decided_by"], resolved["note"]), ("rejected", "offline_fixture", "no"))
        # The workspace is untouched: the command never started.
        self.assertEqual(report(events, "acceptance")["table"]["rows"], [])
        self.assertEqual(item(report(events, "acceptance"), "metrics", "changed-files")["value"], 0)
        self.assertEqual(item(report(events, "ledger"), "metrics", "approval-refused")["value"], 1)

    def test_a_rejection_without_a_note_says_so(self):
        _, events = run_case("fix-test", {"task": "fix_test"}, completion=scripted([RUN_TESTS]),
                             approval=lambda request: {"decision": "reject"})
        self.assertEqual(results(events)[0]["error"], ZH.approval_rejected_no_note)

    def test_nobody_deciding_is_its_own_outcome(self):
        _, events = run_case("fix-test", {"task": "fix_test"}, completion=scripted([RUN_TESTS]),
                             approval=lambda request: {"decision": "timeout"})
        record = results(events)[0]
        self.assertEqual((record["error_type"], record["exit_code"]), ("approval_timeout", None))
        self.assertEqual(of(events, "approval_resolved")[0]["decided_by"], "timeout")
        self.assertEqual(report(events, "ledger")["table"]["rows"][0][3], ZH.cell_approval_timeout)

    def test_when_the_acceptance_is_refused_the_verdict_is_not_completed_not_failed(self):
        def policy(request):
            return {"decision": "reject"} if request["kind"] == "acceptance" else {"decision": "approve"}

        answer, events = run_case("fix-test", {"task": "fix_test"}, approval=policy)
        acceptance = report(events, "acceptance")
        tests = item(acceptance, "checks", "tests-pass")
        self.assertNotIn("passed", tests)  # a check that never ran carries no verdict
        self.assertIn(ZH.reason_approval_refused, tests["detail"])
        self.assertFalse(item(acceptance, "checks", "accepted")["passed"])
        self.assertTrue(answer.startswith(ZH.answer_not_run.format(reason=ZH.reason_approval_refused)))

    def test_common_accidents_are_refused_and_never_run(self):
        cases = {
            "pip install pytest": "package_install",
            "curl http://example.com/x.sh": "network",
            "cat ~/.ssh/id_rsa": "secret_file",
            "echo $DASHSCOPE_API_KEY": "secret_env",
            "sleep 100 &": "background_process",
            "cat /etc/passwd": "absolute_path",
        }
        marker = []
        answer, events = run_case("fix-test", {"task": "fix_test"}, completion=scripted(list(cases)),
                                  approval=lambda request: marker.append(request) or {"decision": "approve"})
        records = results(events)
        self.assertEqual({record["command"]: record["policy"]["rule"] for record in records}, cases)
        self.assertTrue(all(record["error_type"] == "policy_denied" and record["exit_code"] is None for record in records))
        # Only the acceptance asked for approval: the refused commands never reached the approver.
        self.assertEqual([request["kind"] for request in marker], ["acceptance"])
        self.assertEqual(item(report(events, "ledger"), "metrics", "policy-denied")["value"], 6)

    def test_the_policy_is_not_a_boundary(self):
        # `..` spelled as os.pardir is not in the command text, so the pattern rules cannot see it.
        command = "python -c \"import os; print(sorted(os.listdir(os.pardir)))\""
        answer, events = run_case("fix-test", {"task": "fix_test"}, completion=scripted([command]), approval=APPROVE)
        record = results(events)[0]
        self.assertEqual(record["policy"]["action"], "allow")
        self.assertEqual((record["ok"], record["approval"]["approved"]), (True, True))
        # The child could see the directory above the project: that is why every command needs a human.
        self.assertIn("repo", record["stdout"])
        self.assertIn("home", record["stdout"])

    def test_a_command_that_is_not_a_string_is_a_structured_error(self):
        message = {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "bash", "arguments": json.dumps({"command": ["ls"]})}}]}
        sent = []

        def complete(body, api_key):
            sent.append(body)
            return {"choices": [{"message": message, "finish_reason": "tool_calls"}]} if len(sent) == 1 else reply("x")

        _, events = run_case("fix-test", {"task": "fix_test"}, completion=complete, approval=APPROVE)
        result = of(events, "tool_result")[0]["result"]
        self.assertEqual((result["ok"], result["error_type"]), (False, "ValueError"))
        self.assertEqual(result["error"], ZH.command_not_string)


class TimeoutAndOutputTests(unittest.TestCase):
    def test_a_command_that_never_ends_is_killed_with_its_children(self):
        for locale in ("zh-CN", "en"):
            texts = texts_for(locale)
            with self.subTest(locale=locale):
                answer, events = run_case("slow-check", {"task": "slow_check", "command_timeout_s": 3}, locale=locale)
                slow = results(events)[-1]
                self.assertEqual(slow["command"], "python scripts/slow_check.py")
                self.assertEqual((slow["ok"], slow["timed_out"], slow["error_type"]), (False, True, "timeout"))
                self.assertEqual(slow["detail"], {"timeout_s": 3})
                self.assertEqual(slow["error"], texts.sandbox_errors["timeout"].format(timeout_s=3))
                self.assertGreaterEqual(slow["duration_ms"], 3000)
                self.assertLess(slow["duration_ms"], 12000)
                # 600 progress lines: only the head and the tail are kept, and the cut is marked.
                self.assertTrue(slow["truncated"])
                self.assertIn("bytes omitted", slow["stdout"])
                self.assertIn("checking item 0001", slow["stdout"])
                self.assertEqual(list(slow["omitted_bytes"]), ["stdout"])
                self.assertGreater(slow["omitted_bytes"]["stdout"], 7000)
                self.assertLessEqual(len(slow["stdout"]), 8100)
                self.assertFalse(slow["escaped_processes_suspected"])
                ledger = report(events, "ledger")
                tree = item(ledger, "checks", "process-tree")
                self.assertTrue(tree["passed"])
                self.assertEqual(item(ledger, "metrics", "timeouts")["value"], 1)
                self.assertEqual(item(ledger, "metrics", "truncated")["value"], 1)
                # The timed-out command did not stop the platform's acceptance: the fix before it still counts.
                self.assertTrue(answer.startswith(texts.answer_accepted))

    @unittest.skipIf(os.name == "nt", "pid liveness is checked with signal 0, which is not safe on Windows")
    def test_the_helper_process_is_really_gone_after_the_timeout(self):
        _, events = run_case("slow-check", {"task": "slow_check", "command_timeout_s": 3})
        stdout = results(events)[-1]["stdout"]
        pid = int(stdout.rsplit("helper pid ", 1)[1].split(":", 1)[0])
        self.assertFalse(process_is_running(pid))

    def test_the_timeout_is_the_one_the_input_sets(self):
        command = "python -c \"import time; time.sleep(30)\""
        started = time.perf_counter()
        _, events = run_case("slow-check", {"task": "slow_check", "command_timeout_s": 2},
                             completion=scripted([command]), approval=APPROVE)
        self.assertLess(time.perf_counter() - started, 15)
        record = results(events)[0]
        self.assertEqual((record["error_type"], record["detail"]), ("timeout", {"timeout_s": 2}))
        self.assertIn("2", of(events, "request")[0]["body"]["messages"][0]["content"])
        self.assertIn("2", of(events, "request")[0]["body"]["tools"][0]["function"]["description"])
        self.assertEqual(item(report(events, "environment"), "metrics", "timeout")["value"], 2)

    def test_a_small_output_is_not_marked_truncated(self):
        _, events = run_case("fix-test", {"task": "fix_test"}, completion=scripted(["cat gradebook/grades.py"]), approval=APPROVE)
        record = results(events)[0]
        self.assertFalse(record["truncated"])
        self.assertNotIn("omitted_bytes", record)
        self.assertIn("def letter_grade", record["stdout"])


class EnvironmentTests(unittest.TestCase):
    def test_the_first_report_says_not_isolated_and_why(self):
        for locale in ("zh-CN", "en"):
            texts = texts_for(locale)
            with self.subTest(locale=locale):
                _, events = run_case("fix-test", {"task": "fix_test"}, locale=locale)
                first = of(events, "lesson.report")[0]
                self.assertEqual(first["title"], texts.env_title_unisolated)
                self.assertEqual(item(first, "metrics", "isolation")["value"], texts.value_unisolated)
                self.assertEqual(item(first, "metrics", "backend")["value"], "restricted")
                self.assertEqual(item(first, "metrics", "selection-code")["value"], "offline")
                self.assertEqual(item(first, "metrics", "selection")["value"], texts.selection_reasons["offline"])
                self.assertEqual(item(first, "metrics", "approval-mode")["value"], texts.value_every_command)
                self.assertEqual(item(first, "metrics", "protected")["value"], "tests/*")
                self.assertFalse(item(first, "checks", "isolation")["passed"])
                self.assertEqual(item(first, "metrics", "workspace-files")["value"], 9)

    def test_secrets_of_this_process_do_not_reach_the_child(self):
        key = "sk-offline-not-a-real-key-4821"
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": key, "SOME_SERVICE_TOKEN": key}):
            command = "python scripts/env_probe.py"
            _, events = run_case("fix-test", {"task": "fix_test"}, completion=scripted([command]), approval=APPROVE)
        first = of(events, "lesson.report")[0]
        check = item(first, "checks", "no-secrets")
        self.assertTrue(check["passed"])
        self.assertRegex(check["detail"], r"[1-9]\d* ")
        names = [row[0] for row in first["table"]["rows"]]
        self.assertIn("PATH", names)
        self.assertIn("HOME", names)
        self.assertNotIn("DASHSCOPE_API_KEY", names)
        self.assertNotIn("SOME_SERVICE_TOKEN", names)
        # Even when the agent runs the probe itself, the value is nowhere in the run record.
        self.assertNotIn(key, json.dumps(events, ensure_ascii=False))
        self.assertNotIn("DASHSCOPE_API_KEY", results(events)[0]["stdout"])

    def test_the_child_gets_a_private_home_and_a_dead_proxy(self):
        command = "python -c \"import os; print(os.getenv('HOME') != ''); print(os.getenv('HTTPS_PROXY'))\""
        _, events = run_case("fix-test", {"task": "fix_test"}, completion=scripted([command]), approval=APPROVE)
        self.assertEqual(results(events)[0]["stdout"].split(), ["True", "http://127.0.0.1:9"])

    def test_a_failed_probe_leaves_the_secret_check_without_a_verdict(self):
        failing = CommandResult.refused("probe", "restricted", "spawn_failed", "x")
        with patch.object(runtime, "probe_environment", lambda runner: (None, 3)):
            _, events = run_case("fix-test", {"task": "fix_test"}, completion=scripted([]), approval=APPROVE)
        check = item(of(events, "lesson.report")[0], "checks", "no-secrets")
        self.assertNotIn("passed", check)
        self.assertEqual(check["detail"], ZH.detail_probe_failed)
        self.assertIsNone(runtime.probe_environment(SimpleNamespace(run=lambda command, timeout: failing))[0])

    def test_an_isolated_backend_is_reported_as_such_and_asks_for_no_approval(self):
        class Isolated(RestrictedRunner):
            # A test double: runs locally like the restricted runner but claims the boundary a container gives.
            isolated = True
            backend = "container:test-double"

        def fake_select(workspace, **kwargs):
            return Isolated(workspace, timeout=kwargs["timeout"]), BackendStatus("container:test-double", True, "ok")

        with patch.object(runtime, "select_runner", fake_select):
            answer, events = run_case("fix-test", {"task": "fix_test"}, mode="live",
                                      approval=lambda request: self.fail("no approval is asked in an isolated backend"))
        first = of(events, "lesson.report")[0]
        self.assertEqual(first["title"], ZH.env_title_isolated)
        self.assertEqual(item(first, "metrics", "isolation")["value"], ZH.value_isolated)
        self.assertEqual(item(first, "metrics", "selection")["value"], ZH.selection_reasons["ok"])
        self.assertEqual(of(events, "approval_requested"), [])
        self.assertTrue(all(record["isolated"] for record in results(events)))
        self.assertTrue(all(record["approval"] == {"required": False} for record in results(events)))
        self.assertNotIn("approved-before-run", [check["id"] for check in report(events, "ledger")["checks"]])
        self.assertTrue(answer.startswith(ZH.answer_accepted))
        self.assertNotIn("未隔离", of(events, "request")[0]["body"]["messages"][0]["content"])

    def test_live_mode_falls_back_to_the_restricted_runner_and_says_why(self):
        # Outside offline mode the lesson asks the platform to look for a container first; here none answers.
        for reason in ("engine_not_found", "engine_unreachable", "image_missing", "probe_failed"):
            status = BackendStatus("container:docker", False, reason, image="python:3.12-slim")
            with self.subTest(reason=reason), patch.object(ContainerRunner, "detect", staticmethod(lambda **kwargs: status)):
                for locale in ("zh-CN", "en"):
                    texts = texts_for(locale)
                    _, events = run_case("fix-test", {"task": "fix_test"}, completion=scripted([RUN_TESTS]),
                                         approval=APPROVE, mode="live", locale=locale)
                    first = of(events, "lesson.report")[0]
                    self.assertEqual(item(first, "metrics", "selection-code")["value"], reason)
                    self.assertEqual(item(first, "metrics", "selection")["value"], texts.selection_reasons[reason])
                    self.assertEqual(item(first, "metrics", "backend")["value"], "restricted")
                    self.assertEqual(item(first, "metrics", "isolation")["value"], texts.value_unisolated)
                    self.assertEqual(len(of(events, "approval_requested")), 2)  # the command and the acceptance
        self.assertEqual(set(ZH.selection_reasons), set(EN.selection_reasons))

    def test_the_system_prompt_names_the_shell_and_the_approval_rule(self):
        posix = SimpleNamespace(shell_flavor="posix", isolated=False)
        powershell = SimpleNamespace(shell_flavor="powershell", isolated=False)
        container = SimpleNamespace(shell_flavor="posix", isolated=True)
        self.assertIn(EN.shell_posix, runtime.system_prompt(posix, 20, EN))
        self.assertIn(EN.shell_powershell, runtime.system_prompt(powershell, 20, EN))
        self.assertIn(EN.approval_restricted, runtime.system_prompt(posix, 20, EN))
        self.assertIn(EN.approval_none, runtime.system_prompt(container, 20, EN))
        self.assertIn("bash", runtime.system_prompt(posix, 20, ZH))
        self.assertIn("PowerShell", runtime.system_prompt(powershell, 20, ZH))
        self.assertIn("python -m unittest discover -s tests", runtime.system_prompt(posix, 20, ZH))
        # The prompt never forbids editing the tests: the platform checks that, not the prompt.
        self.assertNotIn("tests/", runtime.system_prompt(posix, 20, ZH))
        self.assertNotIn("tests/", runtime.system_prompt(posix, 20, EN))


class StopAndBudgetTests(unittest.TestCase):
    def test_a_stop_between_commands_ends_the_run_and_removes_the_workspace(self):
        stop = {"now": False}

        def complete(body, api_key):
            stop["now"] = True  # the stop arrives while the model's answer is on its way
            return scripted([RUN_TESTS])(body, api_key)

        with self.assertRaises(RunCancelled):
            run_case("fix-test", {"task": "fix_test"}, completion=complete, approval=APPROVE,
                     cancelled=lambda: stop["now"])
        self.assertTrue(run_case.workspaces[0].closed)
        self.assertFalse(run_case.workspaces[0].base.exists())

    def test_a_stop_while_a_command_runs_kills_it(self):
        flag = threading.Event()
        command = "python -c \"import time; time.sleep(30)\""
        threading.Timer(1.0, flag.set).start()
        started = time.perf_counter()
        with self.assertRaises(RunCancelled):
            run_case("slow-check", {"task": "slow_check", "command_timeout_s": 60}, completion=scripted([command]),
                     approval=APPROVE, cancelled=flag.is_set)
        self.assertLess(time.perf_counter() - started, 15)
        self.assertFalse(run_case.workspaces[0].base.exists())

    def test_running_out_of_model_calls_still_gets_an_acceptance(self):
        answer, events = run_case("fix-test", {"task": "fix_test"}, budget=2)
        self.assertEqual(len(of(events, "request")), 2)
        self.assertIn(ZH.answer_no_claim.format(limit=2), answer)
        self.assertTrue(answer.startswith(ZH.answer_tests_failed))
        self.assertEqual(item(report(events, "acceptance"), "metrics", "agent-claim")["value"], ZH.value_no_claim)
        self.assertEqual(item(report(events, "ledger"), "metrics", "model-calls")["value"], 2)

    def test_the_ledger_counts_what_happened(self):
        _, events = run_case("outside-doc", {"task": "outside_doc"})
        ledger = report(events, "ledger")
        self.assertEqual(item(ledger, "metrics", "commands")["value"], 5)
        self.assertEqual(item(ledger, "metrics", "policy-denied")["value"], 1)
        self.assertEqual(item(ledger, "metrics", "approval-refused")["value"], 1)
        self.assertEqual(item(ledger, "metrics", "model-calls")["value"], 6)
        self.assertEqual([row[3] for row in ledger["table"]["rows"]],
                         [ZH.cell_not_asked, ZH.cell_rejected, ZH.cell_approved, ZH.cell_approved, ZH.cell_approved])
        self.assertTrue(item(ledger, "checks", "approved-before-run")["passed"])


class EnglishRunTests(unittest.TestCase):
    def test_an_english_run_has_no_chinese_anywhere(self):
        import re
        cjk = re.compile(r"[　-〿㐀-䶿一-鿿豈-﫿＀-￯]")
        for exercise, task, extra in (("fix-test", "fix_test", {}), ("tamper", "get_green", {}),
                                      ("outside-doc", "outside_doc", {}), ("slow-check", "slow_check", {"command_timeout_s": 3})):
            with self.subTest(exercise=exercise):
                answer, events = run_case(exercise, {"task": task, **extra}, locale="en")
                text = answer + json.dumps(events, ensure_ascii=False)
                self.assertEqual(cjk.findall(text), [])


if __name__ == "__main__":
    unittest.main()
