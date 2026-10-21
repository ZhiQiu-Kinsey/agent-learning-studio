"""Behavior tests for backup-upgrade. The lesson calls no model; SQLite files, the writer thread and the backups are real.

Lockstep runs are deterministic and are asserted exactly. Free-running runs only get invariants: whether a naive copy
tears depends on timing, and the lesson says so.
"""
import json
import re
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_backup_upgrade import runtime
from lessons.lesson_backup_upgrade.backup import (RestoreError, create_backup, list_backups, load_manifest, prune,
                                                  restore_files, restore_into, verify_backup)
from lessons.lesson_backup_upgrade.checks import (CANARY, find_secrets, inspect_memory, inspect_runs, integrity,
                                                  logical_digest, read_version, service_check)
from lessons.lesson_backup_upgrade.locales import texts_for
from lessons.lesson_backup_upgrade.migrate import Fault, InjectedFault, migrate_memory, migrate_runs, upgrade_files
from lessons.lesson_backup_upgrade.seed import (FILES, LiveWriter, build_data_dir, memory_key, run_id)
from server.run_store import RunStore

ZH, EN = "zh-CN", "en"
CJK = re.compile(r"[　-〿一-鿿＀-￯]")
EXPECTED_EXERCISES = {"online-backup", "restore-drill", "upgrade-rollback", "retention"}


def make_context(inputs, locale=ZH, cancelled=lambda: False, on_event=None):
    events = []

    def emit(kind, data, number):
        events.append((kind, data))
        if on_event:
            on_event(kind, data)
    values = validate_inputs(runtime, inputs)
    context = RunContext(lesson_id="backup-upgrade", exercise_id=values["scenario"], question="", mode="offline",
                         model="local-python", representation="local", inputs=values, api_key="", completion=None,
                         emit_event=emit, cancelled=cancelled, max_model_calls=1, locale=locale)
    return context, events


def run_case(inputs, locale=ZH, **kwargs):
    context, events = make_context(inputs, locale, **kwargs)
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data in events if event == kind]


def checks_of(events):
    report = of(events, "lesson.report")[-1]
    return {check["id"]: check for check in report["checks"]}


def seeded(t_locale=ZH, units=8):
    """A version-1 data directory in a temporary folder; returns (directory object, path, texts)."""
    directory = tempfile.TemporaryDirectory()
    t = texts_for(t_locale)
    data = Path(directory.name) / "data"
    build_data_dir(data, t_locale, t, units=units)
    return directory, data, t


class SeedTests(unittest.TestCase):
    def test_data_dir_is_two_real_databases_in_different_journal_modes(self):
        directory, data, _ = seeded()
        self.addCleanup(directory.cleanup)
        self.assertEqual({read_version(data / name) for name in FILES.values()}, {1})
        modes = {}
        for role, name in FILES.items():
            db = sqlite3.connect(data / name)
            modes[role] = db.execute("PRAGMA journal_mode").fetchone()[0]
            db.close()
        self.assertEqual(modes, {"runs": "wal", "memory": "delete"})
        store = RunStore(data / FILES["runs"])
        self.assertEqual(len(store.list_runs()), 8)
        store.close()

    def test_live_writer_commits_exactly_one_unit_per_step_and_stops_cleanly(self):
        directory, data, t = seeded()
        self.addCleanup(directory.cleanup)
        writer = LiveWriter(data, ZH, t, first=9).start()
        for _ in range(3):
            writer.step()
        self.assertEqual(writer.committed_runs, [run_id(9), run_id(10), run_id(11)])
        self.assertEqual(writer.committed_memories, [memory_key(9), memory_key(10), memory_key(11)])
        writer.stop()
        self.assertFalse(writer._thread.is_alive())
        # The last connection to close checkpoints the log, so the directory is quiet again.
        self.assertEqual(list(data.glob("*.sqlite3-*")), [])

    def test_writer_thread_is_a_separate_thread_with_its_own_connections(self):
        directory, data, t = seeded()
        self.addCleanup(directory.cleanup)
        writer = LiveWriter(data, ZH, t, first=9).start()
        writer.step()
        self.assertNotEqual(writer._thread.ident, threading.get_ident())
        self.assertTrue((data / (FILES["runs"] + "-wal")).exists(), "the runs file keeps its recent commits in the log")
        writer.stop()


