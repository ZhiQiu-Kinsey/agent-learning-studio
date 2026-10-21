"""Behavior tests for async-concurrency: deterministic model data; the tools, the graph and the scheduler really run.

Timings are real wall-clock time on small delays. Assertions use bounds that hold by construction (a task that sleeps
d milliseconds cannot end sooner than d) and orderings with a wide margin, never exact milliseconds.
"""
import asyncio
import json
import re
import threading
import time
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled, execute_tool
from lessons.lesson_async_concurrency import runtime
from lessons.lesson_async_concurrency.fixtures import create_completion
from lessons.lesson_async_concurrency.graph import GraphError, Ref, Task, critical_path_ms, levels, refs_in, resolve
from lessons.lesson_async_concurrency.locales import texts_for
from lessons.lesson_async_concurrency.locales.fixture import texts_for as fixture_texts_for
from lessons.lesson_async_concurrency.runtime import (NOTES, Variant, build_tasks, build_variants,
                                                      dependency_violation, peak_concurrency)
from lessons.lesson_async_concurrency.scheduler import STATUSES, THREAD_PREFIX, Outcome, Scheduler
from lessons.lesson_async_concurrency.tools import (LOCK_PROBE_SHARE, MissingInput, NoteLocked, TaskStopped,
                                                    UnknownNote, build_sheet, make_tools, read_note)

LOCALES = ("zh-CN", "en")
CJK = re.compile(r"[　-〿一-鿿＀-￯]")
DELAY = 60  # milliseconds a tool waits and the offline model pauses, in the run-level tests


def live_threads():
    deadline = time.perf_counter() + 1
    while time.perf_counter() < deadline:
        names = [thread.name for thread in threading.enumerate() if thread.name.startswith(THREAD_PREFIX)]
        if not names:
            return names
        time.sleep(0.01)
    return names


def run_case(inputs, locale="zh-CN", completion="fixture", cancelled=lambda: False, max_calls=12):
    events = []
    values = validate_inputs(runtime, inputs)
    if completion == "fixture":
        completion = create_completion("test", values, locale)
    context = RunContext(
        lesson_id="async-concurrency", exercise_id="test", question="", mode="offline", model="fixture-model",
        representation="sdk_standardized", inputs=values, api_key="", completion=completion, max_model_calls=max_calls,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)), locale=locale)
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def reports(events):
    return of(events, "lesson.report")


def total(events):
    """The comparison report at the end of the run."""
    return reports(events)[-1]


def metrics(events):
    return {item["id"]: item["value"] for item in total(events)["metrics"] if "id" in item}


def checks(events):
    return {item["id"]: item for item in total(events)["checks"]}


def variant_report(events, index):
    return reports(events)[index]


def variant_metrics(events, index):
    return {item["id"]: item["value"] for item in variant_report(events, index)["metrics"]}


def task_events(events, variant):
    return {data["id"]: data for data in of(events, "lesson.task") if data["variant"] == variant}


def statuses(events, variant):
    return {task_id: data["status"] for task_id, data in task_events(events, variant).items()}


# ---------- Scheduler-level helpers: tasks that really sleep, on real threads ----------
def make(task_id, needs=(), timeout=5.0, join="all"):
    return Task(task_id, "tool", "work", {"after": [Ref(need, "value") for need in needs]}, timeout, join)


def sleeper(durations=None, cooperative=True, fail=(), raises=None):
    """Work that sleeps durations[id] seconds: on the stop Event if cooperative, in time.sleep otherwise."""
    durations = durations or {}

    async def work(task, inputs, stop, in_thread):
        def blocking():
            seconds = durations.get(task.id, 0.05)
            if cooperative:
                if stop.wait(seconds):
                    return {"ok": False, "error_type": "TaskStopped", "error": "stopped"}
            else:
                time.sleep(seconds)
            if raises and task.id in raises:
                raise raises[task.id]
            if task.id in fail:
                return {"ok": False, "error_type": "Boom", "error": "failed on purpose"}
            return {"ok": True, "result": {"value": task.id, "inputs": inputs}}
        return await in_thread(task.id, blocking)
    return work


def schedule(tasks, work=None, **options):
    seen, stops = [], []
    settings = dict(limit=4, schedule="by_dependency", on_failure="continue", deadline_s=30, stop_requested=lambda: False,
                    on_outcome=seen.append, on_stop=lambda: stops.append(1))
    scheduler = Scheduler(tasks, run_task=work or sleeper(), **{**settings, **options})
    asyncio.run(scheduler.run())
    scheduler.seen, scheduler.stops_seen = seen, len(stops)
    return scheduler


def state(scheduler):
    return {task_id: outcome.status for task_id, outcome in scheduler.outcomes.items()}


