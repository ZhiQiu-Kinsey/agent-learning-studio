"""The SQLite memory store shared by the two memory lessons.

persistent-memory reads the tables, get and recall: memory is external data the program saves; it reads back after reopening.
memory-lifecycle reads put's version check, plus expiry, scope and deletion.
"""
import re
import sqlite3
import time
from pathlib import Path

from lessons.lesson_10_persistent_memory.locales.shared import texts_for

# namespace, key and task_id accept only short ASCII identifiers; they always go in as SQL parameters.
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}\Z")
SCOPES = ("persistent", "current_task")


class VersionConflict(ValueError):
    """The writer's version differs from the store's current one: a stale write; the current value stays."""


class MemoryStore:
    def __init__(self, path: Path, *, locale: str, read_only: bool = False):
        # Error messages and recall reasons reach events, so they come in the run's language.
        self.t = texts_for(locale)
        if read_only:
            # mode=ro: this connection cannot write at the database level; a missing file is an error, not a new file.
            # as_uri escapes # and % in the path; otherwise the path is cut at # and opens another file.
            self.connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        else:
            self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        if not read_only:
            # One row is one memory: value, source and version stored together; one row per key in a namespace.
            self.connection.execute("""CREATE TABLE IF NOT EXISTS memories (
                namespace TEXT NOT NULL, key TEXT NOT NULL,
                value TEXT NOT NULL, source TEXT NOT NULL,
                version INTEGER NOT NULL, updated_at REAL NOT NULL,
                expires_at REAL, scope TEXT NOT NULL DEFAULT 'persistent', task_id TEXT,
                PRIMARY KEY (namespace, key))""")
            # A second table keeps each key's latest version: deleting a memory keeps it, so a rewrite counts on.
            self.connection.execute("""CREATE TABLE IF NOT EXISTS versions (
                namespace TEXT NOT NULL, key TEXT NOT NULL, version INTEGER NOT NULL,
                PRIMARY KEY (namespace, key))""")
            # Back-fill versions for memories in older stores: a stale write is still caught after delete-and-recreate.
            self.connection.execute("INSERT OR IGNORE INTO versions SELECT namespace, key, version FROM memories")
            self.connection.commit()

    def close(self):
        self.connection.close()

    def check_id(self, value: str) -> str:
        if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
            raise ValueError(self.t.bad_identifier)
        return value

    def get(self, namespace: str, key: str, now: float | None = None) -> dict | None:
        """Read one row by namespace + key; None when the row is missing or expired."""
        row = self.connection.execute("SELECT * FROM memories WHERE namespace=? AND key=?",
                                      (self.check_id(namespace), self.check_id(key))).fetchone()
        return None if row is None or self.expired(dict(row), now) else dict(row)

    def recall(self, namespace: str, task_id: str | None = None,
               now: float | None = None) -> tuple[list[dict], list[dict]]:
        """Recall the memories of a namespace that belong in this request; returns (included, excluded)."""
        included, excluded = [], []
        rows = self.connection.execute("SELECT * FROM memories WHERE namespace=? ORDER BY key",
                                       (self.check_id(namespace),))
        for item in map(dict, rows):
            reason = self.skip_reason(item, task_id, now)
            if reason:
                excluded.append({**item, "reason": reason})
            else:
                included.append(item)
        return included, excluded

    def put(self, namespace: str, key: str, value: str, source: str, expected_version: int | None, *,
            expires_at: float | None = None, scope: str = "persistent", task_id: str | None = None) -> dict:
        """Write one memory. expected_version is the version the writer last read; None for a new key."""
        namespace, key = self.check_id(namespace), self.check_id(key)
        if scope not in SCOPES or (scope == "current_task") != (task_id is not None):
            raise ValueError(self.t.bad_scope)
        if task_id is not None:
            self.check_id(task_id)
        # 1. Take the write lock before reading the version: no other connection can write in between.
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute("SELECT * FROM memories WHERE namespace=? AND key=?",
                                          (namespace, key)).fetchone()
            current = row["version"] if row else None
            # 2. A version mismatch is a stale write: reject it, keep the value. An expired row may be rewritten as new (None).
            revive = row is not None and expected_version is None and self.expired(dict(row))
            if current != expected_version and not revive:
                raise VersionConflict(self.t.version_conflict.format(expected=expected_version, current=current))
            # 3. Versions only go up, from the highest version this key ever had. Rewriting an expired row or
            #    recreating a deleted key never restarts at 1, so a writer holding a pre-delete version still fails.
            last = self.connection.execute("SELECT version FROM versions WHERE namespace=? AND key=?",
                                           (namespace, key)).fetchone()
            version = max(current or 0, last["version"] if last else 0) + 1
            record = {"namespace": namespace, "key": key, "value": value, "source": source,
                      "version": version, "updated_at": time.time(),
                      "expires_at": expires_at, "scope": scope, "task_id": task_id}
            self.connection.execute(
                "INSERT OR REPLACE INTO memories (namespace, key, value, source, version, updated_at,"
                " expires_at, scope, task_id) VALUES (:namespace, :key, :value, :source, :version,"
                " :updated_at, :expires_at, :scope, :task_id)", record)
            self.connection.execute("INSERT OR REPLACE INTO versions (namespace, key, version)"
                                    " VALUES (:namespace, :key, :version)", record)
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise
        return record

    @staticmethod
    def expired(row: dict, now: float | None = None) -> bool:
        # Expiry is a read rule: an expired row is still in the table; get and recall treat it as absent.
        return row["expires_at"] is not None and row["expires_at"] <= (time.time() if now is None else now)

    def skip_reason(self, item: dict, task_id: str | None, now: float | None = None) -> str | None:
        """Why recall skips this record; None means it goes into this request."""
        if self.expired(item, now):
            return self.t.reason_expired
        # Scope is a read rule too: another task's current_task rows stay in the table, they are just not recalled.
        if item["scope"] == "current_task" and item["task_id"] != task_id:
            return self.t.reason_other_task
        return None

    def stored(self, namespace: str, key: str) -> bool:
        """Whether the row is in the table, expired or not: tells "not readable" from "deleted"."""
        return self.connection.execute("SELECT 1 FROM memories WHERE namespace=? AND key=?",
                                       (self.check_id(namespace), self.check_id(key))).fetchone() is not None

    def delete(self, namespace: str, key: str) -> bool:
        # Deletion is a storage operation: the row leaves the table and no connection reads it back. versions keeps its count.
        with self.connection:
            cursor = self.connection.execute("DELETE FROM memories WHERE namespace=? AND key=?",
                                             (self.check_id(namespace), self.check_id(key)))
        return cursor.rowcount == 1

    def end_task(self, namespace: str, task_id: str) -> int:
        # Ending a task deletes only its own current_task rows; persistent rows and other tasks stay.
        with self.connection:
            cursor = self.connection.execute(
                "DELETE FROM memories WHERE namespace=? AND scope='current_task' AND task_id=?",
                (self.check_id(namespace), self.check_id(task_id)))
        return cursor.rowcount

    def count(self, namespace: str) -> int:
        """Rows of this namespace in the table, expired ones included."""
        return self.connection.execute("SELECT COUNT(*) FROM memories WHERE namespace=?",
                                       (self.check_id(namespace),)).fetchone()[0]
