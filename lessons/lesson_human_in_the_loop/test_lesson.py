"""Behavior tests for human-in-the-loop: real bank writes, real checkpoints, resume with and without the lookup.

The model and the approver are the offline fixtures (deterministic test data, never a real model or
person). The exercise bank, the checkpoints and the platform's resume path run for real: the platform
tests reopen the run store the way a server restart would.
"""
import importlib
import json
import re
import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from course.execution import RunContext, approval_digest
from course.runner import RunCancelled
from lessons.lesson_human_in_the_loop import runtime
from lessons.lesson_human_in_the_loop.bank import BankError, ExerciseBank, exercise_problems
from lessons.lesson_human_in_the_loop.fixtures import create_approval_policy, create_completion
from lessons.lesson_human_in_the_loop.locales import texts_for
from lessons.lesson_human_in_the_loop.runtime import INPUT_MODEL, run
from server.catalog import LESSONS, load_lessons
from server.run_store import RunStore

CJK = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")
THREAD = "a1b2c3d4" * 4
TOPIC = {"zh-CN": "过滤偶数", "en": "Filter even numbers"}


def kinds(events):
    return [kind for kind, _, _ in events]


def data_of(events, kind, nth=0):
    return [data for event_kind, data, _ in events if event_kind == kind][nth]


def tool_names(events):
    return [data["function"]["name"] for kind, data, _ in events if kind == "tool_call"]


def report(events, title_key, texts):
    """The run report (the second lesson.report) as a dict of metrics and checks by id."""
    last = [data for kind, data, _ in events if kind == "lesson.report"][-1]
    return {"metrics": {item["id"]: item["value"] for item in last["metrics"]},
            "checks": {item["id"]: item for item in last["checks"]}, "raw": last}


class FlowCase(unittest.TestCase):
    """Unit tests that call run(context) directly; the bank lives in a temporary folder."""
    locale = "zh-CN"

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(runtime, "BANK_ROOT_OVERRIDE", Path(directory.name)))
        self.t = texts_for(self.locale)
        self.root = Path(directory.name)

    def start(self, *, exercise="approve-save", policy=None, resume=None, cancelled=None, completion=True, **inputs):
        """Run the lesson once; returns (events, answer). resume is a checkpoint state from an earlier run."""
        values = {"topic": TOPIC[self.locale], **inputs}
        events = []
        context = RunContext(
            lesson_id="human-in-the-loop", exercise_id=exercise, question="note", mode="offline", model="m",
            representation="sdk_standardized", inputs=INPUT_MODEL.model_validate(values).model_dump(mode="json"),
            api_key="", completion=create_completion(exercise, values, self.locale) if completion else None,
            emit_event=lambda kind, data, number: events.append((kind, data, number)),
            cancelled=cancelled or (lambda: False), max_model_calls=2, locale=self.locale,
            approval_policy=policy or create_approval_policy(exercise, values, self.locale),
            resume_state=resume, resumed_from=({"run_id": "r" * 32, "checkpoint_id": "cp-2", "name": "approved"}
                                               if resume else None),
            thread_id=THREAD, source_hash="sha256:" + "a" * 64)
        answer = run(context)
        return events, answer

    def checkpoints(self, events):
        return [data for kind, data, _ in events if kind == "checkpoint"]

    def state_of(self, events, name):
        return next(cp["state"] for cp in self.checkpoints(events) if cp["name"] == name)

    def bank(self):
        return ExerciseBank(self.root / THREAD, self.t)


