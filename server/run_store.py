"""服务端运行存储：append-only SQLite，每个事件写入后立即提交。

只接收已经脱敏、序列化完成的事件文本；本模块不做脱敏，也不修改已写入的事件。
唯一的删除路径是 `clear()`（界面“一键清除”），它删除全部记录并截断 WAL。
运行状态可以在 running 与 paused（等待审批）之间切换；检查点就是 `checkpoint` 事件，
恢复时按 (run_id, checkpoint_id) 从事件表读取，服务重启后仍然可用。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    lesson_id TEXT NOT NULL,
    exercise_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    model TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    representation TEXT,
    provenance TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    locale TEXT NOT NULL DEFAULT 'zh-CN'
);
CREATE TABLE IF NOT EXISTS events (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    seq INTEGER NOT NULL CHECK (seq >= 1),
    type TEXT NOT NULL,
    event TEXT NOT NULL,
    PRIMARY KEY (run_id, seq)
);
CREATE TRIGGER IF NOT EXISTS events_append_only_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
"""

RUN_FIELDS = ("run_id", "lesson_id", "exercise_id", "mode", "model", "provider_id", "representation",
              "provenance", "schema_version", "status", "created_at", "finished_at", "locale",
              "thread_id", "resumed_from_run", "resumed_from_checkpoint")
