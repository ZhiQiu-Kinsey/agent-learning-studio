"""Background jobs, result injection and a scheduled trigger, inside one run.

The model starts slow jobs with start_background_job and gets a job id back at once. A background executor runs
them on real threads against a virtual clock (executor.py); the runner moves that clock between rounds and, before
every request, hands over the results of jobs that have ended as one separate message (source marked, not a tool
result and not the learner's words). After each round the runner judges the goal itself (goal.py): ok, impossible
or continue, with a reason, and a round budget that ends the run explicitly. Jobs still running when the run ends
or is stopped are cancelled and their threads joined. The scenario "schedule" has no model: a fixed-interval trigger
starts jobs and applies an overlap policy. All of it lives inside one run; a durable scheduler needs a process that
outlives it. Learn Claude Code s11 (background tasks, MIT) and s12 (cron scheduler, MIT) and the chapter 6 async
runtime of ai-agent-book (Apache-2.0) are the references; the tools, jobs, clock and checks are written for this project.
"""
import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_long_running_tasks.executor import BackgroundExecutor, Job, VirtualClock
from lessons.lesson_long_running_tasks.goal import SCENARIOS, decide, evaluate_goal
from lessons.lesson_long_running_tasks.jobs import SPECS
from lessons.lesson_long_running_tasks.locales import Texts, texts_for
from lessons.lesson_long_running_tasks.scheduler import Scheduler

SCHEDULED_KIND = "checksum_pack"
LOCAL_TICK = 1  # the scheduler scenario moves the clock one virtual second at a time


class Inputs(LessonInputs):
    scenario: Literal["nightly", "late", "deep", "schedule"] = "nightly"
    tick_seconds: int = Field(default=5, ge=1, le=30)  # virtual seconds one round takes
    max_rounds: int = Field(default=8, ge=1, le=12)  # model calls this run may spend
    max_running: int = Field(default=3, ge=1, le=4)  # background jobs allowed at once
    max_attempts: int = Field(default=2, ge=1, le=3)  # starts of one kind before the goal is given up
    overlap: Literal["skip", "queue", "parallel"] = "skip"
    interval_seconds: int = Field(default=5, ge=2, le=20)
    horizon_seconds: int = Field(default=40, ge=10, le=120)
    max_concurrent: int = Field(default=2, ge=1, le=4)


INPUT_MODEL = Inputs


@dataclass
class RunState:
    """What the runner remembers: the round, the latest report, how many polls, and what each request really carried."""
    round: int = 1
    report: dict | None = None
    polls: int = 0
    injections: int = 0
    sent: dict[int, str] = field(default_factory=dict)
    lines: dict[str, str] = field(default_factory=dict)  # job id -> the exact line injected for it
    goal_checks: list[dict] = field(default_factory=list)


# ---------- tools the model can call ----------
def tool_definitions(locale: str) -> list[dict]:
    """The model's tools. Names and parameters are code; the descriptions follow the run's language."""
    t = texts_for(locale)

    def spec(name, description, properties, required):
        return {"type": "function", "function": {"name": name, "description": description, "parameters": {
            "type": "object", "properties": properties, "required": required, "additionalProperties": False}}}
    job_id = {"job_id": {"type": "string"}}
    return [
        spec("start_background_job", t.start_description, {
            "kind": {"type": "string", "enum": list(SPECS)},
            "timeout_seconds": {"type": "integer", "minimum": 5, "maximum": 120}}, ["kind"]),
        spec("check_job", t.check_description, job_id, ["job_id"]),
        spec("cancel_job", t.cancel_description, job_id, ["job_id"]),
        spec("read_policy", t.policy_description, {"topic": {"type": "string", "enum": list(t.policies)}}, ["topic"]),
        spec("submit_report", t.report_description, {"results": {"type": "array", "items": {
            "type": "object", "properties": {"kind": {"type": "string", "enum": list(SPECS)}, "value": {"type": "string"}},
            "required": ["kind", "value"], "additionalProperties": False}}}, ["results"]),
    ]