class NormalFlowTests(FlowCase):
    def test_draft_checkpoint_approval_checkpoint_write_checkpoint_receipt_in_order(self):
        events, answer = self.start()
        self.assertEqual(kinds(events), [
            "request", "response", "checkpoint", "approval_requested", "approval_resolved", "checkpoint",
            "tool_call", "tool_result", "tool_call", "tool_result", "checkpoint", "request", "response",
            "lesson.report", "lesson.report"])
        self.assertEqual([cp["name"] for cp in self.checkpoints(events)], ["drafted", "approved", "saved"])
        self.assertEqual(tool_names(events), ["lookup_operation", "save_exercise"])
        self.assertTrue(answer.startswith("【离线脚本回答】"))
        rows = self.bank().rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["operation_id"], "save-a1b2c3d4-1")
        self.assertEqual(rows[0]["origin"], "fresh")
        self.assertEqual(rows[0]["title"], f"练习：{TOPIC['zh-CN']}")

    def test_nothing_is_written_before_the_approval(self):
        seen = []

        def policy(request):
            seen.append(self.bank().rows())  # the bank, read at the moment the person is asked
            return {"decision": "approve"}

        self.start(policy=policy)
        self.assertEqual(seen, [[]])

    def test_approved_checkpoint_carries_the_digest_of_what_was_approved(self):
        events, _ = self.start()
        approved = self.state_of(events, "approved")
        self.assertEqual(approved["approved_digest"], approval_digest(approved["approved"]))
        self.assertEqual(approved["approved"], approved["draft"])
        self.assertEqual(approved["operation_id"], self.state_of(events, "drafted")["operation_id"])
        self.assertEqual(self.state_of(events, "saved")["saved_id"], 1)

    def test_report_checks_come_from_the_bank_not_from_the_model(self):
        events, _ = self.start()
        result = report(events, "run", self.t)
        self.assertEqual(result["metrics"]["status"], "saved")
        self.assertEqual({key: item["passed"] for key, item in result["checks"].items()},
                         {"approval-gate": True, "written-once": True, "draft-once": True})
        self.assertEqual(result["metrics"]["model-calls"], 2)
        ledger = [data for kind, data, _ in events if kind == "lesson.report"][0]
        self.assertEqual(len(ledger["table"]["rows"]), 1)

    def test_events_hold_no_absolute_local_path(self):
        events, _ = self.start()
        self.assertNotIn(str(self.root), json.dumps(events, ensure_ascii=False))


class ApprovalOutcomeTests(FlowCase):
    def test_rejection_ends_without_a_write_or_an_approved_checkpoint(self):
        events, answer = self.start(policy=lambda request: {"decision": "reject", "note": "no"})
        self.assertEqual(self.bank().rows(), [])
        self.assertEqual([cp["name"] for cp in self.checkpoints(events)], ["drafted"])
        self.assertEqual(report(events, "run", self.t)["metrics"]["status"], "rejected")
        self.assertNotIn("tool_call", kinds(events))
        self.assertEqual(kinds(events).count("request"), 1)  # no receipt for a save that never happened
        self.assertIn("拒绝", answer)

    def test_timeout_is_its_own_status(self):
        events, _ = self.start(policy=lambda request: {"decision": "timeout"})
        self.assertEqual(report(events, "run", self.t)["metrics"]["status"], "timed_out")
        self.assertEqual(self.bank().rows(), [])

    def test_a_person_edit_is_what_gets_approved_checkpointed_and_saved(self):
        events, _ = self.start(exercise="edit-state")
        approved = self.state_of(events, "approved")
        self.assertTrue(approved["edited"])
        self.assertNotEqual(approved["approved"], approved["draft"])
        self.assertEqual(approved["approved"]["difficulty"], "hard")
        row = self.bank().rows()[0]
        self.assertEqual((row["title"], row["difficulty"]), (approved["approved"]["title"], "hard"))
        resolved = data_of(events, "approval_resolved")
        self.assertTrue(resolved["edited"])
        self.assertNotEqual(resolved["payload_digest"], resolved["requested_digest"])
        result = report(events, "run", self.t)
        self.assertTrue(result["checks"]["edit-traced"]["passed"])
        diff = result["raw"]["table"]["rows"]
        self.assertNotEqual(diff[0][1], diff[0][2])  # title: draft vs approved
        self.assertEqual(diff[0][2], diff[0][3])  # approved vs bank

    def test_an_edit_the_bank_would_refuse_never_becomes_an_approved_checkpoint(self):
        def policy(request):
            return {"decision": "approve", "edited_payload": {**request["payload"], "difficulty": "impossible"}}

        events, answer = self.start(policy=policy, exercise="edit-state")
        self.assertEqual([cp["name"] for cp in self.checkpoints(events)], ["drafted"])
        self.assertEqual(report(events, "run", self.t)["metrics"]["status"], "failed")
        self.assertEqual(self.bank().rows(), [])
        self.assertIn("没有保存", answer)

    def test_an_unusable_draft_never_reaches_the_approval(self):
        with patch("lessons.lesson_human_in_the_loop.test_lesson.create_completion",
                   return_value=lambda body, key: {"choices": [{"message": {"role": "assistant", "content": "just one line"}}]}):
            events, _ = self.start()
        self.assertNotIn("approval_requested", kinds(events))
        self.assertEqual(self.checkpoints(events), [])
        self.assertEqual(report(events, "run", self.t)["metrics"]["status"], "failed")

    def test_cancel_after_the_approval_lands_before_the_write(self):
        flag = {"stop": False}

        def policy(request):
            flag["stop"] = True
            return {"decision": "approve"}

        with self.assertRaises(RunCancelled):
            self.start(policy=policy, cancelled=lambda: flag["stop"])
        self.assertEqual(self.bank().rows(), [])


