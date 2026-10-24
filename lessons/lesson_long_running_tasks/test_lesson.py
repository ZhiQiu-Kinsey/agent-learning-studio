"""Behavior tests for long-running-tasks: deterministic model data; the executor, jobs, scheduler and checks really run in Python.

The clock is virtual, so nothing here waits for real time; threads are real, and every test ends with a check
that no background thread is left.
"""
import hashlib
import json
import re
import threading
import time
import unittest
from types import SimpleNamespace

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_long_running_tasks import runtime
from lessons.lesson_long_running_tasks.executor import (EXIT_CODES, THREAD_PREFIX, BackgroundExecutor, JobRefused,
                                                        VirtualClock)
from lessons.lesson_long_running_tasks.fixtures import create_completion
from lessons.lesson_long_running_tasks.goal import SCENARIOS, decide, evaluate_goal
from lessons.lesson_long_running_tasks.jobs import PACK, PASS_LINE, SCORES, SPECS
from lessons.lesson_long_running_tasks.locales import texts_for
from lessons.lesson_long_running_tasks.scheduler import QUEUE_LIMIT, Scheduler

ZH, EN = texts_for("zh-CN"), texts_for("en")
CJK = re.compile(r"[　-〿一-鿿＀-￯]")
EXERCISE_INPUTS = {"background-basic": {"scenario": "nightly"}, "failed-job": {"scenario": "late"},
                   "budget-stop": {"scenario": "deep", "max_rounds": 5},
                   "schedule-skip": {"scenario": "schedule", "overlap": "skip"},
                   "schedule-queue": {"scenario": "schedule", "overlap": "queue"},
                   "schedule-parallel": {"scenario": "schedule", "overlap": "parallel"}}


def live_threads():
    return [thread.name for thread in threading.enumerate() if thread.name.startswith(THREAD_PREFIX)]


def run_case(exercise_id, inputs=None, completion="fixture", budget=12, cancelled=lambda: False, locale="zh-CN",
             stop_after_events=None):
    events = []
    values = validate_inputs(runtime, inputs if inputs is not None else EXERCISE_INPUTS[exercise_id])
    if completion == "fixture":
        completion = None if values["scenario"] == "schedule" else create_completion(exercise_id, values, locale)

    def emit(kind, data, number):
        events.append((kind, data, number))

    stopped = (lambda: cancelled() or (stop_after_events is not None and len(events) >= stop_after_events))
    context = RunContext(
        lesson_id="long-running-tasks", exercise_id=exercise_id, question="", mode="offline", model="fixture-model",
        representation="sdk_standardized", inputs=values, api_key="", completion=completion, max_model_calls=budget,
        cancelled=stopped, emit_event=emit, locale=locale)
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def report(events):
    return of(events, "lesson.report")[-1]


def metrics(events):
    return {item["id"]: item["value"] for item in report(events)["metrics"] if "id" in item}


def checks(events):
    return {item["id"]: item for item in report(events)["checks"]}


def requests(events):
    return [json.dumps(data["body"]["messages"], ensure_ascii=False) for kind, data, _ in events if kind == "request"]