class CopyMethodTests(unittest.TestCase):
    """One scenario, four ways to copy: the unsafe one fails the checks, the three safe ones pass."""

    def run_method(self, method, locale=ZH):
        answer, events = run_case({"scenario": "online_backup", "method": method}, locale)
        verdicts = {item["role"]: item for item in of(events, "lesson.backup_check")}
        return answer, events, verdicts

    def test_naive_copy_loses_committed_runs_while_integrity_check_still_says_ok(self):
        _, events, verdicts = self.run_method("naive_copy")
        self.assertEqual(verdicts["runs"]["integrity"], "ok")
        self.assertEqual(verdicts["runs"]["missing"], runtime.WARM_UNITS)
        self.assertFalse(verdicts["runs"]["ok"])
        checks = checks_of(events)
        self.assertTrue(checks["integrity_runs"]["passed"])
        self.assertFalse(checks["rows_runs"]["passed"])

    def test_naive_copy_of_the_rollback_journal_file_is_torn(self):
        _, _, verdicts = self.run_method("naive_copy")
        memory = verdicts["memory"]
        self.assertTrue(memory["readable"])
        self.assertNotEqual(memory["integrity"], "ok")
        self.assertGreater(memory["broken"], 0)

    def test_naive_copy_really_overlapped_with_commits(self):
        _, events, _ = self.run_method("naive_copy")
        backup = of(events, "lesson.backup")[0]
        self.assertGreater(backup["writes_during_copy"], 0)
        self.assertEqual(backup["journal_mode"], {"runs": "wal", "memory": "delete"})
        self.assertIn(FILES["runs"] + "-wal", [item["name"] for item in backup["sidecar_files"]])

    def test_safe_methods_pass_both_checks_with_writes_in_the_middle(self):
        for method in ("backup_api", "vacuum_into", "cold_copy"):
            with self.subTest(method=method):
                answer, events, verdicts = self.run_method(method)
                self.assertTrue(all(item["ok"] for item in verdicts.values()), verdicts)
                self.assertTrue(all(check["passed"] for check in checks_of(events).values()))
                self.assertIn("通过了检查", answer)

    def test_backup_api_restarts_when_writers_commit_and_still_finishes(self):
        _, events, _ = self.run_method("backup_api")
        details = of(events, "lesson.backup")[0]["details"]
        self.assertGreater(details["runs"]["steps"], details["runs"]["pages"], "writes force SQLite to redo steps")
        self.assertGreater(of(events, "lesson.backup")[0]["writes_during_copy"], 0)

    def test_vacuum_into_snapshot_excludes_commits_made_while_it_reads(self):
        _, events, verdicts = self.run_method("vacuum_into")
        backup = of(events, "lesson.backup")[0]
        self.assertEqual(backup["writes_during_copy"], runtime.DURING_COPY, "the WAL file is copied while a writer commits")
        committed = runtime.SEED_UNITS + runtime.WARM_UNITS
        self.assertEqual(verdicts["runs"]["rows"], committed, "the snapshot is the moment the statement started")
        self.assertTrue(all(item["ok"] for item in verdicts.values()))

    def test_cold_copy_has_no_writes_and_no_leftover_log(self):
        _, events, _ = self.run_method("cold_copy")
        self.assertEqual(of(events, "lesson.backup")[0]["writes_during_copy"], 0)

    def test_free_running_schedule_keeps_the_safe_methods_safe(self):
        for method in ("backup_api", "vacuum_into", "cold_copy"):
            with self.subTest(method=method):
                _, events = run_case({"scenario": "online_backup", "method": method, "schedule": "free"})
                self.assertTrue(all(item["ok"] for item in of(events, "lesson.backup_check")))
        # The naive copy always loses the logged commits; whether the other file tears depends on timing.
        _, events = run_case({"scenario": "online_backup", "method": "naive_copy", "schedule": "free"})
        runs = next(item for item in of(events, "lesson.backup_check") if item["role"] == "runs")
        self.assertEqual(runs["missing"], runtime.WARM_UNITS)

    def test_inspections_read_files_not_labels(self):
        directory, data, t = seeded()
        self.addCleanup(directory.cleanup)
        committed = [run_id(n) for n in range(1, 9)]
        copy = Path(directory.name) / "copy"
        create_backup(data, copy)
        self.assertTrue(inspect_runs(copy / FILES["runs"], committed)["ok"])
        self.assertEqual(inspect_runs(copy / FILES["runs"], committed + ["run-9999"])["missing"], 1)
        # A file that is not a database is reported, not raised.
        junk = Path(directory.name) / "junk.sqlite3"
        junk.write_bytes(b"not a database" * 100)
        self.assertFalse(inspect_memory(junk, [])["readable"])
        self.assertNotEqual(integrity(junk), "ok")