def make_tools(context: RunContext, t: Texts, executor: BackgroundExecutor, state: RunState) -> dict:
    def start_background_job(kind, timeout_seconds=None):
        job = executor.start(kind, origin="model", round_number=state.round, timeout_seconds=timeout_seconds)
        context.emit("lesson.background_job", job_record(t, job, "started"), state.round)
        return {"job_id": job.id, "kind": job.kind, "status": job.status, "started_at": job.started_at,
                "timeout_seconds": job.timeout_seconds, "note": t.start_note}

    def check_job(job_id):
        job = executor.get(job_id)
        state.polls += 1
        view = {"job_id": job.id, "kind": job.kind, "status": job.status, "progress": progress(job),
                "started_at": job.started_at, "elapsed": executor.clock.now - job.started_at}
        if job.status != "running":
            # A result is shown only after it was handed over; polling must never get ahead of the injection.
            if job.delivered:
                view.update(exit_code=job.exit_code, finished_at=job.finished_at, summary=summary_text(t, job))
            else:
                view["result"] = t.result_pending
        return view

    def cancel_job(job_id):
        job = executor.cancel(job_id, "model_request")
        job.delivered, job.delivered_round = True, state.round  # the tool result below is how the model learns it
        context.emit("lesson.background_job", job_record(t, job, "cancelled"), state.round)
        return {"job_id": job.id, "status": job.status, "exit_code": job.exit_code, "progress": progress(job),
                "finished_at": job.finished_at}

    def read_policy(topic):
        if topic not in t.policies:
            raise ValueError(t.unknown_topic.format(topic=topic, topics=t.list_separator.join(t.policies)))
        return {"topic": topic, "text": t.policies[topic]}

    def submit_report(results):
        if not isinstance(results, list) or not results:
            raise ValueError(t.report_shape)
        items = {}
        for item in results:
            if not isinstance(item, dict) or set(item) != {"kind", "value"} or not isinstance(item["value"], str):
                raise ValueError(t.report_shape)
            if item["kind"] not in SPECS or item["kind"] in items:
                raise ValueError(t.report_kind.format(kind=item["kind"], kinds=t.list_separator.join(SPECS)))
            items[item["kind"]] = item["value"].strip()
        state.report = {"round": state.round, "items": items}  # recorded, not judged: the goal check judges
        return {"recorded": len(items)}

    return {"start_background_job": start_background_job, "check_job": check_job, "cancel_job": cancel_job,
            "read_policy": read_policy, "submit_report": submit_report}


# ---------- the round loop ----------
def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    executor = BackgroundExecutor(VirtualClock(), t, values.max_running)
    try:
        if values.scenario == "schedule":
            return run_schedule(context, t, values, executor)
        return run_rounds(context, t, values, executor)
    finally:
        # Also after an error or a stop: no thread outlives the run. A stopped run cannot publish events any more.
        executor.shutdown("run_end")