class StopPointTests(FlowCase):
    def test_after_draft_leaves_only_the_drafted_checkpoint(self):
        events, answer = self.start(stop_at="after_draft")
        self.assertEqual([cp["name"] for cp in self.checkpoints(events)], ["drafted"])
        self.assertNotIn("approval_requested", kinds(events))
        self.assertEqual(self.bank().rows(), [])
        result = report(events, "run", self.t)
        self.assertEqual(result["metrics"]["status"], "suspended")
        self.assertIn("suspended", answer)

    def test_before_save_leaves_an_approved_checkpoint_and_an_empty_bank(self):
        events, _ = self.start(stop_at="before_save")
        self.assertEqual([cp["name"] for cp in self.checkpoints(events)], ["drafted", "approved"])
        self.assertEqual(self.bank().rows(), [])
        self.assertNotIn("tool_call", kinds(events))
        self.assertNotIn("written-once", report(events, "run", self.t)["checks"])  # nothing to check yet

    def test_after_save_has_written_but_the_last_checkpoint_still_says_approved(self):
        events, _ = self.start(stop_at="after_save")
        self.assertEqual([cp["name"] for cp in self.checkpoints(events)], ["drafted", "approved"])
        self.assertEqual(len(self.bank().rows()), 1)
        result = report(events, "run", self.t)
        self.assertEqual(result["metrics"]["status"], "suspended")
        self.assertTrue(result["checks"]["written-once"]["passed"])


class InterruptionAndStorageTests(FlowCase):
    def test_a_simulated_stop_is_recorded_as_the_lessons_own_doing(self):
        events, _ = self.start(stop_at="after_save")
        interruption = data_of(events, "lesson.interruption")
        self.assertEqual(interruption, {"point": "after_save", "simulated": True, "source": "stop_at"})
        normal, _ = self.start()
        self.assertNotIn("lesson.interruption", kinds(normal))

    def test_bank_folders_follow_the_mode_and_old_offline_folders_are_pruned(self):
        import os
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp, patch.object(runtime, "BANK_ROOT_OVERRIDE", None), \
                patch.object(runtime.tempfile, "gettempdir", return_value=temp):
            root = Path(temp) / "agent-lab-human-in-the-loop"
            old = root / ("o" * 32)
            old.mkdir(parents=True)
            os.utime(old, (1, 1))
            offline = runtime.bank_folder(SimpleNamespace(mode="offline", thread_id="T" * 32))
            self.assertEqual(offline, root / ("t" * 32))
            self.assertFalse(old.exists())
            live = runtime.bank_folder(SimpleNamespace(mode="live", thread_id="../../etc"))
            self.assertEqual(live, runtime.ROOT / ".runtime" / "human-in-the-loop" / "etc")
            self.assertEqual(runtime.thread_key(SimpleNamespace(thread_id=None)), "local")


