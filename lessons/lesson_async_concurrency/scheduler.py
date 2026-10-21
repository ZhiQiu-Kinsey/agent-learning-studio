"""An asyncio scheduler: dependencies first, a concurrency limit, per-task timeouts, one deadline, a failure policy.

Every task is one asyncio task that waits for its dependencies, then for a free slot of a Semaphore, then runs its
work on a worker thread (the work is blocking code: a sleeping tool, an HTTP request). The slot is held until that
thread has really ended, not just until the scheduler stopped waiting, so the limit counts requests the provider is
still serving. A timeout or a cancel stops the *waiting* at once; whether the work stops too depends on the work:
a tool listens to a stop Event and quits within milliseconds, a model request cannot be recalled and runs to its end.
All scheduler state is touched from the event-loop thread only, except the thread registry, which has its own lock.
"""
import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from course.runner import RunCancelled
from lessons.lesson_async_concurrency.graph import Task, levels, resolve

THREAD_PREFIX = "ac-task-"
WATCH_INTERVAL_S = 0.01
# Statuses a task can end in. "skipped" means the work never started (reason says why); "cancelled" means it was
# running when the scheduler stopped it.
STATUSES = ("done", "failed", "timed_out", "cancelled", "skipped")
# What a task that did not end well does to the others when the policy is cancel_all.
TRIGGERS = ("failed", "timed_out")


@dataclass
class Outcome:
    task: Task
    status: str
    reason: str | None  # error, task_timeout, dependency, deadline, policy, user_stop
    started_ms: int | None
    ended_ms: int
    # When the task let go of its slot: later than ended_ms if the work kept running after the scheduler gave up.
    released_ms: int | None = None
    detail: dict = field(default_factory=dict)

    @property
    def late_ms(self) -> int:
        # Only a task the scheduler gave up on can be late; any other task ended when its work ended.
        if self.status not in ("timed_out", "cancelled"):
            return 0
        return max((self.released_ms or self.ended_ms) - self.ended_ms, 0)


