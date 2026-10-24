"""Behavior tests for file-edit-evidence. The model is scripted test data (fixtures.py or the stubs below); the file
tools, the hashes, the diffs, the sandbox runner and the unittest runs in the temporary workspace are all real."""
import hashlib
import json
import os
import re
import stat
import unittest
from pathlib import Path
from unittest import mock

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from course.sandbox import RestrictedRunner, Workspace
from lessons.lesson_file_edit_evidence import evidence, runtime
from lessons.lesson_file_edit_evidence.file_tools import (
    FileNotFound, FileTools, InvalidArgument, InvalidRange, LineNumbersStale, NoOpEdit, NotATextFile, NotReadYet,
    OldStringNotFound, OldStringNotUnique, PartialRead, PathOutsideWorkspace, ProtectedPath, StaleRead, WriteFailed,
    split_lines)
from lessons.lesson_file_edit_evidence.fixtures import (NEW_SHIPPING, NEW_TIER, OLD_SHIPPING, OLD_TIER, PATH,
                                                        create_approval_policy, create_completion)
from lessons.lesson_file_edit_evidence.locales import texts_for

ZH, EN = "zh-CN", "en"
CJK = re.compile(r"[　-〿一-鿿＀-￯]")
SPEC = {"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}
FIXED = (OLD_TIER, NEW_TIER, OLD_SHIPPING, NEW_SHIPPING)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_case(exercise, inputs=None, *, completion=None, approvals=None, cancelled=lambda: False, locale=ZH,
             mode="offline", budget=10, question=""):
    """One run through the real execute_lesson with a RunContext; returns the answer and the recorded events."""
    events = []
    values = validate_inputs(runtime, inputs or ({"scenario": "guards"} if exercise == "guards"
                                                 else {"scenario": "edit", "strategy": exercise}))
    context = RunContext(
        lesson_id="file-edit-evidence", exercise_id=exercise, question=question, mode=mode, model="fixture-model",
        representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise, values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale, approval_policy=approvals or create_approval_policy(exercise, values, locale))
    answer = execute_lesson(SPEC, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def report(events):
    return of(events, "lesson.report")[-1]


def check(events, check_id):
    return next(item for item in report(events)["checks"] if item["id"] == check_id)


def metric(events, metric_id):
    return next(item["value"] for item in report(events)["metrics"] if item["id"] == metric_id)


def call(name, arguments, index=1, turn=0):
    return {"id": f"call_{turn}_{index}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}


def scripted(*turns, usage=None):
    """A model that plays the given turns in order: each turn is a list of tool calls, or a string (the final answer)."""
    state = {"turn": 0, "calls": 0}

    def complete(body, api_key):
        turn = turns[state["turn"]]
        state["turn"] = min(state["turn"] + 1, len(turns) - 1)
        state["calls"] += 1
        message = {"role": "assistant", "content": turn if isinstance(turn, str) else ""}
        if not isinstance(turn, str):
            message["tool_calls"] = turn
        response = {"choices": [{"message": message}]}
        if usage is not None:
            response["usage"] = usage[min(state["calls"] - 1, len(usage) - 1)]
        return response
    return complete


class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        self.workspace = Workspace(runtime.FIXTURE)
        self.addCleanup(self.workspace.cleanup)
        self.rows = []
        self.t = texts_for(EN)
        self.tools = FileTools(self.workspace, self.t, protected=runtime.PROTECTED, record=self.rows.append)

    def text(self, path=PATH):
        return (self.workspace.root / path).read_bytes().decode("utf-8")

    def write_outside_the_tools(self, path, text):
        (self.workspace.root / path).write_bytes(text.encode("utf-8"))


class ReadFileTests(WorkspaceCase):
    def test_lines_are_numbered_and_the_version_is_the_hash_prefix(self):
        result = self.tools.read_file(PATH)
        first = result["content"].split("\n")[0]
        self.assertEqual(first, f"   1| {split_lines(self.text())[0].rstrip(chr(10))}")
        self.assertEqual(result["version"], sha256(self.text())[:12])
        self.assertEqual((result["start_line"], result["end_line"], result["truncated"]),
                         (1, result["total_lines"], False))

    def test_range_and_defaults(self):
        part = self.tools.read_file(PATH, 2, 4)
        self.assertEqual([row[:4].strip() for row in part["content"].split("\n")], ["2", "3", "4"])
        self.assertTrue(part["truncated"])
        # null for an optional argument means the default, which is what models often send.
        self.assertEqual(self.tools.read_file(PATH, None, None)["start_line"], 1)

    def test_long_files_stop_at_the_read_limit(self):
        self.tools.write_file("big.txt", "".join(f"line {n}\n" for n in range(1, 501)))
        part = self.tools.read_file("big.txt")
        self.assertEqual((part["end_line"], part["total_lines"], part["truncated"]), (400, 500, True))
        self.assertEqual(self.tools.read_file("big.txt", 401)["end_line"], 500)

    def test_bad_ranges_are_structured_errors(self):
        for arguments in ((PATH, 0, 3), (PATH, 99, None), (PATH, 5, 2), (PATH, "1", None), (PATH, True, None)):
            with self.subTest(arguments=arguments):
                with self.assertRaises((InvalidRange, InvalidArgument)):
                    self.tools.read_file(*arguments)

    def test_missing_directory_binary_and_non_utf8_files(self):
        self.write_outside_the_tools("blob.bin", "a\x00b")
        (self.workspace.root / "latin.txt").write_bytes("café".encode("latin-1"))
        with self.assertRaises(FileNotFound):
            self.tools.read_file("nope.py")
        for path in ("shop", "blob.bin", "latin.txt"):
            with self.subTest(path=path):
                with self.assertRaises(NotATextFile):
                    self.tools.read_file(path)

    def test_a_file_past_the_size_limit_is_refused(self):
        self.write_outside_the_tools("huge.txt", "x" * 200_001)
        with self.assertRaises(NotATextFile):
            self.tools.read_file("huge.txt")


class PathTests(WorkspaceCase):
    def test_every_form_of_leaving_the_workspace_is_refused(self):
        for path in ("../outside.txt", "/etc/passwd", "~/secret", "shop/../../x", "", "   ", "a\x00b", 5, None):
            with self.subTest(path=path):
                with self.assertRaises(PathOutsideWorkspace):
                    self.tools.read_file(path)
                with self.assertRaises(PathOutsideWorkspace):
                    self.tools.write_file(path, "x")
        self.assertFalse((self.workspace.base / "outside.txt").exists())

    def test_a_symlink_to_the_outside_does_not_open_the_door(self):
        outside = self.workspace.base / "secret.txt"
        outside.write_text("secret", encoding="utf-8")
        try:
            os.symlink(outside, self.workspace.root / "link.txt")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available here")
        with self.assertRaises(PathOutsideWorkspace):
            self.tools.read_file("link.txt")
        with self.assertRaises(PathOutsideWorkspace):
            self.tools.write_file("link.txt", "overwritten")
        self.assertEqual(outside.read_text(encoding="utf-8"), "secret")

    def test_the_error_names_the_path_in_the_run_language(self):
        with self.assertRaises(PathOutsideWorkspace) as caught:
            self.tools.read_file("../x")
        self.assertEqual(str(caught.exception), texts_for(EN).path_outside.format(path="../x"))
        self.tools.t = texts_for(ZH)
        with self.assertRaises(PathOutsideWorkspace) as caught:
            self.tools.read_file("../x")
        self.assertIn("不在工作区内", str(caught.exception))

    def test_protected_files_can_be_read_but_never_written(self):
        self.tools.read_file("tests/test_pricing.py")
        before = self.text("tests/test_pricing.py")
        with self.assertRaises(ProtectedPath):
            self.tools.edit_file("tests/test_pricing.py", "4.5", "0.0")
        with self.assertRaises(ProtectedPath):
            self.tools.write_file("tests/new_test.py", "x = 1\n")
        self.assertEqual(self.text("tests/test_pricing.py"), before)
        self.assertFalse((self.workspace.root / "tests" / "new_test.py").exists())
        self.assertEqual([row["error_type"] for row in self.rows], ["ProtectedPath", "ProtectedPath"])


class WriteGuardTests(WorkspaceCase):
    def test_an_existing_file_cannot_be_written_or_edited_unread(self):
        before = self.text()
        for action in (lambda: self.tools.write_file(PATH, ""), lambda: self.tools.edit_file(PATH, "TAX_RATE", "X"),
                       lambda: self.tools.edit_lines(PATH, 1, 1, "x")):
            with self.assertRaises(NotReadYet):
                action()
        self.assertEqual(self.text(), before)

    def test_a_new_file_needs_no_read_and_creates_parents(self):
        result = self.tools.write_file("docs/notes/todo.txt", "one\n")
        self.assertTrue(result["created"])
        self.assertIsNone(result["previous_version"])
        self.assertEqual(self.text("docs/notes/todo.txt"), "one\n")
        row = self.rows[-1]
        self.assertEqual((row["before_sha256"], row["after_sha256"]), (None, sha256("one\n")))
        self.assertIn("--- /dev/null", row["diff"])

    def test_write_file_needs_the_whole_file_and_a_partial_read_is_not_enough(self):
        self.tools.read_file(PATH, 1, 5)
        with self.assertRaises(PartialRead):
            self.tools.write_file(PATH, "x")
        # Partial reads of one version add up to a full read.
        self.tools.read_file(PATH, 5, 400)
        self.assertTrue(self.tools.write_file(PATH, self.text() + "# more\n")["changed"])

    def test_a_file_changed_after_the_read_is_refused_not_overwritten(self):
        self.tools.read_file(PATH)
        self.write_outside_the_tools(PATH, self.text() + "# someone else\n")
        for action in (lambda: self.tools.write_file(PATH, "mine"),
                       lambda: self.tools.edit_file(PATH, "TAX_RATE", "X"),
                       lambda: self.tools.edit_lines(PATH, 1, 1, "x")):
            with self.assertRaises(StaleRead):
                action()
        self.assertTrue(self.text().endswith("# someone else\n"))
        # Reading again is the way out.
        self.tools.read_file(PATH)
        self.assertTrue(self.tools.edit_file(PATH, "TAX_RATE = 0.08", "TAX_RATE = 0.09")["changed"])
        self.assertTrue(self.text().endswith("# someone else\n"))

    def test_stale_is_checked_before_line_numbers(self):
        self.tools.read_file(PATH)
        self.tools.edit_file(PATH, "TAX_RATE = 0.08", "TAX_RATE = 0.09")
        self.write_outside_the_tools(PATH, self.text() + "x\n")
        with self.assertRaises(StaleRead):
            self.tools.edit_lines(PATH, 1, 1, "y")

    def test_a_write_made_by_the_tools_does_not_make_the_next_one_stale(self):
        self.tools.read_file(PATH)
        self.tools.edit_file(PATH, "TAX_RATE = 0.08", "TAX_RATE = 0.09")
        self.assertTrue(self.tools.edit_file(PATH, "SHIPPING_FEE = 4.5", "SHIPPING_FEE = 5.0")["changed"])

    def test_a_failed_write_leaves_the_file_and_says_so(self):
        self.tools.read_file(PATH)
        before = self.text()
        with mock.patch("lessons.lesson_file_edit_evidence.file_tools._atomic_write", side_effect=PermissionError):
            with self.assertRaises(WriteFailed):
                self.tools.edit_file(PATH, "TAX_RATE = 0.08", "TAX_RATE = 0.09")
        self.assertEqual(self.text(), before)
        self.assertEqual((self.rows[-1]["ok"], self.rows[-1]["error_type"]), (False, "WriteFailed"))

    def test_writes_are_atomic_and_keep_the_file_mode(self):
        self.tools.read_file(PATH)
        target = self.workspace.root / PATH
        target.chmod(0o640)
        self.tools.edit_file(PATH, "TAX_RATE = 0.08", "TAX_RATE = 0.09")
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)
        self.assertEqual([p.name for p in target.parent.iterdir() if p.name.startswith(".edit-")], [])


class EditFileTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.tools.read_file(PATH)

    def test_the_old_text_must_match_exactly_once(self):
        before = self.text()
        with self.assertRaises(OldStringNotUnique) as caught:
            self.tools.edit_file(PATH, "return 0.0", "return 1.0")
        self.assertIn("2 times", str(caught.exception))
        self.assertIn("22, 33", str(caught.exception))
        with self.assertRaises(OldStringNotFound):
            self.tools.edit_file(PATH, "return 9.9", "x")
        with self.assertRaises(InvalidArgument):
            self.tools.edit_file(PATH, "", "x")
        with self.assertRaises(InvalidArgument):
            self.tools.edit_file(PATH, "TAX_RATE", 5)
        with self.assertRaises(NoOpEdit):
            self.tools.edit_file(PATH, "TAX_RATE = 0.08", "TAX_RATE = 0.08")
        self.assertEqual(self.text(), before)
        self.assertEqual([row["error_type"] for row in self.rows],
                         ["OldStringNotUnique", "OldStringNotFound", "InvalidArgument", "InvalidArgument", "NoOpEdit"])

    def test_the_line_number_prefix_is_not_part_of_the_file(self):
        with self.assertRaises(OldStringNotFound):
            self.tools.edit_file(PATH, "  16| def discount_rate(amount):", "x")

    def test_a_unique_replace_changes_only_that_text_and_keeps_every_other_byte(self):
        crlf = "alpha\r\nbeta\r\ngamma\r\n"
        self.write_outside_the_tools("win.txt", crlf)
        self.tools.read_file("win.txt")
        result = self.tools.edit_file("win.txt", "beta", "BETA")
        self.assertEqual(self.text("win.txt"), "alpha\r\nBETA\r\ngamma\r\n")
        self.assertEqual((result["added"], result["removed"]), (1, 1))
        self.assertEqual(self.rows[-1]["after_sha256"], sha256("alpha\r\nBETA\r\ngamma\r\n"))

    def test_the_result_is_short_and_reports_syntax(self):
        result = self.tools.edit_file(PATH, "TAX_RATE = 0.08", "TAX_RATE = 0.09")
        self.assertEqual(set(result), {"path", "changed", "created", "previous_version", "version", "added", "removed",
                                       "total_lines", "syntax"})
        self.assertEqual(result["syntax"], {"ok": True})
        broken = self.tools.edit_file(PATH, "def tax(amount):", "def tax(amount")
        self.assertFalse(broken["syntax"]["ok"])
        self.assertIsNotNone(broken["syntax"]["line"])
        self.assertIn("def tax(amount", self.text())
        self.assertFalse(self.rows[-1]["syntax_ok"])


class EditLinesTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.write_outside_the_tools("list.txt", "a\nb\nc\nd\n")
        self.tools.read_file("list.txt")

    def lines(self):
        return self.text("list.txt")

    def test_replace_insert_delete_and_keep_the_line_structure(self):
        self.tools.edit_lines("list.txt", 2, 3, "X\nY\nZ")
        self.assertEqual(self.lines(), "a\nX\nY\nZ\nd\n")
        self.tools.read_file("list.txt")
        self.tools.edit_lines("list.txt", 1, 1, "")
        self.assertEqual(self.lines(), "X\nY\nZ\nd\n")
        self.tools.read_file("list.txt")
        self.tools.edit_lines("list.txt", 4, 4, "last\n")
        self.assertEqual(self.lines(), "X\nY\nZ\nlast\n")

    def test_a_last_line_without_a_newline_stays_without_one(self):
        self.write_outside_the_tools("tail.txt", "a\nb")
        self.tools.read_file("tail.txt")
        self.tools.edit_lines("tail.txt", 2, 2, "B")
        self.assertEqual(self.text("tail.txt"), "a\nB")

    def test_the_range_must_describe_real_lines(self):
        for arguments in ((0, 1), (3, 2), (1, 5), (1.0, 2), ("1", 2), (True, 2)):
            with self.subTest(arguments=arguments):
                with self.assertRaises(InvalidRange):
                    self.tools.edit_lines("list.txt", *arguments, "x")
        with self.assertRaises(InvalidArgument):
            self.tools.edit_lines("list.txt", 1, 1, None)
        with self.assertRaises(NoOpEdit):
            self.tools.edit_lines("list.txt", 1, 1, "a")
        self.assertEqual(self.lines(), "a\nb\nc\nd\n")

    def test_every_write_voids_the_line_numbers_until_the_next_read(self):
        self.tools.edit_lines("list.txt", 1, 1, "A\nA2")
        with self.assertRaises(LineNumbersStale):
            self.tools.edit_lines("list.txt", 3, 3, "C")
        self.assertEqual(self.lines(), "A\nA2\nb\nc\nd\n")
        # An edit_file in between voids them too, because it can move any line below it.
        self.tools.read_file("list.txt")
        self.tools.edit_file("list.txt", "b", "b\nb2")
        with self.assertRaises(LineNumbersStale):
            self.tools.edit_lines("list.txt", 1, 1, "x")
        self.tools.read_file("list.txt")
        self.assertTrue(self.tools.edit_lines("list.txt", 1, 1, "x")["changed"])

    def test_a_partial_read_is_enough_for_line_edits(self):
        self.tools.read_file("list.txt", 1, 2)
        self.assertTrue(self.tools.edit_lines("list.txt", 2, 2, "B")["changed"])


class JournalTests(WorkspaceCase):
    def test_every_call_leaves_a_row_with_hashes_and_the_diff(self):
        self.tools.read_file(PATH)
        self.tools.edit_file(PATH, OLD_SHIPPING, NEW_SHIPPING)
        with self.assertRaises(OldStringNotFound):
            self.tools.edit_file(PATH, "no such text", "x")
        ok, refused = self.rows
        self.assertEqual([row["seq"] for row in self.rows], [1, 2])
        self.assertEqual(ok["before_sha256"], self.workspace.baseline.hashes[PATH])
        self.assertEqual(ok["after_sha256"], self.workspace.snapshot().hashes[PATH])
        self.assertEqual((ok["added"], ok["removed"], ok["changed"], ok["ok"]), (1, 1, True, True))
        self.assertIn("-    if amount > FREE_SHIPPING_FROM:", ok["diff"])
        self.assertIn("+    if amount >= FREE_SHIPPING_FROM:", ok["diff"])
        self.assertEqual((refused["ok"], refused["changed"], refused["error_type"]), (False, False, "OldStringNotFound"))
        self.assertEqual(refused["before_sha256"], refused["after_sha256"])
        self.assertEqual(self.tools.journal, self.rows)

    def test_writing_the_same_content_is_ok_but_changes_nothing(self):
        self.tools.read_file(PATH)
        result = self.tools.write_file(PATH, self.text())
        self.assertFalse(result["changed"])
        row = self.rows[-1]
        self.assertEqual((row["ok"], row["changed"], row["diff"]), (True, False, ""))
        self.assertEqual(row["before_sha256"], row["after_sha256"])

    def test_the_chain_closes_for_the_tools_and_breaks_for_a_change_behind_their_back(self):
        baseline = self.workspace.baseline.hashes
        self.tools.read_file(PATH)
        self.tools.edit_file(PATH, OLD_SHIPPING, NEW_SHIPPING)
        self.assertEqual(evidence.verify_chain(self.tools.journal, baseline, self.workspace.snapshot().hashes), [])
        self.write_outside_the_tools("shop/report.py", self.text("shop/report.py") + "# x\n")
        problems = evidence.verify_chain(self.tools.journal, baseline, self.workspace.snapshot().hashes)
        self.assertEqual([(p["path"], p["reason"]) for p in problems], [("shop/report.py", "unexplained_change")])

    def test_the_record_callback_gets_the_same_rows(self):
        self.tools.read_file(PATH)
        self.tools.edit_file(PATH, OLD_SHIPPING, NEW_SHIPPING)
        self.assertIs(self.rows[0], self.tools.journal[0])


class EvidenceTests(unittest.TestCase):
    def test_unified_diff_counts_stay_exact_when_the_text_is_cut(self):
        before = "".join(f"line {n}\n" for n in range(300))
        after = "".join(f"LINE {n}\n" for n in range(300))
        text, added, removed = evidence.unified_diff("big.txt", before, after, limit=400)
        self.assertEqual((added, removed), (300, 300))
        self.assertIn("chars omitted", text)
        self.assertTrue(text.startswith("--- a/big.txt\n+++ b/big.txt"))

    def test_a_new_file_diffs_against_dev_null(self):
        text, added, removed = evidence.unified_diff("new.txt", None, "a\nb\n")
        self.assertTrue(text.startswith("--- /dev/null\n+++ b/new.txt"))
        self.assertEqual((added, removed), (2, 0))

    def test_verify_chain_names_each_kind_of_problem(self):
        base = {"a.py": "h0"}
        row = lambda seq, before, after, **extra: {"seq": seq, "path": "a.py", "ok": True, "changed": True,
                                                    "before_sha256": before, "after_sha256": after, **extra}
        self.assertEqual(evidence.verify_chain([row(1, "h0", "h1"), row(2, "h1", "h2")], base, {"a.py": "h2"}), [])
        broken = evidence.verify_chain([row(1, "h0", "h1"), row(2, "hX", "h2")], base, {"a.py": "h2"})
        self.assertEqual([(p["seq"], p["reason"]) for p in broken], [(2, "broken_chain")])
        mismatch = evidence.verify_chain([row(1, "h0", "h1")], base, {"a.py": "h9"})
        self.assertEqual([p["reason"] for p in mismatch], ["final_mismatch"])
        silent = evidence.verify_chain([], base, {"a.py": "h9"})
        self.assertEqual([p["reason"] for p in silent], ["unexplained_change"])
        # Refused and no-change rows move nothing.
        skipped = [row(1, "h0", "h0", changed=False), row(2, "h0", "h0", ok=False)]
        self.assertEqual(evidence.verify_chain(skipped, base, base), [])
        # A created file starts from nothing.
        created = row(1, None, "h5", path="new.py")
        self.assertEqual(evidence.verify_chain([created], {}, {"new.py": "h5"}), [])

    def test_symbol_changes_see_a_function_that_vanished(self):
        before = "import os\nA = 1\n\n\ndef f():\n    return 1\n\n\ndef g():\n    return 2\n"
        after = "import os\nA = 1\n\n\ndef f():\n    return 3\n\n\ndef h():\n    return 4\n"
        self.assertEqual(evidence.symbol_changes(before, after),
                         {"changed": ["f"], "added": ["h"], "removed": ["g"]})
        self.assertIsNone(evidence.symbol_changes(before, "def broken(:\n"))

    def test_unittest_summary(self):
        self.assertEqual(evidence.unittest_summary("..\nRan 2 tests in 0.1s\n\nOK\n"),
                         {"ran": 2, "outcome": "OK", "detail": ""})
        self.assertEqual(evidence.unittest_summary("Ran 7 tests in 0.1s\n\nFAILED (failures=2)\n"),
                         {"ran": 7, "outcome": "FAILED", "detail": "failures=2"})
        self.assertEqual(evidence.unittest_summary("no tests here"), {"ran": None, "outcome": None, "detail": ""})


class StrategyRunTests(unittest.TestCase):
    def test_each_strategy_fixes_the_task_and_ends_at_the_same_file(self):
        finals, written = {}, {}
        for strategy in ("rewrite", "replace", "lines"):
            for locale in (ZH, EN):
                with self.subTest(strategy=strategy, locale=locale):
                    answer, events = run_case(strategy, locale=locale)
                    for check_id in ("tests_pass", "tests_untouched", "scope", "evidence_chain"):
                        self.assertTrue(check(events, check_id)["passed"], check_id)
                    self.assertEqual(of(events, "done"), [])  # lifecycle events belong to the platform
                    finals[(strategy, locale)] = metric(events, "final_sha256")
                    written[strategy] = [row["tool"] for row in of(events, "lesson.file_change") if row["ok"]]
                    self.assertTrue(answer)
        # The scripted model makes the same fix three ways, so the files end up byte for byte the same.
        self.assertEqual(len(set(finals.values())), 1)
        self.assertEqual(written, {"rewrite": ["write_file"], "replace": ["edit_file"] * 2,
                                   "lines": ["edit_lines"] * 2})

    def test_only_the_strategys_own_write_tool_is_offered(self):
        for strategy, tool in runtime.WRITE_TOOLS.items():
            with self.subTest(strategy=strategy):
                _, events = run_case(strategy)
                offered = [item["function"]["name"] for item in of(events, "request")[0]["body"]["tools"]]
                self.assertEqual(offered, ["read_file", tool, "run_tests"])

    def test_the_lines_strategy_meets_stale_numbers_and_pays_for_a_second_read(self):
        _, events = run_case("lines")
        rows = of(events, "lesson.file_change")
        self.assertEqual([(row["ok"], row["error_type"]) for row in rows],
                         [(True, None), (False, "LineNumbersStale"), (True, None)])
        self.assertEqual(metric(events, "write_calls"), "2 / 1")
        self.assertEqual(metric(events, "read_calls"), 2)
        self.assertEqual(metric(events, "model_calls"), 6)
        # Refused calls cost arguments too: they count in what was sent.
        replace_events = run_case("replace")[1]
        self.assertEqual(metric(replace_events, "write_calls"), "2 / 0")
        self.assertEqual(metric(replace_events, "model_calls"), 4)

    def test_rewrite_sends_far_more_characters_than_a_local_edit(self):
        sent = {strategy: metric(run_case(strategy)[1], "write_arg_chars") for strategy in ("rewrite", "replace")}
        self.assertGreater(sent["rewrite"], sent["replace"])
        whole = self.fixture_chars()
        self.assertGreater(sent["rewrite"], whole)

    @staticmethod
    def fixture_chars():
        return len((runtime.FIXTURE / PATH).read_text(encoding="utf-8"))

    def test_events_follow_tool_call_then_change_then_result(self):
        _, events = run_case("replace")
        kinds = [kind for kind, _, _ in events]
        first = kinds.index("lesson.file_change")
        self.assertEqual(kinds[first - 1], "tool_call")
        self.assertEqual(kinds[first + 1], "tool_result")
        self.assertEqual(kinds[0:2], ["lesson.sandbox", "lesson.task_card"])

    def test_the_report_table_lists_every_journal_row(self):
        _, events = run_case("lines")
        table = report(events)["table"]
        self.assertEqual([row[0] for row in table["rows"]], [1, 2, 3])
        self.assertEqual([row[3] for row in table["rows"]], ["已写入", "LineNumbersStale", "已写入"])
        self.assertEqual(table["rows"][1][4], table["rows"][1][5])
        self.assertIn("+    if amount >= 300:", metric(events, "diff"))

    def test_usage_is_only_what_the_provider_reported(self):
        _, events = run_case("replace")
        self.assertEqual(metric(events, "completion_tokens"), "未报告")
        self.assertEqual(metric(run_case("replace", locale=EN)[1], "total_tokens"), "not reported")
        edits = [call("edit_file", {"path": PATH, "old": OLD_SHIPPING, "new": NEW_SHIPPING})]
        model = scripted([call("read_file", {"path": PATH})], edits, [call("run_tests", {})], "done",
                         usage=[{"completion_tokens": 10, "total_tokens": 100}, {"completion_tokens": 20, "total_tokens": 150},
                                {"total_tokens": 160}, None])
        _, events = run_case("replace", completion=model)
        self.assertEqual(metric(events, "completion_tokens"), "30（另有 2 次响应未报告）")
        self.assertEqual(metric(events, "total_tokens"), "410（另有 1 次响应未报告）")


class FailureRunTests(unittest.TestCase):
    PRICING = (runtime.FIXTURE / PATH).read_text(encoding="utf-8")

    def lossy_rewrite(self):
        """A rewrite that silently drops the tax function while it fixes the two bugs."""
        fixed = self.PRICING.replace(OLD_TIER, NEW_TIER).replace(OLD_SHIPPING, NEW_SHIPPING)
        start = fixed.index("def tax(amount):")
        end = fixed.index("def grand_total")
        lossy = fixed[:start] + fixed[end:]
        return scripted([call("read_file", {"path": PATH})], [call("write_file", {"path": PATH, "content": lossy})],
                        [call("run_tests", {})], "Fixed both bugs.")

    def test_a_rewrite_that_drops_code_is_caught_by_the_platform_not_by_the_chain(self):
        answer, events = run_case("rewrite", completion=self.lossy_rewrite(), locale=EN)
        # The journal is complete and closes: evidence of WHAT happened says nothing about whether it is right.
        self.assertTrue(check(events, "evidence_chain")["passed"])
        self.assertFalse(check(events, "scope")["passed"])
        self.assertIn("tax", check(events, "scope")["detail"])
        self.assertFalse(check(events, "tests_pass")["passed"])
        self.assertEqual(metric(events, "self_check"), "yes")
        self.assertIn("The model says: Fixed both bugs.", answer)
        self.assertIn("The platform reran the tests: failed", answer)
        removed = [row["removed"] for row in of(events, "lesson.file_change")]
        self.assertGreater(removed[0], 5)

    def test_a_model_that_never_edits_still_gets_an_honest_report(self):
        _, events = run_case("replace", completion=scripted("I think it is already fine."))
        self.assertFalse(check(events, "tests_pass")["passed"])
        self.assertTrue(check(events, "evidence_chain")["passed"])
        self.assertEqual(metric(events, "write_calls"), "0 / 0")
        self.assertEqual(metric(events, "self_check"), "否")
        self.assertEqual(report(events)["table"]["rows"], [])
        self.assertEqual(metric(events, "diff"), "无")

    def test_editing_a_test_is_refused_and_the_tests_stay_untouched(self):
        cheat = [call("read_file", {"path": "tests/test_pricing.py"}),
                 call("edit_file", {"path": "tests/test_pricing.py", "old": "self.assertEqual(shipping(50.0), 0.0)",
                                    "new": "self.assertEqual(shipping(50.0), 4.5)"}, 2)]
        _, events = run_case("replace", completion=scripted(cheat, "Done."))
        self.assertTrue(check(events, "tests_untouched")["passed"])
        self.assertEqual(report(events)["table"]["rows"][0][3], "ProtectedPath")
        self.assertFalse(check(events, "tests_pass")["passed"])

    def test_a_model_that_never_stops_uses_its_rounds_and_still_gets_a_report(self):
        forever = scripted([call("read_file", {"path": PATH})])
        answer, events = run_case("replace", completion=forever, locale=EN, budget=runtime.MAX_ROUNDS)
        self.assertEqual(len(of(events, "request")), runtime.MAX_ROUNDS)
        self.assertEqual(metric(events, "read_calls"), runtime.MAX_ROUNDS)
        self.assertIn("used up the round limit of 10", answer)
        self.assertTrue(check(events, "evidence_chain")["passed"])

    def test_a_scope_creep_is_flagged_even_when_the_tests_pass(self):
        extra = self.PRICING.replace(OLD_TIER, NEW_TIER).replace(OLD_SHIPPING, NEW_SHIPPING)
        extra = extra.replace("TAX_RATE = 0.08", "TAX_RATE = 0.08\nEXTRA = 1").replace("round(amount * TAX_RATE, 2)",
                                                                                         "round(amount * TAX_RATE, 2) + 0")
        model = scripted([call("read_file", {"path": PATH})], [call("write_file", {"path": PATH, "content": extra})],
                         [call("run_tests", {})], "ok")
        _, events = run_case("rewrite", completion=model)
        self.assertTrue(check(events, "tests_pass")["passed"])
        self.assertFalse(check(events, "scope")["passed"])
        self.assertIn("tax", check(events, "scope")["detail"])

    def test_a_syntax_error_is_reported_to_the_model_and_to_the_scope_check(self):
        broken = self.PRICING.replace("def tax(amount):", "def tax(amount")
        model = scripted([call("read_file", {"path": PATH})], [call("write_file", {"path": PATH, "content": broken})], "x")
        _, events = run_case("rewrite", completion=model, locale=EN)
        result = of(events, "tool_result")[1]["result"]["result"]
        self.assertFalse(result["syntax"]["ok"])
        self.assertFalse(check(events, "scope")["passed"])
        self.assertIn("does not parse", check(events, "scope")["detail"])


class ApprovalTests(unittest.TestCase):
    def test_the_test_command_waits_for_approval_and_shows_what_will_run(self):
        _, events = run_case("replace")
        kinds = [kind for kind, _, _ in events]
        requested = [i for i, kind in enumerate(kinds) if kind == "approval_requested"]
        self.assertEqual(len(requested), 2, "the model's run_tests and the platform's acceptance run")
        first = of(events, "approval_requested")[0]
        self.assertEqual(first["payload"]["command"], runtime.TEST_COMMAND)
        self.assertFalse(first["payload"]["isolated"])
        self.assertEqual(first["payload"]["changed_files"], [{"path": PATH, "status": "modified"}])
        self.assertEqual(first["risk"], "high")
        self.assertIn("未隔离", first["summary"])
        # The command runs after the decision, never before.
        run_tests_result = next(i for i, (kind, data, _) in enumerate(events)
                                if kind == "tool_result" and data["name"] == "run_tests")
        self.assertLess(requested[0], kinds.index("approval_resolved"))
        self.assertLess(kinds.index("approval_resolved"), run_tests_result)
        self.assertEqual(of(events, "approval_resolved")[0]["decided_by"], "offline_fixture")

    def test_a_rejected_command_does_not_run_and_the_platform_does_not_claim_a_pass(self):
        calls = []

        def reject(request):
            calls.append(request["payload"]["tool"])
            return {"decision": "reject", "note": "no"}
        _, events = run_case("replace", approvals=reject, locale=EN)
        self.assertEqual(calls, ["run_tests", "acceptance"])
        result = next(data for data in of(events, "tool_result") if data["name"] == "run_tests")["result"]["result"]
        self.assertEqual((result["ok"], result["error_type"], result["stderr"]), (False, "approval_rejected", ""))
        self.assertEqual(result["error"], texts_for(EN).sandbox_errors["approval_rejected"])
        tests = check(events, "tests_pass")
        self.assertNotIn("passed", tests, "a command that never ran is not a failed or a passed check")
        self.assertIn("did not run", tests["detail"])
        self.assertTrue(check(events, "evidence_chain")["passed"])

    def test_a_timeout_without_a_decision_does_not_run_either(self):
        _, events = run_case("replace", approvals=lambda request: {"decision": "timeout"})
        result = next(data for data in of(events, "tool_result") if data["name"] == "run_tests")["result"]["result"]
        self.assertEqual(result["error_type"], "approval_timeout")
        self.assertNotIn("passed", check(events, "tests_pass"))

    def test_an_isolated_runner_needs_no_per_command_approval(self):
        class Contained(RestrictedRunner):
            isolated = True
        real = runtime.select_runner

        def contained(workspace, **options):
            runner, status = real(workspace, **options)
            return Contained(workspace, timeout=30), status
        with mock.patch.object(runtime, "select_runner", contained):
            _, events = run_case("replace", approvals=lambda request: self.fail("no approval expected"))
        self.assertEqual(of(events, "approval_requested"), [])
        self.assertTrue(check(events, "tests_pass")["passed"])
        sandbox = of(events, "lesson.sandbox")[0]
        self.assertEqual((sandbox["isolated"], sandbox["approval"]), (True, "none"))
        self.assertIn("已隔离", sandbox["label"])

    def test_offline_runs_always_use_the_restricted_runner_and_live_runs_ask_for_auto(self):
        seen = []
        real = runtime.select_runner

        def spy(workspace, **options):
            seen.append(options["prefer"])
            return real(workspace, prefer="restricted", timeout=30)
        with mock.patch.object(runtime, "select_runner", spy):
            run_case("replace", mode="offline")
            run_case("replace", mode="live")
        self.assertEqual(seen, ["restricted", "auto"])

    def test_the_sandbox_event_marks_the_run_as_not_isolated(self):
        for locale, mark in ((ZH, "未隔离 · 命令在你的机器上执行"), (EN, "Not isolated · commands run on your machine")):
            _, events = run_case("replace", locale=locale)
            sandbox = of(events, "lesson.sandbox")[0]
            self.assertEqual((sandbox["label"], sandbox["backend"], sandbox["isolated"]), (mark, "restricted", False))
            self.assertIn(mark, metric(events, "environment"))


class GuardRunTests(unittest.TestCase):
    def test_all_five_cases_behave_as_declared(self):
        for locale in (ZH, EN):
            with self.subTest(locale=locale):
                answer, events = run_case("guards", locale=locale)
                checks = report(events)["checks"]
                self.assertEqual([item["id"] for item in checks], [f"case_{name}" for name in runtime.CASES])
                self.assertTrue(all(item["passed"] for item in checks), checks)
                rows = report(events)["table"]["rows"]
                self.assertTrue(all(row[3] == row[4] for row in rows), "declared and actual outcomes agree")
                self.assertEqual(metric(events, "commands_run"), 0)
                self.assertEqual(metric(events, "model_calls"), 0)
                self.assertEqual(of(events, "request"), [])
                self.assertEqual(metric(events, "rejected"), sum(1 for row in rows if row[4] != "ok"))
                self.assertTrue(answer)

    def test_every_call_is_the_runners_not_the_models(self):
        _, events = run_case("guards")
        calls = of(events, "tool_call")
        self.assertTrue(calls and all(item["origin"] == "course_program" for item in calls))
        self.assertTrue(all(item["origin"] == "course_program" for item in of(events, "tool_result")))

    def test_a_single_case_runs_alone(self):
        _, events = run_case("guards", {"scenario": "guards", "case": "stale"})
        self.assertEqual([item["id"] for item in report(events)["checks"]], ["case_stale"])
        change = of(events, "lesson.external_change")[0]
        self.assertTrue(change["simulated"])
        self.assertEqual(change["by"], "course_program")
        self.assertNotEqual(change["before_sha256"], change["after_sha256"])
        rows = of(events, "lesson.file_change")
        self.assertEqual([(row["ok"], row["error_type"]) for row in rows], [(False, "StaleRead"), (True, None)])
        # The refused write left the externally changed file as it was, and the later write started from it.
        self.assertEqual(rows[0]["before_sha256"], change["after_sha256"])
        self.assertEqual(rows[1]["before_sha256"], change["after_sha256"])

    def test_the_stale_case_proves_the_chain_notices_changes_behind_the_tools(self):
        _, events = run_case("guards", {"scenario": "guards", "case": "stale"})
        self.assertTrue(report(events)["checks"][0]["passed"])
        self.assertIn("哈希链和预期一致：是", report(events)["checks"][0]["detail"])
        # The expected finding is exactly one broken link, at the file the runner changed.
        self.assertEqual(of(events, "lesson.external_change")[0]["path"], "shop/report.py")

    def test_line_drift_shows_the_old_number_pointing_at_another_line(self):
        _, events = run_case("guards", {"scenario": "guards", "case": "line_drift"}, locale=EN)
        self.assertIn("the old line number really pointed at another line: yes", report(events)["checks"][0]["detail"])
        self.assertEqual([row[4] for row in report(events)["table"]["rows"]],
                         ["ok", "ok", "LineNumbersStale", "ok", "ok"])

    def test_guards_run_without_any_model_connection(self):
        events = []
        values = validate_inputs(runtime, {"scenario": "guards"})
        context = RunContext(lesson_id="file-edit-evidence", exercise_id="guards", question="", mode="offline",
                             model="local-python", representation="local", inputs=values, api_key="",
                             completion=None, emit_event=lambda kind, data, number: events.append((kind, data)),
                             max_model_calls=1)
        execute_lesson(SPEC, runtime, context)
        self.assertTrue(all(item["passed"] for item in of_pairs(events, "lesson.report")[-1]["checks"]))


def of_pairs(events, kind):
    return [data for event, data in events if event == kind]


class SafetyTests(unittest.TestCase):
    def test_events_never_carry_local_paths(self):
        for exercise in ("replace", "guards"):
            _, events = run_case(exercise)
            text = json.dumps(events, ensure_ascii=False)
            for needle in ("als-sandbox", str(Path.home()), "/tmp/"):
                self.assertNotIn(needle, text, exercise)
        failing = scripted("nothing")
        _, events = run_case("replace", completion=failing)
        self.assertIn("<workspace>", json.dumps(of(events, "tool_result"), ensure_ascii=False) + "<workspace>")

    def test_the_workspace_is_removed_after_a_run_and_after_a_cancelled_one(self):
        seen = []
        real = Workspace

        class Spy(real):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                seen.append(self)
        with mock.patch.object(runtime, "Workspace", Spy):
            run_case("replace")
            run_case("guards")
            ticks = {"n": 0}

            def cancel_midway():
                # Counts how often the platform asks "stopped yet?"; the run is cut off partway through its work.
                ticks["n"] += 1
                return ticks["n"] > 20
            with self.assertRaises(RunCancelled):
                run_case("replace", cancelled=cancel_midway)
        self.assertEqual(len(seen), 7)
        self.assertTrue(all(workspace.closed for workspace in seen))

    def test_the_source_fixture_is_never_modified(self):
        before = {path: sha256((runtime.FIXTURE / path).read_text(encoding="utf-8"))
                  for path in ("shop/pricing.py", "shop/report.py", "tests/test_pricing.py")}
        for exercise in ("rewrite", "replace", "lines", "guards"):
            run_case(exercise)
        after = {path: sha256((runtime.FIXTURE / path).read_text(encoding="utf-8")) for path in before}
        self.assertEqual(before, after)

    def test_the_fixture_repository_starts_with_exactly_the_two_failing_tests(self):
        with Workspace(runtime.FIXTURE) as workspace:
            runner = RestrictedRunner(workspace, timeout=30)
            result = runner.run(runtime.TEST_COMMAND)
        summary = evidence.unittest_summary(result.stderr)
        self.assertEqual((summary["ran"], summary["outcome"], summary["detail"]), (7, "FAILED", "failures=2"))
        self.assertIn("test_new_tier_from_300", result.stderr)
        self.assertIn("test_free_shipping_from_exactly_50", result.stderr)

    def test_the_fixture_anchors_exist_in_the_repository(self):
        text = (runtime.FIXTURE / PATH).read_text(encoding="utf-8")
        for anchor in (OLD_TIER, OLD_SHIPPING):
            self.assertEqual(text.count(anchor), 1)


class InputTests(unittest.TestCase):
    def test_inputs_are_validated(self):
        self.assertEqual(runtime.INPUT_MODEL().model_dump(), {"scenario": "edit", "strategy": "replace", "case": "all"})
        for bad in ({"strategy": "patch"}, {"case": "everything"}, {"scenario": "bash"}, {"unknown": 1}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):
                    runtime.INPUT_MODEL(**bad)

    def test_the_learner_note_only_reaches_the_report(self):
        _, events = run_case("replace", question="my note")
        self.assertEqual(metric(events, "note"), "my note")
        for request in of(events, "request"):
            self.assertNotIn("my note", json.dumps(request, ensure_ascii=False))

    def test_a_stop_request_ends_the_run_before_any_model_call(self):
        with self.assertRaises(RunCancelled):
            run_case("replace", cancelled=lambda: True)


class LocaleTests(unittest.TestCase):
    def test_english_runs_contain_no_chinese(self):
        for exercise in ("rewrite", "replace", "lines", "guards"):
            _, events = run_case(exercise, locale=EN)
            self.assertIsNone(CJK.search(json.dumps(events, ensure_ascii=False)), exercise)

    def test_chinese_runs_speak_chinese_to_the_model_and_in_the_report(self):
        _, events = run_case("replace")
        request = of(events, "request")[0]["body"]
        self.assertEqual(request["messages"][0]["content"], texts_for(ZH).system_prompt)
        self.assertTrue(CJK.search(request["messages"][1]["content"]))
        self.assertEqual(report(events)["title"], "精确替换：edit_file")
        self.assertEqual(report(run_case("replace", locale=EN)[1])["title"], "Exact replace: edit_file")

    def test_the_task_message_lists_the_real_files_and_the_command(self):
        _, events = run_case("replace", locale=EN)
        user = of(events, "request")[0]["body"]["messages"][1]["content"]
        self.assertIn("shop/pricing.py (45 lines)", user)
        self.assertIn(runtime.TEST_COMMAND, user)
        self.assertNotIn("{", user)

    def test_catalogs_agree_on_structure(self):
        zh, en = texts_for(ZH), texts_for(EN)
        for field in zh.__dataclass_fields__:
            first, second = getattr(zh, field), getattr(en, field)
            self.assertIs(type(first), type(second), field)
            if isinstance(first, dict):
                self.assertEqual(set(first), set(second), field)
            if isinstance(first, str):
                self.assertEqual(sorted(re.findall(r"\{\w+\}", first)), sorted(re.findall(r"\{\w+\}", second)), field)

    def test_model_visible_text_is_the_catalogs_text(self):
        t = texts_for(EN)
        _, events = run_case("lines", locale=EN)
        stale = next(data for data in of(events, "tool_result") if data["result"].get("error_type") == "LineNumbersStale")
        self.assertEqual(stale["result"]["error"], t.line_numbers_stale.format(path=PATH))
        tools = of(events, "request")[0]["body"]["tools"]
        self.assertEqual(tools[1]["function"]["description"], t.desc_edit_lines)


if __name__ == "__main__":
    unittest.main()