class GraphTests(unittest.TestCase):
    def test_dependencies_are_read_from_the_references_not_declared(self):
        task = Task("t", "tool", "x", {"a": Ref("one", "k"), "b": [{"c": Ref("two", "k")}, Ref("one", "j")]}, 1)
        self.assertEqual(task.needs, ("one", "two"))
        self.assertEqual([ref.key for ref in refs_in(task.inputs)], ["k", "k", "j"])
        self.assertEqual(Task("u", "tool", "x", {"plain": [1, "two"]}, 1).needs, ())

    def test_resolve_replaces_references_and_leaves_none_where_nothing_exists_yet(self):
        inputs = {"a": Ref("one", "k"), "b": [Ref("two", "k"), 7]}
        self.assertEqual(resolve(inputs, {"one": {"k": "x"}}), {"a": "x", "b": [None, 7]})

    def test_levels_of_the_two_workloads(self):
        values = runtime.Inputs()
        for workload, expected in (("pair", {"read": 1, "sheet": 2}), ("review", {"read": 1, "sum": 2, "sheet": 3})):
            tasks = build_tasks(Variant("x", workload), values)
            depth = levels(tasks)
            for task in tasks:
                self.assertEqual(depth[task.id], expected[task.id.split("-")[0]], task.id)

    def test_tasks_on_one_level_never_depend_on_each_other(self):
        tasks = build_tasks(Variant("x", "review"), runtime.Inputs())
        depth = levels(tasks)
        for task in tasks:
            self.assertTrue(all(depth[need] < depth[task.id] for need in task.needs))

    def test_a_cycle_an_unknown_reference_and_a_duplicate_are_refused(self):
        with self.assertRaisesRegex(GraphError, "cycle"):
            levels([make("a", ["b"]), make("b", ["a"])])
        with self.assertRaisesRegex(GraphError, "not a task"):
            levels([make("a", ["ghost"])])
        with self.assertRaisesRegex(GraphError, "unique"):
            levels([make("a"), make("a")])
        with self.assertRaises(GraphError):
            Scheduler([make("a", ["b"]), make("b", ["a"])], limit=1, schedule="by_dependency", on_failure="continue",
                      deadline_s=1, stop_requested=lambda: False, run_task=sleeper(), on_outcome=lambda o: None,
                      on_stop=lambda: None)

    def test_the_critical_path_is_the_longest_chain_of_durations(self):
        tasks = [make("a"), make("b"), make("c", ["a", "b"]), make("d", ["c"])]
        self.assertEqual(critical_path_ms(tasks, {"a": 100, "b": 300, "c": 50, "d": 10}), 360)
        self.assertEqual(critical_path_ms(tasks, {}), 0)
        self.assertEqual(critical_path_ms([], {}), 0)


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.t = texts_for("en")

    def test_read_note_returns_the_real_note_after_really_waiting(self):
        started = time.perf_counter()
        result = read_note(self.t, "context-budget", 80, stop=threading.Event())
        self.assertGreaterEqual(time.perf_counter() - started, 0.08)
        self.assertEqual(result["note"], self.t.notes["context-budget"])
        self.assertEqual(result["chars"], len(result["note"]))
        self.assertGreaterEqual(result["waited_ms"], 80)

    def test_a_stop_signal_ends_the_wait_at_once(self):
        stop = threading.Event()
        threading.Timer(0.05, stop.set).start()
        started = time.perf_counter()
        with self.assertRaises(TaskStopped) as caught:
            read_note(self.t, "context-budget", 3000, stop=stop)
        self.assertLess(time.perf_counter() - started, 1.0)
        self.assertRegex(str(caught.exception), r"after waiting \d+ ms")

    def test_a_locked_note_fails_after_the_probe_not_the_full_delay(self):
        started = time.perf_counter()
        with self.assertRaises(NoteLocked) as caught:
            read_note(self.t, "context-budget", 500, lock=True, stop=threading.Event())
        elapsed = time.perf_counter() - started
        self.assertGreaterEqual(elapsed, 0.5 * LOCK_PROBE_SHARE)
        self.assertLess(elapsed, 0.45)
        self.assertIn("context-budget", str(caught.exception))

    def test_an_unknown_lesson_is_refused(self):
        with self.assertRaises(UnknownNote):
            read_note(self.t, "no-such-lesson", 10, stop=threading.Event())

    def test_the_sheet_needs_every_entry_unless_partial_is_allowed(self):
        entries = [{"lesson": "a", "text": "one"}, {"lesson": "b", "text": None}]
        with self.assertRaises(MissingInput) as caught:
            build_sheet(self.t, ["a", "b"], entries)
        self.assertIn("b", str(caught.exception))
        partial = build_sheet(self.t, ["a", "b"], entries, allow_partial=True)
        self.assertEqual((partial["complete"], partial["missing"], partial["lines"]), (False, ["b"], ["a: one"]))
        whole = build_sheet(self.t, ["a", "b"], [*entries[:1], {"lesson": "b", "text": " two "}])
        self.assertEqual((whole["complete"], whole["missing"], whole["lines"]), (True, [], ["a: one", "b: two"]))

    def test_the_sheet_refuses_malformed_arguments(self):
        with self.assertRaises(ValueError):
            build_sheet(self.t, "a", [])
        with self.assertRaises(ValueError):
            build_sheet(self.t, ["a"], [{"lesson": "z", "text": "x"}])
        with self.assertRaises(ValueError):
            build_sheet(self.t, ["a"], ["not an object"])

    def test_through_the_tool_loop_every_failure_is_a_structured_error(self):
        stop = threading.Event()
        tools = make_tools(self.t, stop)

        def call(name, arguments):
            return execute_tool({"id": "c", "type": "function",
                                 "function": {"name": name, "arguments": json.dumps(arguments)}}, tools, "en")
        ok = call("read_note", {"lesson": "prompt-caching", "delay_ms": 10})
        self.assertTrue(ok["ok"])
        for arguments, error_type in (({"lesson": "x", "delay_ms": 10}, "UnknownNote"),
                                      ({"lesson": "prompt-caching", "delay_ms": 10, "lock": True}, "NoteLocked")):
            failed = call("read_note", arguments)
            self.assertEqual((failed["ok"], failed["error_type"]), (False, error_type))
        self.assertEqual(call("build_sheet", {"lessons": ["a"], "entries": []})["error_type"], "MissingInput")
        self.assertEqual(call("read_note", {"lesson": "prompt-caching"})["error_type"], "TypeError")  # missing delay_ms
        self.assertEqual(call("no_such_tool", {})["error_type"], "ValueError")
        stop.set()
        self.assertEqual(call("read_note", {"lesson": "prompt-caching", "delay_ms": 3000})["error_type"], "TaskStopped")