def script(*steps):
    """A custom model: step n of the script answers the n-th request; a string is a reply, a list of (name, args) calls."""
    state = {"n": 0}

    def complete(body, key):
        action = steps[min(state["n"], len(steps) - 1)]
        state["n"] += 1
        if isinstance(action, str):
            return {"choices": [{"message": {"role": "assistant", "content": action}, "finish_reason": "stop"}]}
        calls = [{"id": f"c{state['n']}_{i}", "type": "function",
                  "function": {"name": name, "arguments": json.dumps(arguments)}} for i, (name, arguments) in enumerate(action)]
        return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": calls}}]}
    return complete


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.t = ZH
        self.executor = BackgroundExecutor(VirtualClock(), self.t)

    def tearDown(self):
        self.executor.shutdown("run_end")
        self.assertEqual(live_threads(), [])

    def test_start_returns_at_once_with_a_job_parked_on_the_clock(self):
        job = self.executor.start("checksum_pack", origin="model", round_number=1)
        self.assertEqual((job.id, job.status, job.progress, job.started_at), ("job-1", "running", 0, 0))
        self.assertTrue(job.thread.is_alive())
        self.assertEqual(self.executor.clock.now, 0, "starting a job moves no time")
        self.assertEqual(self.executor.next_terminal(), 12)

    def test_jobs_end_on_their_declared_schedule_and_compute_real_results(self):
        grades = self.executor.start("grade_stats", origin="model")
        pack = self.executor.start("checksum_pack", origin="model")
        self.executor.advance_to(5)
        self.assertEqual((grades.status, grades.progress, pack.progress), ("running", 1, 1))
        self.executor.advance_to(9)
        self.assertEqual((grades.status, grades.finished_at, grades.exit_code), ("completed", 6, 0))
        self.assertIsNone(grades.observed_at, "the runner has not looked yet")
        self.assertEqual(grades.result["value"], str(sum(score >= PASS_LINE for score in SCORES)))
        self.executor.advance_to(40)
        digest = hashlib.sha256(b"".join(body for _, body in PACK)).hexdigest()[:12]
        self.assertEqual((pack.status, pack.finished_at, pack.result["value"]), ("completed", 12, digest))
        self.assertEqual(pack.result["detail"], self.t.detail_checksum.format(
            files=6, size=sum(len(body) for _, body in PACK), digest=digest))

    def test_a_job_that_raises_fails_alone_with_the_run_language_error(self):
        for locale in ("zh-CN", "en"):
            executor = BackgroundExecutor(VirtualClock(), texts_for(locale))
            failing = executor.start("late_import", origin="model")
            fine = executor.start("grade_stats", origin="model")
            executor.advance_to(10)
            self.assertEqual((failing.status, failing.exit_code, failing.finished_at, failing.progress),
                             ("failed", 1, 6, 1))
            self.assertEqual(failing.error, {"error_type": "ValueError",
                                             "error": texts_for(locale).bad_score.format(row=6, value="8x")})
            self.assertEqual(fine.status, "completed", "a failing sibling does not stop it")
            executor.shutdown("run_end")

    def test_default_deadline_times_the_long_scan_out(self):
        scan = self.executor.start("deep_scan", origin="model")
        self.executor.advance_to(39)
        self.assertEqual((scan.status, scan.progress), ("running", 3))
        self.executor.advance_to(40)
        # The fourth step ends exactly at the deadline and counts; the fifth would end at 50, so the job times out at 40.
        self.assertEqual((scan.status, scan.exit_code, scan.finished_at, scan.progress), ("timed_out", 124, 40, 4))
        long_deadline = self.executor.start("deep_scan", origin="model", timeout_seconds=120)
        self.executor.advance_to(40 + 80)
        self.assertEqual((long_deadline.status, long_deadline.result["value"]), ("completed", "2"))

    def test_cancel_stops_the_thread_and_sets_the_exit_code(self):
        job = self.executor.start("deep_scan", origin="model")
        self.executor.advance_to(15)
        self.executor.cancel(job.id, "model_request")
        self.assertEqual((job.status, job.exit_code, job.finished_at, job.cancel_reason, job.progress),
                         ("cancelled", 143, 15, "model_request", 1))
        self.assertFalse(job.thread.is_alive())
        with self.assertRaises(JobRefused) as caught:
            self.executor.cancel(job.id, "model_request")
        self.assertEqual(caught.exception.code, "already_finished")
        with self.assertRaises(JobRefused) as caught:
            self.executor.cancel("job-99", "model_request")
        self.assertEqual(caught.exception.code, "unknown_job")
        self.assertEqual(self.executor.collect_finished(), [], "a cancelled job reports through the cancel, not the injection")

    def test_refusals_are_coded_and_in_the_run_language(self):
        executor = BackgroundExecutor(VirtualClock(), EN, max_running=2)
        executor.start("deep_scan", origin="model")
        executor.start("deep_scan", origin="model")
        cases = [("too_many_jobs", lambda: executor.start("deep_scan", origin="model")),
                 ("unknown_kind", lambda: executor.start("rm_rf", origin="model")),
                 ("bad_timeout", lambda: executor.start("grade_stats", origin="model", timeout_seconds=4)),
                 ("bad_timeout", lambda: executor.start("grade_stats", origin="model", timeout_seconds=True)),
                 ("bad_timeout", lambda: executor.start("grade_stats", origin="model", timeout_seconds=121))]
        for code, action in cases:
            with self.subTest(code=code), self.assertRaises(JobRefused) as caught:
                action()
            self.assertEqual(caught.exception.code, code)
            self.assertFalse(CJK.search(str(caught.exception)))
        self.assertEqual(len(executor.jobs), 2, "a refused start leaves no job behind")
        executor.start("deep_scan", origin="schedule", limit=False)  # the scheduler applies its own cap
        executor.shutdown("run_end")

    def test_results_are_collected_once_oldest_first(self):
        slow = self.executor.start("checksum_pack", origin="model")
        quick = self.executor.start("grade_stats", origin="model")
        self.executor.advance_to(20)
        self.assertEqual([job.id for job in self.executor.collect_finished()], [quick.id, slow.id])
        self.assertEqual((quick.observed_at, slow.observed_at), (20, 20))
        self.assertEqual(self.executor.collect_finished(), [])

    def test_two_executors_give_the_same_timeline(self):
        def timeline():
            executor = BackgroundExecutor(VirtualClock(), self.t, max_running=4)
            try:
                jobs = [executor.start(kind, origin="model") for kind in ("deep_scan", "checksum_pack", "late_import", "grade_stats")]
                for moment in (3, 7, 12, 31, 90):
                    executor.advance_to(moment)
            finally:
                executor.shutdown("run_end")
            return [(job.id, job.status, job.finished_at, job.progress, job.result, job.error) for job in jobs]
        self.assertEqual(timeline(), timeline())

    def test_a_long_run_waits_for_no_real_time(self):
        began = time.monotonic()
        self.executor.start("deep_scan", origin="model", timeout_seconds=120)
        for moment in range(1, 121):
            self.executor.advance_to(moment)
        self.assertLess(time.monotonic() - began, 5)
        self.assertEqual(self.executor.jobs["job-1"].status, "completed")

    def test_the_clock_never_runs_backwards(self):
        self.executor.advance_to(10)
        self.executor.advance_to(4)
        self.assertEqual(self.executor.clock.now, 10)

    def test_shutdown_cancels_running_jobs_joins_threads_and_is_idempotent(self):
        for kind in ("deep_scan", "checksum_pack", "grade_stats"):
            self.executor.start(kind, origin="model")
        self.executor.advance_to(7)  # grade_stats is done, the others are not
        self.assertEqual(len(self.executor.running()), 2)
        cancelled = self.executor.shutdown("run_end")
        self.assertEqual(sorted(job.kind for job in cancelled), ["checksum_pack", "deep_scan"])
        self.assertTrue(all(job.cancel_reason == "run_end" and job.exit_code == 143 for job in cancelled))
        self.assertEqual((self.executor.alive(), live_threads()), (0, []))
        self.assertEqual(self.executor.shutdown("run_end"), [])

    def test_exit_codes_are_the_documented_ones(self):
        self.assertEqual(EXIT_CODES, {"completed": 0, "failed": 1, "timed_out": 124, "cancelled": 143})
        self.assertEqual({kind: (spec.steps * spec.step_seconds, spec.timeout_seconds) for kind, spec in SPECS.items()},
                         {"checksum_pack": (12, 30), "grade_stats": (6, 30), "late_import": (6, 30), "deep_scan": (80, 40)})


