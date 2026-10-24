"""Learning progress: persistent memory with an operation id that makes one approved write happen once.

The store is the persistent-memory lesson's MemoryStore, unchanged: one row per lesson in
the learner's namespace, versioned. This file adds the one thing a retry needs. An
operation id names the approved write; applying it twice must leave the store as it was
after the first time. Two facts are checked, not just one flag: the operations table (this
operation is done) and the stored row (the state already equals what the operation would
write), because a crash can fall between the row and the table entry.
"""
import hashlib
import json
import time
from pathlib import Path

from lessons.lesson_10_persistent_memory.store import MemoryStore


def operation_id(learner: str, lesson: str, status: str, note: str) -> str:
    """The same approved write always gets the same id, so a replay after a crash can be recognised."""
    canonical = json.dumps([learner, lesson, status, note], ensure_ascii=False, separators=(",", ":"))
    return "op-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def encode(status: str, note: str) -> str:
    return json.dumps({"status": status, "note": note}, ensure_ascii=False, sort_keys=True)


class ProgressStore:
    def __init__(self, path: Path, locale: str, *, read_only: bool = False):
        self.memory = MemoryStore(path, locale=locale, read_only=read_only)
        if not read_only:
            self.memory.connection.execute(
                "CREATE TABLE IF NOT EXISTS progress_ops (op_id TEXT PRIMARY KEY, namespace TEXT NOT NULL,"
                " key TEXT NOT NULL, version INTEGER NOT NULL, applied_at REAL NOT NULL)")
            self.memory.connection.commit()

    def close(self):
        self.memory.close()

    def records(self, learner: str) -> list[dict]:
        """What this learner's namespace holds, as the read tool reports it: lesson, status, note, version, source."""
        found, _ = self.memory.recall(learner)
        return [{"lesson": row["key"], **json.loads(row["value"]), "version": row["version"], "source": row["source"]}
                for row in found]

    def operations(self) -> int:
        return self.memory.connection.execute("SELECT COUNT(*) FROM progress_ops").fetchone()[0]

    def digest(self) -> str:
        """A hash over every row and every operation: equal before and after means nothing was written."""
        connection = self.memory.connection
        rows = connection.execute("SELECT namespace, key, value, version FROM memories ORDER BY namespace, key").fetchall()
        ops = connection.execute("SELECT op_id FROM progress_ops ORDER BY op_id").fetchall()
        text = json.dumps([[list(row) for row in rows], [row[0] for row in ops]], ensure_ascii=False)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def apply(self, op_id: str, learner: str, lesson: str, status: str, note: str) -> dict:
        """Write one approved operation once. Returns what happened: new, replayed or state_matches."""
        connection = self.memory.connection
        done = connection.execute("SELECT version FROM progress_ops WHERE op_id=?", (op_id,)).fetchone()
        current = self.memory.get(learner, lesson)
        # 1. Already applied: the operations table says so. The stored row is read back, not rebuilt.
        if done is not None:
            return {"applied": False, "reason": "replayed", "operation_id": op_id, "lesson": lesson,
                    "version": current["version"] if current else None}
        wanted = encode(status, note)
        if current is not None and current["value"] == wanted:
            # 2. Crash window: the row was written, the table entry was not. Record the operation, write nothing.
            record, applied, reason = current, False, "state_matches"
        else:
            # 3. A new write, guarded by the version just read (None for a new lesson).
            record = self.memory.put(learner, lesson, wanted, f"approved:{op_id}",
                                     current["version"] if current else None)
            applied, reason = True, "new"
        with connection:
            connection.execute("INSERT OR IGNORE INTO progress_ops (op_id, namespace, key, version, applied_at)"
                               " VALUES (?, ?, ?, ?, ?)", (op_id, learner, lesson, record["version"], time.time()))
        return {"applied": applied, "reason": reason, "operation_id": op_id, "lesson": lesson,
                "version": record["version"]}


def connect_read_only(path: Path, locale: str) -> ProgressStore:
    """Open for reading; with no file yet, an empty in-memory store, so reading never creates a file."""
    if path.exists():
        return ProgressStore(path, locale, read_only=True)
    return ProgressStore(Path(":memory:"), locale)
