"""A fixed-interval trigger and what it does when the previous run has not finished.

The trigger fires at every multiple of its interval on the virtual clock. Each fire is decided at once and
recorded, whatever the decision: start a run, skip, queue, or refuse. A run is one background job with its own
run id, so every fire that starts something leaves its own record. Nothing here survives the process: a real
product needs an external scheduler or a persistent queue for that.
"""
from lessons.lesson_long_running_tasks.executor import BackgroundExecutor, Job

POLICIES = ("skip", "queue", "parallel")
QUEUE_LIMIT = 2  # the queue policy holds at most this many waiting fires; later ones are dropped


class Scheduler:
    def __init__(self, executor: BackgroundExecutor, *, kind: str, every: int, policy: str, max_concurrent: int):
        if policy not in POLICIES:
            raise ValueError(f"unknown overlap policy: {policy}")
        self.executor, self.kind, self.every, self.policy = executor, kind, every, policy
        # skip and queue never run two at once; only the parallel policy lets runs overlap, up to a cap.
        self.capacity = max_concurrent if policy == "parallel" else 1
        self.trigger_id = f"every-{every}s"
        self.next_due, self.fires = every, 0
        self.queue: list[dict] = []
        self.runs: dict[str, Job] = {}

    def active(self) -> list[str]:
        return [run_id for run_id, job in self.runs.items() if job.status == "running"]

    def poll(self, now: int) -> list[dict]:
        """Decide every fire that has come due at now; return one record per decision, in order."""
        records = []
        # 1. A freed slot goes to the oldest queued fire before any new fire.
        while self.queue and len(self.active()) < self.capacity:
            waiting = self.queue.pop(0)
            records.append(self._start(waiting["fire_no"], waiting["due_at"], now, "started_from_queue"))
        # 2. Every slot that has come due, oldest first; a long jump of the clock yields several fires.
        while self.next_due <= now:
            self.fires += 1
            due_at, self.next_due = self.next_due, self.next_due + self.every
            records.append(self._decide(self.fires, due_at, now))
        return records

    def _decide(self, fire_no: int, due_at: int, now: int) -> dict:
        if len(self.active()) < self.capacity:
            return self._start(fire_no, due_at, now, "started")
        if self.policy == "skip":
            return self._record(fire_no, due_at, now, "skipped", reason="previous_running")
        if self.policy == "queue":
            if len(self.queue) < QUEUE_LIMIT:
                self.queue.append({"fire_no": fire_no, "due_at": due_at})
                return self._record(fire_no, due_at, now, "queued", reason="previous_running")
            return self._record(fire_no, due_at, now, "dropped", reason="queue_full")
        return self._record(fire_no, due_at, now, "denied", reason="concurrency_limit")

    def _start(self, fire_no: int, due_at: int, now: int, action: str) -> dict:
        job = self.executor.start(self.kind, origin="schedule", limit=False)
        run_id = f"run-{len(self.runs) + 1}"
        self.runs[run_id] = job
        return self._record(fire_no, due_at, now, action, run_id=run_id, job=job)

    def _record(self, fire_no, due_at, now, action, *, reason=None, run_id=None, job=None) -> dict:
        return {"trigger": self.trigger_id, "fire_no": fire_no, "due_at": due_at, "at": now,
                "policy": self.policy, "action": action, "reason": reason, "run_id": run_id,
                "job_id": job.id if job else None, "active_runs": self.active(), "queued": len(self.queue)}