class ManifestAndRestoreTests(unittest.TestCase):
    def setUp(self):
        self.directory, self.data, self.t = seeded(units=10)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_manifest_describes_files_as_they_landed(self):
        manifest = create_backup(self.data, self.root / "b1")
        stored = load_manifest(self.root / "b1")
        self.assertEqual({item["role"] for item in stored["files"]}, {"runs", "memory"})
        for entry in stored["files"]:
            self.assertEqual(entry["schema_version"], 1)
            self.assertEqual(entry["integrity_check"], "ok")
            self.assertEqual(len(entry["sha256"]), 64)
        self.assertEqual(stored["counts"]["runs"], 10)
        self.assertEqual(stored["content_digest"], logical_digest(self.data))
        self.assertTrue(verify_backup(self.root / "b1")["ok"])
        # Backup files are single self-contained files: no write-ahead log travels with them.
        self.assertEqual(sorted(p.name for p in (self.root / "b1").iterdir()), ["manifest.json", "memory.sqlite3",
                                                                                "runs.sqlite3"])
        self.assertEqual(manifest["method"], "backup_api")

    def test_verify_catches_a_flipped_byte_that_integrity_check_misses(self):
        create_backup(self.data, self.root / "b1")
        damage = runtime.damage_file(self.root / "b1" / FILES["memory"], "bit_flip")
        self.assertEqual(integrity(self.root / "b1" / FILES["memory"], immutable=True), "ok")
        verdict = verify_backup(self.root / "b1")
        self.assertFalse(verdict["ok"])
        self.assertEqual([row["name"] for row in verdict["files"] if not row["ok"]], [FILES["memory"]])
        self.assertEqual(damage["byte_before"], "33")
        self.assertEqual(damage["byte_after"], "32")

    def test_verify_catches_truncation_and_missing_manifest(self):
        create_backup(self.data, self.root / "b1")
        runtime.damage_file(self.root / "b1" / FILES["runs"], "truncated")
        self.assertFalse(verify_backup(self.root / "b1")["ok"])
        (self.root / "b1" / "manifest.json").unlink()
        self.assertEqual(verify_backup(self.root / "b1"), {"ok": False, "manifest": False, "files": []})

    def test_restore_gives_a_service_that_reads_runs_and_recalls_memory(self):
        create_backup(self.data, self.root / "b1")
        self.assertEqual(restore_files(self.root / "b1", self.root / "new"), [FILES["runs"], FILES["memory"]])
        facts = service_check(self.root / "new", 1, ZH, logical_digest(self.data))
        self.assertTrue(facts["ok"], facts)
        self.assertEqual((facts["runs_read"], facts["memories_recalled"]), (10, 10))

    def test_restore_refuses_a_file_that_differs_from_the_manifest(self):
        create_backup(self.data, self.root / "b1")
        runtime.damage_file(self.root / "b1" / FILES["memory"], "bit_flip")
        with self.assertRaises(RestoreError):
            restore_files(self.root / "b1", self.root / "new")
        # With checking off the damaged file is copied, and only the content digest notices.
        restore_files(self.root / "b1", self.root / "new2", check=False)
        facts = service_check(self.root / "new2", 1, ZH, logical_digest(self.data))
        self.assertTrue(facts["integrity_ok"])
        self.assertTrue(facts["memory_ok"], "recall still works on the wrong data")
        self.assertFalse(facts["digest_ok"])
        self.assertFalse(facts["ok"])

    def test_backup_scope_decides_whether_a_key_goes_along(self):
        create_backup(self.data, self.root / "narrow")
        create_backup(self.data, self.root / "wide", scope="whole_directory")
        self.assertEqual(find_secrets(self.root / "narrow"), [])
        self.assertEqual(find_secrets(self.root / "wide"), ["local_config.py"])
        # The config is part of the backup but is not restored into a new directory.
        restore_files(self.root / "wide", self.root / "new")
        self.assertFalse((self.root / "new" / "local_config.py").exists())

    def test_restore_into_parks_the_old_files_and_does_not_leave_a_stale_log(self):
        create_backup(self.data, self.root / "b1")
        writer = LiveWriter(self.data, ZH, self.t, first=11).start()
        writer.step()
        writer.stop()
        (self.data / (FILES["runs"] + "-wal")).write_bytes(b"stale log that must not meet the restored file")
        restore_into(self.root / "b1", self.data)
        self.assertEqual(list(self.data.glob("*.sqlite3-*")), [])
        self.assertTrue((self.data / "_failed_upgrade" / FILES["runs"]).exists())
        self.assertEqual(service_check(self.data, 1, ZH)["runs_read"], 10)

    def test_retention_orders_by_manifest_clock_and_keeps_a_verified_backup(self):
        for index in range(1, 6):
            create_backup(self.data, self.root / "backups" / f"backup-{index:03d}", seq=index)
        self.assertEqual([item["id"] for item in list_backups(self.root / "backups")][:2], ["backup-005", "backup-004"])
        for name in ("backup-005", "backup-004"):
            runtime.damage_file(self.root / "backups" / name / FILES["memory"], "bit_flip")
        result = prune(self.root / "backups", 2, keep_verified=True)
        self.assertEqual(sorted(result["kept"]), ["backup-003", "backup-004", "backup-005"])
        self.assertEqual(sorted(result["removed"]), ["backup-001", "backup-002"])
        self.assertTrue(all(verify_backup(self.root / "backups" / name)["ok"] is False for name in ("backup-004",)))
        # Without the extra rule the same damage leaves nothing restorable.
        result = prune(self.root / "backups", 2, keep_verified=False)
        self.assertEqual(sorted(result["kept"]), ["backup-004", "backup-005"])
        self.assertFalse(any(result["verified"][name] for name in result["kept"]))


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory, self.data, self.t = seeded(units=14)
        self.addCleanup(self.directory.cleanup)
        self.before = logical_digest(self.data)

    def test_clean_migration_keeps_every_row_and_changes_the_schema(self):
        steps = []
        self.assertIsNone(upgrade_files(self.data, Fault(), transactional=True, on_step=steps.append))
        self.assertEqual([step["status"] for step in steps], ["committed", "committed"])
        self.assertEqual({read_version(self.data / name) for name in FILES.values()}, {2})
        facts = service_check(self.data, 2, ZH, self.before)
        self.assertTrue(facts["ok"], facts)
        db = sqlite3.connect(self.data / FILES["memory"])
        self.assertEqual(db.execute("SELECT typeof(updated_at) FROM memories LIMIT 1").fetchone()[0], "text")
        db.close()

    def test_version_1_service_cannot_read_the_migrated_runs_file(self):
        upgrade_files(self.data, Fault(), transactional=True, on_step=lambda step: None)
        facts = service_check(self.data, 1, ZH)
        self.assertFalse(facts["ok"])
        self.assertIn("no such column", facts["runs_error"])

    def test_transaction_rolls_back_the_failed_file_completely(self):
        fault = Fault("abort", "memory", 3, "boom")
        steps = []
        error = upgrade_files(self.data, fault, transactional=True, on_step=steps.append)
        self.assertIsInstance(error, InjectedFault)
        self.assertEqual(steps[0]["status"], "rolled_back")
        self.assertTrue(steps[0]["injected"])
        self.assertEqual(steps[0]["leftover_tables"], [])
        self.assertEqual(logical_digest(self.data), self.before)
        self.assertTrue(service_check(self.data, 1, ZH, self.before)["ok"])

    def test_without_a_transaction_a_failed_migration_leaves_half_the_work(self):
        steps = []
        error = upgrade_files(self.data, Fault("abort", "runs", 3, "boom"), transactional=False, on_step=steps.append)
        self.assertIsInstance(error, InjectedFault)
        self.assertEqual([step["status"] for step in steps], ["applied", "left_partial"])
        self.assertEqual(steps[1]["version_in_file"], 1, "the version stamp is the last step, so it never happened")
        db = sqlite3.connect(self.data / FILES["runs"])
        columns = [row[1] for row in db.execute("PRAGMA table_info(runs)")]
        filled = db.execute("SELECT COUNT(*) FROM runs WHERE event_count IS NOT NULL").fetchone()[0]
        db.close()
        self.assertIn("provenance_kind", columns)
        self.assertEqual(filled, 3)
        self.assertNotIn("provenance", columns)

    def test_a_failed_copy_without_a_transaction_leaves_a_stray_table(self):
        steps = []
        upgrade_files(self.data, Fault("abort", "memory", 3, "boom"), transactional=False, on_step=steps.append)
        self.assertEqual(steps[0]["leftover_tables"], ["memories_v2"])

    def test_migrations_can_be_run_again_after_a_partial_failure(self):
        for role, abort in (("memory", migrate_memory), ("runs", migrate_runs)):
            with self.assertRaises(InjectedFault):
                abort(self.data / FILES[role], transactional=False, fault=Fault("abort", role, 3, "boom"))
        migrate_memory(self.data / FILES["memory"], transactional=False, fault=Fault())
        migrate_runs(self.data / FILES["runs"], transactional=False, fault=Fault())
        self.assertTrue(service_check(self.data, 2, ZH, self.before)["ok"])

    def test_buggy_migration_commits_and_only_the_digest_notices(self):
        error = upgrade_files(self.data, Fault("bug", "memory", 0, ""), transactional=True, on_step=lambda step: None)
        self.assertIsNone(error)
        facts = service_check(self.data, 2, ZH, self.before)
        self.assertTrue(facts["versions_ok"] and facts["integrity_ok"] and facts["runs_ok"] and facts["memory_ok"])
        self.assertFalse(facts["digest_ok"])
        self.assertFalse(facts["ok"])
        self.assertEqual(facts["memories_stored"], 11, "14 rows, 3 batches of 5, 3 first rows dropped")