def run_rounds(context: RunContext, t: Texts, values: Inputs, executor: BackgroundExecutor) -> str:
    required, state = SCENARIOS[values.scenario], RunState()
    context.emit("lesson.task_card", task_card(t, values, required), 1)
    messages = [{"role": "system", "content": t.system}, {"role": "user", "content": t.tasks[values.scenario]}]
    tools = make_tools(context, t, executor, state)
    yielded, decision = False, None
    for round_number in range(1, values.max_rounds + 1):
        context.check_cancelled()
        state.round = round_number
        # 1. Time passes. A model that had nothing to do waits until a job can end; one that worked, one tick.
        if round_number > 1:
            advance_clock(context, t, values, executor, round_number, wait_for_job=yielded)
        # 2. Hand over what finished. Only here does a background result enter the history, as its own message.
        inject_results(context, t, executor, state, messages)
        state.sent[round_number] = json.dumps(messages, ensure_ascii=False)
        # 3. One request, then run the calls the model proposed.
        response = context.complete({"messages": messages, "tools": tool_definitions(context.locale),
                                     "tool_choice": "auto", "temperature": 0}, round_number)
        message = response["choices"][0].get("message") or {}
        calls = message.get("tool_calls") or []
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls} if calls
                        else {"role": "assistant", "content": message.get("content") or ""})
        for call in calls:
            result = context.execute_proposal(call, tools)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)})
        yielded = not calls
        # 4. The runner judges the goal; the model's words do not decide. Then continue, or stop for a stated reason.
        goal = evaluate_goal(t, required, list(executor.jobs.values()), state.report, values.max_attempts)
        decision = decide(goal, round_number, values.max_rounds)
        record_goal(context, t, goal, decision, state, values, round_number)
        if decision["stop"]:
            break
        # 5. A model that stopped calling tools with nothing left running gets the reason, as a marked message.
        if yielded and not executor.running():
            feedback(context, t, goal, state, messages, round_number)
    return finish_rounds(context, t, values, executor, state, required, goal, decision)


def advance_clock(context, t, values, executor, round_number, *, wait_for_job):
    now = executor.clock.now
    target, reason = now + values.tick_seconds, "round"
    if wait_for_job and executor.next_terminal() is not None and executor.next_terminal() > target:
        target, reason = executor.next_terminal(), "idle_wait"
    executor.advance_to(target)
    context.emit("lesson.clock", {"clock": "virtual", "from": now, "now": target, "advanced_by": target - now,
                                  "reason": reason, "running": [job.id for job in executor.running()]}, round_number)


def inject_results(context, t, executor, state, messages):
    fresh = executor.collect_finished()
    if not fresh:
        return
    for job in fresh:
        context.emit("lesson.background_job", job_record(t, job, "finished"), state.round)
    now = executor.clock.now
    lines = {job.id: line_for(t, job) for job in fresh}
    text = t.injection_header.format(now=now) + "\n" + "\n".join(lines.values())
    messages.append({"role": "user", "content": text})
    state.injections += 1
    state.lines.update(lines)
    context.emit("lesson.harness_injected", {"kind": "background_result", "source": "background_job", "text": text,
                                             "jobs": [job.id for job in fresh], "round": state.round, "at": now},
                 state.round)
    for job in fresh:
        job.delivered, job.delivered_round = True, state.round
        context.emit("lesson.background_job", {"job_id": job.id, "kind": job.kind, "phase": "injected",
                                               "round": state.round, "waited_seconds": now - job.finished_at},
                     state.round)


def feedback(context, t, goal, state, messages, round_number):
    text = t.feedback.format(round=round_number, reason=goal["reason"])
    messages.append({"role": "user", "content": text})
    context.emit("lesson.harness_injected", {"kind": "goal_feedback", "source": "goal_check", "text": text,
                                             "round": round_number}, round_number)


def record_goal(context, t, goal, decision, state, values, round_number):
    data = {"round": round_number, "verdict": goal["verdict"], "reason_code": goal["reason_code"],
            "reason": goal["reason"], "checks": goal["checks"], "attempts": goal["attempts"],
            "decision": "stop" if decision["stop"] else "continue",
            "budget": {"rounds_used": round_number, "max_rounds": values.max_rounds}}
    if decision["stop"]:
        data["outcome"] = decision["outcome"]  # only the check that ends the run carries an outcome
    if decision["stop"] and decision["outcome"] == "budget_exhausted":
        data["reason"] = t.reasons["budget"].format(rounds=values.max_rounds, state=goal["reason"])
        data["reason_code"] = "budget"
    state.goal_checks.append(data)
    context.emit("lesson.goal_check", data, round_number)