class SchedulerTests(unittest.TestCase):
    def play(self, policy, horizon=40, every=5, cap=2, step=1):
        executor = BackgroundExecutor(VirtualClock(), ZH)
        scheduler = Scheduler(executor, kind="checksum_pack", every=every, policy=policy, max_concurrent=cap)
        records = []
        for now in range(step, horizon + 1, step):
            executor.advance_to(now)
            records += scheduler.poll(now)
        self.addCleanup(lambda: (executor.shutdown("run_end"), self.assertEqual(live_threads(), [])))
        return executor, scheduler, records

    def summary(self, records):
        return [(item["fire_no"], item["at"], item["action"], item["run_id"]) for item in records]

    def test_skip_drops_a_fire_while_the_previous_run_is_going(self):
        _, scheduler, records = self.play("skip")
        self.assertEqual(self.summary(records), [
            (1, 5, "started", "run-1"), (2, 10, "skipped", None), (3, 15, "skipped", None),
            (4, 20, "started", "run-2"), (5, 25, "skipped", None), (6, 30, "skipped", None),
            (7, 35, "started", "run-3"), (8, 40, "skipped", None)])
        self.assertTrue(all(item["reason"] == "previous_running" for item in records if item["action"] == "skipped"))
        self.assertEqual(scheduler.fires, 8)

    def test_queue_keeps_the_order_and_drops_past_its_limit(self):
        _, scheduler, records = self.play("queue")
        self.assertEqual(QUEUE_LIMIT, 2)
        self.assertEqual(self.summary(records), [
            (1, 5, "started", "run-1"), (2, 10, "queued", None), (3, 15, "queued", None),
            (2, 17, "started_from_queue", "run-2"), (4, 20, "queued", None), (5, 25, "dropped", None),
            (3, 29, "started_from_queue", "run-3"), (6, 30, "queued", None), (7, 35, "dropped", None),
            (8, 40, "dropped", None)])
        self.assertEqual([item["reason"] for item in records if item["action"] == "dropped"], ["queue_full"] * 3)
        self.assertEqual(len(scheduler.queue), 2, "two fires are still waiting when the horizon ends")

    def test_parallel_runs_overlap_up_to_the_cap_and_refuse_beyond_it(self):
        _, _, records = self.play("parallel")
        self.assertEqual(self.summary(records), [
            (1, 5, "started", "run-1"), (2, 10, "started", "run-2"), (3, 15, "denied", None),
            (4, 20, "started", "run-3"), (5, 25, "started", "run-4"), (6, 30, "denied", None),
            (7, 35, "started", "run-5"), (8, 40, "started", "run-6")])
        self.assertEqual(max(len(item["active_runs"]) for item in records), 2)
        self.assertEqual([item["reason"] for item in records if item["action"] == "denied"], ["concurrency_limit"] * 2)

    def test_a_long_jump_of_the_clock_yields_every_due_fire_in_order(self):
        executor = BackgroundExecutor(VirtualClock(), ZH)
        self.addCleanup(lambda: executor.shutdown("run_end"))
        scheduler = Scheduler(executor, kind="grade_stats", every=5, policy="skip", max_concurrent=1)
        executor.advance_to(22)
        records = scheduler.poll(22)
        self.assertEqual([(item["fire_no"], item["due_at"], item["at"], item["action"]) for item in records],
                         [(1, 5, 22, "started"), (2, 10, 22, "skipped"), (3, 15, 22, "skipped"),
                          (4, 20, 22, "skipped")])

    def test_every_started_run_has_its_own_job_and_run_id(self):
        executor, scheduler, records = self.play("parallel")
        runs = [item["run_id"] for item in records if item["run_id"]]
        self.assertEqual(len(set(runs)), len(runs))
        self.assertEqual(len(executor.jobs), len(runs))
        self.assertEqual({job.origin for job in executor.jobs.values()}, {"schedule"})

    def test_unknown_policy_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            Scheduler(BackgroundExecutor(VirtualClock(), ZH), kind="grade_stats", every=5, policy="retry", max_concurrent=1)