class Scheduler:
    def __init__(self, tasks: list[Task], *, limit: int, schedule: str, on_failure: str, deadline_s: float,
                 stop_requested: Callable[[], bool],
                 run_task: Callable[[Task, dict, threading.Event, Callable], Awaitable[dict]],
                 on_outcome: Callable[[Outcome], None], on_stop: Callable[[], None]):
        self.tasks, self.levels = tasks, levels(tasks)
        self.limit, self.schedule, self.on_failure, self.deadline_s = limit, schedule, on_failure, deadline_s
        self.stop_requested, self.run_task, self.on_outcome, self.on_stop = stop_requested, run_task, on_outcome, on_stop
        self.outcomes: dict[str, Outcome] = {}
        self.results: dict[str, dict] = {}
        self.stops: dict[str, threading.Event] = {}
        self.stop_reason: str | None = None
        self.stop_origin: str | None = None
        self.stop_at_ms: int | None = None
        self.wall_ms = 0
        self._live: set[str] = set()
        self._ended: dict[str, asyncio.Event] = {}  # set from the loop when a task's thread has really ended
        self._peak_threads = 0
        self._thread_lock = threading.Lock()
        self._t0 = time.perf_counter()

    def now_ms(self) -> int:
        return round((time.perf_counter() - self._t0) * 1000)

    @property
    def threads_alive(self) -> int:
        with self._thread_lock:
            return len(self._live)

    @property
    def peak_threads(self) -> int:
        return self._peak_threads

    async def run(self) -> None:
        self._t0 = time.perf_counter()
        self._slots = asyncio.Semaphore(self.limit)
        self._settled = {task.id: asyncio.Event() for task in self.tasks}
        self._async_tasks = {task.id: asyncio.create_task(self._run(task), name=task.id) for task in self.tasks}
        watcher = asyncio.create_task(self._watch())
        try:
            # 1. Wait for every task: each one records its own outcome, so a cancelled task is a normal result here.
            ended = await asyncio.gather(*self._async_tasks.values(), return_exceptions=True)
        finally:
            # 2. The watcher is ours too: cancel it and wait until it is really gone.
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
        self.wall_ms = self.now_ms()
        for task in self.tasks:  # a task cancelled before its first step never ran its own bookkeeping
            if task.id not in self.outcomes:
                self._skip(task, self.stop_reason or "user_stop")
        # 3. Anything that is not a plain cancellation is a bug in the scheduler or the work: do not swallow it.
        for item in ended:
            if isinstance(item, BaseException) and not isinstance(item, asyncio.CancelledError):
                raise item

    async def _run(self, task: Task) -> None:
        try:
            # 1. Wait for the values this task needs (all_at_once skips the wait and runs on whatever exists).
            if self.schedule == "by_dependency":
                for need in task.needs:
                    await self._settled[need].wait()
                blocked = [need for need in task.needs if self.outcomes[need].status != "done"]
                if blocked and task.join == "all":
                    return self._skip(task, "dependency", {"blocked_by": blocked})
            # 2. Wait for a free slot; a stop that arrived while waiting means the work never starts.
            async with self._slots:
                if self.stop_reason:
                    return self._skip(task, self.stop_reason)
                await self._execute(task)
        except asyncio.CancelledError:
            if task.id not in self.outcomes:
                self._skip(task, self.stop_reason or "user_stop")
            raise  # a cancelled task records itself and then lets the cancellation continue
        finally:
            self._settled[task.id].set()

    async def _execute(self, task: Task) -> None:
        stop = self.stops[task.id] = threading.Event()
        started = self.now_ms()
        status, reason, detail = "done", None, {}
        # The timer starts here, after the slot was granted: waiting in line must not eat the task's own time.
        timeout = asyncio.timeout(task.timeout_s)
        try:
            inputs = resolve(task.inputs, self.results)
            async with timeout:
                result = await self.run_task(task, inputs, stop, self._in_thread)
            if result.get("ok"):
                self.results[task.id] = result["result"]
            else:
                status, reason = "failed", "error"
                detail = {"error_type": result.get("error_type"), "error": result.get("error")}
        except TimeoutError as error:
            if timeout.expired():
                status, reason = "timed_out", "task_timeout"
            else:  # a timeout raised by the work itself (a socket) is a failure, not this scheduler's timer
                status, reason, detail = "failed", "error", {"error_type": type(error).__name__, "error": str(error)}
        except asyncio.CancelledError:
            status, reason = "cancelled", self.stop_reason or "user_stop"
            raise
        except RunCancelled:
            status, reason = "cancelled", "user_stop"
        except Exception as error:  # the work failed alone; its siblings are the failure policy's business
            status, reason = "failed", "error"
            detail = {"error_type": type(error).__name__, "error": str(error)[:300]}
        finally:
            await self._finish(task, stop, Outcome(task, status, reason, started, self.now_ms(), None, detail))

    async def _finish(self, task: Task, stop: threading.Event, outcome: Outcome) -> None:
        """Record how the task ended, apply the failure policy, and give the slot back only when the work is over."""
        self.outcomes[task.id] = outcome
        if outcome.status in TRIGGERS and self.on_failure == "cancel_all":
            self.cancel_all("policy", task.id)
        stop.set()  # whatever ended it, the work has no reason left to go on
        # Hold the slot until the work's thread has really ended; only then is the provider free again.
        cancelled_again = await self._thread_ended(task.id)
        outcome.released_ms = self.now_ms()
        try:
            self.on_outcome(outcome)
        except RunCancelled:
            pass  # after a stop the platform takes no more events; the outcome is still in self.outcomes
        if cancelled_again:
            raise asyncio.CancelledError

    def cancel_all(self, reason: str, origin: str | None = None) -> None:
        """Stop everything that is still waiting or running; the first reason given is the one recorded."""
        if self.stop_reason:
            return
        self.stop_reason, self.stop_origin, self.stop_at_ms = reason, origin, self.now_ms()
        try:
            self.on_stop()  # recorded before anything is cancelled, so it can say which tasks were still running
        except RunCancelled:
            pass
        for event in self.stops.values():
            event.set()  # a tool hears this at once, even before its awaiting task has noticed the cancel
        for task in self._async_tasks.values():
            if task is not asyncio.current_task() and not task.done():
                task.cancel()

    async def _watch(self) -> None:
        """Poll the two things only a clock can notice: the Stop button and the overall deadline."""
        deadline_at = self._t0 + self.deadline_s
        while True:
            if self.stop_requested():
                return self.cancel_all("user_stop")
            if time.perf_counter() >= deadline_at:
                return self.cancel_all("deadline")
            await asyncio.sleep(WATCH_INTERVAL_S)

    def _skip(self, task: Task, reason: str, detail: dict | None = None) -> None:
        now = self.now_ms()
        outcome = self.outcomes[task.id] = Outcome(task, "skipped", reason, None, now, now, detail or {})
        try:
            self.on_outcome(outcome)
        except RunCancelled:
            pass

    def _in_thread(self, task_id: str, function: Callable) -> asyncio.Future:
        """Run blocking work on its own thread and return a future for its result.

        Not asyncio.to_thread: the scheduler must know when the thread has *really* ended, and a future
        cancelled by a timeout says nothing about that.
        """
        loop = asyncio.get_running_loop()
        future, ended = loop.create_future(), asyncio.Event()
        self._ended[task_id] = ended
        with self._thread_lock:
            self._live.add(task_id)
            self._peak_threads = max(self._peak_threads, len(self._live))

        def work():
            try:
                value, error = function(), None
            except BaseException as caught:  # handed to the awaiting task, which decides what it means
                value, error = None, caught
            with self._thread_lock:
                self._live.discard(task_id)
            try:
                loop.call_soon_threadsafe(_deliver, future, value, error)
                loop.call_soon_threadsafe(ended.set)
            except RuntimeError:  # the loop is already closed: nobody is waiting any more
                pass

        threading.Thread(target=work, name=f"{THREAD_PREFIX}{task_id}", daemon=True).start()
        return future

    async def _thread_ended(self, task_id: str) -> bool:
        """Wait until the task's thread has ended, even through a cancel; True if one arrived meanwhile."""
        cancelled = False
        while task_id in self._ended and not self._ended[task_id].is_set():
            try:
                await self._ended[task_id].wait()
            except asyncio.CancelledError:
                cancelled = True  # the slot is still in use: finish waiting, then pass the cancel on
        return cancelled


def _deliver(future: asyncio.Future, value, error) -> None:
    if future.done():  # cancelled by a timeout or a stop: the result has nowhere to go
        return
    if error is not None:
        future.set_exception(error)
    else:
        future.set_result(value)