class SchedulerTests(unittest.TestCase):
    def test_a_dependent_task_starts_only_after_what_it_needs_has_ended(self):
        tasks = [make("a"), make("b"), make("c", ["a", "b"]), make("d", ["c"])]
        scheduler = schedule(tasks, sleeper({"a": 0.05, "b": 0.12, "c": 0.05, "d": 0.02}))
        out = scheduler.outcomes
        self.assertEqual(set(state(scheduler).values()), {"done"})
        self.assertGreaterEqual(out["c"].started_ms, out["b"].ended_ms)
        self.assertGreaterEqual(out["d"].started_ms, out["c"].ended_ms)
        self.assertLess(out["b"].started_ms, out["a"].ended_ms, "independent tasks overlap")
        self.assertEqual(scheduler.results["c"]["inputs"], {"after": ["a", "b"]})
        self.assertIsNone(dependency_violation(scheduler))

    def test_a_dependent_task_gets_the_values_its_dependencies_produced(self):
        scheduler = schedule([make("a"), make("b", ["a"])])
        self.assertEqual(scheduler.results["b"]["inputs"], {"after": ["a"]})

    def test_the_limit_holds_and_slots_go_in_arrival_order(self):
        tasks = [make(name) for name in "abcdef"]
        scheduler = schedule(tasks, sleeper({name: 0.05 for name in "abcdef"}), limit=2)
        started = sorted(scheduler.outcomes.values(), key=lambda o: (o.started_ms, o.task.id))
        self.assertEqual([o.task.id for o in started], list("abcdef"))
        self.assertEqual(peak_concurrency(list(scheduler.outcomes.values())), 2)
        self.assertGreaterEqual(scheduler.wall_ms, 3 * 50)
        self.assertEqual(scheduler.peak_threads, 2)

    def test_limit_one_is_the_serial_run_and_costs_the_sum(self):
        scheduler = schedule([make("a"), make("b"), make("c")], sleeper({"a": 0.06, "b": 0.06, "c": 0.06}), limit=1)
        self.assertEqual(peak_concurrency(list(scheduler.outcomes.values())), 1)
        self.assertGreaterEqual(scheduler.wall_ms, 180)

    def test_the_timeout_clock_starts_after_the_slot_is_granted(self):
        # b waits 150 ms for a's slot; it only runs 150 ms, so a 250 ms timeout is enough for both.
        slow = {"a": 0.15, "b": 0.15}
        queued = schedule([make("a", timeout=0.25), make("b", timeout=0.25)], sleeper(slow), limit=1)
        self.assertEqual(state(queued), {"a": "done", "b": "done"})
        side_by_side = schedule([make("a", timeout=0.1), make("b", timeout=0.1)], sleeper(slow), limit=2)
        self.assertEqual(state(side_by_side), {"a": "timed_out", "b": "timed_out"})
        self.assertEqual({o.reason for o in side_by_side.outcomes.values()}, {"task_timeout"})

    def test_a_cooperative_task_stops_within_milliseconds_of_its_timeout(self):
        scheduler = schedule([make("a", timeout=0.05), make("b")], sleeper({"a": 3.0, "b": 0.02}), limit=1)
        a, b = scheduler.outcomes["a"], scheduler.outcomes["b"]
        self.assertEqual((a.status, a.reason), ("timed_out", "task_timeout"))
        self.assertLess(a.late_ms, 100)
        self.assertLess(b.started_ms, 200, "the slot came free as soon as the tool really stopped")
        self.assertLess(scheduler.wall_ms, 1000)
        self.assertEqual(scheduler.threads_alive, 0)

    def test_work_that_cannot_stop_keeps_its_slot_until_it_really_ends(self):
        scheduler = schedule([make("a", timeout=0.05), make("b")], sleeper({"a": 0.3, "b": 0.02}, cooperative=False), limit=1)
        a, b = scheduler.outcomes["a"], scheduler.outcomes["b"]
        self.assertEqual(a.status, "timed_out")
        self.assertLess(a.ended_ms, 150, "the scheduler stopped waiting at the timeout")
        self.assertGreaterEqual(a.late_ms, 150, "but the work ran on")
        self.assertGreaterEqual(b.started_ms, 250, "so the next task could not take the slot before it ended")
        self.assertEqual(peak_concurrency(list(scheduler.outcomes.values())), 1)
        self.assertEqual(scheduler.threads_alive, 0)

    def test_the_deadline_cancels_what_runs_and_skips_what_waits(self):
        tasks = [make(name) for name in "abcde"]
        scheduler = schedule(tasks, sleeper({name: 0.2 for name in "abcde"}), limit=2, deadline_s=0.3)
        self.assertEqual(state(scheduler), {"a": "done", "b": "done", "c": "cancelled", "d": "cancelled", "e": "skipped"})
        self.assertEqual({o.reason for o in scheduler.outcomes.values() if o.status != "done"}, {"deadline"})
        self.assertIsNone(scheduler.outcomes["e"].started_ms)
        self.assertEqual((scheduler.stop_reason, scheduler.stops_seen), ("deadline", 1))
        self.assertLess(scheduler.wall_ms, 600)
        self.assertEqual(scheduler.threads_alive, 0)

    def test_continue_lets_the_others_finish(self):
        tasks = [make("a"), make("b"), make("c")]
        scheduler = schedule(tasks, sleeper({"a": 0.02, "b": 0.1, "c": 0.05}, fail=("a",)), limit=2, on_failure="continue")
        self.assertEqual(state(scheduler), {"a": "failed", "b": "done", "c": "done"})
        self.assertEqual(scheduler.outcomes["a"].detail["error_type"], "Boom")
        self.assertIsNone(scheduler.stop_reason)

    def test_cancel_all_stops_the_running_and_skips_the_waiting_and_names_the_cause(self):
        tasks = [make("a"), make("b"), make("c")]
        scheduler = schedule(tasks, sleeper({"a": 0.02, "b": 3.0, "c": 0.05}, fail=("a",)), limit=2, on_failure="cancel_all")
        self.assertEqual(state(scheduler), {"a": "failed", "b": "cancelled", "c": "skipped"})
        self.assertEqual((scheduler.stop_reason, scheduler.stop_origin), ("policy", "a"))
        self.assertEqual({o.reason for o in scheduler.outcomes.values()}, {"error", "policy"})
        self.assertLess(scheduler.wall_ms, 1000)
        self.assertEqual(scheduler.threads_alive, 0)

    def test_a_timeout_triggers_the_failure_policy_too(self):
        scheduler = schedule([make("a", timeout=0.05), make("b")], sleeper({"a": 3.0, "b": 3.0}), limit=2,
                             on_failure="cancel_all")
        self.assertEqual(state(scheduler), {"a": "timed_out", "b": "cancelled"})

    def test_a_task_that_needs_a_failed_task_never_starts_but_a_settled_join_still_runs(self):
        tasks = [make("a"), make("strict", ["a"]), make("lenient", ["a"], join="settled")]
        scheduler = schedule(tasks, sleeper(fail=("a",)))
        self.assertEqual(state(scheduler), {"a": "failed", "strict": "skipped", "lenient": "done"})
        self.assertEqual(scheduler.outcomes["strict"].detail, {"blocked_by": ["a"]})
        self.assertEqual(scheduler.results["lenient"]["inputs"], {"after": [None]})

    def test_all_at_once_ignores_the_dependencies_and_the_check_sees_it(self):
        tasks = [make("a"), make("b", ["a"])]
        scheduler = schedule(tasks, sleeper({"a": 0.1, "b": 0.02}), schedule="all_at_once")
        self.assertLess(scheduler.outcomes["b"].started_ms, scheduler.outcomes["a"].ended_ms)
        self.assertEqual(scheduler.results["b"]["inputs"], {"after": [None]})
        self.assertEqual(dependency_violation(scheduler), ("b", "a"))

    def test_a_limit_does_not_fix_a_dependency_bug_it_only_changes_who_finds_what(self):
        tasks = [make("a"), make("b"), make("c", ["a", "b"])]
        work = sleeper({"a": 0.03, "b": 0.2, "c": 0.01})
        queued = schedule(tasks, work, schedule="all_at_once", limit=2)  # c takes the slot a frees, while b still runs
        self.assertEqual(queued.results["c"]["inputs"], {"after": ["a", None]})
        self.assertEqual(dependency_violation(queued), ("c", "b"))
        roomy = schedule(tasks, work, schedule="all_at_once", limit=3)  # c gets a slot at once and reads nothing
        self.assertEqual(roomy.results["c"]["inputs"], {"after": [None, None]})

    def test_an_error_in_the_work_fails_that_task_only(self):
        scheduler = schedule([make("a"), make("b")], sleeper(raises={"a": ValueError("bad input")}))
        self.assertEqual(state(scheduler), {"a": "failed", "b": "done"})
        self.assertEqual(scheduler.outcomes["a"].detail, {"error_type": "ValueError", "error": "bad input"})

    def test_a_timeout_raised_by_the_work_is_a_failure_not_the_schedulers_timer(self):
        scheduler = schedule([make("a")], sleeper(raises={"a": TimeoutError("socket timed out")}))
        outcome = scheduler.outcomes["a"]
        self.assertEqual((outcome.status, outcome.reason, outcome.detail["error_type"]), ("failed", "error", "TimeoutError"))

    def test_a_stop_request_cancels_everything_and_the_scheduler_still_returns(self):
        started = time.perf_counter()

        def refuse(outcome):
            raise RunCancelled("stopped")  # what the platform does with an event after a stop

        scheduler = schedule([make(name) for name in "abcd"], sleeper({name: 3.0 for name in "abcd"}), limit=2,
                             stop_requested=lambda: time.perf_counter() - started > 0.1, on_outcome=refuse)
        self.assertEqual(state(scheduler), {"a": "cancelled", "b": "cancelled", "c": "skipped", "d": "skipped"})
        self.assertEqual({o.reason for o in scheduler.outcomes.values()}, {"user_stop"})
        self.assertLess(scheduler.wall_ms, 1000)
        self.assertEqual(scheduler.threads_alive, 0)

    def test_a_bug_in_a_callback_is_raised_not_swallowed(self):
        def broken(outcome):
            raise ValueError("bug in callback")
        with self.assertRaisesRegex(ValueError, "bug in callback"):
            schedule([make("a"), make("b")], on_outcome=broken)
        self.assertEqual(live_threads(), [])

    def test_every_status_is_one_of_the_documented_five(self):
        scheduler = schedule([make("a"), make("b", ["a"])], sleeper(fail=("a",)))
        self.assertTrue(set(state(scheduler).values()) <= set(STATUSES))
        self.assertEqual(STATUSES, tuple(texts_for("en").status_names))


