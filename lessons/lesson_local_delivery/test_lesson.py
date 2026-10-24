"""Behavior tests for local-delivery. The lesson calls no model: the notes app really starts as a child process,
really listens on a loopback port, really refuses bad configuration, and is really killed. Every credential in
these tests is a made-up string, and the tests check that it appears in no event, answer, log shown or response."""
import json
import os
import re
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_local_delivery import logscan, runtime
from lessons.lesson_local_delivery.launcher import (AppProcess, child_environment, credential_env, http_probe,
                                                other_interface_address, pid_alive, port_accepts, wait_gone)
from lessons.lesson_local_delivery.locales import texts_for
from lessons.lesson_local_delivery.notes_store import InvalidNote, LimitReached, NotesStore, StoreCorrupt
from lessons.lesson_local_delivery.settings import (LOOPBACK_HOST, SETTINGS, SettingsError, load_settings, read_file,
                                                    secret_values)

ZH, EN = "zh-CN", "en"
SECRET = "sk-demo-TESTONLY0123456789ab"
PARENT_DECOY = "sk-parent-DECOY9876543210zz"
CJK = re.compile(r"[　-〿一-鿿＀-￯]")
SPEC = {"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}
SCENARIOS = ("config_layers", "startup_probe", "logs_secrets", "restart_rollback")
POSIX = os.name != "nt"


def make_context(inputs, locale=ZH, cancelled=lambda: False, on_event=None):
    events = []

    def emit(kind, data, number):
        events.append((kind, data, number))
        if on_event:
            on_event(kind, data)
    values = validate_inputs(runtime, inputs)
    context = RunContext(lesson_id="local-delivery", exercise_id=values["scenario"], question="", mode="offline",
                         model="local-python", representation="local", inputs=values, api_key="", completion=None,
                         max_model_calls=1, cancelled=cancelled, emit_event=emit, locale=locale)
    return context, events


def run_case(scenario, locale=ZH, **inputs):
    context, events = make_context({"scenario": scenario, **inputs}, locale)
    answer = execute_lesson(SPEC, runtime, context)
    return answer, events


def reports(events):
    return {number: data for kind, data, number in events if kind == "lesson.report"}


def check(report, check_id):
    return next(item for item in report["checks"] if item["id"] == check_id)


def metric(report, metric_id):
    return next(item for item in report["metrics"] if item["id"] == metric_id)["value"]


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


class Workdir(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ld-test-")
        self.addCleanup(self.directory.cleanup)
        self.workdir = Path(self.directory.name)


class SettingsTests(Workdir):
    def file(self, content):
        path = self.workdir / "settings.json"
        path.write_text(json.dumps(content), encoding="utf-8")
        return path

    def test_precedence_default_then_file_then_environment(self):
        path = self.file({"settings_version": 1, "model": "from-file", "log_level": "debug", "max_notes": 7})
        resolved = load_settings(path, {"NOTES_MODEL": "from-env", "NOTES_API_KEY": "k", "NOTES_MAX_NOTES": "9"})
        self.assertEqual((resolved.values["model"], resolved.sources["model"]), ("from-env", "env"))
        self.assertEqual((resolved.values["max_notes"], resolved.sources["max_notes"]), (9, "env"))
        self.assertEqual((resolved.values["log_level"], resolved.sources["log_level"]), ("debug", "file"))
        self.assertEqual((resolved.values["host"], resolved.sources["host"]), (LOOPBACK_HOST, "default"))

    def test_every_problem_is_listed_and_none_carries_a_value(self):
        with self.assertRaises(SettingsError) as caught:
            load_settings(None, {"NOTES_PORT": "99999-not-a-port", "NOTES_LOG_LEVEL": "shout"})
        found = {(problem.name, problem.code) for problem in caught.exception.problems}
        self.assertEqual(found, {("model", "missing"), ("api_key", "missing"), ("port", "invalid"),
                                 ("log_level", "invalid")})
        self.assertNotIn("99999", str(caught.exception))
        self.assertNotIn("shout", repr(caught.exception.problems))

    def test_a_credential_in_the_file_and_an_unknown_key_are_refused(self):
        path = self.file({"settings_version": 1, "model": "m", "api_key": SECRET, "log_lvl": "debug"})
        with self.assertRaises(SettingsError) as caught:
            load_settings(path, {"NOTES_API_KEY": "valid-from-env"})
        found = {(problem.name, problem.code) for problem in caught.exception.problems}
        self.assertEqual(found, {("api_key", "secret_in_file"), ("log_lvl", "unknown_key")})
        self.assertNotIn(SECRET, str(caught.exception))

    def test_a_bad_value_is_not_replaced_by_a_lower_layer(self):
        path = self.file({"settings_version": 1, "model": "m", "max_notes": 10})
        with self.assertRaises(SettingsError) as caught:
            load_settings(path, {"NOTES_API_KEY": "k", "NOTES_MAX_NOTES": "zero"})
        self.assertEqual([(p.name, p.code) for p in caught.exception.problems], [("max_notes", "invalid")])

    def test_only_loopback_and_relative_data_dir_are_accepted(self):
        base = {"NOTES_MODEL": "m", "NOTES_API_KEY": "k"}
        for name, value in (("NOTES_HOST", "0.0.0.0"), ("NOTES_HOST", "localhost"), ("NOTES_DATA_DIR", "/etc"),
                            ("NOTES_DATA_DIR", "../outside"), ("NOTES_PORT", "70000"), ("NOTES_MAX_NOTES", "0")):
            with self.subTest(name=name, value=value), self.assertRaises(SettingsError):
                load_settings(None, {**base, name: value})

    def test_unusable_file_and_unsupported_version(self):
        broken = self.workdir / "settings.json"
        broken.write_text("{not json", encoding="utf-8")
        self.assertEqual(read_file(broken)[1][0].code, "file_unreadable")
        self.assertEqual(read_file(self.workdir / "missing.json")[1][0].code, "file_unreadable")
        path = self.file({"settings_version": 2, "model_id": "m"})
        codes = {(p.name, p.code) for p in read_file(path)[1]}
        self.assertEqual(codes, {("settings_version", "unsupported_version"), ("model_id", "unknown_key")})

    def test_empty_environment_value_counts_as_unset_and_unknown_names_only_warn(self):
        resolved = load_settings(None, {"NOTES_MODEL": "m", "NOTES_API_KEY": "k", "NOTES_PORT": "", "NOTES_MODLE": "x",
                                        "PATH": "/bin"})
        self.assertEqual(resolved.sources["port"], "default")
        self.assertEqual([(w.name, w.code) for w in resolved.warnings], [("NOTES_MODLE", "unknown_env")])

    def test_public_view_never_shows_a_secret_value(self):
        resolved = load_settings(None, {"NOTES_MODEL": "m", "NOTES_API_KEY": SECRET})
        text = json.dumps(resolved.public())
        self.assertNotIn(SECRET, text)
        row = next(item for item in resolved.public() if item["name"] == "api_key")
        self.assertEqual((row["set"], row["source"], "value" in row), (True, "env", False))
        self.assertEqual(secret_values({"NOTES_API_KEY": SECRET}), {"api_key": SECRET})
        self.assertEqual([s.name for s in SETTINGS if s.secret], ["api_key"])


class StoreTests(Workdir):
    def test_repeated_op_id_returns_the_first_note_and_writes_nothing(self):
        store = NotesStore(self.workdir / "data" / "notes.json", 5)
        first, duplicate = store.add("op-1", "a")
        self.assertFalse(duplicate)
        before = (self.workdir / "data" / "notes.json").read_bytes()
        again, duplicate = store.add("op-1", "different text")
        self.assertTrue(duplicate)
        self.assertEqual(again, first)
        self.assertEqual((self.workdir / "data" / "notes.json").read_bytes(), before)

    def test_limit_validation_and_no_temp_files_left(self):
        store = NotesStore(self.workdir / "data" / "notes.json", 1)
        store.add("a", "x")
        with self.assertRaises(LimitReached):
            store.add("b", "y")
        for op_id, text in (("Bad Id", "x"), ("ok", ""), ("ok", "x" * 201), (1, "x"), ("ok", None)):
            with self.subTest(op_id=op_id), self.assertRaises(InvalidNote):
                store.add(op_id, text)
        self.assertEqual([path.name for path in (self.workdir / "data").iterdir()], ["notes.json"])

    def test_reload_and_corrupt_file(self):
        path = self.workdir / "notes.json"
        NotesStore(path, 5).add("a", "x")
        self.assertEqual([note["op_id"] for note in NotesStore(path, 5).snapshot()], ["a"])
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(StoreCorrupt):
            NotesStore(path, 5)
        path.write_text(json.dumps({"notes": [1, 2]}), encoding="utf-8")
        with self.assertRaises(StoreCorrupt):
            NotesStore(path, 5)

    def test_a_failed_write_does_not_leave_the_note_in_memory(self):
        store = NotesStore(self.workdir / "notes.json", 5)
        with mock.patch("os.replace", side_effect=OSError("disk full")), self.assertRaises(OSError):
            store.add("a", "x")
        self.assertEqual(store.snapshot(), [])
        self.assertEqual(list(self.workdir.iterdir()), [])


class LogScanTests(unittest.TestCase):
    def test_structure_lifecycle_and_leaks(self):
        good = "\n".join(json.dumps({"ts": "t", "level": "info", "event": name}) for name in logscan.LIFECYCLE)
        lines = logscan.parse(good)
        self.assertTrue(logscan.structured(lines))
        self.assertTrue(logscan.lifecycle_in_order(lines))
        self.assertFalse(logscan.structured(logscan.parse(good + "\nplain text line")))
        self.assertFalse(logscan.structured(logscan.parse('{"level": "info", "event": "x"}')))
        swapped = "\n".join(json.dumps({"ts": "t", "level": "i", "event": n}) for n in reversed(logscan.LIFECYCLE))
        self.assertFalse(logscan.lifecycle_in_order(logscan.parse(swapped)))
        leaky = logscan.parse(good + "\n" + json.dumps({"ts": "t", "level": "info", "event": "dump", "k": SECRET}))
        found = logscan.leaks(leaky, {"api_key": SECRET})
        self.assertEqual([(leak.line, leak.event, leak.setting) for leak in found], [(7, "dump", "api_key")])

    def test_redact_replaces_every_occurrence_and_the_result_scans_clean(self):
        text = f"a {SECRET} b {SECRET}"
        shown = logscan.redact(text, {"api_key": SECRET})
        self.assertEqual(shown, "a [REDACTED:api_key] b [REDACTED:api_key]")
        self.assertEqual(logscan.scan_text(shown, {"api_key": SECRET}), [])
        self.assertEqual(logscan.scan_text(text, {"api_key": SECRET, "other": ""}), ["api_key"])


class LauncherTests(Workdir):
    def test_child_environment_keeps_nothing_but_the_allow_list_and_the_extras(self):
        with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": PARENT_DECOY, "OPENAI_API_KEY": PARENT_DECOY}):
            environment = child_environment({"NOTES_API_KEY": SECRET})
        self.assertNotIn(PARENT_DECOY, json.dumps(environment))
        self.assertEqual(environment["NOTES_API_KEY"], SECRET)
        self.assertLessEqual(set(environment) - {"NOTES_API_KEY"}, set(os.environ))

    def test_other_interface_address_is_not_loopback(self):
        address = other_interface_address()
        self.assertTrue(address is None or not address.startswith("127."))

    def test_the_whole_group_is_reaped_when_the_block_ends(self):
        with AppProcess(self.workdir, credential_env(SECRET)) as app:
            app.start()
            self.assertEqual(app.wait_listening(10, lambda: None).state, "listening")
            app.note_worker()
            self.assertEqual(len(app.pids), 2)
            self.assertTrue(all(pid_alive(pid) for pid in app.pids))
            port = app.port
        self.assertEqual(wait_gone(app.pids, 3.0), [])
        self.assertFalse(port_accepts(port))

    def test_a_graceful_stop_removes_the_worker_too_and_a_leader_kill_does_not(self):
        with AppProcess(self.workdir, credential_env(SECRET), name="a") as app:
            app.start()
            app.wait_listening(10, lambda: None)
            app.note_worker()
            stopped = app.stop()
            self.assertEqual(wait_gone(app.pids, 3.0), [])
        if POSIX:
            self.assertEqual((stopped.method, stopped.exit_code), ("graceful", 0))
        with AppProcess(self.workdir, credential_env(SECRET), name="b") as app:
            app.start()
            app.wait_listening(10, lambda: None)
            app.note_worker()
            app.kill_leader()
            self.assertEqual(wait_gone(app.pids, 0.3), [app.worker_pid])
        self.assertEqual(wait_gone(app.pids, 3.0), [])

    def test_the_app_binds_loopback_only_and_refuses_another_host(self):
        with AppProcess(self.workdir, credential_env(SECRET, NOTES_HOST="0.0.0.0")) as app:
            app.start()
            result = app.wait_listening(10, lambda: None)
        self.assertEqual((result.state, result.exit_code), ("exited", 2))
        lines = logscan.parse(app.log_text())
        self.assertEqual(logscan.find(lines, "config_invalid")["problems"], [{"name": "host", "code": "invalid"}])
        with AppProcess(self.workdir, credential_env(SECRET), name="ok") as app:
            app.start()
            app.wait_listening(10, lambda: None)
            self.assertEqual(http_probe(app.port, "GET", "/config").body["bind"], "127.0.0.1")

    def test_a_corrupt_data_file_stops_the_start_and_is_left_alone(self):
        data = self.workdir / "data"
        data.mkdir()
        (data / "notes.json").write_text("{broken", encoding="utf-8")
        with AppProcess(self.workdir, credential_env(SECRET)) as app:
            app.start()
            result = app.wait_listening(10, lambda: None)
        self.assertEqual((result.state, result.exit_code), ("exited", 5))
        self.assertIsNotNone(logscan.find(logscan.parse(app.log_text()), "data_corrupt"))
        self.assertEqual((data / "notes.json").read_text(encoding="utf-8"), "{broken")

    def test_notes_endpoints_wait_for_readiness_and_validate_input(self):
        with AppProcess(self.workdir, credential_env(SECRET), warmup_ms=600) as app:
            app.start()
            app.wait_listening(10, lambda: None)
            self.assertEqual(http_probe(app.port, "GET", "/ready").status, 503)
            self.assertEqual(http_probe(app.port, "POST", "/notes", {"op_id": "a", "text": "x"}).status, 503)
            self.assertEqual(app.wait_ready(10, lambda: None).state, "ready")
            self.assertEqual(http_probe(app.port, "POST", "/notes", {"op_id": "Bad", "text": "x"}).status, 400)
            self.assertEqual(http_probe(app.port, "POST", "/notes", {"op_id": "a", "text": "x"}).status, 201)
            self.assertEqual(http_probe(app.port, "POST", "/notes", {"op_id": "a", "text": "x"}).status, 200)
            self.assertEqual(http_probe(app.port, "GET", "/nothing").status, 404)
            self.assertEqual(http_probe(app.port, "GET", "/health").body["version"], "1.0.0")

    def test_the_log_level_setting_controls_request_lines(self):
        counts = {}
        for level in ("info", "debug"):
            with AppProcess(self.workdir, credential_env(SECRET, NOTES_LOG_LEVEL=level), name=level) as app:
                app.start()
                app.wait_listening(10, lambda: None)
                http_probe(app.port, "GET", "/health")
                app.stop()
            counts[level] = sum(1 for line in logscan.parse(app.log_text()) if line.record["event"] == "request")
        self.assertEqual(counts["info"], 0)
        self.assertGreaterEqual(counts["debug"], 1)


class InputTests(unittest.TestCase):
    def test_inputs_are_validated(self):
        self.assertEqual(validate_inputs(runtime, {})["scenario"], "config_layers")
        for bad in ({"scenario": "nope"}, {"startup_timeout_ms": 10}, {"ready_timeout_ms": 99999},
                    {"warmup_ms": 0}, {"extra": 1}, {"api_key": SECRET}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)

    def test_evidence_refuses_a_payload_with_a_credential(self):
        context, events = make_context({})
        evidence = runtime.Evidence(context, {"api_key": SECRET})
        evidence.emit("lesson.report", {"title": "clean"}, 1)
        with self.assertRaises(runtime.SecretLeak) as caught:
            evidence.emit("lesson.report", {"title": f"oops {SECRET}"}, 1)
        self.assertNotIn(SECRET, str(caught.exception))
        self.assertEqual(len(events), 1)

    def test_the_demo_secret_is_fresh_and_never_a_real_key(self):
        first, second = runtime.new_demo_secret(), runtime.new_demo_secret()
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("sk-demo-"))


class ScenarioTests(unittest.TestCase):
    """Each scenario runs once per language with a known fake credential; the tests read the recorded events."""
    runs = {}

    @classmethod
    def setUpClass(cls):
        cls.patches = [mock.patch.object(runtime, "new_demo_secret", return_value=SECRET),
                       mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": PARENT_DECOY, "NOTES_PARENT": "x"})]
        for patch in cls.patches:
            patch.start()
        for scenario in SCENARIOS:
            for locale in (ZH, EN):
                cls.runs[(scenario, locale)] = run_case(scenario, locale)

    @classmethod
    def tearDownClass(cls):
        for patch in cls.patches:
            patch.stop()

    def test_no_event_answer_or_report_contains_a_credential(self):
        for (scenario, locale), (answer, events) in self.runs.items():
            with self.subTest(scenario=scenario, locale=locale):
                text = json.dumps(events, ensure_ascii=False) + answer
                self.assertNotIn(SECRET, text)
                self.assertNotIn(PARENT_DECOY, text)
                self.assertNotRegex(text, r"/tmp/|local-delivery-|ld-test-")

    def test_no_model_request_is_made_and_no_model_is_claimed(self):
        for (scenario, locale), (_, events) in self.runs.items():
            with self.subTest(scenario=scenario, locale=locale):
                self.assertFalse([kind for kind, _, _ in events if kind in ("request", "response")])

    def test_english_runs_have_no_chinese_and_chinese_runs_are_chinese(self):
        for (scenario, locale), (answer, events) in self.runs.items():
            text = json.dumps(events, ensure_ascii=False) + answer
            with self.subTest(scenario=scenario, locale=locale):
                if locale == EN:
                    self.assertIsNone(CJK.search(text))
                else:
                    self.assertIsNotNone(CJK.search(answer))

    def test_every_process_started_is_gone_afterwards(self):
        for (scenario, locale), (_, events) in self.runs.items():
            pids = {data["pid"] for kind, data, _ in events if kind == "lesson.process"}
            with self.subTest(scenario=scenario, locale=locale):
                self.assertEqual(wait_gone(list(pids), 3.0), [])

    def test_config_layers(self):
        for locale in (ZH, EN):
            answer, events = self.runs[("config_layers", locale)]
            made = reports(events)
            with self.subTest(locale=locale):
                self.assertEqual(sorted(made), [1, 2, 3])
                self.assertTrue(all(item["passed"] for report in made.values() for item in report["checks"]))
                layers = made[1]
                rows = {row[0]: row for row in layers["table"]["rows"]}
                self.assertEqual((rows["model"][2], rows["model"][3], rows["model"][4]), ("file-model", "env-model", "env"))
                self.assertEqual(rows["api_key"][3], texts_for(locale).values["set"])
                self.assertEqual(metric(layers, "sources-env"), 2)
                self.assertEqual(metric(made[2], "exit-code"), 2)
                self.assertEqual(metric(made[2], "problems"), 3)
                self.assertEqual(metric(made[3], "problems"), 2)
                self.assertEqual(metric(layers, "model-calls"), 0)
                failed = of(events, "lesson.start_failed")
                self.assertEqual([(item["reason"], item["exit_code"]) for item in failed],
                                 [("config_invalid", 2)] * 2)
                self.assertEqual({(p["name"], p["code"]) for p in failed[1]["problems"]},
                                 {("api_key", "secret_in_file"), ("log_lvl", "unknown_key")})
                self.assertIn("15/15", answer)

    def test_startup_probe(self):
        for locale in (ZH, EN):
            _, events = self.runs[("startup_probe", locale)]
            made = reports(events)
            with self.subTest(locale=locale):
                self.assertEqual(sorted(made), [1, 2, 3, 4, 5])
                self.assertTrue(all(item["passed"] for report in made.values() for item in report["checks"]
                                    if not (item["id"] == "stopped-gracefully" and not POSIX)))
                normal = made[1]
                statuses = [(row[1], row[2]) for row in normal["table"]["rows"]]
                self.assertEqual(statuses, [("GET /health", 200), ("GET /ready", 503), ("GET /ready", 200)])
                self.assertEqual(metric(made[2], "last-log-event"), "config_loaded")
                self.assertEqual(metric(made[3], "ready-status"), 503)
                self.assertEqual(metric(made[3], "failing-check"), "warmup")
                self.assertEqual(metric(made[4], "bind-reason").replace("WSA", ""), "EADDRINUSE")
                self.assertEqual(metric(made[5], "orphans-after-leader-kill"), 1)
                self.assertEqual(metric(made[5], "orphans-after-group-kill"), 0)
                reasons = [item["reason"] for item in of(events, "lesson.start_failed")]
                self.assertEqual(reasons, ["startup_timeout", "port_in_use"])
                timeout = of(events, "lesson.start_failed")[0]
                self.assertTrue(timeout["alive"])
                self.assertIsNone(timeout["exit_code"])
                phases = [data["phase"] for data in of(events, "lesson.process")]
                for phase in ("spawned", "listening", "ready", "not_ready", "stopped", "leader_killed", "group_reaped"):
                    self.assertIn(phase, phases)

    def test_logs_and_secrets(self):
        for locale in (ZH, EN):
            answer, events = self.runs[("logs_secrets", locale)]
            made = reports(events)
            with self.subTest(locale=locale):
                self.assertTrue(all(item["passed"] for item in made[1]["checks"]))
                self.assertGreater(metric(made[1], "request-lines"), 0)
                self.assertFalse(check(made[2], "leak-log-clean")["passed"])
                self.assertTrue(check(made[2], "leak-located")["passed"])
                self.assertTrue(check(made[2], "leak-report-clean")["passed"])
                self.assertEqual(metric(made[2], "leaked-settings"), "api_key")
                self.assertEqual(metric(made[2], "release-gate"), texts_for(locale).values["blocked"])
                shown = json.dumps(made[2]["table"], ensure_ascii=False)
                self.assertIn("[REDACTED:api_key]", shown)
                self.assertNotIn(SECRET, shown)
                self.assertIn("7/8", answer)

    def test_restart_and_rollback(self):
        for locale in (ZH, EN):
            _, events = self.runs[("restart_rollback", locale)]
            made = reports(events)
            with self.subTest(locale=locale):
                self.assertEqual(sorted(made), [2, 4])
                self.assertTrue(all(item["passed"] for report in made.values() for item in report["checks"]))
                self.assertEqual(metric(made[2], "notes-after-restart"), 2)
                self.assertEqual(metric(made[2], "duplicate-writes"), 0)
                self.assertEqual(metric(made[4], "notes-after-rollback"), 3)
                self.assertEqual([row[3] for row in made[4]["table"]["rows"]], [True, True])
                failed = of(events, "lesson.start_failed")
                self.assertEqual(len(failed), 1)
                self.assertEqual({(p["name"], p["code"]) for p in failed[0]["problems"]},
                                 {("settings_version", "unsupported_version"), ("model_id", "unknown_key"),
                                  ("model", "missing")})
                self.assertEqual([d["phase"] for d in of(events, "lesson.process")][:4], ["spawned", "listening", "ready", "crashed"])

    def test_all_report_text_comes_from_the_catalog_in_the_run_language(self):
        for (scenario, locale), (_, events) in self.runs.items():
            t = texts_for(locale)
            for number, report in reports(events).items():
                with self.subTest(scenario=scenario, locale=locale, round=number):
                    self.assertIn(report["title"], t.titles.values())
                    self.assertIn(report["summary"], t.summaries.values())
                    self.assertIn(tuple(report["table"]["columns"]), t.columns.values())
                    for item in report["checks"]:
                        self.assertEqual(item["label"], t.check_labels[item["id"]])


class CancellationTests(unittest.TestCase):
    def test_stopping_the_run_stops_the_child_and_raises(self):
        state = {"stop": False}
        pids = []

        def on_event(kind, data):
            if kind == "lesson.process" and data["phase"] == "spawned":
                pids.append(data["pid"])
            if kind == "lesson.process" and data["phase"] == "listening":
                state["stop"] = True

        context, events = make_context({"scenario": "startup_probe"}, cancelled=lambda: state["stop"],
                                       on_event=on_event)
        started = time.monotonic()
        with self.assertRaises(RunCancelled):
            execute_lesson(SPEC, runtime, context)
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(len(pids), 1)
        self.assertEqual(wait_gone(pids, 3.0), [])
        self.assertFalse([data for kind, data, _ in events if kind == "lesson.report"])

    def test_a_run_that_fails_midway_still_removes_its_directory_and_processes(self):
        context, events = make_context({"scenario": "config_layers"})
        seen = []
        with mock.patch.object(runtime.Delivery, "listen", side_effect=RuntimeError("boom")), \
                mock.patch.object(runtime.AppProcess, "start", autospec=True,
                                  side_effect=runtime.AppProcess.start) as start:
            with self.assertRaises(RuntimeError):
                execute_lesson(SPEC, runtime, context)
            seen = [call.args[0].pid for call in start.call_args_list]
        self.assertTrue(seen)
        self.assertEqual(wait_gone([pid for pid in seen if pid], 3.0), [])


class PortTests(unittest.TestCase):
    def test_a_fixed_free_port_is_used_and_released(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            free = probe.getsockname()[1]
        with tempfile.TemporaryDirectory(prefix="ld-test-") as directory:
            with AppProcess(Path(directory), credential_env(SECRET, NOTES_PORT=str(free))) as app:
                app.start()
                self.assertEqual(app.wait_listening(10, lambda: None).port, free)
        self.assertFalse(port_accepts(free))


if __name__ == "__main__":
    unittest.main()
