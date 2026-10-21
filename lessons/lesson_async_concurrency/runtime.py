"""Parallel work under limits: read the dependencies, run what is independent at once, never beyond a limit.

The work is a small review-sheet job: read several lesson notes (a slow local tool), have the model summarize each note
in one sentence, then assemble a sheet. One run goes through the same job several times, once per variant of one
scenario (serial, by dependency and ignoring dependencies; limit 1, 2 and 4; ...), so the comparison comes from one
run under one load. The graph (graph.py) is read from the tasks' references, the scheduler (scheduler.py) runs it on
asyncio, and this file builds the tasks, wires the work to RunContext and writes the evidence. Timings are the
backend's own clock; the only injected quantities are the tool delay and the optional slow or locked note, and both
are written into the tool call itself. The overlap of independent requests follows claude-cookbooks patterns/agents
(MIT); the cooperative stop and the "nothing keeps running after the verdict" rule follow ai-agent-book chapter 6 and
chapter 10 (Apache-2.0). Every text that reaches the model or an event is in locales/, one catalog per run language.
"""
import threading
from dataclasses import dataclass, replace
from functools import partial
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_async_concurrency.graph import Ref, Task, critical_path_ms
from lessons.lesson_async_concurrency.locales import Texts, texts_for
from lessons.lesson_async_concurrency.scheduler import Outcome, Scheduler
from lessons.lesson_async_concurrency.tools import make_tools

# Notes are keyed by lesson slug: displayed lesson numbers change when lessons are inserted, slugs do not.
NOTES = ("messages-context", "application-state", "context-budget", "prompt-caching")
PAIR = NOTES[:2]
NoteChoice = Literal["none", "messages-context", "application-state", "context-budget", "prompt-caching"]
# A variant that is not about timeouts gets timeouts so long they never fire (30 s per tool, 5 min per run).
NO_TIMEOUT_MS = 30_000
NO_DEADLINE_MS = 300_000
MODEL_TIMEOUT_S = 30


class Inputs(LessonInputs):
    # Each scenario runs its own variants one after another in one run; the other fields tune what a scenario uses.
    scenario: Literal["dependency", "limits", "timeouts", "failure"] = "limits"
    tool_delay_ms: int = Field(200, ge=10, le=3000)
    # timeouts: which note is slow, how slow, the per-task timeout and the overall deadline of its variants.
    slow_lesson: NoteChoice = "context-budget"
    slow_delay_ms: int = Field(1500, ge=10, le=10000)
    task_timeout_ms: int = Field(500, ge=50, le=30000)
    deadline_ms: int = Field(700, ge=100, le=60000)
    # failure: which note is locked. timeouts and failure share the concurrency limit below.
    locked_lesson: NoteChoice = "messages-context"
    max_concurrency: int = Field(2, ge=1, le=4)


INPUT_MODEL = Inputs


@dataclass(frozen=True)
class Variant:
    """One configuration of the same job; a scenario is a list of these."""
    id: str
    workload: Literal["pair", "review"]
    schedule: Literal["by_dependency", "all_at_once"] = "by_dependency"
    limit: int = 4
    tool_timeout_ms: int = NO_TIMEOUT_MS
    deadline_ms: int = NO_DEADLINE_MS
    slow_lesson: str = "none"
    locked_lesson: str = "none"
    on_failure: Literal["continue", "cancel_all"] = "continue"


def build_variants(values: Inputs) -> list[Variant]:
    """The variants of the chosen scenario. The wrong schedule (all_at_once) exists only in the pair scenario."""
    if values.scenario == "dependency":
        pair = Variant("serial", "pair", limit=1)
        return [pair, replace(pair, id="by-dependency", limit=4),
                replace(pair, id="all-at-once", limit=4, schedule="all_at_once")]
    review = Variant("limit-1", "review", limit=1)
    if values.scenario == "limits":
        return [review, replace(review, id="limit-2", limit=2), replace(review, id="limit-4", limit=4)]
    review = replace(review, limit=values.max_concurrency)
    if values.scenario == "timeouts":
        slow = replace(review, slow_lesson=values.slow_lesson)
        return [replace(slow, id="waited"), replace(slow, id="task-timeout", tool_timeout_ms=values.task_timeout_ms),
                replace(review, id="deadline", deadline_ms=values.deadline_ms)]
    locked = replace(review, locked_lesson=values.locked_lesson)
    return [replace(locked, id="continue"), replace(locked, id="cancel-all", on_failure="cancel_all")]