class AnalysisTests(unittest.TestCase):
    def outcome(self, start, end, release=None, status="done"):
        return Outcome(make("t"), status, None, start, end, end if release is None else release)

    def test_peak_concurrency_is_recomputed_from_the_timestamps(self):
        spans = [self.outcome(0, 100), self.outcome(10, 90), self.outcome(20, 120), self.outcome(95, 200)]
        self.assertEqual(peak_concurrency(spans), 3)  # at 20 three overlap; at 95 only the first, third and fourth do
        self.assertEqual(peak_concurrency([self.outcome(0, 100), self.outcome(100, 200)]), 1, "an end sorts before a start")
        self.assertEqual(peak_concurrency([]), 0)

    def test_a_slot_is_held_until_release_not_until_the_scheduler_gave_up(self):
        late = self.outcome(0, 50, release=300, status="timed_out")
        self.assertEqual(peak_concurrency([late, self.outcome(100, 150)]), 2)
        self.assertEqual(late.late_ms, 250)
        self.assertEqual(self.outcome(0, 50, release=300).late_ms, 0, "only a task that was given up on can be late")

    def test_skipped_tasks_hold_no_slot(self):
        skipped = Outcome(make("s"), "skipped", "deadline", None, 5, 5)
        self.assertEqual(peak_concurrency([skipped, self.outcome(0, 10)]), 1)