class ResumeTests(FlowCase):
    def interrupted(self, point):
        events, _ = self.start(stop_at=point)
        return events

    def test_resume_before_the_write_writes_once_and_sends_only_the_receipt(self):
        first = self.interrupted("before_save")
        events, _ = self.start(stop_at="before_save", resume=self.state_of(first, "approved"))
        self.assertEqual(kinds(events).count("request"), 1)
        self.assertNotIn("approval_requested", kinds(events))
        self.assertEqual(tool_names(events), ["lookup_operation", "save_exercise"])
        rows = self.bank().rows()
        self.assertEqual((len(rows), rows[0]["origin"]), (1, "resumed"))
        result = report(events, "run", self.t)
        self.assertEqual(result["metrics"]["status"], "saved")
        self.assertEqual(result["metrics"]["model-calls"], 1)
        self.assertTrue(result["checks"]["draft-once"]["passed"])
        self.assertIn("approved", result["metrics"]["resumed-from"])

    def test_resume_after_the_write_finds_the_operation_and_does_not_write_again(self):
        first = self.interrupted("after_save")
        events, _ = self.start(stop_at="after_save", resume=self.state_of(first, "approved"))
        self.assertEqual(tool_names(events), ["lookup_operation"])
        self.assertEqual(len(self.bank().rows()), 1)
        result = report(events, "run", self.t)
        self.assertEqual(result["metrics"]["status"], "already_saved")
        self.assertTrue(result["checks"]["written-once"]["passed"])
        self.assertEqual([cp["name"] for cp in self.checkpoints(events)], ["saved"])
        self.assertEqual(self.state_of(events, "saved")["saved_id"], 1)

    def test_resuming_the_same_checkpoint_again_still_leaves_one_row(self):
        state = self.state_of(self.interrupted("before_save"), "approved")
        for _ in range(3):
            self.start(resume=state)
        self.assertEqual(len(self.bank().rows()), 1)

    def test_a_blind_resume_writes_the_same_operation_twice(self):
        first = self.interrupted("after_save")
        events, _ = self.start(stop_at="after_save", resume=self.state_of(first, "approved"), resume_guard="blind")
        self.assertEqual(tool_names(events), ["save_exercise"])
        rows = self.bank().rows()
        self.assertEqual([row["operation_id"] for row in rows], ["save-a1b2c3d4-1"] * 2)
        result = report(events, "run", self.t)
        self.assertEqual(result["metrics"]["status"], "duplicated")
        self.assertFalse(result["checks"]["written-once"]["passed"])

    def test_resume_from_the_drafted_checkpoint_asks_for_a_new_approval_without_a_new_draft(self):
        state = self.state_of(self.interrupted("after_draft"), "drafted")
        events, _ = self.start(stop_at="after_draft", resume=state)
        self.assertIn("approval_requested", kinds(events))
        self.assertEqual(kinds(events).count("request"), 1)  # only the receipt
        self.assertEqual(len(self.bank().rows()), 1)
        self.assertTrue(report(events, "run", self.t)["checks"]["draft-once"]["passed"])

    def test_a_person_edit_survives_the_restart(self):
        first, _ = self.start(exercise="edit-state", stop_at="before_save")
        self.start(exercise="edit-state", stop_at="before_save", resume=self.state_of(first, "approved"))
        row = self.bank().rows()[0]
        self.assertEqual(row["difficulty"], "hard")
        self.assertTrue(row["title"].endswith("（已改）"))

    def test_a_position_that_no_longer_matches_its_approval_is_refused(self):
        state = self.state_of(self.interrupted("before_save"), "approved")
        tampered = {**state, "approved": {**state["approved"], "title": "someone changed this"}}
        events, answer = self.start(resume=tampered)
        self.assertEqual(self.bank().rows(), [])
        self.assertNotIn("tool_call", kinds(events))
        self.assertEqual(report(events, "run", self.t)["metrics"]["status"], "failed")
        self.assertIn("摘要", answer)

    def test_a_saved_checkpoint_the_bank_cannot_confirm_is_reported_not_rewritten(self):
        saved = self.state_of(self.start()[0], "saved")
        for row_file in (self.root / THREAD).glob("bank.sqlite3"):
            row_file.unlink()
        events, answer = self.start(resume=saved)
        self.assertEqual(tool_names(events), ["lookup_operation"])
        self.assertEqual(self.bank().rows(), [])
        self.assertEqual(report(events, "run", self.t)["metrics"]["status"], "failed")

    def test_resuming_a_saved_checkpoint_with_the_row_in_place_is_a_no_op(self):
        events, _ = self.start()
        saved = self.state_of(events, "saved")
        again, _ = self.start(resume=saved)
        self.assertEqual(len(self.bank().rows()), 1)
        self.assertEqual(report(again, "run", self.t)["metrics"]["status"], "already_saved")

    def test_a_resumed_run_never_stops_at_the_simulated_point_again(self):
        state = self.state_of(self.interrupted("before_save"), "approved")
        events, _ = self.start(stop_at="before_save", resume=state)
        self.assertEqual(report(events, "run", self.t)["metrics"]["status"], "saved")

    def test_threads_do_not_share_a_bank(self):
        self.start()
        other = ExerciseBank(self.root / "another", self.t)
        self.assertEqual(other.rows(), [])


