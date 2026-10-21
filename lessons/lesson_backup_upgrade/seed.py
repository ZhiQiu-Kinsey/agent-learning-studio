"""The teaching data directory: two real SQLite files shaped like .runtime/, plus a decoy config file.

Every exercise builds its own directory inside a temporary folder; nothing here touches the real .runtime/.
The runs file is written through the platform's RunStore (WAL mode) and the memory file through the memory lessons'
MemoryStore (rollback-journal mode), so the two files really behave differently when someone copies them.
LiveWriter is a real thread that keeps committing while a backup runs, like a server that stays up.
"""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from lessons.lesson_10_persistent_memory.store import MemoryStore
from server.run_store import RunStore

RUNS_FILE, MEMORY_FILE, CONFIG_FILE = "runs.sqlite3", "memory.sqlite3", "local_config.py"
FILES = {"runs": RUNS_FILE, "memory": MEMORY_FILE}
NAMESPACE = "learner_demo"
SCHEMA_V1 = 1
# A made-up string standing in for an API key. It only lives in the decoy config so the scope check has something to find.
CANARY = "sk-demo-canary-7f3a91-not-a-real-key"
EVENT_KINDS = ("run_start", "tool_call", "tool_result")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_id(n: int) -> str:
    return f"run-{n:04d}"


def memory_key(n: int) -> str:
    return f"note_{n:04d}"


def write_unit(runs: RunStore, memory: MemoryStore, n: int, t, locale: str) -> None:
    """One unit of work: a finished run (start, two events, done in one transaction) and one saved memory."""
    rid = run_id(n)
    runs.create_run(run_id=rid, lesson_id="demo", exercise_id="demo", mode="offline", model="local-python",
                    provider_id="local", representation=None, provenance="lesson-demo", schema_version=2,
                    created_at=utc_now(), locale=locale)
    for seq, kind in enumerate(EVENT_KINDS, 1):
        # The note is padded so a few runs fill several database pages, as real request bodies do.
        note = (t.event_note.format(n=n) + " ") * 6
        runs.append(rid, seq, kind, json.dumps({"run_id": rid, "seq": seq, "type": kind, "data": {"note": note}}))
    runs.finish(rid, len(EVENT_KINDS) + 1, "done", json.dumps({"run_id": rid, "seq": len(EVENT_KINDS) + 1,
                                                               "type": "done", "data": {"status": "completed"}}),
                "completed", utc_now())
    topic = t.memory_topics[n % len(t.memory_topics)]
    memory.put(NAMESPACE, memory_key(n), t.memory_value.format(topic=topic, n=n), t.memory_source, None)


def set_version(path: Path, version: int) -> None:
    """Record the schema version in the file header (PRAGMA user_version), where a migration can read it."""
    db = sqlite3.connect(path)
    try:
        db.execute(f"PRAGMA user_version = {int(version)}")
    finally:
        db.close()


def build_data_dir(root: Path, locale: str, t, *, units: int) -> None:
    """Create a version-1 data directory with `units` finished runs and as many memories, all closed cleanly."""
    root.mkdir(parents=True, exist_ok=True)
    runs, memory = RunStore(root / RUNS_FILE), MemoryStore(root / MEMORY_FILE, locale=locale)
    try:
        for n in range(1, units + 1):
            write_unit(runs, memory, n, t, locale)
    finally:
        memory.close()
        runs.close()
    for name in FILES.values():
        set_version(root / name, SCHEMA_V1)
    (root / CONFIG_FILE).write_text(f'API_KEY = "{CANARY}"\n', encoding="utf-8")


def add_units(root: Path, locale: str, t, first: int, count: int) -> None:
    """Reopen the stores like a restarted server and write `count` more units."""
    runs, memory = RunStore(root / RUNS_FILE), MemoryStore(root / MEMORY_FILE, locale=locale)
    try:
        for n in range(first, first + count):
            write_unit(runs, memory, n, t, locale)
    finally:
        memory.close()
        runs.close()


class LiveWriter:
    """A writer thread with two pacing modes: lockstep (step() commits exactly one unit) and free-running (release()).

    It opens its own connections and keeps them open, so the runs file really has a write-ahead log behind it.
    """

    def __init__(self, root: Path, locale: str, t, *, first: int):
        self.root, self.locale, self.t = root, locale, t
        self.next_n = first
        self.committed_runs: list[str] = []
        self.committed_memories: list[str] = []
        self.busy = 0
        self.error: BaseException | None = None
        self._go, self._done = threading.Event(), threading.Event()
        self._stop = threading.Event()
        self._free_left = 0
        self._thread = threading.Thread(target=self._loop, name="backup-upgrade-writer", daemon=True)

    def start(self) -> "LiveWriter":
        self._thread.start()
        return self

    def _loop(self) -> None:
        runs = memory = None
        try:
            runs = RunStore(self.root / RUNS_FILE)
            memory = MemoryStore(self.root / MEMORY_FILE, locale=self.locale)
            while not self._stop.is_set():
                if self._free_left > 0:
                    self._unit(runs, memory)
                    self._free_left -= 1
                    self._stop.wait(0.001)
                elif self._go.wait(0.02):
                    self._go.clear()
                    self._unit(runs, memory)
                    self._done.set()
        except BaseException as error:  # reported to whoever is waiting in step()
            self.error = error
            self._done.set()
        finally:
            if memory:
                memory.close()
            if runs:
                runs.close()

    def _unit(self, runs: RunStore, memory: MemoryStore) -> None:
        n = self.next_n
        self.next_n += 1  # an id is never reused, even when the unit fails halfway
        try:
            write_unit(runs, memory, n, self.t, self.locale)
        except sqlite3.OperationalError:
            # A free-running writer can meet a backup's lock; count it and try the next unit.
            if self._free_left <= 0:
                raise
            self.busy += 1
            return
        self.committed_runs.append(run_id(n))
        self.committed_memories.append(memory_key(n))

    def step(self) -> None:
        """Lockstep: ask for exactly one unit and wait until it has committed."""
        self._done.clear()
        self._go.set()
        if not self._done.wait(15) or self.error:
            raise RuntimeError("the writer thread did not finish a unit") from self.error

    def release(self, units: int) -> None:
        """Free-running: write up to `units` units in the background without waiting for step()."""
        self._free_left = units

    def stop(self) -> None:
        """Stop the thread and close its connections (the last close checkpoints the write-ahead log)."""
        self._stop.set()
        self._thread.join(15)
        if self._thread.is_alive():
            raise RuntimeError("the writer thread did not stop")
        if self.error:
            raise RuntimeError("the writer thread failed") from self.error

    @property
    def committed(self) -> int:
        return len(self.committed_runs)