# ---------- the scheduler scenario (no model) ----------
def run_schedule(context: RunContext, t: Texts, values: Inputs, executor: BackgroundExecutor) -> str:
    scheduler = Scheduler(executor, kind=SCHEDULED_KIND, every=values.interval_seconds, policy=values.overlap,
                          max_concurrent=values.max_concurrent)
    context.emit("lesson.task_card", schedule_card(t, values), 1)
    records, runs_by_job = [], {}
    for second in range(LOCAL_TICK, values.horizon_seconds + 1, LOCAL_TICK):
        context.check_cancelled()
        executor.advance_to(second)
        for job in executor.collect_finished():
            context.emit("lesson.background_job", {**job_record(t, job, "finished"), "run_id": runs_by_job.get(job.id)}, 1)
            job.delivered = True
        for record in scheduler.poll(second):
            records.append(record)
            # Fields that do not apply are left out, so each one only appears on the decisions it describes.
            event = {key: value for key, value in record.items() if value is not None}
            if record["action"] == "started_from_queue":
                event["delayed_by"] = record["at"] - record["due_at"]
            context.emit("lesson.schedule_fire", {**event, "detail": t.fire_details[record["action"]]}, 1)
            if record["job_id"]:
                runs_by_job[record["job_id"]] = record["run_id"]
                context.emit("lesson.background_job", {**job_record(t, executor.jobs[record["job_id"]], "started"),
                                                       "run_id": record["run_id"]}, 1)
    leftovers = cancel_leftovers(context, t, executor, 1)
    return finish_schedule(context, t, values, executor, scheduler, records, leftovers)


# ---------- records, report and answers ----------
def progress(job: Job) -> str:
    return f"{job.progress}/{job.spec.steps}"


def summary_text(t: Texts, job: Job) -> str:
    if job.status == "completed":
        return job.result["detail"]
    if job.status == "failed":
        return job.error["error"]
    if job.status == "timed_out":
        return t.timeout_detail.format(seconds=job.timeout_seconds)
    return t.cancel_detail.format(reason=t.cancel_reasons[job.cancel_reason])


def line_for(t: Texts, job: Job) -> str:
    """The exact line one job contributes to the injected message: source, id, status, exit code and result."""
    return t.injection_items[job.status].format(
        job_id=job.id, kind=job.kind, exit_code=job.exit_code, finished_at=job.finished_at,
        value=job.result["value"] if job.result else "", summary=summary_text(t, job))


def job_record(t: Texts, job: Job, phase: str) -> dict:
    """lesson.background_job: one phase of a job's life. Times are virtual seconds on the run's clock."""
    data = {"job_id": job.id, "kind": job.kind, "phase": phase, "origin": job.origin, "clock": "virtual"}
    if phase == "started":
        data.update(started_at=job.started_at, started_round=job.started_round, steps=job.spec.steps,
                    step_seconds=job.spec.step_seconds, timeout_seconds=job.timeout_seconds)
        return data
    data.update(status=job.status, exit_code=job.exit_code, finished_at=job.finished_at, progress=progress(job),
                summary=summary_text(t, job))
    if phase == "finished":
        data["observed_at"] = job.observed_at
    if job.result:
        data["value"] = job.result["value"]
    if job.error:
        data["error_type"] = job.error["error_type"]
    if job.cancel_reason:
        data["reason"] = job.cancel_reason
    return data


def cancel_leftovers(context, t, executor, round_number) -> list[Job]:
    leftovers = executor.shutdown("run_end")
    for job in leftovers:
        context.emit("lesson.background_job", job_record(t, job, "cancelled"), round_number)
    return leftovers


def task_card(t: Texts, values: Inputs, required: tuple[str, ...]) -> dict:
    kinds = t.list_separator.join(required)
    return {"goal": t.card_goal.format(kinds=kinds), "input_scope": t.card_input_scope,
            "output": t.card_output.format(kinds=kinds), "evidence": t.card_evidence,
            "failure": t.card_failure.format(attempts=values.max_attempts),
            "stop": t.card_stop.format(rounds=values.max_rounds, tick=values.tick_seconds)}