class EnglishRunTests(FlowCase):
    locale = "en"

    def test_every_event_of_an_english_run_is_free_of_chinese(self):
        for exercise, extra in (("approve-save", {}), ("edit-state", {"stop_at": "before_save"}),
                                ("crash-after-write", {"stop_at": "after_save"})):
            with self.subTest(exercise=exercise):
                events, answer = self.start(exercise=exercise, **extra)
                self.assertEqual(CJK.findall(json.dumps(events, ensure_ascii=False) + answer), [])

    def test_english_resume_is_english_too(self):
        first, _ = self.start(stop_at="after_save")
        events, answer = self.start(stop_at="after_save", resume=self.state_of(first, "approved"))
        self.assertEqual(CJK.findall(json.dumps(events, ensure_ascii=False) + answer), [])
        self.assertEqual(report(events, "run", self.t)["metrics"]["status"], "already_saved")


class BankTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.bank = ExerciseBank(Path(directory.name) / "t", texts_for("en"))

    def save(self, operation="save-abc-1", **overrides):
        values = {"operation_id": operation, "title": "T", "difficulty": "easy", "body": "B", "origin": "fresh"}
        return self.bank.save_exercise(**{**values, **overrides})

    def test_lookup_reads_and_never_writes(self):
        self.assertEqual(self.bank.lookup_operation("save-abc-1"), {"found": False, "exercise_id": None, "rows": 0})
        self.assertEqual(self.bank.rows(), [])
        self.save()
        self.assertEqual(self.bank.lookup_operation("save-abc-1"), {"found": True, "exercise_id": 1, "rows": 1})

    def test_the_store_itself_does_not_stop_a_second_row(self):
        self.save()
        self.save()
        self.assertEqual(self.bank.lookup_operation("save-abc-1")["rows"], 2)

    def test_invalid_arguments_fail_before_any_write(self):
        for overrides in ({"operation_id": "oops"}, {"title": ""}, {"difficulty": "hard-ish"}, {"body": "x" * 1501},
                          {"origin": "elsewhere"}, {"title": "x" * 81}):
            with self.subTest(overrides=overrides), self.assertRaises(BankError):
                self.save(**overrides)
        with self.assertRaises(BankError):
            self.bank.lookup_operation("../escape")
        self.assertEqual(self.bank.rows(), [])

    def test_exercise_problems(self):
        good = {"title": "T", "difficulty": "easy", "body": "B"}
        self.assertEqual(exercise_problems(good), [])
        self.assertEqual(exercise_problems({**good, "extra": 1}), ["fields"])
        self.assertEqual(exercise_problems({"title": "T"}), ["fields"])
        self.assertEqual(exercise_problems([]), ["fields"])
        self.assertEqual(exercise_problems({**good, "title": " ", "difficulty": "x", "body": ""}),
                         ["title", "difficulty", "body"])

    def test_tool_errors_become_structured_results(self):
        from course.runner import execute_tool
        call = {"id": "c1", "function": {"name": "save_exercise", "arguments": json.dumps(
            {"operation_id": "bad", "title": "T", "difficulty": "easy", "body": "B", "origin": "fresh"})}}
        result = execute_tool(call, self.bank.tools(), "en")
        self.assertEqual((result["ok"], result["error_type"]), (False, "BankError"))