class ScenarioTests(unittest.TestCase):
    """Each scenario runs once for the whole class; the tests read different things from the same events."""
    runs: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.runs = {
            "dependency": run_case({"scenario": "dependency", "tool_delay_ms": DELAY}, completion=None),
            "limits": run_case({"scenario": "limits", "tool_delay_ms": 100}),
            "timeouts": run_case({"scenario": "timeouts"}),
            "failure": run_case({"scenario": "failure", "tool_delay_ms": DELAY}),
        }

    def events(self, name):
        return self.runs[name][1]

    def test_the_dependency_scenario_runs_serial_by_dependency_and_ignoring_dependencies(self):
        events = self.events("dependency")
        self.assertEqual([d["variant"] for d in of(events, "lesson.graph")], ["serial", "by-dependency", "all-at-once"])
        serial, together, naive = (statuses(events, name) for name in ("serial", "by-dependency", "all-at-once"))
        self.assertEqual(set(serial.values()) | set(together.values()), {"done"})
        self.assertEqual(naive["sheet"], "failed")
        self.assertEqual(task_events(events, "all-at-once")["sheet"]["error_type"], "MissingInput")
        for index, wall in enumerate((variant_metrics(events, i)["wall_ms"] for i in range(3))):
            self.assertGreater(wall, 0, index)

    def test_ignoring_the_dependency_is_fast_and_wrong(self):
        events = self.events("dependency")
        walls = [variant_metrics(events, i)["wall_ms"] for i in range(3)]
        self.assertGreaterEqual(walls[0], 2 * DELAY, "serial costs the two reads one after the other")
        self.assertLess(walls[1], walls[0], "by dependency the reads overlap")
        self.assertLess(walls[2], walls[0], "ignoring dependencies is not slower: it is just wrong")
        found = checks(events)
        self.assertTrue(found["dependencies.serial"]["passed"] and found["dependencies.by-dependency"]["passed"])
        self.assertFalse(found["dependencies.all-at-once"]["passed"])
        self.assertFalse(found["complete.all-at-once"]["passed"])
        self.assertTrue(found["complete.by-dependency"]["passed"])
        results = [r for r in of(events, "tool_result") if r["name"] == "build_sheet"]
        self.assertEqual([r["result"]["ok"] for r in results], [True, True, False])
        self.assertEqual(results[2]["result"]["error_type"], "MissingInput")
        self.assertEqual(metrics(events)["verdict.all-at-once"], texts_for("zh-CN").verdicts["failed"])

    def test_the_sheet_tool_is_called_once_in_every_variant_even_when_it_cannot_work(self):
        calls = [c for c in of(self.events("dependency"), "tool_call") if c["function"]["name"] == "build_sheet"]
        self.assertEqual(len(calls), 3, "the wrong schedule does not skip it: nothing in it knows the inputs are missing")
        self.assertEqual(of(self.events("dependency"), "request"), [])
        self.assertEqual(metrics(self.events("dependency"))["model_calls"], 0)

    def test_peak_concurrency_in_the_dependency_scenario(self):
        events = self.events("dependency")
        serial, together, naive = (variant_metrics(events, i)["peak"] for i in range(3))
        self.assertEqual((serial, together), (1, 2))
        self.assertIn(naive, (2, 3), "the wrong schedule starts the sheet with the reads; on a loaded machine it can overlap both")

    def test_each_limit_is_respected_and_a_lower_limit_costs_more_wall_time(self):
        events = self.events("limits")
        pause = 100
        walls = [metrics(events)[f"wall_ms.limit-{n}"] for n in (1, 2, 4)]
        self.assertGreaterEqual(walls[0], 8 * pause)
        self.assertGreaterEqual(walls[1], 4 * pause)
        self.assertGreater(walls[0], walls[1] + pause)
        self.assertGreater(walls[1], walls[2] + pause)
        self.assertEqual([metrics(events)[f"peak.limit-{n}"] for n in (1, 2, 4)], [1, 2, 4])
        self.assertTrue(checks(events)["limit_held"]["passed"])
        self.assertEqual([metrics(events)[f"model_calls.limit-{n}"] for n in (1, 2, 4)], [4, 4, 4], "the limit changes no counts")
        self.assertEqual(metrics(events)["model_calls"], 12)

    def test_limits_variants_do_the_same_work_in_a_different_order_of_waiting(self):
        events = self.events("limits")
        for name in ("limit-1", "limit-2", "limit-4"):
            self.assertEqual(set(statuses(events, name).values()), {"done"}, name)
        self.assertTrue(all(checks(events)[f"complete.limit-{n}"]["passed"] for n in (1, 2, 4)))
        self.assertGreaterEqual(variant_metrics(events, 0)["serial_ms"], variant_metrics(events, 0)["wall_ms"] - 20)
        self.assertGreater(variant_metrics(events, 2)["serial_ms"], variant_metrics(events, 2)["wall_ms"] * 2,
                           "four at a time: the durations add up to far more than the wall-clock time")

    def test_requests_and_responses_pair_by_branch_and_calls_by_id_across_variants(self):
        events = self.events("limits")
        requests, responses = of(events, "request"), of(events, "response")
        branches = [r["branch"] for r in requests]
        self.assertEqual(len(branches), 12)
        self.assertEqual(sorted(set(branches)), sorted(f"limit-{n}/sum-{lesson}" for n in (1, 2, 4) for lesson in NOTES))
        self.assertEqual(sorted(r["branch"] for r in responses), sorted(branches))
        call_ids = [c["id"] for c in of(events, "tool_call")]
        self.assertEqual(len(call_ids), 15)
        self.assertEqual(len(set(call_ids)), 15)
        self.assertEqual(sorted(r["tool_call_id"] for r in of(events, "tool_result")), sorted(call_ids))
        self.assertTrue(all(c["origin"] == "course_program" for c in of(events, "tool_call")))

    def test_every_variant_orders_its_stages(self):
        events = self.events("limits")
        for name in ("limit-1", "limit-2", "limit-4"):
            tasks = task_events(events, name)
            self.assertGreaterEqual(tasks["sheet"]["started_ms"], max(tasks[f"sum-{n}"]["ended_ms"] for n in NOTES))
            for lesson in NOTES:
                self.assertGreaterEqual(tasks[f"sum-{lesson}"]["started_ms"], tasks[f"read-{lesson}"]["ended_ms"])

    def test_rounds_do_not_collide_across_variants(self):
        events = self.events("limits")
        by_branch = {}
        for kind, data, number in events:
            if kind == "request":
                by_branch[data["branch"]] = number
        self.assertEqual({by_branch[f"limit-{n}/sum-{NOTES[0]}"] for n in (1, 2, 4)}, {2, 5, 8})

    def test_the_timeouts_scenario_compares_waiting_a_task_timeout_and_a_deadline(self):
        events = self.events("timeouts")
        waited, timed, deadline = (statuses(events, name) for name in ("waited", "task-timeout", "deadline"))
        self.assertEqual(set(waited.values()), {"done"})
        self.assertEqual({k: v for k, v in timed.items() if v != "done"},
                         {"read-context-budget": "timed_out", "sum-context-budget": "skipped"})
        self.assertEqual(sorted(k for k, v in deadline.items() if v == "cancelled"), ["sum-context-budget", "sum-prompt-caching"])
        self.assertEqual(deadline["sheet"], "skipped")
        zh = texts_for("zh-CN")
        self.assertEqual([metrics(events)[f"verdict.{n}"] for n in ("waited", "task-timeout", "deadline")],
                         [zh.verdicts["complete"], zh.verdicts["partial"], zh.verdicts["partial"]])
        walls = {n: metrics(events)[f"wall_ms.{n}"] for n in ("waited", "task-timeout")}
        self.assertGreaterEqual(walls["waited"], 1500, "without a timeout the run waits for the slow note")
        self.assertLess(walls["task-timeout"], walls["waited"] - 500, "the timeout stopped the wait")

    def test_a_task_timeout_stops_the_tool_and_leaves_what_is_missing_on_the_sheet(self):
        events = self.events("timeouts")
        slow = task_events(events, "task-timeout")["read-context-budget"]
        self.assertEqual((slow["status"], slow["reason"]), ("timed_out", "task_timeout"))
        self.assertGreaterEqual(slow["duration_ms"], 500)
        self.assertLess(slow["late_ms"], 100, "the tool heard the stop signal and quit within milliseconds")
        stopped = [r for r in of(events, "tool_result") if r["result"].get("error_type") == "TaskStopped"]
        self.assertEqual([r["tool_call_id"] for r in stopped], ["call-task-timeout-read-context-budget"])
        self.assertEqual(variant_metrics(events, 1)["sheet"], texts_for("zh-CN").sheet_partial.format(missing="context-budget"))
        self.assertEqual(variant_metrics(events, 1)["model_calls"], 3, "no request was sent for the note that never arrived")
        blocked = task_events(events, "task-timeout")["sum-context-budget"]
        self.assertEqual((blocked["status"], blocked["blocked_by"]), ("skipped", ["read-context-budget"]))

    def test_the_deadline_stops_the_work_and_the_report_says_who_was_cut_off(self):
        events = self.events("timeouts")
        stop = [d for d in of(events, "lesson.stop") if d["variant"] == "deadline"][0]
        self.assertEqual((stop["reason"], stop["origin"]), ("deadline", None))
        self.assertGreaterEqual(stop["at_ms"], 700)
        self.assertTrue(stop["running"] and set(stop["running"]) <= {"sum-context-budget", "sum-prompt-caching"})
        cut = task_events(events, "deadline")
        self.assertEqual({d["reason"] for d in cut.values() if d["status"] != "done"}, {"deadline"})
        # A request that was already sent cannot be recalled: all four really went out, and two came back late.
        self.assertEqual(variant_metrics(events, 2)["model_calls"], 4)
        self.assertEqual(variant_metrics(events, 2)["late"], 2)
        self.assertEqual(variant_metrics(events, 2)["sheet"], texts_for("zh-CN").sheet_not_built)
        self.assertEqual([d["variant"] for d in of(events, "lesson.stop")], ["deadline"], "only the deadline variant stops")

    def test_no_thread_is_left_in_any_variant(self):
        for name in ("dependency", "limits", "timeouts", "failure"):
            self.assertTrue(checks(self.events(name))["no_orphans"]["passed"], name)
        self.assertEqual(live_threads(), [])

    def test_the_failure_scenario_compares_carrying_on_with_cancelling_everything(self):
        events = self.events("failure")
        carry, stop = statuses(events, "continue"), statuses(events, "cancel-all")
        self.assertEqual((carry["read-messages-context"], carry["sum-messages-context"], carry["sheet"]),
                         ("failed", "skipped", "done"))
        self.assertEqual(sum(status == "done" for status in carry.values()), 7)
        failed = task_events(events, "continue")["read-messages-context"]
        self.assertEqual((failed["error_type"], failed["reason"]), ("NoteLocked", "error"))
        self.assertEqual((stop["read-messages-context"], stop["read-application-state"]), ("failed", "cancelled"))
        self.assertTrue(all(status == "skipped" for task_id, status in stop.items()
                            if task_id not in ("read-messages-context", "read-application-state")), stop)
        self.assertEqual((metrics(events)["model_calls.continue"], metrics(events)["model_calls.cancel-all"]), (3, 0))
        zh = texts_for("zh-CN")
        self.assertEqual((metrics(events)["verdict.continue"], metrics(events)["verdict.cancel-all"]),
                         (zh.verdicts["partial"], zh.verdicts["failed"]))
        lesson_stop = of(events, "lesson.stop")
        self.assertEqual([(d["variant"], d["reason"], d["origin"], d["running"]) for d in lesson_stop],
                         [("cancel-all", "policy", "read-messages-context", ["read-application-state"])])

    def test_the_answer_has_one_line_per_variant_and_names_what_is_missing(self):
        answer = self.runs["failure"][0]
        zh = texts_for("zh-CN")
        self.assertIn(zh.variant_names["continue"], answer)
        self.assertIn(zh.variant_names["cancel-all"], answer)
        self.assertIn("read-messages-context（失败）", answer)
        self.assertIn(zh.verdicts["partial"], answer)

    def test_the_graph_event_lists_the_levels_the_scheduler_read(self):
        graph = of(self.events("limits"), "lesson.graph")
        self.assertEqual(len(graph), 3)
        self.assertEqual([len(layer) for layer in graph[0]["levels"]], [4, 4, 1])
        self.assertEqual({node["id"]: node["needs"] for node in graph[0]["nodes"]}["sheet"], [f"sum-{n}" for n in NOTES])
        self.assertEqual({node["id"]: node["join"] for node in graph[0]["nodes"]}["sheet"], "settled")

    def test_the_comparison_table_has_one_row_per_variant(self):
        table = total(self.events("limits"))["table"]
        self.assertEqual(len(table["columns"]), 9)
        self.assertEqual([row[0] for row in table["rows"]], [texts_for("zh-CN").variant_names[f"limit-{n}"] for n in (1, 2, 4)])
        self.assertTrue(all(len(row) == 9 for row in table["rows"]))