def schedule_card(t: Texts, values: Inputs) -> dict:
    return {"goal": t.schedule_goal.format(interval=values.interval_seconds, kind=SCHEDULED_KIND),
            "input_scope": t.schedule_input_scope, "output": t.schedule_output,
            "evidence": t.schedule_evidence,
            "failure": t.schedule_failure.format(policy=t.policy_names[values.overlap]),
            "stop": t.schedule_stop.format(horizon=values.horizon_seconds)}


def first_seen_rounds(state: RunState, jobs: list[Job]) -> dict[str, int | None]:
    """The first request that really carried each injected line; the runner recorded what it sent."""
    seen = {}
    for job in jobs:
        needle = json.dumps(state.lines[job.id], ensure_ascii=False)[1:-1]
        seen[job.id] = next((number for number, body in sorted(state.sent.items()) if needle in body), None)
    return seen


def finish_rounds(context, t, values, executor, state, required, goal, decision) -> str:
    leftovers = cancel_leftovers(context, t, executor, state.round)
    jobs = list(executor.jobs.values())
    injected = [job for job in jobs if job.id in state.lines]
    seen = first_seen_rounds(state, injected)
    early = [job.id for job in injected if seen[job.id] != job.delivered_round]
    report_state = next(item for item in goal["checks"] if item["id"] == "report")
    checks = [
        {"id": "goal_logged", "label": t.check_goal_logged,
         "passed": len(state.goal_checks) == state.round and all(item["reason"] for item in state.goal_checks),
         "detail": t.detail_goal_logged.format(rounds=state.round)},
        {"id": "not_seen_early", "label": t.check_not_early, "passed": not early,
         "detail": t.detail_not_early_bad.format(jobs=t.list_separator.join(early)) if early
         else t.detail_not_early.format(count=len(injected))},
        {"id": "no_orphans", "label": t.check_no_orphans, "passed": executor.alive() == 0,
         "detail": t.detail_no_orphans.format(count=len(leftovers))},
    ]
    if report_state["status"] in ("match", "mismatch"):
        checks.insert(0, {"id": "report_matches", "label": t.check_report, "passed": report_state["status"] == "match",
                          "detail": report_state["detail"]})
    else:  # no report to compare: the check did not run, so it carries no passed flag
        checks.insert(0, {"id": "report_matches", "label": t.check_report, "detail": report_state["detail"]})
    by_status = lambda status: sum(job.status == status for job in jobs)  # noqa: E731
    context.emit("lesson.report", {
        "title": t.report_titles[values.scenario], "summary": t.report_summary, "checks": checks,
        "metrics": [
            {"id": "outcome", "label": t.label_outcome, "value": t.outcomes[decision["outcome"]]},
            {"id": "stop_reason", "label": t.label_stop_reason, "value": state.goal_checks[-1]["reason"]},
            {"id": "rounds", "label": t.label_rounds, "value": state.round},
            {"id": "max_rounds", "label": t.label_max_rounds, "value": values.max_rounds},
            {"id": "jobs_started", "label": t.label_jobs_started, "value": len(jobs)},
            {"id": "jobs_completed", "label": t.label_jobs_completed, "value": by_status("completed")},
            {"id": "jobs_failed", "label": t.label_jobs_failed, "value": by_status("failed")},
            {"id": "jobs_timed_out", "label": t.label_jobs_timed_out, "value": by_status("timed_out")},
            {"id": "jobs_cancelled", "label": t.label_jobs_cancelled, "value": by_status("cancelled")},
            {"id": "polls", "label": t.label_polls, "value": state.polls},
            {"id": "injections", "label": t.label_injections, "value": state.injections},
            {"id": "clock_end", "label": t.label_clock_end, "value": t.value_seconds.format(seconds=executor.clock.now)},
            {"id": "orphans", "label": t.label_orphans, "value": executor.alive()},
            {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.job_columns), "rows": [job_row(t, job) for job in jobs]},
    }, state.round)
    return answer_rounds(t, decision, goal, state)


