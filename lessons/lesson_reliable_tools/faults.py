"""Fault injection: the runner deliberately creates the failures this lesson studies.

Each one is announced first as a lesson.fault event with source fault_injection, so nobody takes it
for a failure that happened on its own:

- store_locked: another connection holds an exclusive lock on the database, so the tool really
  waits timeout_s and gives up;
- outbox_locked: another writer's lock file sits in the outbox, so write_outbox really finds it busy;
- response_lost: the tool really runs and commits; its result is then dropped on the way back,
  as when a connection breaks after the other side has finished.
"""
import sqlite3
from contextlib import contextmanager

from lessons.lesson_reliable_tools.store import PracticeStore, ToolFailure

FAULTS = ("store_locked", "outbox_locked", "response_lost")


class ResponseLost(ToolFailure):
    """The call may well have taken effect; the caller never saw its result."""


class FaultInjector:
    def __init__(self, store: PracticeStore, plan: dict[tuple[str, int], str], texts):
        """plan maps (operation, attempt number) to a fault; attempts not in it run untouched."""
        unknown = set(plan.values()) - set(FAULTS)
        if unknown:
            raise ValueError(f"unknown faults: {sorted(unknown)}")
        self.store = store
        self.plan = plan
        self.t = texts
        self._drop_result = False

    @contextmanager
    def attempt(self, context, operation: str, tool: str, number: int):
        """Set up this attempt's fault (if any) around the real tool call, then clear it."""
        fault = self.plan.get((operation, number))
        if fault is not None:
            context.emit("lesson.fault", {"source": "fault_injection", "operation": operation, "tool": tool,
                                          "attempt": number, "fault": fault})
        if fault == "store_locked":
            with self._database_locked():
                yield
        elif fault == "outbox_locked":
            with self._outbox_locked():
                yield
        else:
            self._drop_result = fault == "response_lost"
            try:
                yield
            finally:
                self._drop_result = False

    def tools(self, functions: dict) -> dict:
        """Wrap each tool so a planned response_lost drops the result after the tool really ran."""
        def wrap(function):
            def call(**arguments):
                result = function(**arguments)
                if self._drop_result:
                    raise ResponseLost(self.t.response_lost)
                return result
            return call
        return {name: wrap(function) for name, function in functions.items()}

    @contextmanager
    def _database_locked(self):
        # A second connection stands in for another process: BEGIN EXCLUSIVE blocks readers and writers alike.
        holder = sqlite3.connect(self.store.database, isolation_level=None)
        try:
            holder.execute("BEGIN EXCLUSIVE")
            yield
            holder.execute("ROLLBACK")
        finally:
            holder.close()

    @contextmanager
    def _outbox_locked(self):
        lock = self.store.outbox / ".lock"
        lock.write_text("held by another writer", encoding="utf-8")
        try:
            yield
        finally:
            lock.unlink(missing_ok=True)