class RunTests(unittest.TestCase):
    def test_the_models_scenarios_need_a_model_connection_and_the_dependency_scenario_does_not(self):
        for scenario in ("limits", "timeouts", "failure"):
            with self.subTest(scenario=scenario), self.assertRaisesRegex(ValueError, "dependency"):
                run_case({"scenario": scenario}, completion=None)
        run_case({"scenario": "dependency", "tool_delay_ms": 10}, completion=None)

    def test_a_provider_error_fails_that_summary_only(self):
        inner = create_completion("test", {"tool_delay_ms": DELAY}, "zh-CN")

        def flaky(body, key):
            if texts_for("zh-CN").notes["prompt-caching"] in body["messages"][1]["content"]:
                raise RuntimeError("provider unavailable")
            return inner(body, key)
        _, events = run_case({"scenario": "limits", "tool_delay_ms": DELAY}, completion=flaky)
        for name in ("limit-1", "limit-2", "limit-4"):
            failed = task_events(events, name)["sum-prompt-caching"]
            self.assertEqual((failed["status"], failed["error_type"], failed["error"]), ("failed", "RuntimeError", "provider unavailable"))
            self.assertEqual(sum(status == "done" for status in statuses(events, name).values()), 8)

    def test_an_empty_model_answer_is_a_structured_failure_not_a_summary(self):
        def silent(body, key):
            return {"choices": [{"message": {"role": "assistant", "content": "  "}, "finish_reason": "stop"}]}
        _, events = run_case({"scenario": "limits", "tool_delay_ms": DELAY}, completion=silent)
        self.assertEqual({d["error_type"] for d in of(events, "lesson.task") if d["kind"] == "model"}, {"EmptyReply"})
        self.assertEqual(metrics(events)["verdict.limit-4"], texts_for("zh-CN").verdicts["failed"])

    def test_the_platforms_model_call_budget_still_applies_across_variants(self):
        _, events = run_case({"scenario": "limits", "tool_delay_ms": DELAY}, max_calls=6)
        self.assertEqual(len(of(events, "request")), 6)
        refused = [d for d in of(events, "lesson.task") if d.get("error_type") == "RuntimeError"]
        self.assertEqual(len(refused), 6)
        self.assertEqual({d["variant"] for d in refused}, {"limit-2", "limit-4"})
        self.assertTrue(all(d["kind"] == "model" for d in refused))

    def test_a_stop_ends_the_run_with_no_thread_left(self):
        for inputs, after in (({"scenario": "limits", "tool_delay_ms": DELAY}, 0.04),
                              ({"scenario": "limits", "tool_delay_ms": DELAY}, 0.2),
                              ({"scenario": "failure", "tool_delay_ms": 300}, 0.15),
                              ({"scenario": "timeouts", "tool_delay_ms": 300, "slow_delay_ms": 3000}, 0.8)):
            started = time.perf_counter()
            with self.subTest(inputs=inputs, after=after), self.assertRaises(RunCancelled):
                run_case(inputs, cancelled=lambda: time.perf_counter() - started > after)
            self.assertEqual(live_threads(), [])

    def test_a_stop_reaches_a_tool_that_would_wait_seconds(self):
        started = time.perf_counter()
        with self.assertRaises(RunCancelled):
            run_case({"scenario": "limits", "tool_delay_ms": 3000}, cancelled=lambda: time.perf_counter() - started > 0.1)
        self.assertLess(time.perf_counter() - started, 1.5, "tools listen to the stop signal instead of sleeping on")
        self.assertEqual(live_threads(), [])

    def test_a_stop_between_variants_skips_the_variants_not_yet_started(self):
        events = []
        values = validate_inputs(runtime, {"scenario": "dependency", "tool_delay_ms": 30})
        context = RunContext(
            lesson_id="async-concurrency", exercise_id="test", question="", mode="offline", model="m",
            representation="sdk_standardized", inputs=values, api_key="", completion=None, max_model_calls=1,
            cancelled=lambda: any(kind == "lesson.report" for kind, _, _ in events),
            emit_event=lambda kind, data, number: events.append((kind, data, number)))
        with self.assertRaises(RunCancelled):
            execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
        self.assertEqual({d["variant"] for kind, d, _ in events if kind == "lesson.graph"}, {"serial"})

    def test_english_runs_carry_no_chinese_anywhere(self):
        small = {"tool_delay_ms": DELAY, "slow_delay_ms": 300, "task_timeout_ms": 120, "deadline_ms": 200}
        for scenario in ("dependency", "limits", "timeouts", "failure"):
            with self.subTest(scenario=scenario):
                completion = None if scenario == "dependency" else "fixture"
                answer, events = run_case({"scenario": scenario, **small}, locale="en", completion=completion)
                self.assertFalse(CJK.search(json.dumps(events, ensure_ascii=False) + answer))
        _, events = run_case({"scenario": "dependency", "tool_delay_ms": DELAY}, completion=None)
        self.assertTrue(CJK.search(json.dumps(events, ensure_ascii=False)))

    def test_both_languages_give_the_same_structure(self):
        shapes = []
        for locale in LOCALES:
            _, events = run_case({"scenario": "failure", "tool_delay_ms": DELAY}, locale=locale)
            shapes.append((sorted((d["variant"], d["id"], d["status"]) for d in of(events, "lesson.task")),
                           [item["id"] for item in total(events)["metrics"] if "id" in item],
                           [item["id"] for item in total(events)["checks"]]))
        self.assertEqual(shapes[0], shapes[1])

    def test_events_are_json_and_free_of_absolute_paths(self):
        _, events = run_case({"scenario": "failure", "tool_delay_ms": DELAY})
        text = json.dumps(events, ensure_ascii=False)
        self.assertNotIn("/home/", text)
        self.assertNotIn("Traceback", text)