class Counts:
    """How many requests and tool calls one variant really made; workers on several threads add to it."""

    def __init__(self):
        self._lock = threading.Lock()
        self.model = self.tool = 0

    def add(self, kind: str):
        with self._lock:
            setattr(self, kind, getattr(self, kind) + 1)


@dataclass
class Finished:
    """What one variant left behind, for the comparison at the end."""
    variant: Variant
    scheduler: Scheduler
    counts: Counts
    verdict: str
    peak: int
    violation: tuple[str, str] | None


def build_tasks(variant: Variant, values: Inputs) -> list[Task]:
    """The task list. Dependencies are not declared anywhere: they come from the Refs in the inputs."""
    lessons = PAIR if variant.workload == "pair" else NOTES
    review = variant.workload == "review"
    tool_s = variant.tool_timeout_ms / 1000
    tasks = [Task(f"read-{lesson}", "tool", "read_note",
                  {"lesson": lesson, "lock": lesson == variant.locked_lesson,
                   "delay_ms": values.slow_delay_ms if lesson == variant.slow_lesson else values.tool_delay_ms}, tool_s)
             for lesson in lessons]
    if review:
        tasks += [Task(f"sum-{lesson}", "model", "summarize",
                       {"lesson": lesson, "note": Ref(f"read-{lesson}", "note")}, MODEL_TIMEOUT_S) for lesson in lessons]
    source, key = ("sum", "summary") if review else ("read", "note")
    entries = [{"lesson": lesson, "text": Ref(f"{source}-{lesson}", key)} for lesson in lessons]
    # The sheet of the review job tolerates missing summaries (join settled) and says so; the pair's sheet does not.
    tasks.append(Task("sheet", "tool", "build_sheet",
                      {"lessons": list(lessons), "entries": entries, "allow_partial": review}, tool_s,
                      join="settled" if review else "all"))
    return tasks


def ask_model(context: RunContext, t: Texts, counts: Counts, branch: str, inputs: dict, round_number: int) -> dict:
    """One summary request on its own branch. It runs on a worker thread and cannot be recalled once sent."""
    note = inputs["note"]
    if not isinstance(note, str) or not note.strip():
        # Nothing to summarize yet: refuse before the request is sent, so no model call is wasted on an empty prompt.
        return {"ok": False, "error_type": "MissingInput", "error": t.summary_missing_input.format(lesson=inputs["lesson"])}
    counts.add("model")
    response = context.complete({"messages": [{"role": "system", "content": t.summary_system},
                                              {"role": "user", "content": t.summary_request.format(
                                                  lesson=inputs["lesson"], note=note)}],
                                 "temperature": 0}, round_number, branch=branch)
    content = response["choices"][0].get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        return {"ok": False, "error_type": "EmptyReply", "error": t.empty_reply}
    return {"ok": True, "result": {"lesson": inputs["lesson"], "summary": content.strip()}}


async def run(context: RunContext):
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    variants = build_variants(values)
    if variants[0].workload == "review" and context.completion is None:
        raise ValueError(t.needs_model)
    finished = []
    for index, variant in enumerate(variants):
        # 1. Each variant is a whole run of the job on its own scheduler, three rounds apart from the one before.
        finished.append(await run_variant(context, t, values, variant, 3 * index))
        # 2. A Stop that arrived during a variant ends the run here, after that variant's threads are gone.
        context.check_cancelled()
    return _report_total(context, t, values, finished)


async def run_variant(context: RunContext, t: Texts, values: Inputs, variant: Variant, base_round: int) -> Finished:
    counts, tasks = Counts(), build_tasks(variant, values)

    async def work(task: Task, inputs: dict, stop: threading.Event, in_thread) -> dict:
        # The blocking part goes to a worker thread; this coroutine only waits for it (or stops waiting).
        round_number = base_round + scheduler.levels[task.id]
        if task.kind == "model":
            branch = f"{variant.id}/{task.id}"
            return await in_thread(task.id, partial(ask_model, context, t, counts, branch, inputs, round_number))
        counts.add("tool")
        return await in_thread(task.id, partial(context.call_tool, task.name, inputs, make_tools(t, stop), round_number,
                                                f"call-{variant.id}-{task.id}"))

    scheduler = Scheduler(
        tasks, limit=variant.limit, schedule=variant.schedule, on_failure=variant.on_failure,
        deadline_s=variant.deadline_ms / 1000, stop_requested=context.cancelled, run_task=work,
        on_outcome=lambda outcome: _emit_task(context, t, scheduler, variant, base_round, outcome),
        on_stop=lambda: _emit_stop(context, t, scheduler, variant, base_round))
    _announce(context, t, scheduler, variant, base_round)
    # Run the whole graph on one event loop. It returns when every task has an outcome and every thread has ended.
    await scheduler.run()
    context.check_cancelled()
    outcomes = [scheduler.outcomes[task.id] for task in tasks]
    done = Finished(variant, scheduler, counts, verdict_of(scheduler, variant), peak_concurrency(outcomes),
                    dependency_violation(scheduler))
    _report_variant(context, t, done, base_round)
    return done


