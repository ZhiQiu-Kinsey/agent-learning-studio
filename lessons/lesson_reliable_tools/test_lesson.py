"""Behavior tests for reliable-tools. The lesson calls no model; SQLite and the outbox folder really read and write
in a temporary directory, the faults are real locks, and backoff waits go through an injectable clock."""
import json
import random
import re
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_reliable_tools import runtime
from lessons.lesson_reliable_tools.faults import FaultInjector, ResponseLost
from lessons.lesson_reliable_tools.locales import texts_for
from lessons.lesson_reliable_tools.retry import RetryPolicy, backoff_delay, classify, decide
from lessons.lesson_reliable_tools.store import (BusinessRejected, InvalidArgument, KeyConflict, OutboxBusy,
                                                 PracticeStore, StoreTimeout)

ZH, EN = "zh-CN", "en"
CJK = re.compile(r"[　-〿一-鿿＀-￯]")
SPEC = {"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}


class FakeClock:
    """Backoff waits advance virtual time instead of sleeping; lock timeouts stay real (and short)."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def make_context(inputs, locale=ZH, cancelled=lambda: False, question=""):
    events = []

    def emit(kind, data, number):
        events.append((kind, data))
    values = validate_inputs(runtime, inputs)
    context = RunContext(lesson_id="reliable-tools", exercise_id=values["scenario"], question=question,
                         mode="offline", model="local-python", representation="local", inputs=values, api_key="",
                         completion=None, emit_event=emit, cancelled=cancelled, max_model_calls=1, locale=locale)
    return context, events, values


def run_case(inputs, locale=ZH):
    context, events, _ = make_context(inputs, locale)
    answer = execute_lesson(SPEC, runtime, context)
    return answer, events


def run_with_clock(inputs, locale=ZH):
    """Call the scenario directly with a fake clock: no real backoff sleeps."""
    context, events, values = make_context(inputs, locale)
    clock = FakeClock()
    with tempfile.TemporaryDirectory() as directory:
        answer = runtime.SCENARIOS[values["scenario"]](context, Path(directory), values, clock,
                                                       random.Random(runtime.JITTER_SEED))
    return answer, events, clock


def of(events, kind):
    return [data for event, data in events if event == kind]


def report(events):
    return of(events, "lesson.report")[-1]


def check(events, check_id):
    return next(item for item in report(events)["checks"] if item["id"] == check_id)


def new_store(directory, timeout_s=0.05):
    store = PracticeStore(Path(directory), texts_for(ZH), timeout_s)
    store.seed("a", 3)
    store.seed("empty", 0)
    return store


class ClassificationTests(unittest.TestCase):
    def test_every_error_type_maps_to_a_category(self):
        self.assertEqual(classify("StoreTimeout"), "transient")
        self.assertEqual(classify("OutboxBusy"), "transient")
        self.assertEqual(classify("ResponseLost"), "outcome_unknown")
        self.assertEqual(classify("InvalidArgument"), "invalid")
        self.assertEqual(classify("TypeError"), "invalid")
        self.assertEqual(classify("BusinessRejected"), "rejected")
        self.assertEqual(classify("KeyConflict"), "rejected")
        # Nobody classified it: never guess "transient".
        self.assertEqual(classify("ZeroDivisionError"), "unclassified")

    def test_decisions(self):
        self.assertEqual(decide("transient", repeatable=False), ("retry", "transient"))
        self.assertEqual(decide("outcome_unknown", repeatable=True), ("retry", "repeatable"))
        self.assertEqual(decide("outcome_unknown", repeatable=False), ("stop", "outcome_unknown"))
        self.assertEqual(decide("outcome_unknown", repeatable=False, blind=True), ("retry", "blind"))
        for category in ("invalid", "rejected", "unclassified"):
            with self.subTest(category=category):
                self.assertEqual(decide(category, repeatable=True, blind=True), ("stop", category))

    def test_backoff_grows_is_capped_and_jittered(self):
        policy = RetryPolicy(max_attempts=6, timeout_s=0.1, base_delay_s=0.1, budget_s=10, max_delay_s=0.3)
        rng = random.Random(1)
        delays = [backoff_delay(attempt, policy, rng) for attempt in range(1, 6)]
        ceilings = [0.1, 0.2, 0.3, 0.3, 0.3]
        for delay, ceiling in zip(delays, ceilings):
            self.assertGreaterEqual(delay, ceiling * 0.5)
            self.assertLess(delay, ceiling)
        # The same seed gives the same waits: a run can be reproduced.
        again = random.Random(1)
        self.assertEqual(delays, [backoff_delay(attempt, policy, again) for attempt in range(1, 6)])


class StoreTests(unittest.TestCase):
    def test_same_key_writes_once_and_returns_the_first_result(self):
        with tempfile.TemporaryDirectory() as directory:
            store = new_store(directory)
            first = store.submit_practice("a", "safe-divide", "答案", "k1")
            again = store.submit_practice("a", "safe-divide", "答案", "k1")
            self.assertFalse(first["replayed"])
            self.assertTrue(again["replayed"])
            self.assertEqual(again["submission_id"], first["submission_id"])
            snapshot = store.snapshot()
            self.assertEqual(len(snapshot["submissions"]), 1)
            self.assertEqual(snapshot["accounts"]["a"], 2)
            self.assertEqual(snapshot["operations"][0]["idempotency_key"], "k1")

    def test_without_a_key_every_call_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = new_store(directory)
            store.submit_practice("a", "safe-divide", "答案")
            store.submit_practice("a", "safe-divide", "答案")
            self.assertEqual(len(store.snapshot()["submissions"]), 2)
            self.assertEqual(store.snapshot()["accounts"]["a"], 1)

    def test_a_key_reused_for_different_content_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            store = new_store(directory)
            store.submit_practice("a", "safe-divide", "答案", "k1")
            with self.assertRaises(KeyConflict):
                store.submit_practice("a", "safe-divide", "另一个答案", "k1")
            self.assertEqual(len(store.snapshot()["submissions"]), 1)

    def test_business_rule_and_invalid_arguments_change_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            store = new_store(directory)
            before = store.snapshot()
            with self.assertRaises(BusinessRejected):
                store.submit_practice("empty", "safe-divide", "答案", "k1")
            with self.assertRaises(InvalidArgument):
                store.submit_practice("a", "speed-typing", "答案", "k2")
            with self.assertRaises(InvalidArgument):
                store.submit_practice("a", "safe-divide", "  ", "k3")
            with self.assertRaises(InvalidArgument):
                store.submit_practice("nobody", "safe-divide", "答案", "k4")
            # The refusal rolled back inside the transaction: no submission, no operation record.
            self.assertEqual(store.snapshot(), before)

    def test_a_locked_database_really_times_out_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            store = new_store(directory, timeout_s=0.05)
            holder = sqlite3.connect(store.database, isolation_level=None)
            holder.execute("BEGIN EXCLUSIVE")
            try:
                started = time.perf_counter()
                with self.assertRaises(StoreTimeout):
                    store.read_account("a")
                self.assertGreaterEqual(time.perf_counter() - started, 0.04)
                with self.assertRaises(StoreTimeout):
                    store.submit_practice("a", "safe-divide", "答案", "k1")
            finally:
                holder.execute("ROLLBACK")
                holder.close()
            self.assertEqual(store.snapshot()["submissions"], [])
            self.assertEqual(store.read_account("a")["credits"], 3)

    def test_outbox_write_is_repeatable_and_respects_the_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            store = new_store(directory)
            submission = store.submit_practice("a", "safe-divide", "答案", "k1")["submission_id"]
            (store.outbox / ".lock").write_text("x", encoding="utf-8")
            with self.assertRaises(OutboxBusy):
                store.write_outbox(submission)
            self.assertEqual(store.snapshot()["outbox"], [])
            (store.outbox / ".lock").unlink()
            first = store.write_outbox(submission)
            store.write_outbox(submission)
            self.assertEqual(store.snapshot()["outbox"], [first["file"]])
            self.assertFalse((store.outbox / ".lock").exists(), "the tool releases its own lock")

    def test_compensation_refunds_once(self):
        with tempfile.TemporaryDirectory() as directory:
            store = new_store(directory)
            submission = store.submit_practice("a", "safe-divide", "答案", "k1")["submission_id"]
            self.assertTrue(store.cancel_submission(submission)["refunded"])
            self.assertFalse(store.cancel_submission(submission)["refunded"])
            snapshot = store.snapshot()
            self.assertEqual(snapshot["accounts"]["a"], 3)
            self.assertEqual(snapshot["submissions"][0]["status"], "cancelled")
            with self.assertRaises(InvalidArgument):
                store.write_outbox(submission)

    def test_response_lost_happens_after_the_tool_really_ran(self):
        with tempfile.TemporaryDirectory() as directory:
            store = new_store(directory)
            faults = FaultInjector(store, {("submit", 1): "response_lost"}, texts_for(ZH))
            tools = faults.tools(store.tools())
            context, events, _ = make_context({"scenario": "lost_response"})
            with faults.attempt(context, "submit", "submit_practice", 1):
                with self.assertRaises(ResponseLost):
                    tools["submit_practice"](learner="a", exercise="safe-divide", answer="答案")
            self.assertEqual(len(store.snapshot()["submissions"]), 1, "the write committed before the loss")
            self.assertEqual(of(events, "lesson.fault")[0]["source"], "fault_injection")
            with self.assertRaises(ValueError):
                FaultInjector(store, {("submit", 1): "meteor"}, texts_for(ZH))


class ScenarioTests(unittest.TestCase):
    def test_read_retries_until_the_lock_is_gone(self):
        answer, events = run_case({"scenario": "read_timeout", "locked_attempts": 2})
        self.assertEqual(len(of(events, "tool_call")), 3)
        retries = of(events, "lesson.retry")
        self.assertEqual([item["decision"] for item in retries], ["retry", "retry"])
        self.assertEqual({item["error_type"] for item in retries}, {"StoreTimeout"})
        # Each locked attempt really waited for the lock (timeout_ms is 200 by default).
        self.assertTrue(all(item["took_ms"] >= 150 for item in retries))
        self.assertTrue(check(events, "read_unchanged")["passed"])
        self.assertTrue(check(events, "read_result")["passed"])
        self.assertTrue(all(call["origin"] == "course_program" for call in of(events, "tool_call")))
        self.assertEqual(of(events, "request"), [], "no model is called")
        self.assertIn("3", answer)

    def test_every_fault_is_announced_before_its_tool_call(self):
        _, events = run_case({"scenario": "read_timeout", "locked_attempts": 2})
        kinds = [kind for kind, _ in events]
        for index, kind in enumerate(kinds):
            if kind == "lesson.fault":
                self.assertEqual(kinds[index + 1], "tool_call")
        self.assertEqual(len(of(events, "lesson.fault")), 2)
        # Calls and results pair up by id.
        calls = [call["id"] for call in of(events, "tool_call")]
        self.assertEqual(calls, [result["tool_call_id"] for result in of(events, "tool_result")])

    def test_attempt_limit_stops_a_read(self):
        answer, events, clock = run_with_clock({"scenario": "read_timeout", "locked_attempts": 6,
                                                "max_attempts": 3, "timeout_ms": 50})
        self.assertEqual(len(of(events, "tool_call")), 3)
        self.assertEqual(of(events, "lesson.retry")[-1]["reason"], "max_attempts")
        self.assertEqual(len(clock.sleeps), 2, "no wait after the last attempt")
        self.assertFalse(check(events, "read_result")["passed"])
        self.assertIn("失败", answer)

    def test_time_budget_stops_before_an_attempt_that_cannot_fit(self):
        _, events, clock = run_with_clock({"scenario": "read_timeout", "locked_attempts": 6, "max_attempts": 6,
                                           "timeout_ms": 50, "base_delay_ms": 1000, "budget_ms": 2000})
        retries = of(events, "lesson.retry")
        self.assertEqual(retries[-1]["reason"], "budget")
        self.assertLess(len(of(events, "tool_call")), 6)
        self.assertLessEqual(clock.now, 2.0)

    def test_classify_retries_only_transient_failures(self):
        _, events = run_case({"scenario": "classify"})
        retries = of(events, "lesson.retry")
        by_operation = {}
        for item in retries:
            by_operation.setdefault(item["operation"], []).append((item["category"], item["decision"]))
        self.assertEqual(by_operation["invalid"], [("invalid", "stop")])
        self.assertEqual(by_operation["rejected"], [("rejected", "stop")])
        self.assertEqual(by_operation["submit"], [("transient", "retry")])
        self.assertEqual(by_operation["export"], [("transient", "retry")])
        self.assertEqual(len(of(events, "tool_call")), 6)
        self.assertTrue(all(item["passed"] for item in report(events)["checks"]), report(events)["checks"])
        storage = of(events, "lesson.storage")[-1]
        self.assertEqual(storage["accounts"], {"learner-a": 2, "learner-b": 0})
        self.assertEqual(storage["outbox"], ["outbox/1.json"])

    def test_lost_response_three_ways(self):
        answer, events = run_case({"scenario": "lost_response"})
        storages = {item["label"]: item for item in of(events, "lesson.storage")}
        self.assertEqual(len(storages["blind_retry"]["submissions"]), 2, "blind retry duplicates the write")
        self.assertEqual(storages["blind_retry"]["accounts"]["learner-a"], 1)
        self.assertEqual(len(storages["stop_when_unknown"]["submissions"]), 1)
        self.assertEqual(len(storages["idempotency_key"]["submissions"]), 1)
        self.assertEqual(storages["idempotency_key"]["accounts"]["learner-a"], 2)
        self.assertEqual(len(storages["idempotency_key"]["operations"]), 1)
        self.assertFalse(check(events, "blind_retry_written_once")["passed"])
        self.assertTrue(check(events, "stop_when_unknown_written_once")["passed"])
        self.assertTrue(check(events, "idempotency_key_written_once")["passed"])
        self.assertTrue(check(events, "key_in_store")["passed"])
        stop = [item for item in of(events, "lesson.retry") if item["reason"] == "outcome_unknown"]
        self.assertEqual(len(stop), 1)
        replayed = [item["result"]["result"] for item in of(events, "tool_result")
                    if item["result"]["ok"] and item["result"]["result"].get("replayed")]
        self.assertEqual(len(replayed), 1, "the keyed retry gets the first result back")
        self.assertIn("2", answer)

    def test_partial_write_is_compensated(self):
        answer, events, _ = run_with_clock({"scenario": "partial_write", "outbox_busy_attempts": 6})
        names = [call["function"]["name"] for call in of(events, "tool_call")]
        self.assertEqual(names, ["submit_practice"] + ["write_outbox"] * 4 + ["cancel_submission"])
        storage = of(events, "lesson.storage")[-1]
        self.assertEqual(storage["submissions"][0]["status"], "cancelled")
        self.assertEqual(storage["accounts"]["learner-a"], 3)
        self.assertEqual(storage["outbox"], [])
        self.assertTrue(check(events, "final_state")["passed"])
        self.assertEqual(report(events)["metrics"][0]["value"], "未完成，已补偿")
        self.assertIn("没有完成", answer)

    def test_partial_write_completes_when_the_outbox_frees_up(self):
        answer, events, _ = run_with_clock({"scenario": "partial_write", "outbox_busy_attempts": 1})
        names = [call["function"]["name"] for call in of(events, "tool_call")]
        self.assertEqual(names, ["submit_practice", "write_outbox", "write_outbox"])
        storage = of(events, "lesson.storage")[-1]
        self.assertEqual(storage["submissions"][0]["status"], "active")
        self.assertEqual(storage["outbox"], ["outbox/1.json"])
        self.assertTrue(check(events, "final_state")["passed"])
        self.assertIn("提交完成", answer)

    def test_learner_note_goes_into_the_report_only(self):
        context, events, _ = make_context({"scenario": "classify"}, question="我的备注")
        execute_lesson(SPEC, runtime, context)
        note = next(item for item in report(events)["metrics"] if item["id"] == "note")
        self.assertEqual(note["value"], "我的备注")

    def test_no_local_paths_in_events(self):
        _, events = run_case({"scenario": "partial_write"})
        dumped = json.dumps([data for _, data in events], ensure_ascii=False)
        self.assertNotIn(tempfile.gettempdir(), dumped)
        self.assertNotIn("reliable-tools-", dumped)


class LocaleAndInputTests(unittest.TestCase):
    def test_english_runs_have_no_chinese(self):
        for scenario in runtime.SCENARIOS:
            with self.subTest(scenario=scenario):
                answer, events = run_case({"scenario": scenario, "timeout_ms": 50}, locale=EN)
                text = json.dumps([data for _, data in events], ensure_ascii=False) + answer
                self.assertIsNone(CJK.search(text), CJK.search(text) and text[CJK.search(text).start() - 40:][:80])

    def test_chinese_runs_stay_chinese(self):
        answer, events = run_case({"scenario": "lost_response"})
        self.assertRegex(answer, CJK)
        self.assertRegex(report(events)["title"], CJK)

    def test_input_validation(self):
        for bad in ({"scenario": "flaky"}, {"timeout_ms": 10}, {"max_attempts": 0}, {"max_attempts": 7},
                    {"budget_ms": 50}, {"locked_attempts": -1}, {"surprise": 1}):
            with self.subTest(inputs=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)
        self.assertEqual(validate_inputs(runtime, {})["scenario"], "read_timeout")

    def test_stop_request_ends_the_run_before_more_tool_calls(self):
        calls = []

        def cancelled():
            return len(calls) >= 1
        context, events, _ = make_context({"scenario": "read_timeout", "locked_attempts": 3, "timeout_ms": 50},
                                          cancelled=cancelled)
        original = context.emit_event

        def emit(kind, data, number):
            if kind == "tool_result":
                calls.append(data)
            original(kind, data, number)
        context.emit_event = emit
        with self.assertRaises(RunCancelled):
            execute_lesson(SPEC, runtime, context)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(of(events, "tool_call")), 1)


if __name__ == "__main__":
    unittest.main()