def job_row(t: Texts, job: Job) -> list:
    dash = "—"
    waited = job.observed_at - job.finished_at if job.observed_at is not None and job.finished_at is not None else dash
    return [job.id, job.kind, job.started_at, job.started_round or dash,
            job.finished_at if job.finished_at is not None else dash, t.status_names[job.status],
            job.exit_code if job.exit_code is not None else dash, job.delivered_round or dash, waited]


def answer_rounds(t: Texts, decision: dict, goal: dict, state: RunState) -> str:
    items = state.report["items"] if state.report else {}
    return t.answers[decision["outcome"]].format(
        reason=state.goal_checks[-1]["reason"], rounds=state.round,
        results=t.list_separator.join(f"{kind}={value}" for kind, value in items.items()) or t.value_none)


def finish_schedule(context, t, values, executor, scheduler, records, leftovers) -> str:
    jobs = list(executor.jobs.values())
    count = lambda action: sum(item["action"] == action for item in records)  # noqa: E731
    started = count("started") + count("started_from_queue")
    expected = values.horizon_seconds // values.interval_seconds
    recorded_runs = len({item["run_id"] for item in records if item["run_id"]})
    checks = [
        {"id": "every_fire", "label": t.check_every_fire, "passed": len(records) - count("started_from_queue") == expected,
         "detail": t.detail_every_fire.format(fires=scheduler.fires, expected=expected)},
        {"id": "every_run", "label": t.check_every_run, "passed": recorded_runs == started == len(jobs),
         "detail": t.detail_every_run.format(runs=started)},
        {"id": "no_orphans", "label": t.check_no_orphans, "passed": executor.alive() == 0,
         "detail": t.detail_no_orphans.format(count=len(leftovers))},
    ]
    dash = "—"
    context.emit("lesson.report", {
        "title": t.schedule_report_title.format(policy=t.policy_names[values.overlap]), "summary": t.schedule_summary,
        "checks": checks,
        "metrics": [
            {"id": "policy", "label": t.label_policy, "value": t.policy_names[values.overlap]},
            {"id": "fires", "label": t.label_fires, "value": scheduler.fires},
            {"id": "runs_started", "label": t.label_runs_started, "value": started},
            {"id": "skipped", "label": t.label_skipped, "value": count("skipped")},
            {"id": "queued", "label": t.label_queued, "value": count("queued")},
            {"id": "dropped", "label": t.label_dropped, "value": count("dropped")},
            {"id": "denied", "label": t.label_denied, "value": count("denied")},
            {"id": "runs_finished", "label": t.label_runs_finished, "value": sum(job.status == "completed" for job in jobs)},
            {"id": "cancelled_at_end", "label": t.label_cancelled_at_end, "value": len(leftovers)},
            {"id": "waiting_at_end", "label": t.label_waiting_at_end, "value": len(scheduler.queue)},
            {"id": "clock_end", "label": t.label_clock_end, "value": t.value_seconds.format(seconds=executor.clock.now)},
            {"id": "orphans", "label": t.label_orphans, "value": executor.alive()},
            {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.fire_columns), "rows": [
            [item["fire_no"], item["due_at"], item["at"], t.fire_actions[item["action"]], item["run_id"] or dash,
             t.fire_reasons[item["reason"]] if item["reason"] else dash] for item in records]},
    }, 1)
    return t.schedule_answer.format(policy=t.policy_names[values.overlap], fires=scheduler.fires, started=started,
                                    skipped=count("skipped"), queued=count("queued"), dropped=count("dropped"),
                                    denied=count("denied"), cancelled=len(leftovers))