class VariantTests(unittest.TestCase):
    def test_each_scenario_builds_its_variants_from_the_inputs(self):
        def ids(**fields):
            return [(v.id, v.workload, v.limit) for v in build_variants(runtime.Inputs(**fields))]
        self.assertEqual(ids(scenario="dependency"), [("serial", "pair", 1), ("by-dependency", "pair", 4), ("all-at-once", "pair", 4)])
        self.assertEqual(ids(scenario="limits"), [("limit-1", "review", 1), ("limit-2", "review", 2), ("limit-4", "review", 4)])
        self.assertEqual(ids(scenario="timeouts", max_concurrency=3), [("waited", "review", 3), ("task-timeout", "review", 3), ("deadline", "review", 3)])
        self.assertEqual(ids(scenario="failure"), [("continue", "review", 2), ("cancel-all", "review", 2)])

    def test_only_the_dependency_scenario_has_the_wrong_schedule(self):
        for scenario in ("limits", "timeouts", "failure"):
            self.assertEqual({v.schedule for v in build_variants(runtime.Inputs(scenario=scenario))}, {"by_dependency"})
        self.assertEqual([v.schedule for v in build_variants(runtime.Inputs(scenario="dependency"))],
                         ["by_dependency", "by_dependency", "all_at_once"])

    def test_the_inputs_reach_the_variants_that_use_them(self):
        values = runtime.Inputs(scenario="timeouts", slow_lesson="prompt-caching", task_timeout_ms=250, deadline_ms=400)
        waited, timed, deadline = build_variants(values)
        self.assertEqual((waited.slow_lesson, waited.tool_timeout_ms, waited.deadline_ms), ("prompt-caching", 30000, 300000))
        self.assertEqual(timed.tool_timeout_ms, 250)
        self.assertEqual((deadline.deadline_ms, deadline.slow_lesson), (400, "none"))
        locked = build_variants(runtime.Inputs(scenario="failure", locked_lesson="context-budget"))
        self.assertEqual({v.locked_lesson for v in locked}, {"context-budget"})
        self.assertEqual([v.on_failure for v in locked], ["continue", "cancel_all"])

    def test_the_slow_and_locked_notes_are_written_into_the_tool_calls(self):
        values = runtime.Inputs(scenario="timeouts", slow_delay_ms=900, tool_delay_ms=40)
        variant = build_variants(values)[0]
        reads = {task.id: task.inputs for task in build_tasks(variant, values) if task.kind == "tool" and task.name == "read_note"}
        self.assertEqual({k: v["delay_ms"] for k, v in reads.items()}, {"read-messages-context": 40, "read-application-state": 40,
                                                                     "read-context-budget": 900, "read-prompt-caching": 40})
        locked = build_variants(runtime.Inputs(scenario="failure"))[0]
        reads = {task.id: task.inputs["lock"] for task in build_tasks(locked, runtime.Inputs(scenario="failure"))
                 if task.name == "read_note"}
        self.assertEqual([k for k, v in reads.items() if v], ["read-messages-context"])


