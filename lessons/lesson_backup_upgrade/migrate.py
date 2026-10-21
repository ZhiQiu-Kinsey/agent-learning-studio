"""Schema migration v1 -> v2 for both data files, with a fault you can switch on.

memory.sqlite3: updated_at changes from a float to an ISO-8601 string. SQLite cannot change a column's type in
place, so the table is rebuilt. runs.sqlite3: provenance is renamed provenance_kind and event_count is added and
filled; version-1 code cannot read the renamed column. Each step can check where it stands first, so running it
again after a failure is safe.
"""
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from lessons.lesson_backup_upgrade.checks import iso, open_readonly, read_version
from lessons.lesson_backup_upgrade.seed import FILES

SCHEMA_V2 = 2
BATCH = 5
EXPECTED_TABLES = {"memory": {"memories", "versions"}, "runs": {"runs", "events"}}


class InjectedFault(RuntimeError):
    """Raised on purpose by the lesson, never by SQLite: the exercise's way to make an upgrade fail midway."""


@dataclass(frozen=True)
class Fault:
    kind: str = "none"  # none | abort (raise after some rows) | bug (silently skip rows)
    role: str | None = None
    after_rows: int = 3
    message: str = ""

    def check(self, role: str, done: int) -> None:
        if self.kind == "abort" and self.role == role and done >= self.after_rows:
            raise InjectedFault(self.message)

    def skipping(self, role: str) -> bool:
        return self.kind == "bug" and self.role == role


def batches(rows: list, buggy: bool):
    """Copy in batches of BATCH. The injected bug slices from the second row, losing each batch's first row."""
    for start in range(0, len(rows), BATCH):
        batch = rows[start:start + BATCH]
        yield from (batch[1:] if buggy else batch)


def migrate_memory(path: Path, *, transactional: bool, fault: Fault) -> int:
    """Rebuild memories with an ISO-8601 updated_at; returns the rows copied."""
    db = sqlite3.connect(path, isolation_level=None)  # autocommit: transactions are explicit below
    db.row_factory = sqlite3.Row
    copied = 0
    try:
        if transactional:
            db.execute("BEGIN IMMEDIATE")
        # 1. Build the new table next to the old one; drop a leftover from an earlier failed run first.
        db.execute("DROP TABLE IF EXISTS memories_v2")
        db.execute("""CREATE TABLE memories_v2 (
            namespace TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, source TEXT NOT NULL,
            version INTEGER NOT NULL, updated_at TEXT NOT NULL, expires_at REAL,
            scope TEXT NOT NULL DEFAULT 'persistent', task_id TEXT, PRIMARY KEY (namespace, key))""")
        rows = db.execute("SELECT * FROM memories ORDER BY namespace, key").fetchall()
        for row in batches(rows, fault.skipping("memory")):
            fault.check("memory", copied)
            values = dict(row, updated_at=iso(row["updated_at"]))
            db.execute("INSERT INTO memories_v2 VALUES (:namespace, :key, :value, :source, :version,"
                       " :updated_at, :expires_at, :scope, :task_id)", values)
            copied += 1
        # 2. Swap the tables and stamp the new version; with a transaction all of this commits together or not at all.
        db.execute("DROP TABLE memories")
        db.execute("ALTER TABLE memories_v2 RENAME TO memories")
        db.execute(f"PRAGMA user_version = {SCHEMA_V2}")
        if transactional:
            db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()
    return copied


def migrate_runs(path: Path, *, transactional: bool, fault: Fault) -> int:
    """Rename provenance, add event_count and fill it; returns the runs filled."""
    db = sqlite3.connect(path, isolation_level=None)
    filled = 0
    try:
        if transactional:
            db.execute("BEGIN IMMEDIATE")
        columns = {row[1] for row in db.execute("PRAGMA table_info(runs)")}
        # 1. Each schema change first checks whether an earlier attempt already made it.
        if "provenance" in columns:
            db.execute("ALTER TABLE runs RENAME COLUMN provenance TO provenance_kind")
        if "event_count" not in columns:
            db.execute("ALTER TABLE runs ADD COLUMN event_count INTEGER")
        # 2. Backfill one run at a time: the long part, where a failure leaves half the rows done without a transaction.
        for (run,) in db.execute("SELECT run_id FROM runs ORDER BY run_id").fetchall():
            fault.check("runs", filled)
            count = db.execute("SELECT COUNT(*) FROM events WHERE run_id = ?", (run,)).fetchone()[0]
            db.execute("UPDATE runs SET event_count = ? WHERE run_id = ?", (count, run))
            filled += 1
        db.execute(f"PRAGMA user_version = {SCHEMA_V2}")
        if transactional:
            db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()
    return filled


STEPS = (("memory", migrate_memory), ("runs", migrate_runs))


def leftover_tables(path: Path, role: str) -> list[str]:
    """Tables a failed, non-transactional migration left behind next to the real ones."""
    db = open_readonly(path)
    try:
        names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    finally:
        db.close()
    return sorted(names - EXPECTED_TABLES[role])


def upgrade_files(data_dir: Path, fault: Fault, *, transactional: bool, on_step: Callable[[dict], None]) -> Exception | None:
    """Migrate the files one after another, memory first; stop at the first failure and return it."""
    for role, step in STEPS:
        try:
            rows = step(data_dir / FILES[role], transactional=transactional, fault=fault)
        except Exception as error:  # the caller decides how to recover; here it is only reported
            on_step({"role": role, "file": FILES[role], "transactional": transactional,
                     "status": "rolled_back" if transactional else "left_partial",
                     "injected": isinstance(error, InjectedFault), "error": str(error),
                     "version_in_file": read_version(data_dir / FILES[role]),
                     "leftover_tables": leftover_tables(data_dir / FILES[role], role)})
            return error
        on_step({"role": role, "file": FILES[role], "transactional": transactional,
                 "status": "committed" if transactional else "applied", "rows": rows})
    return None