# ---------- Events ----------
def _announce(context: RunContext, t: Texts, scheduler: Scheduler, variant: Variant, base_round: int) -> None:
    """lesson.graph: what the scheduler read from the references, level by level."""
    depth = scheduler.levels
    layers = [[task.id for task in scheduler.tasks if depth[task.id] == level] for level in range(1, max(depth.values()) + 1)]
    context.emit("lesson.graph", {
        "variant": variant.id, "workload": variant.workload, "schedule": variant.schedule, "limit": variant.limit,
        "nodes": [{"id": task.id, "kind": task.kind, "name": task.name, "needs": list(task.needs),
                   "level": depth[task.id], "timeout_ms": round(task.timeout_s * 1000), "join": task.join}
                  for task in scheduler.tasks],
        "levels": layers, "detail": t.graph_detail.format(
            variant=t.variant_names[variant.id], count=len(scheduler.tasks), levels=len(layers))}, base_round + 1)


def reason_text(t: Texts, scheduler: Scheduler, outcome: Outcome) -> str:
    """One sentence for why a task ended the way it did; empty for a task that finished well."""
    if outcome.reason is None:
        return ""
    return t.reason_texts[outcome.reason].format(
        error=outcome.detail.get("error", ""), error_type=outcome.detail.get("error_type", ""),
        blocked=t.list_separator.join(outcome.detail.get("blocked_by", [])), origin=scheduler.stop_origin or "",
        timeout_ms=round(outcome.task.timeout_s * 1000))


def _emit_task(context: RunContext, t: Texts, scheduler: Scheduler, variant: Variant, base_round: int,
               outcome: Outcome) -> None:
    """lesson.task: how one task ended. Times are milliseconds on the backend clock, counted from the variant's start."""
    task, start = outcome.task, outcome.started_ms
    context.emit("lesson.task", {
        "variant": variant.id, "id": task.id, "kind": task.kind, "name": task.name, "level": scheduler.levels[task.id],
        "needs": list(task.needs), "status": outcome.status, "reason": outcome.reason,
        "started_ms": start, "ended_ms": outcome.ended_ms,
        "duration_ms": None if start is None else outcome.ended_ms - start,
        "late_ms": outcome.late_ms, **outcome.detail, "detail": reason_text(t, scheduler, outcome)},
        base_round + scheduler.levels[task.id])


def _emit_stop(context: RunContext, t: Texts, scheduler: Scheduler, variant: Variant, base_round: int) -> None:
    """lesson.stop: the moment the scheduler told everything to stop, and which tasks were running then."""
    running = [task_id for task_id in scheduler.stops if task_id not in scheduler.outcomes]
    context.emit("lesson.stop", {
        "variant": variant.id, "reason": scheduler.stop_reason, "origin": scheduler.stop_origin,
        "at_ms": scheduler.stop_at_ms, "running": running,
        "detail": t.stop_details[scheduler.stop_reason].format(
            origin=scheduler.stop_origin or "", deadline_ms=variant.deadline_ms, running=len(running))}, base_round + 1)


# ---------- Measurements ----------
def peak_concurrency(outcomes: list[Outcome]) -> int:
    """The most tasks that held a slot at the same moment, counted from the recorded start and release times.

    This does not read the semaphore: it recomputes the number from the timestamps, so it can disagree with it.
    Ends sort before starts at the same millisecond, because a task takes a slot only after another let go of one.
    """
    marks = sorted([(o.started_ms, 1) for o in outcomes if o.started_ms is not None]
                   + [(o.released_ms, -1) for o in outcomes if o.started_ms is not None])
    now = peak = 0
    for _, step in marks:
        now += step
        peak = max(peak, now)
    return peak