class InputTests(unittest.TestCase):
    def test_inputs_are_validated(self):
        self.assertEqual(INPUT_MODEL(topic="t").stop_at, "none")
        for bad in ({"topic": ""}, {"topic": "t", "stop_at": "sometime"}, {"topic": "t", "resume_guard": "maybe"},
                    {"topic": "t", "difficulty": "easy", "extra": 1}, {}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                INPUT_MODEL.model_validate(bad)

    def test_topic_has_no_chinese_default(self):
        self.assertTrue(INPUT_MODEL.model_fields["topic"].is_required())

    def test_message_catalogs_have_matching_status_keys(self):
        zh, en = texts_for("zh-CN"), texts_for("en")
        for name in ("answers", "reasons", "point_names", "status_summaries", "lookup_names", "write_names"):
            self.assertEqual(set(getattr(zh, name)), set(getattr(en, name)), name)
        self.assertEqual(set(zh.status_summaries),
                         {"saved", "already_saved", "duplicated", "suspended", "rejected", "timed_out", "failed"})


def lesson_spec():
    spec = next((item for item in LESSONS if item["id"] == "human-in-the-loop"), None)
    return spec or next(item for item in load_lessons(include_planned=True) if item["id"] == "human-in-the-loop")


web = importlib.import_module("server.app")


class PlatformResumeTests(unittest.TestCase):
    """The real lesson through POST /api/runs and /resume, with the run store reopened like a server restart."""

    def setUp(self):
        self.client = TestClient(web.app, base_url="http://localhost")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.previous = web.run_store
        self.store = RunStore(self.directory / "runs.sqlite3")
        web.run_store = self.store

        def restore():
            web.run_store = self.previous
            self.store.close()

        self.addCleanup(restore)
        self.spec = lesson_spec()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(runtime, "BANK_ROOT_OVERRIDE", self.directory / "banks"))
        stack.enter_context(patch.object(web, "lesson_spec", side_effect=lambda lesson_id: (
            self.spec if lesson_id == "human-in-the-loop" else None)))

    def wait_idle(self, timeout=10.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not web.run_lock.locked():
                return
            time.sleep(0.02)
        self.fail("the run did not finish")

    def read(self, run_id):
        text = self.client.get(f"/api/runs/{run_id}/events").text
        events = [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]
        self.wait_idle()
        return events

    def body(self, exercise, locale="zh-CN"):
        """The preset request: offline runs accept only the lesson's own exercises with their own inputs."""
        exercises = {item["id"]: item for item in self.spec["presets"][locale]["exercises"]}
        return {"lesson_id": "human-in-the-loop", "exercise_id": exercise, "mode": "offline", "locale": locale,
                "question": exercises[exercise]["question"]}

    def run_exercise(self, exercise, locale="zh-CN"):
        created = self.client.post("/api/runs", json=self.body(exercise, locale))
        self.assertEqual(created.status_code, 202, created.text)
        return created.json()["run_id"], self.read(created.json()["run_id"])

    def restart(self):
        path = self.store.path
        self.store.close()
        self.store = RunStore(path)
        web.run_store = self.store

    def resume(self, run_id, checkpoint_id):
        created = self.client.post(f"/api/runs/{run_id}/resume", json={"checkpoint_id": checkpoint_id})
        self.assertEqual(created.status_code, 202, created.text)
        return created.json()["run_id"], self.read(created.json()["run_id"])

    def checkpoint(self, events, name):
        return next(e["data"] for e in events if e["type"] == "checkpoint" and e["data"]["name"] == name)

    def rows(self, thread):
        return ExerciseBank(self.directory / "banks" / thread, texts_for("zh-CN")).rows()

    def metrics(self, events):
        last = [e for e in events if e["type"] == "lesson.report"][-1]["data"]
        return {item["id"]: item["value"] for item in last["metrics"]}

    def test_restart_then_resume_writes_once_under_the_same_thread(self):
        run_id, first = self.run_exercise("restart-resume")
        self.assertEqual(first[-1]["data"]["status"], "completed")
        self.assertEqual(self.metrics(first)["status"], "suspended")
        self.assertEqual(self.rows(run_id), [])
        approved = self.checkpoint(first, "approved")
        self.assertEqual(approved["thread_id"], run_id)
        self.restart()
        new_id, resumed = self.resume(run_id, approved["checkpoint_id"])
        self.assertEqual(resumed[0]["data"]["thread_id"], run_id)
        self.assertEqual(resumed[0]["data"]["resumed_from"]["state"], approved["state"])
        self.assertEqual([e["type"] for e in resumed].count("request"), 1)
        self.assertEqual(self.metrics(resumed)["status"], "saved")
        self.assertEqual(len(self.rows(run_id)), 1)
        self.assertEqual(self.client.get(f"/api/runs/{new_id}").json()["thread_id"], run_id)

    def test_write_then_crash_then_resume_twice_never_duplicates(self):
        run_id, first = self.run_exercise("crash-after-write")
        self.assertEqual(len(self.rows(run_id)), 1)
        approved = self.checkpoint(first, "approved")
        self.assertNotIn("saved", [e["data"]["name"] for e in first if e["type"] == "checkpoint"])
        self.restart()
        _, second = self.resume(run_id, approved["checkpoint_id"])
        self.assertEqual(self.metrics(second)["status"], "already_saved")
        _, third = self.resume(run_id, approved["checkpoint_id"])
        self.assertEqual(self.metrics(third)["status"], "already_saved")
        self.assertEqual(len(self.rows(run_id)), 1)

    def test_edit_state_resume_saves_the_edited_version(self):
        run_id, first = self.run_exercise("edit-state")
        approved = self.checkpoint(first, "approved")
        self.assertTrue(approved["state"]["edited"])
        self.resume(run_id, approved["checkpoint_id"])
        self.assertEqual(self.rows(run_id)[0]["difficulty"], "hard")

    def test_source_change_refuses_the_old_checkpoint(self):
        run_id, first = self.run_exercise("restart-resume")
        with patch.object(web, "lesson_source_hash", return_value="sha256:" + "0" * 64):
            stale = self.client.post(f"/api/runs/{run_id}/resume",
                                     json={"checkpoint_id": self.checkpoint(first, "approved")["checkpoint_id"]})
        self.assertEqual((stale.status_code, stale.json()["code"]), (409, "checkpoint_stale"))
        self.assertEqual(self.rows(run_id), [])

    def test_every_exercise_runs_in_both_languages_to_completion(self):
        for locale in ("zh-CN", "en"):
            for exercise in ("approve-save", "restart-resume", "crash-after-write", "edit-state"):
                with self.subTest(locale=locale, exercise=exercise):
                    _, events = self.run_exercise(exercise, locale)
                    self.assertEqual(events[-1]["data"]["status"], "completed")
                    self.assertEqual(events[0]["data"]["locale"], locale)
                    if locale == "en":
                        self.assertEqual(CJK.findall(json.dumps(events, ensure_ascii=False)), [])

    def test_the_approval_in_a_live_style_run_waits_for_a_person(self):
        """Without a fixture decision the run pauses at the gate until the page submits one (here: a rejection)."""
        policy = patch.object(web, "approval_for", return_value=lambda request: None)
        with policy:
            created = self.client.post("/api/runs", json=self.body("approve-save"))
            self.assertEqual(created.status_code, 202, created.text)
            run_id = created.json()["run_id"]
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not any(
                    e["type"] == "approval_requested" for e in map(json.loads, (t for _, _, t in self.store.events(run_id)))):
                time.sleep(0.02)
            requested = next(e for e in map(json.loads, (t for _, _, t in self.store.events(run_id)))
                             if e["type"] == "approval_requested")
            self.assertEqual(self.rows(run_id), [])
            sent = self.client.post(f"/api/runs/{run_id}/approvals", json={
                "approval_id": requested["data"]["approval_id"], "decision": "reject",
                "payload_digest": requested["data"]["payload_digest"]})
            self.assertEqual(sent.status_code, 200, sent.text)
            events = self.read(run_id)
        self.assertEqual(self.metrics(events)["status"], "rejected")
        self.assertEqual(self.rows(run_id), [])


class DefaultTopicTests(unittest.TestCase):
    def test_the_default_topic_cannot_be_read_as_removing_the_even_numbers(self):
        # "Filter ... out" reads as "remove" in English, and the model's drafts then contradicted their own titles.
        manifest = json.loads((Path(__file__).parent / "lesson.json").read_text(encoding="utf-8"))
        topic = manifest["input_defaults"]["topic"]
        self.assertNotRegex(topic["en"], r"(?i)\bfilter\b.*\bout\b")
        self.assertIn("only", topic["en"].lower())
        self.assertIn("只保留", topic["zh-CN"])


if __name__ == "__main__":
    unittest.main()