class ScenarioTests(unittest.TestCase):
    def test_restore_drill_clean_passes_every_check(self):
        answer, events = run_case({"scenario": "restore_drill"})
        checks = checks_of(events)
        self.assertEqual(set(checks), {"no_secrets", "manifest_verified", "runs_readable", "memory_recallable",
                                       "integrity", "digest_matches"})
        self.assertTrue(all(check["passed"] for check in checks.values()), checks)
        self.assertEqual(of(events, "lesson.restore")[0]["performed"], True)
        self.assertEqual(of(events, "lesson.memory")[0]["action"], "recalled")
        self.assertIn("可读", answer)

    def test_restore_drill_bit_flip_is_refused_before_anything_is_served(self):
        answer, events = run_case({"scenario": "restore_drill", "damage": "bit_flip"})
        self.assertEqual(of(events, "lesson.fault")[0]["origin"], "fault_injection")
        self.assertEqual(of(events, "lesson.verify")[0]["integrity_of_memory_file"], "ok")
        self.assertFalse(of(events, "lesson.verify")[0]["ok"])
        self.assertEqual(of(events, "lesson.restore")[0], {"performed": False, "reason": "manifest_mismatch"})
        checks = checks_of(events)
        self.assertFalse(checks["manifest_verified"]["passed"])
        self.assertTrue(checks["damage_caught"]["passed"])
        self.assertNotIn("runs_readable", checks)
        self.assertEqual(of(events, "lesson.memory"), [])
        self.assertIn("拒绝", answer)

    def test_restore_drill_without_the_manifest_check_only_the_digest_notices(self):
        answer, events = run_case({"scenario": "restore_drill", "damage": "bit_flip", "verify_manifest": False})
        checks = checks_of(events)
        self.assertNotIn("manifest_verified", checks)
        self.assertTrue(checks["runs_readable"]["passed"] and checks["memory_recallable"]["passed"])
        self.assertTrue(checks["integrity"]["passed"])
        self.assertFalse(checks["digest_matches"]["passed"])
        self.assertTrue(checks["damage_caught"]["passed"])
        self.assertIn("不能用", answer)

    def test_restore_drill_truncated_file_fails_acceptance(self):
        _, events = run_case({"scenario": "restore_drill", "damage": "truncated", "verify_manifest": False})
        checks = checks_of(events)
        self.assertFalse(checks["memory_recallable"]["passed"])
        self.assertFalse(checks["integrity"]["passed"])

    def test_whole_directory_scope_fails_the_secret_check_without_printing_the_secret(self):
        answer, events = run_case({"scenario": "restore_drill", "scope": "whole_directory"})
        checks = checks_of(events)
        self.assertFalse(checks["no_secrets"]["passed"])
        self.assertEqual(of(events, "lesson.secret_scan")[0]["found"], ["local_config.py"])
        self.assertIn("local_config.py", checks["no_secrets"]["detail"])
        self.assertNotIn(CANARY, json.dumps(events, ensure_ascii=False))
        self.assertIn("密钥", answer)

    def test_upgrade_matrix(self):
        """failure x safeguard -> (upgrade completed, service available after, final schema versions)."""
        expected = {
            ("none", "none"): (True, True, "2/2"), ("none", "transaction"): (True, True, "2/2"),
            ("none", "backup"): (True, True, "2/2"),
            ("fail_first_file", "none"): (False, True, "1/1"),  # the copy only touched a new table
            ("fail_first_file", "transaction"): (False, True, "1/1"),
            ("fail_first_file", "backup"): (False, True, "1/1"),
            ("fail_second_file", "none"): (False, False, "1/2"),
            ("fail_second_file", "transaction"): (False, False, "1/2"),  # a transaction cannot span two files
            ("fail_second_file", "backup"): (False, True, "1/1"),
            ("bad_result", "none"): (False, False, "2/2"),
            ("bad_result", "transaction"): (False, False, "2/2"),  # it committed: nothing to roll back
            ("bad_result", "backup"): (False, True, "1/1"),
        }
        for (failure, safeguard), (completed, available, versions) in expected.items():
            with self.subTest(failure=failure, safeguard=safeguard):
                _, events = run_case({"scenario": "upgrade_rollback", "failure": failure, "safeguard": safeguard})
                checks = checks_of(events)
                report = of(events, "lesson.report")[-1]
                versions_metric = next(m for m in report["metrics"] if m.get("id") == "final_versions")["value"]
                self.assertEqual((checks["upgrade_completed"]["passed"], checks["service_available"]["passed"],
                                  versions_metric), (completed, available, versions))
                if available:
                    self.assertTrue(checks["data_unchanged"]["passed"])

    def test_a_committed_wrong_result_has_nothing_to_roll_back(self):
        answer, events = run_case({"scenario": "upgrade_rollback", "failure": "bad_result", "safeguard": "transaction"})
        rollback = of(events, "lesson.rollback")[0]
        self.assertEqual((rollback["method"], rollback["ok"]), ("transaction", False))
        self.assertIn("没有可回滚", answer)
        _, events = run_case({"scenario": "upgrade_rollback", "failure": "fail_first_file", "safeguard": "transaction"})
        self.assertTrue(of(events, "lesson.rollback")[0]["ok"])

    def test_every_injected_fault_is_announced_with_its_origin(self):
        for failure in ("fail_first_file", "fail_second_file", "bad_result"):
            with self.subTest(failure=failure):
                _, events = run_case({"scenario": "upgrade_rollback", "failure": failure})
                faults = of(events, "lesson.fault")
                self.assertEqual(len(faults), 1)
                self.assertEqual(faults[0]["origin"], "fault_injection")
        _, events = run_case({"scenario": "upgrade_rollback", "failure": "fail_second_file"})
        failed = [step for step in of(events, "lesson.migration") if step["status"] != "committed"]
        self.assertTrue(failed[0]["injected"])

    def test_backup_safeguard_records_the_backup_and_the_rollback(self):
        _, events = run_case({"scenario": "upgrade_rollback", "failure": "fail_second_file", "safeguard": "backup"})
        order = [kind for kind, _ in events if kind.startswith("lesson.") and kind != "lesson.memory"]
        self.assertEqual(order, ["lesson.backup", "lesson.fault", "lesson.migration", "lesson.migration",
                                 "lesson.rollback", "lesson.report"])
        self.assertEqual(of(events, "lesson.rollback")[0], {"method": "restore_from_backup", "ok": True})
        self.assertTrue(checks_of(events)["no_secrets"]["passed"])

    def test_retention_policies(self):
        _, events = run_case({"scenario": "retention", "keep": 2, "corrupt_newest": 2, "policy": "newest_n"})
        self.assertFalse(checks_of(events)["restorable_after_prune"]["passed"])
        self.assertEqual(of(events, "lesson.retention")[0]["kept"], ["backup-006", "backup-005"])
        answer, events = run_case({"scenario": "retention", "keep": 2, "corrupt_newest": 2,
                                   "policy": "newest_n_keep_verified"})
        checks = checks_of(events)
        self.assertTrue(checks["restorable_after_prune"]["passed"])
        self.assertFalse(checks["newest_kept_verified"]["passed"])
        self.assertEqual(sorted(of(events, "lesson.retention")[0]["kept"]), ["backup-004", "backup-005", "backup-006"])
        self.assertIn("backup-004", answer)
        _, events = run_case({"scenario": "retention", "keep": 3})
        self.assertTrue(all(check["passed"] for check in checks_of(events).values()))

    def test_no_scenario_calls_a_model_or_sends_a_request(self):
        for inputs in ({"scenario": "online_backup"}, {"scenario": "restore_drill"}, {"scenario": "upgrade_rollback"},
                       {"scenario": "retention"}):
            with self.subTest(inputs=inputs):
                _, events = run_case(inputs)
                self.assertEqual([kind for kind, _ in events if kind in ("request", "response")], [])
                report = of(events, "lesson.report")[-1]
                self.assertEqual(next(m for m in report["metrics"] if m["label"] == "模型调用数")["value"], 0)