FINAL_STATUSES = ("completed", "error", "cancelled", "interrupted")
# 运行中的两种状态：paused 表示停在审批点等人决定，决定后回到 running。
LIVE_STATUSES = ("running", "paused")
# 加入恢复之前建的库没有这几列：打开时补上，旧运行的 thread_id 为空（读取时按自己的 run_id 理解）。
_ADDED_COLUMNS = {"thread_id": "TEXT", "resumed_from_run": "TEXT", "resumed_from_checkpoint": "TEXT"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    """单连接 + 互斥锁；本地单用户场景下读写都很短，不需要连接池。"""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA foreign_keys=ON")
        # 清除记录时覆盖已释放的页面，避免脱敏后的历史内容残留在文件空闲页中。
        self._db.execute("PRAGMA secure_delete=ON")
        self._db.executescript(_SCHEMA)
        # 加入运行语言之前建的库没有 locale 列：补上，旧运行都是中文运行，按默认值记为 zh-CN。
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(runs)")}
        if "locale" not in columns:
            self._db.execute("ALTER TABLE runs ADD COLUMN locale TEXT NOT NULL DEFAULT 'zh-CN'")
        for name, kind in _ADDED_COLUMNS.items():
            if name not in columns:
                self._db.execute(f"ALTER TABLE runs ADD COLUMN {name} {kind}")
        # 新进程启动时不可能还有运行在执行；上次异常退出遗留的 running/paused 如实标记为中断。
        with self._lock:
            self._db.execute("UPDATE runs SET status = 'interrupted', finished_at = ? "
                             "WHERE status IN ('running', 'paused')", (utc_now(),))

    def close(self):
        with self._lock:
            self._db.close()

    def create_run(self, *, run_id: str, lesson_id: str, exercise_id: str, mode: str, model: str,
                   provider_id: str, representation: str | None, provenance: str,
                   schema_version: int, created_at: str, locale: str = "zh-CN", thread_id: str | None = None,
                   resumed_from_run: str | None = None, resumed_from_checkpoint: str | None = None):
        with self._lock:
            self._db.execute(
                "INSERT INTO runs (run_id, lesson_id, exercise_id, mode, model, provider_id, representation,"
                " provenance, schema_version, status, created_at, locale, thread_id, resumed_from_run,"
                " resumed_from_checkpoint)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?)",
                (run_id, lesson_id, exercise_id, mode, model, provider_id, representation, provenance,
                 schema_version, created_at, locale, thread_id or run_id, resumed_from_run,
                 resumed_from_checkpoint))

    def set_live_status(self, run_id: str, status: str):
        """running ↔ paused；已经结束的运行不受影响（结束状态只由 finish 写入）。"""
        if status not in LIVE_STATUSES:
            raise ValueError("只能在 running 与 paused 之间切换。")
        with self._lock:
            self._db.execute("UPDATE runs SET status = ? WHERE run_id = ? AND status IN ('running', 'paused')",
                             (status, run_id))

    def checkpoint(self, run_id: str, checkpoint_id: str) -> dict | None:
        """读取某次运行的一个检查点：返回 checkpoint 事件（信封 + data），没有时返回 None。"""
        with self._lock:
            rows = list(self._db.execute(
                "SELECT event FROM events WHERE run_id = ? AND type = 'checkpoint' ORDER BY seq", (run_id,)))
        for (text,) in rows:
            event = json.loads(text)
            if event.get("data", {}).get("checkpoint_id") == checkpoint_id:
                return event
        return None

    def last_checkpoint_number(self, run_id: str) -> int:
        """某次运行已存检查点的最大编号（cp-N 的 N）；没有检查点时为 0。恢复出来的运行从它之后接着编号。"""
        with self._lock:
            rows = list(self._db.execute(
                "SELECT event FROM events WHERE run_id = ? AND type = 'checkpoint'", (run_id,)))
        numbers = [int(str(json.loads(text).get("data", {}).get("checkpoint_id", "cp-0")).removeprefix("cp-") or 0)
                   for (text,) in rows]
        return max(numbers, default=0)

    def first_event(self, run_id: str, kind: str) -> dict | None:
        """按 seq 找某次运行第一条指定类型的事件（恢复时读取 run_start）。"""
        with self._lock:
            row = self._db.execute("SELECT event FROM events WHERE run_id = ? AND type = ? ORDER BY seq LIMIT 1",
                                   (run_id, kind)).fetchone()
        return json.loads(row[0]) if row else None

    def append(self, run_id: str, seq: int, kind: str, event_json: str):
        """追加一条事件；(run_id, seq) 重复时由主键拒绝。自动提交。"""
        with self._lock:
            self._db.execute("INSERT INTO events (run_id, seq, type, event) VALUES (?, ?, ?, ?)",
                             (run_id, seq, kind, event_json))

    def finish(self, run_id: str, seq: int, kind: str, event_json: str, status: str, finished_at: str):
        """写入结束事件并更新运行状态，两者在同一事务中提交。"""
        if status not in FINAL_STATUSES:
            raise ValueError("未知的运行结束状态。")
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._db.execute("INSERT INTO events (run_id, seq, type, event) VALUES (?, ?, ?, ?)",
                                 (run_id, seq, kind, event_json))
                self._db.execute("UPDATE runs SET status = ?, finished_at = ? WHERE run_id = ?",
                                 (status, finished_at, run_id))
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    def events(self, run_id: str, from_seq: int = 1, through_seq: int | None = None) -> list[tuple[int, str, str]]:
        """按 seq 升序返回 (seq, type, event_json)；through_seq 限制只读到已公开的事件。"""
        query = "SELECT seq, type, event FROM events WHERE run_id = ? AND seq >= ?"
        params: list = [run_id, from_seq]
        if through_seq is not None:
            query += " AND seq <= ?"
            params.append(through_seq)
        with self._lock:
            return list(self._db.execute(query + " ORDER BY seq", params))

    def get_run(self, run_id: str) -> dict | None:
        rows = self._runs("WHERE r.run_id = ? GROUP BY r.run_id", (run_id,))
        return rows[0] if rows else None

    def list_runs(self, limit: int = 50) -> list[dict]:
        return self._runs("GROUP BY r.run_id ORDER BY r.created_at DESC, r.rowid DESC LIMIT ?", (limit,))

    def _runs(self, tail: str, params: tuple) -> list[dict]:
        columns = ", ".join("r." + name for name in RUN_FIELDS)
        query = (f"SELECT {columns}, COUNT(e.seq), MAX(e.seq) FROM runs r "
                 "LEFT JOIN events e ON e.run_id = r.run_id " + tail)
        with self._lock:
            rows = list(self._db.execute(query, params))
        return [{**dict(zip(RUN_FIELDS, row[:len(RUN_FIELDS)])), "event_count": row[-2],
                 "last_seq": row[-1] or 0} for row in rows]

    def clear(self) -> int:
        """一键清除的唯一删除路径：删除全部运行记录，并截断 WAL，避免已删除内容留在日志文件中。"""
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._db.execute("DELETE FROM events")
                deleted = self._db.execute("DELETE FROM runs").rowcount
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            self._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            return deleted
