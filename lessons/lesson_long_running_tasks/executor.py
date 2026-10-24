"""A background executor on real threads, driven by a virtual clock.

A job is a function that really runs (jobs.py) on its own thread. What is virtual is only the time it
declares: every step says how many seconds it takes, and the thread waits for the clock to reach that moment
instead of sleeping. Only the runner moves the clock, and it settles all workers after each move, so one run
always produces the same timeline and a test never waits for real time. A product would use a wall clock here.
Workers never publish events: the runner reads job state after the workers have settled and records it from its
own thread, which is the only thread that may talk to RunContext.
"""
import threading
from dataclasses import dataclass, field

from lessons.lesson_long_running_tasks.jobs import SPECS, JobSpec

# Unix habit: 0 ok, 1 failed, 124 as GNU timeout, 143 = 128 + SIGTERM. The lesson borrows the numbers, not a process.
EXIT_CODES = {"completed": 0, "failed": 1, "timed_out": 124, "cancelled": 143}
TERMINAL = tuple(EXIT_CODES)
THREAD_PREFIX = "lrt-job-"
SETTLE_TIMEOUT_S = 10  # real seconds: a worker that never parks is a bug here, not a slow job


class JobRefused(ValueError):
    """A start, check or cancel the executor refuses; the tool layer turns it into a structured error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class VirtualClock:
    """Time that moves only when the runner says so; worker threads park on it instead of sleeping."""

    def __init__(self, start: int = 0):
        self.cond = threading.Condition()
        self._now = start
        self._parked: dict[str, int] = {}  # job id -> the moment it waits for
        self._workers: set[str] = set()  # job ids whose thread has not finished

    @property
    def now(self) -> int:
        with self.cond:
            return self._now

    def add_worker(self, job_id: str):
        # Registered before the thread starts, so settle() can never pass a worker that has not parked yet.
        with self.cond:
            self._workers.add(job_id)

    def finish_worker(self, job_id: str):
        with self.cond:
            self._workers.discard(job_id)
            self._parked.pop(job_id, None)
            self.cond.notify_all()

    def wait_until(self, job_id: str, moment: int, stop: threading.Event) -> bool:
        """Park until the clock reaches moment; False when the job was stopped first."""
        with self.cond:
            while True:
                if stop.is_set():
                    self._parked.pop(job_id, None)
                    return False
                if self._now >= moment:
                    self._parked.pop(job_id, None)
                    return True
                self._parked[job_id] = moment
                self.cond.notify_all()  # tells settle() this worker has parked
                self.cond.wait()

    def advance_to(self, moment: int):
        with self.cond:
            self._now = max(self._now, moment)  # time never runs backwards
            # A worker whose moment has come is runnable from here on. Removing it now (not when it wakes)
            # keeps settle() from mistaking a worker that is about to run for one that is parked.
            for job_id, due in list(self._parked.items()):
                if due <= self._now:
                    del self._parked[job_id]
            self.cond.notify_all()

    def wake_all(self):
        with self.cond:
            self.cond.notify_all()

    def settle(self):
        """Block until every worker is parked at a future moment or finished."""
        with self.cond:
            if not self.cond.wait_for(lambda: len(self._parked) == len(self._workers), SETTLE_TIMEOUT_S):
                raise RuntimeError("background workers did not settle")


@dataclass
class Job:
    id: str
    kind: str
    spec: JobSpec
    origin: str  # "model" or "schedule": who started it
    started_at: int
    started_round: int | None
    timeout_seconds: int
    status: str = "running"
    progress: int = 0
    finished_at: int | None = None
    result: dict | None = None
    error: dict | None = None
    cancel_reason: str | None = None
    observed_at: int | None = None  # the clock when the runner first saw it finished
    delivered_round: int | None = None  # the round whose request first carried the result
    delivered: bool = False
    stop: threading.Event = field(default_factory=threading.Event, repr=False)
    thread: threading.Thread | None = field(default=None, repr=False)
    state: dict = field(default_factory=dict, repr=False)

    @property
    def exit_code(self) -> int | None:
        return EXIT_CODES.get(self.status)

    @property
    def projected_end(self) -> int:
        """When the job ends if nothing stops it: its last step, or its deadline if that comes first."""
        return min(self.started_at + self.spec.steps * self.spec.step_seconds, self.started_at + self.timeout_seconds)


class BackgroundExecutor:
    def __init__(self, clock: VirtualClock, texts, max_running: int = 3):
        self.clock, self.t, self.max_running = clock, texts, max_running
        self.jobs: dict[str, Job] = {}
        self._counter = 0

    # ---------- start, look, cancel ----------
    def start(self, kind: str, *, origin: str, round_number: int | None = None,
              timeout_seconds: int | None = None, limit: bool = True) -> Job:
        """Register a job and start its thread; returns once the worker is parked, so the caller never races it."""
        t = self.t
        spec = SPECS.get(kind)
        if spec is None:
            raise JobRefused("unknown_kind", t.unknown_kind.format(kind=kind, kinds=t.list_separator.join(SPECS)))
        if timeout_seconds is None:
            timeout_seconds = spec.timeout_seconds
        if type(timeout_seconds) is not int or not 5 <= timeout_seconds <= 120:
            raise JobRefused("bad_timeout", t.bad_timeout)
        if limit and len(self.running()) >= self.max_running:
            raise JobRefused("too_many_jobs", t.too_many_jobs.format(limit=self.max_running))
        self._counter += 1
        job = Job(f"job-{self._counter}", kind, spec, origin, self.clock.now, round_number, timeout_seconds)
        job.thread = threading.Thread(target=self._work, args=(job,), name=f"{THREAD_PREFIX}{job.id}", daemon=True)
        self.jobs[job.id] = job
        self.clock.add_worker(job.id)
        job.thread.start()
        self.clock.settle()
        return job

    def get(self, job_id) -> Job:
        job = self.jobs.get(job_id) if isinstance(job_id, str) else None
        if job is None:
            raise JobRefused("unknown_job", self.t.unknown_job.format(job_id=job_id))
        return job

    def running(self) -> list[Job]:
        with self.clock.cond:
            return [job for job in self.jobs.values() if job.status == "running"]

    def cancel(self, job_id: str, reason: str) -> Job:
        job = self.get(job_id)
        with self.clock.cond:
            if job.status != "running":
                raise JobRefused("already_finished", self.t.already_finished.format(job_id=job.id, status=job.status))
            job.cancel_reason = reason
        job.stop.set()
        self.clock.wake_all()
        job.thread.join(SETTLE_TIMEOUT_S)  # the worker marks itself cancelled; waiting makes the result certain
        if job.thread.is_alive():
            raise RuntimeError("background worker did not stop")
        return job

    # ---------- the runner's view after the workers settled ----------
    def advance_to(self, moment: int):
        self.clock.advance_to(moment)
        self.clock.settle()

    def next_terminal(self) -> int | None:
        """The earliest moment any running job can end; the runner jumps here when the model has nothing to do."""
        ends = [job.projected_end for job in self.running()]
        return min(ends) if ends else None

    def collect_finished(self) -> list[Job]:
        """Jobs that ended on their own since the last call, oldest first. Cancelled jobs report through the cancel."""
        now = self.clock.now
        with self.clock.cond:
            fresh = [job for job in self.jobs.values()
                     if job.status in ("completed", "failed", "timed_out") and job.observed_at is None]
            for job in fresh:
                job.observed_at = now
        return sorted(fresh, key=lambda job: (job.finished_at, job.id))

    def alive(self) -> int:
        return sum(job.thread is not None and job.thread.is_alive() for job in self.jobs.values())

    def shutdown(self, reason: str) -> list[Job]:
        """Cancel whatever still runs and join every thread; safe to call twice, also after an error or a stop."""
        cancelled = []
        for job in list(self.jobs.values()):
            if job.status == "running":
                job.cancel_reason = reason
                job.stop.set()
                cancelled.append(job)
        self.clock.wake_all()
        for job in self.jobs.values():
            if job.thread is not None:
                job.thread.join(SETTLE_TIMEOUT_S)
        return cancelled

    # ---------- the worker thread ----------
    def _work(self, job: Job):
        """1. wait for each step's moment, 2. really do the step, 3. end as completed, failed, timed out or cancelled."""
        spec, clock = job.spec, self.clock
        deadline = job.started_at + job.timeout_seconds
        try:
            for index in range(spec.steps):
                moment = job.started_at + (index + 1) * spec.step_seconds
                if moment > deadline:
                    # The step would end after the deadline: wait for the deadline itself, then give up.
                    if clock.wait_until(job.id, deadline, job.stop):
                        return self._end(job, "timed_out", deadline)
                    return self._end(job, "cancelled", clock.now)
                if not clock.wait_until(job.id, moment, job.stop):
                    return self._end(job, "cancelled", clock.now)
                spec.work(job.state, index, self.t)
                with clock.cond:
                    job.progress = index + 1
            self._end(job, "completed", job.started_at + spec.steps * spec.step_seconds, result=spec.finish(job.state, self.t))
        except Exception as error:  # a job that raises fails alone; its siblings and the runner go on
            self._end(job, "failed", self._failed_at(job),
                      error={"error_type": type(error).__name__, "error": str(error)})
        finally:
            clock.finish_worker(job.id)

    def _failed_at(self, job: Job) -> int:
        """A job fails in the step it was running: that step's moment, not whenever the runner looks."""
        return job.started_at + (job.progress + 1) * job.spec.step_seconds

    def _end(self, job: Job, status: str, finished_at: int, *, result=None, error=None):
        with self.clock.cond:
            job.status, job.finished_at, job.result, job.error = status, finished_at, result, error
            self.clock.cond.notify_all()