class InputTests(unittest.TestCase):
    def test_bad_inputs_are_refused_before_anything_runs(self):
        for bad in ({"max_concurrency": 0}, {"max_concurrency": 5}, {"scenario": "all"}, {"tool_delay_ms": 5},
                    {"task_timeout_ms": 10}, {"deadline_ms": 10}, {"slow_delay_ms": 10001}, {"slow_lesson": "no-such-lesson"},
                    {"locked_lesson": "x"}, {"unknown_field": 1}, {"tool_delay_ms": "slow"}, {"schedule": "all_at_once"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)

    def test_defaults_describe_the_limits_scenario(self):
        values = validate_inputs(runtime, {})
        self.assertEqual((values["scenario"], values["tool_delay_ms"], values["max_concurrency"]), ("limits", 200, 2))
        self.assertEqual((values["slow_lesson"], values["locked_lesson"]), ("context-budget", "messages-context"))

    def test_the_fixture_has_a_sentence_for_every_note(self):
        for locale in LOCALES:
            t, f = texts_for(locale), fixture_texts_for(locale)
            self.assertEqual(set(f.summaries), set(NOTES), locale)
            self.assertEqual(set(t.notes), set(NOTES), locale)

    def test_the_fixture_answers_what_is_in_the_request_and_nothing_else(self):
        for locale in LOCALES:
            t, f = texts_for(locale), fixture_texts_for(locale)
            complete = create_completion("x", {"tool_delay_ms": 10}, locale)
            for lesson in NOTES:
                body = {"messages": [{"role": "system", "content": t.summary_system},
                                     {"role": "user", "content": t.summary_request.format(lesson=lesson, note=t.notes[lesson])}]}
                self.assertEqual(complete(body, "")["choices"][0]["message"]["content"], f.summaries[lesson])
            self.assertEqual(complete({"messages": [{"role": "user", "content": "unrelated"}]}, "")["choices"][0]["message"]["content"], "")

    def test_every_variant_and_scenario_has_a_name_in_both_languages(self):
        for locale in LOCALES:
            t = texts_for(locale)
            for scenario in ("dependency", "limits", "timeouts", "failure"):
                self.assertIn(scenario, t.scenario_names)
                for variant in build_variants(runtime.Inputs(scenario=scenario)):
                    self.assertIn(variant.id, t.variant_names, (locale, variant.id))


if __name__ == "__main__":
    unittest.main()