def dependency_violation(scheduler: Scheduler) -> tuple[str, str] | None:
    """The first task that started before one of the values it needs existed; None when every start was in order."""
    for task in scheduler.tasks:
        outcome = scheduler.outcomes[task.id]
        if outcome.started_ms is None:
            continue
        for need in task.needs:
            dependency = scheduler.outcomes[need]
            if (dependency.status != "done" and task.join == "all") or outcome.started_ms < dependency.ended_ms:
                return task.id, need
    return None


def verdict_of(scheduler: Scheduler, variant: Variant) -> str:
    """complete: everything asked for exists. partial: some of it does. failed: none of it does."""
    outcomes, sheet = scheduler.outcomes, scheduler.results.get("sheet")
    if variant.workload == "pair":
        return "complete" if sheet is not None else "failed"
    summaries = [outcomes[f"sum-{lesson}"].status == "done" for lesson in NOTES]
    if all(summaries) and sheet is not None and sheet["complete"]:
        return "complete"
    return "partial" if any(summaries) else "failed"


def serial_ms(scheduler: Scheduler) -> int:
    """The sum of every task's measured duration: what running them one by one would have taken."""
    return sum(o.ended_ms - o.started_ms for o in scheduler.outcomes.values() if o.started_ms is not None)


def critical_ms(scheduler: Scheduler) -> int:
    durations = {o.task.id: o.ended_ms - o.started_ms for o in scheduler.outcomes.values() if o.started_ms is not None}
    return critical_path_ms(scheduler.tasks, durations)


# ---------- Reports ----------
def _sheet_marker(t: Texts, scheduler: Scheduler) -> str:
    """What the sheet tool itself said about its output; a sheet that was never built has nothing to say."""
    sheet = scheduler.results.get("sheet")
    if sheet is None:
        return t.sheet_not_built
    return t.sheet_complete if sheet["complete"] else t.sheet_partial.format(missing=t.list_separator.join(sheet["missing"]))


def _dependency_detail(t: Texts, scheduler: Scheduler, violation: tuple[str, str] | None) -> str:
    if violation is None:
        return t.detail_dependencies_ok
    task, need = violation
    return t.detail_dependencies_bad.format(
        task=task, need=need, started=scheduler.outcomes[task].started_ms, ended=scheduler.outcomes[need].ended_ms,
        status=t.status_names[scheduler.outcomes[need].status])


def _missing(scheduler: Scheduler) -> list[str]:
    return [task.id for task in scheduler.tasks if scheduler.outcomes[task.id].status != "done"]


def _report_variant(context: RunContext, t: Texts, done: Finished, base_round: int) -> None:
    """Emit one variant's report (lesson.report): its checks, its numbers and one row per task."""
    scheduler, variant = done.scheduler, done.variant
    outcomes = [scheduler.outcomes[task.id] for task in scheduler.tasks]
    by_status = {status: sum(o.status == status for o in outcomes) for status in t.status_names}
    late = [o for o in outcomes if o.late_ms > 0]
    orphans = scheduler.threads_alive
    context.emit("lesson.report", {
        "title": t.variant_title.format(variant=t.variant_names[variant.id]), "summary": t.variant_summary,
        "checks": [
            {"id": "dependencies", "label": t.check_dependencies, "passed": done.violation is None,
             "detail": _dependency_detail(t, scheduler, done.violation)},
            {"id": "limit", "label": t.check_limit, "passed": done.peak <= variant.limit,
             "detail": t.detail_limit.format(peak=done.peak, limit=variant.limit)},
            {"id": "no_orphans", "label": t.check_orphans, "passed": orphans == 0,
             "detail": t.detail_orphans.format(alive=orphans, late=len(late), late_ms=max((o.late_ms for o in late), default=0))},
            {"id": "complete", "label": t.check_complete, "passed": done.verdict == "complete",
             "detail": t.detail_complete_ok if done.verdict == "complete" else t.detail_complete_missing.format(
                 missing=t.list_separator.join(_missing(scheduler)))}],
        "metrics": [
            {"id": "verdict", "label": t.label_verdict, "value": t.verdicts[done.verdict]},
            {"id": "wall_ms", "label": t.label_wall_ms, "value": scheduler.wall_ms},
            {"id": "serial_ms", "label": t.label_serial_ms, "value": serial_ms(scheduler)},
            {"id": "critical_ms", "label": t.label_critical_ms, "value": critical_ms(scheduler)},
            {"id": "limit", "label": t.label_limit, "value": variant.limit},
            {"id": "peak", "label": t.label_peak, "value": done.peak},
            {"id": "peak_threads", "label": t.label_peak_threads, "value": scheduler.peak_threads},
            {"id": "model_calls", "label": t.label_model_calls, "value": done.counts.model},
            {"id": "tool_calls", "label": t.label_tool_calls, "value": done.counts.tool},
            *({"id": status, "label": t.status_labels[status], "value": count} for status, count in by_status.items()),
            {"id": "late", "label": t.label_late, "value": len(late)},
            {"id": "sheet", "label": t.label_sheet, "value": _sheet_marker(t, scheduler)}],
        "table": {"columns": list(t.table_columns), "rows": [
            [o.task.id, t.kind_names[o.task.kind], t.list_separator.join(o.task.needs) or "—", scheduler.levels[o.task.id],
             "—" if o.started_ms is None else o.started_ms, o.ended_ms, t.status_names[o.status],
             reason_text(t, scheduler, o) or "—"] for o in outcomes]},
    }, base_round + max(scheduler.levels.values()))