def fake_job(kind, status, value=None, delivered=True):
    result = {"value": value, "detail": "d"} if value is not None else None
    return SimpleNamespace(kind=kind, status=status, delivered=delivered, result=result, id=f"job-{kind}-{status}")


class GoalTests(unittest.TestCase):
    required = SCENARIOS["nightly"]

    def goal(self, jobs, items=None, attempts=2, t=ZH):
        report_data = {"round": 1, "items": items} if items is not None else None
        return evaluate_goal(t, self.required, jobs, report_data, attempts)

    def test_ok_needs_delivered_results_and_a_matching_report(self):
        jobs = [fake_job("checksum_pack", "completed", "abc"), fake_job("grade_stats", "completed", "9")]
        goal = self.goal(jobs, {"checksum_pack": "abc", "grade_stats": "9"})
        self.assertEqual((goal["verdict"], goal["reason_code"]), ("ok", "goal_met"))
        self.assertEqual(decide(goal, 3, 8), {"stop": True, "outcome": "completed"})

    def test_a_completed_job_that_was_not_delivered_does_not_count(self):
        jobs = [fake_job("checksum_pack", "completed", "abc", delivered=False), fake_job("grade_stats", "completed", "9")]
        goal = self.goal(jobs, {"checksum_pack": "abc", "grade_stats": "9"})
        self.assertEqual(goal["verdict"], "continue")
        self.assertEqual(goal["checks"][0]["status"], "open", "a job that ended but was never shown is not an answer")

    def test_a_report_with_a_wrong_or_missing_value_does_not_pass(self):
        jobs = [fake_job("checksum_pack", "completed", "abc"), fake_job("grade_stats", "completed", "9")]
        wrong = self.goal(jobs, {"checksum_pack": "abc", "grade_stats": "10"})
        self.assertEqual((wrong["verdict"], wrong["reason_code"]), ("continue", "report_mismatch"))
        self.assertEqual(wrong["checks"][-1]["detail"], ZH.report_differs.format(kind="grade_stats"))
        lacking = self.goal(jobs, {"checksum_pack": "abc"})
        self.assertEqual(lacking["checks"][-1]["detail"], ZH.report_lacks.format(kind="grade_stats"))
        self.assertEqual(self.goal(jobs)["reason_code"], "report_missing")

    def test_a_kind_started_to_the_limit_without_success_is_impossible(self):
        failed = [fake_job("checksum_pack", "completed", "abc"), fake_job("grade_stats", "failed"),
                  fake_job("grade_stats", "timed_out")]
        failed[2].id = "job-x"
        goal = self.goal(failed)
        self.assertEqual((goal["verdict"], goal["reason_code"]), ("impossible", "kind_exhausted"))
        self.assertEqual(goal["attempts"], {"checksum_pack": 1, "grade_stats": 2})
        self.assertEqual(decide(goal, 2, 8), {"stop": True, "outcome": "abandoned"})
        retry = self.goal(failed[:2])
        self.assertEqual((retry["verdict"], retry["reason_code"]), ("continue", "open"), "one failure leaves a retry")
        self.assertEqual(self.goal(failed[:2], attempts=1)["verdict"], "impossible")

    def test_a_running_job_means_continue_and_the_budget_ends_it(self):
        goal = self.goal([fake_job("checksum_pack", "running"), fake_job("grade_stats", "completed", "9")])
        self.assertEqual((goal["verdict"], goal["reason_code"]), ("continue", "waiting"))
        self.assertEqual(decide(goal, 4, 8), {"stop": False, "outcome": None})
        self.assertEqual(decide(goal, 8, 8), {"stop": True, "outcome": "budget_exhausted"})

    def test_reasons_follow_the_run_language(self):
        goal = self.goal([fake_job("checksum_pack", "running")], t=EN)
        self.assertEqual(goal["reason"], "Background jobs are still running: checksum_pack.")
        self.assertFalse(CJK.search(json.dumps(goal)))


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.events, self.t = [], ZH
        self.executor = BackgroundExecutor(VirtualClock(), self.t)
        self.state = runtime.RunState()
        context = SimpleNamespace(emit=lambda kind, data, number=None: self.events.append((kind, data, number)))
        self.tools = runtime.make_tools(context, self.t, self.executor, self.state)
        self.addCleanup(lambda: (self.executor.shutdown("run_end"), self.assertEqual(live_threads(), [])))

    def test_start_returns_the_handle_and_no_result(self):
        result = self.tools["start_background_job"]("grade_stats")
        self.assertEqual((result["job_id"], result["status"], result["note"]), ("job-1", "running", self.t.start_note))
        self.assertNotIn("value", json.dumps(result))
        self.assertEqual(self.events[0][1]["phase"], "started")

    def test_check_never_runs_ahead_of_the_injection(self):
        self.tools["start_background_job"]("grade_stats")
        self.assertEqual(self.tools["check_job"]("job-1")["progress"], "0/2")
        self.executor.advance_to(10)  # the job has ended, the runner has not injected it
        job = self.executor.jobs["job-1"]
        pending = self.tools["check_job"]("job-1")
        self.assertEqual((pending["status"], pending["result"]), ("completed", self.t.result_pending))
        self.assertNotIn("summary", pending)
        job.delivered = True
        self.assertEqual(self.tools["check_job"]("job-1")["summary"], job.result["detail"])
        self.assertEqual(self.state.polls, 3)

    def test_cancel_reports_the_final_state_and_marks_it_delivered(self):
        self.tools["start_background_job"]("deep_scan")
        result = self.tools["cancel_job"]("job-1")
        self.assertEqual((result["status"], result["exit_code"]), ("cancelled", 143))
        self.assertTrue(self.executor.jobs["job-1"].delivered)
        with self.assertRaises(JobRefused):
            self.tools["cancel_job"]("job-1")

    def test_submit_report_validates_the_shape_and_keeps_the_last_one(self):
        for bad in ([], "x", [{"kind": "grade_stats"}], [{"kind": "grade_stats", "value": 9}],
                    [{"kind": "grade_stats", "value": "9", "extra": 1}], [{"kind": "nope", "value": "1"}],
                    [{"kind": "grade_stats", "value": "9"}, {"kind": "grade_stats", "value": "9"}]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.tools["submit_report"](bad)
        self.assertIsNone(self.state.report)
        self.tools["submit_report"]([{"kind": "grade_stats", "value": " 9 "}])
        self.tools["submit_report"]([{"kind": "checksum_pack", "value": "abc"}])
        self.assertEqual(self.state.report["items"], {"checksum_pack": "abc"})

    def test_policy_lookup_is_synchronous_and_checked(self):
        self.assertEqual(self.tools["read_policy"]("pass_line")["text"], self.t.policies["pass_line"])
        with self.assertRaises(ValueError):
            self.tools["read_policy"]("grading")


class RunTests(unittest.TestCase):
    def tearDown(self):
        self.assertEqual(live_threads(), [], "no background thread outlives a run")

    def test_results_are_injected_in_a_later_round_as_their_own_message(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("background-basic", locale=locale)
                injected = [(data, number) for kind, data, number in events if kind == "lesson.harness_injected"]
                self.assertEqual([(data["jobs"], number) for data, number in injected], [(["job-2"], 3), (["job-1"], 4)])
                self.assertTrue(all(data["source"] == "background_job" for data, _ in injected))
                third = json.loads(requests(events)[2])
                self.assertEqual(third[-1], {"role": "user", "content": injected[0][0]["text"]})
                self.assertEqual(third[-2]["role"], "assistant", "the model's own reply comes before the injection")
                self.assertTrue(injected[0][0]["text"].startswith(t.injection_header.format(now=10)))
                self.assertTrue(answer.startswith(t.answers["completed"].split("（")[0].split("(")[0]))
                self.assertEqual(metrics(events)["injections"], 2)
                self.assertEqual(of(events, "lesson.goal_check")[-1]["outcome"], "completed")

    def test_a_result_is_in_no_request_before_the_round_that_injects_it(self):
        _, events = run_case("background-basic")
        sent = requests(events)
        jobs = {data["job_id"]: data for data in of(events, "lesson.background_job") if data["phase"] == "finished"}
        digest = jobs["job-1"]["value"]
        for number, body in enumerate(sent, 1):
            self.assertEqual(digest in body, number >= 4, f"round {number}")
        passed = f"value={jobs['job-2']['value']}。"
        for number, body in enumerate(sent, 1):
            self.assertEqual(passed in body, number >= 3, f"round {number}")
        self.assertTrue(checks(events)["not_seen_early"]["passed"])
        started = {data["job_id"]: data for data in of(events, "lesson.background_job") if data["phase"] == "started"}
        self.assertEqual((jobs["job-1"]["finished_at"], jobs["job-1"]["observed_at"], started["job-1"]["started_round"]),
                         (12, 15, 1))

    def test_background_jobs_do_not_block_the_foreground_tool(self):
        _, events = run_case("background-basic")
        names = [data["function"]["name"] for data in of(events, "tool_call")]
        self.assertEqual(names[:3], ["start_background_job", "start_background_job", "read_policy"])
        self.assertEqual(len([e for e in events if e[0] == "request"]), 4, "waiting costs one request per round, no polling")
        self.assertEqual(metrics(events)["polls"], 0)

    def test_the_report_is_judged_by_the_goal_check_not_by_the_model(self):
        _, events = run_case("background-basic")
        self.assertEqual([c["id"] for c in report(events)["checks"]],
                         ["report_matches", "goal_logged", "not_seen_early", "no_orphans"])
        self.assertTrue(all(c["passed"] for c in report(events)["checks"]))
        self.assertEqual([c["verdict"] for c in of(events, "lesson.goal_check")], ["continue"] * 3 + ["ok"])
        rows = report(events)["table"]["rows"]
        self.assertEqual(rows[0][:2] + rows[0][2:5], ["job-1", "checksum_pack", 0, 1, 12])
        self.assertEqual(rows[1][-4:], ["已完成", 0, 3, 4])
        self.assertEqual(len(report(events)["table"]["columns"]), len(rows[0]))

    def test_hasty_model_reports_before_it_has_the_results(self):
        invented = [("submit_report", {"results": [{"kind": "checksum_pack", "value": "deadbeef0000"},
                                                    {"kind": "grade_stats", "value": "7"}]})]
        model = script([("start_background_job", {"kind": "checksum_pack"}), ("start_background_job", {"kind": "grade_stats"})],
                       invented)
        answer, events = run_case("background-basic", {"scenario": "nightly", "max_rounds": 4}, model)
        verdicts = of(events, "lesson.goal_check")
        self.assertEqual([c["reason_code"] for c in verdicts], ["waiting", "waiting", "waiting", "budget"])
        self.assertEqual(verdicts[-1]["checks"][-1]["status"], "mismatch")
        self.assertEqual(metrics(events)["outcome"], ZH.outcomes["budget_exhausted"])
        self.assertIs(checks(events)["report_matches"]["passed"], False)
        self.assertTrue(answer.startswith("目标未达成"))
        self.assertIn("deadbeef0000", answer)

    def test_failure_is_injected_with_its_exit_code_and_a_retry_is_given_up_on(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("failed-job", locale=locale)
                goals = of(events, "lesson.goal_check")
                self.assertEqual([item["verdict"] for item in goals], ["continue"] * 4 + ["impossible"])
                self.assertEqual(goals[-1]["attempts"], {"checksum_pack": 1, "late_import": 2})
                self.assertEqual(goals[-1]["outcome"], "abandoned")
                finished = [d for d in of(events, "lesson.background_job") if d["phase"] == "finished"]
                failures = [d for d in finished if d["kind"] == "late_import"]
                self.assertEqual([(d["job_id"], d["status"], d["exit_code"], d["finished_at"]) for d in failures],
                                 [("job-2", "failed", 1, 6), ("job-3", "failed", 1, 16)])
                self.assertEqual(failures[0]["summary"], t.bad_score.format(row=6, value="8x"))
                self.assertIn(t.bad_score.format(row=6, value="8x"), of(events, "lesson.harness_injected")[0]["text"])
                self.assertEqual(metrics(events)["outcome"], t.outcomes["abandoned"])
                self.assertNotIn("passed", checks(events)["report_matches"], "no report to compare: the check did not run")
                self.assertEqual(len(of(events, "request")), 5)
                self.assertTrue(answer.startswith(t.answers["abandoned"].split("（")[0].split(" (")[0].split("{")[0]))

    def test_budget_stop_cancels_what_is_still_running_and_says_why(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("budget-stop", locale=locale)
                self.assertEqual(len(of(events, "request")), 5)
                last = of(events, "lesson.goal_check")[-1]
                self.assertEqual((last["verdict"], last["decision"], last["outcome"], last["reason_code"]),
                                 ("continue", "stop", "budget_exhausted", "budget"))
                self.assertEqual(last["budget"], {"rounds_used": 5, "max_rounds": 5})
                self.assertIn(t.reasons["budget"].format(rounds=5, state=t.reasons["waiting"].format(jobs="deep_scan")),
                              last["reason"])
                cancelled = [d for d in of(events, "lesson.background_job") if d["phase"] == "cancelled"]
                self.assertEqual([(d["job_id"], d["reason"], d["exit_code"]) for d in cancelled],
                                 [("job-1", "model_request", 143), ("job-3", "run_end", 143)])
                self.assertEqual(metrics(events)["polls"], 2)
                self.assertEqual(metrics(events)["jobs_cancelled"], 2)
                self.assertEqual(metrics(events)["orphans"], 0)
                self.assertTrue(checks(events)["no_orphans"]["passed"])
                self.assertEqual(metrics(events)["outcome"], t.outcomes["budget_exhausted"])

    def test_check_job_polls_cost_requests_without_bringing_a_result_earlier(self):
        _, events = run_case("budget-stop")
        polls = [d for d in of(events, "tool_result") if d["name"] == "check_job"]
        self.assertEqual([p["result"]["result"]["progress"] for p in polls], ["0/8", "1/8"])
        self.assertTrue(all(p["result"]["result"]["status"] == "running" for p in polls))

    def test_a_model_that_stops_with_nothing_running_gets_the_reason_back(self):
        model = script([("start_background_job", {"kind": "checksum_pack"}), ("start_background_job", {"kind": "grade_stats"})],
                       "完成了。")
        _, events = run_case("background-basic", {"scenario": "nightly", "max_rounds": 6}, model)
        feedback = [d for d in of(events, "lesson.harness_injected") if d["kind"] == "goal_feedback"]
        self.assertEqual([d["round"] for d in feedback], [4, 5])
        self.assertEqual(feedback[0]["text"], ZH.feedback.format(round=4, reason=ZH.reasons["report_missing"]))
        fifth = json.loads(requests(events)[4])
        self.assertEqual(fifth[-2]["content"], "完成了。")
        self.assertEqual(fifth[-1]["content"], feedback[0]["text"], "the round-4 feedback is what round 5 sees")

    def test_tool_errors_reach_the_model_as_structured_errors(self):
        model = script([("start_background_job", {"kind": "deep_scan"}), ("start_background_job", {"kind": "deep_scan"}),
                        ("start_background_job", {"kind": "deep_scan"}), ("start_background_job", {"kind": "deep_scan"}),
                        ("start_background_job", {"kind": "nope"}), ("check_job", {"job_id": "job-77"})],
                       "好。")
        _, events = run_case("budget-stop", {"scenario": "deep", "max_rounds": 2}, model)
        results = [d["result"] for d in of(events, "tool_result")]
        self.assertEqual([r["ok"] for r in results], [True, True, True, False, False, False])
        self.assertEqual({r["error_type"] for r in results[3:]}, {"JobRefused"})
        self.assertEqual(results[3]["error"], ZH.too_many_jobs.format(limit=3))
        self.assertEqual(metrics(events)["jobs_started"], 3)
        self.assertEqual(metrics(events)["jobs_cancelled"], 3)

    def test_english_runs_carry_no_chinese_anywhere(self):
        for exercise in EXERCISE_INPUTS:
            with self.subTest(exercise=exercise):
                _, events = run_case(exercise, locale="en")
                self.assertFalse(CJK.search(json.dumps(events, ensure_ascii=False)))
        _, events = run_case("background-basic")
        self.assertTrue(CJK.search(json.dumps(events, ensure_ascii=False)))

    def test_stop_cancels_the_jobs_and_leaves_no_thread(self):
        for exercise in ("budget-stop", "schedule-skip"):
            with self.subTest(exercise=exercise), self.assertRaises(RunCancelled):
                run_case(exercise, stop_after_events=9)
            self.assertEqual(live_threads(), [])

    def test_an_error_in_the_middle_still_joins_every_thread(self):
        def breaks(body, key):
            if any(m["role"] == "tool" for m in body["messages"]):
                raise RuntimeError("provider failed")
            return script([("start_background_job", {"kind": "deep_scan"})])(body, key)
        with self.assertRaises(RuntimeError):
            run_case("budget-stop", completion=breaks)
        self.assertEqual(live_threads(), [])
        with self.assertRaises(RuntimeError):  # the platform's call budget ends a run mid-way too
            run_case("budget-stop", budget=2)
        self.assertEqual(live_threads(), [])

    def test_the_idle_clock_jumps_to_the_next_end_instead_of_asking_again(self):
        model = script([("start_background_job", {"kind": "deep_scan", "timeout_seconds": 120})], "我等着。")
        _, events = run_case("budget-stop", {"scenario": "deep", "max_rounds": 4}, model)
        clocks = of(events, "lesson.clock")
        self.assertEqual([(c["now"], c["reason"]) for c in clocks], [(5, "round"), (80, "idle_wait"), (85, "round")])
        injected = [d for d in of(events, "lesson.harness_injected") if d["kind"] == "background_result"]
        self.assertEqual([d["at"] for d in injected], [80], "the jump reaches the end of the job, so the next request has news")

    def test_tick_seconds_moves_the_injection_round(self):
        _, events = run_case("background-basic", {"scenario": "nightly", "tick_seconds": 10})
        # A longer round lets grade_stats (ended at 6) be injected in round 2 instead of round 3.
        self.assertEqual([(d["jobs"], d["round"]) for d in of(events, "lesson.harness_injected")],
                         [(["job-2"], 2), (["job-1"], 3)])
        self.assertEqual(of(events, "lesson.goal_check")[-1]["outcome"], "completed")


class ScheduleRunTests(unittest.TestCase):
    def tearDown(self):
        self.assertEqual(live_threads(), [])

    def test_each_policy_leaves_the_counts_its_rule_implies(self):
        expected = {"skip": dict(fires=8, runs_started=3, skipped=5, queued=0, dropped=0, denied=0, cancelled_at_end=1,
                                 waiting_at_end=0),
                    "queue": dict(fires=8, runs_started=3, skipped=0, queued=4, dropped=3, denied=0, cancelled_at_end=1,
                                  waiting_at_end=2),
                    "parallel": dict(fires=8, runs_started=6, skipped=0, queued=0, dropped=0, denied=2, cancelled_at_end=2,
                                     waiting_at_end=0)}
        for policy, counts in expected.items():
            for locale in ("zh-CN", "en"):
                with self.subTest(policy=policy, locale=locale):
                    answer, events = run_case(f"schedule-{policy}", locale=locale)
                    values = metrics(events)
                    self.assertEqual({key: values[key] for key in counts}, counts)
                    self.assertTrue(all(c["passed"] for c in report(events)["checks"]))
                    self.assertEqual(len(of(events, "request")), 0, "the scheduler scenario calls no model")

    def test_every_fire_is_one_record_and_every_started_run_has_a_job(self):
        _, events = run_case("schedule-queue")
        fires = of(events, "lesson.schedule_fire")
        self.assertEqual(len([f for f in fires if f["action"] != "started_from_queue"]), 8)
        started = {f["run_id"]: f["job_id"] for f in fires if "run_id" in f}
        job_events = [d for d in of(events, "lesson.background_job") if d["phase"] == "started"]
        self.assertEqual({d["run_id"]: d["job_id"] for d in job_events}, started)
        finished = [d for d in of(events, "lesson.background_job") if d["phase"] == "finished"]
        self.assertEqual([d["run_id"] for d in finished], ["run-1", "run-2"])
        self.assertEqual([d["finished_at"] for d in finished], [17, 29])
        self.assertEqual(report(events)["table"]["rows"][0][:3], [1, 5, 5])
        delayed = [(f["fire_no"], f["delayed_by"]) for f in fires if "delayed_by" in f]
        self.assertEqual(delayed, [(2, 7), (3, 14)], "a queued fire starts later than it was due")
        self.assertNotIn("reason", fires[0], "a fire that started has no refusal reason")

    def test_interval_and_horizon_change_the_number_of_fires(self):
        _, events = run_case("schedule-parallel", {"scenario": "schedule", "overlap": "parallel", "interval_seconds": 15,
                                                  "horizon_seconds": 60, "max_concurrent": 1})
        self.assertEqual(metrics(events)["fires"], 4)
        self.assertEqual(metrics(events)["denied"], 0, "a 12-second run is over before the next 15-second fire")
        self.assertTrue(all(c["passed"] for c in report(events)["checks"]))


class InputTests(unittest.TestCase):
    def test_inputs_are_validated(self):
        for bad in ({"scenario": "nope"}, {"tick_seconds": 0}, {"tick_seconds": 31}, {"max_rounds": 13}, {"max_running": 5},
                    {"max_attempts": 0}, {"overlap": "retry"}, {"interval_seconds": 1}, {"horizon_seconds": 9},
                    {"label": "x"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)
        self.assertEqual(validate_inputs(runtime, {})["scenario"], "nightly")

    def test_tool_definitions_keep_names_and_follow_the_language(self):
        zh, en = runtime.tool_definitions("zh-CN"), runtime.tool_definitions("en")
        names = ["start_background_job", "check_job", "cancel_job", "read_policy", "submit_report"]
        self.assertEqual([t["function"]["name"] for t in zh], names)
        self.assertEqual([t["function"]["name"] for t in en], names)
        self.assertEqual(zh[0]["function"]["parameters"]["properties"]["kind"]["enum"], list(SPECS))
        self.assertFalse(CJK.search(json.dumps(en)))
        self.assertTrue(CJK.search(json.dumps(zh, ensure_ascii=False)))


if __name__ == "__main__":
    unittest.main()