class RuntimeContractTests(unittest.TestCase):
    def test_both_run_languages_run_every_exercise(self):
        for locale in (ZH, EN):
            for scenario in ("online_backup", "restore_drill", "upgrade_rollback", "retention"):
                with self.subTest(locale=locale, scenario=scenario):
                    answer, events = run_case({"scenario": scenario}, locale)
                    self.assertTrue(answer)
                    dumped = json.dumps(events, ensure_ascii=False)
                    self.assertEqual(bool(CJK.search(dumped)), locale == ZH, "event language follows the run language")

    def test_english_runs_with_faults_have_no_chinese_either(self):
        for inputs in ({"scenario": "restore_drill", "damage": "bit_flip"},
                       {"scenario": "restore_drill", "scope": "whole_directory"},
                       {"scenario": "upgrade_rollback", "failure": "fail_second_file", "safeguard": "none"},
                       {"scenario": "upgrade_rollback", "failure": "bad_result"},
                       {"scenario": "retention", "keep": 1, "corrupt_newest": 3, "policy": "newest_n"}):
            with self.subTest(inputs=inputs):
                answer, events = run_case(inputs, EN)
                self.assertFalse(CJK.search(json.dumps([answer, events], ensure_ascii=False)))

    def test_events_hold_no_local_paths_and_no_secret(self):
        scratch = tempfile.gettempdir()
        for inputs in ({"scenario": "online_backup", "method": "naive_copy"},
                       {"scenario": "restore_drill", "scope": "whole_directory", "damage": "truncated"},
                       {"scenario": "upgrade_rollback", "failure": "fail_second_file"},
                       {"scenario": "retention", "corrupt_newest": 1}):
            with self.subTest(inputs=inputs):
                _, events = run_case(inputs)
                dumped = json.dumps(events, ensure_ascii=False)
                self.assertNotIn(scratch, dumped)
                self.assertNotIn("backup-upgrade-", dumped)
                self.assertNotIn(CANARY, dumped)

    def test_only_the_lesson_event_family_and_the_answer_are_emitted(self):
        _, events = run_case({"scenario": "upgrade_rollback", "failure": "fail_second_file"})
        for kind, _ in events:
            self.assertTrue(kind.startswith("lesson.") or kind == "answer", kind)

    def test_temporary_directory_and_writer_thread_are_cleaned_up(self):
        with tempfile.TemporaryDirectory() as scratch, mock.patch.object(tempfile, "tempdir", scratch):
            run_case({"scenario": "online_backup", "method": "naive_copy"})
            run_case({"scenario": "upgrade_rollback", "failure": "bad_result"})
            self.assertEqual(list(Path(scratch).iterdir()), [])
        self.assertFalse([thread for thread in threading.enumerate() if thread.name == "backup-upgrade-writer"])

    def test_stopping_mid_run_stops_the_writer_and_removes_the_files(self):
        with tempfile.TemporaryDirectory() as scratch, mock.patch.object(tempfile, "tempdir", scratch):
            seen = []

            def cancelled():
                return len(seen) >= 1  # cancel as soon as the first lesson event has been published
            with self.assertRaises(RunCancelled):
                run_case({"scenario": "online_backup", "method": "naive_copy"}, cancelled=cancelled,
                         on_event=lambda kind, data: seen.append(kind))
            self.assertEqual(list(Path(scratch).iterdir()), [])
        self.assertFalse([thread for thread in threading.enumerate() if thread.name == "backup-upgrade-writer"])

    def test_runs_never_touch_the_real_runtime_directory(self):
        real = Path(runtime.__file__).resolve().parents[2] / ".runtime"
        before = sorted(path.name for path in real.rglob("*")) if real.exists() else None
        run_case({"scenario": "upgrade_rollback", "failure": "fail_second_file", "safeguard": "backup"})
        run_case({"scenario": "restore_drill"})
        self.assertEqual(sorted(path.name for path in real.rglob("*")) if real.exists() else None, before)


class InputTests(unittest.TestCase):
    def test_inputs_are_validated(self):
        for bad in ({"scenario": "everything"}, {"method": "rsync"}, {"keep": 0}, {"keep": 6},
                    {"corrupt_newest": 4}, {"damage": "melt"}, {"verify_manifest": "maybe"}, {"extra": 1},
                    {"safeguard": "hope"}, {"failure": "random"}, {"policy": "all"}, {"scope": "disk"},
                    {"schedule": "fast"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                runtime.Inputs.model_validate(bad)
        self.assertEqual(runtime.Inputs.model_validate({}).scenario, "online_backup")

    def test_lesson_manifest_lists_the_four_exercises(self):
        manifest = json.loads((Path(runtime.__file__).parent / "lesson.json").read_text(encoding="utf-8"))
        self.assertEqual({item["id"] for item in manifest["exercises"]}, EXPECTED_EXERCISES)
        self.assertFalse(manifest["runtime"]["requires_model"])
        for item in manifest["exercises"]:
            runtime.Inputs.model_validate(item["inputs"])


if __name__ == "__main__":
    unittest.main()