def _report_total(context: RunContext, t: Texts, values: Inputs, finished: list[Finished]) -> str:
    """Emit the comparison report (lesson.report) and return the answer, written from what really finished."""
    checks, metrics, rows = [], [], []
    for done in finished:
        name, scheduler, key = t.variant_names[done.variant.id], done.scheduler, done.variant.id
        checks += [
            {"id": f"dependencies.{key}", "label": t.total_check_dependencies.format(variant=name),
             "passed": done.violation is None, "detail": _dependency_detail(t, scheduler, done.violation)},
            {"id": f"complete.{key}", "label": t.total_check_complete.format(variant=name),
             "passed": done.verdict == "complete",
             "detail": t.detail_complete_ok if done.verdict == "complete" else t.detail_complete_missing.format(
                 missing=t.list_separator.join(_missing(scheduler)))}]
        metrics += [{"id": f"{metric}.{key}", "label": t.total_metric.format(variant=name, label=label), "value": value}
                    for metric, label, value in (("wall_ms", t.label_wall_ms, scheduler.wall_ms),
                                                 ("peak", t.label_peak, done.peak),
                                                 ("model_calls", t.label_model_calls, done.counts.model),
                                                 ("late", t.label_late, sum(o.late_ms > 0 for o in scheduler.outcomes.values())),
                                                 ("sheet", t.label_sheet, _sheet_marker(t, scheduler)),
                                                 ("verdict", t.label_verdict, t.verdicts[done.verdict]))]
        rows.append([name, scheduler.wall_ms, serial_ms(scheduler), critical_ms(scheduler), done.variant.limit,
                     done.peak, done.counts.model, done.counts.tool, t.verdicts[done.verdict]])
    alive = sum(done.scheduler.threads_alive for done in finished)
    checks += [
        {"id": "limit_held", "label": t.total_check_limit,
         "passed": all(done.peak <= done.variant.limit for done in finished),
         "detail": t.total_detail_limit.format(peaks=t.list_separator.join(
             f"{done.peak}/{done.variant.limit}" for done in finished))},
        {"id": "no_orphans", "label": t.total_check_orphans, "passed": alive == 0,
         "detail": t.total_detail_orphans.format(alive=alive)}]
    metrics += [{"id": "model_calls", "label": t.label_model_calls, "value": sum(d.counts.model for d in finished)},
                {"label": t.label_note, "value": context.question or t.value_empty}]
    context.emit("lesson.report", {
        "title": t.total_title.format(scenario=t.scenario_names[values.scenario]), "summary": t.total_summary,
        "checks": checks, "metrics": metrics, "table": {"columns": list(t.total_columns), "rows": rows}},
        3 * len(finished))
    return _answer(t, values, finished)


def _answer(t: Texts, values: Inputs, finished: list[Finished]) -> str:
    """One line per variant, and under it what did not finish: a partial result never reads as a whole one."""
    lines = [t.answer_header.format(scenario=t.scenario_names[values.scenario])]
    for done in finished:
        scheduler, missing = done.scheduler, _missing(done.scheduler)
        lines.append(t.answer_variant.format(
            variant=t.variant_names[done.variant.id], verdict=t.verdicts[done.verdict], wall=scheduler.wall_ms,
            done=len(scheduler.tasks) - len(missing), total=len(scheduler.tasks)))
        if missing:
            lines.append(t.answer_missing.format(items=t.list_separator.join(
                t.answer_missing_item.format(id=task_id, status=t.status_names[scheduler.outcomes[task_id].status])
                for task_id in missing)))
    return "\n".join(lines)
