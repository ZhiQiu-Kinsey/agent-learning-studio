"""标准库 SQLite 的有来源、版本和到期时间的教学记忆。"""
from typing import Literal
import re
import sqlite3
import tempfile
import time
from pathlib import Path

from pydantic import Field

from course.execution import LessonInputs, RunContext


DB_PATH = Path(__file__).resolve().parents[2] / ".runtime" / "lesson10-memory.sqlite3"
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}\Z")


class Inputs(LessonInputs):
    namespace: str = Field(default="learner_demo", min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
    key: str = Field(default="learning_goal", min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
    value: str = Field(default="理解 Agent 的消息与状态", min_length=1, max_length=200)
    source: str = Field(default="本次学习者显式输入", min_length=1, max_length=120)
    scenario: Literal["reopen", "conflict", "expiry_delete", "recall_only"] = "reopen"


INPUT_MODEL = Inputs


def _id(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError("namespace/key 只能使用 1–32 位英文字母开头的字母、数字、下划线或连字符。")
    return value


class MemoryStore:
    def __init__(self, path: Path, *, read_only: bool = False):
        self.connection = (sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
                           if read_only else sqlite3.connect(path))
        self.connection.row_factory = sqlite3.Row
        if not read_only:
            self.connection.execute("""CREATE TABLE IF NOT EXISTS memories (
                namespace TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                source TEXT NOT NULL, version INTEGER NOT NULL, expires_at REAL,
                updated_at REAL NOT NULL, PRIMARY KEY(namespace, key))""")
            self.connection.commit()

    def close(self):
        self.connection.close()

    def get(self, namespace: str, key: str, now: float | None = None) -> dict | None:
        row = self.connection.execute("SELECT * FROM memories WHERE namespace=? AND key=?",
                                      (_id(namespace), _id(key))).fetchone()
        if row is None:
            return None
        item = dict(row)
        if item["expires_at"] is not None and item["expires_at"] <= (time.time() if now is None else now):
            return None
        return item

    def put(self, namespace: str, key: str, value: str, source: str,
            expected_version: int | None, expires_at: float | None = None) -> dict:
        namespace, key = _id(namespace), _id(key)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute("SELECT version,expires_at FROM memories WHERE namespace=? AND key=?",
                                          (namespace, key)).fetchone()
            current = row["version"] if row else None
            expired = row is not None and row["expires_at"] is not None and row["expires_at"] <= time.time()
            # 已过期行允许以 expected_version=None 重写，但版本继续递增，不抹掉时间线。
            if current != expected_version and not (expired and expected_version is None):
                raise ValueError(f"版本冲突：期望 {expected_version}，当前 {current}。")
            if row:
                self.connection.execute("""UPDATE memories SET value=?,source=?,version=?,expires_at=?,updated_at=?
                    WHERE namespace=? AND key=?""", (value, source, current + 1, expires_at, time.time(), namespace, key))
            else:
                self.connection.execute("""INSERT INTO memories
                    (namespace,key,value,source,version,expires_at,updated_at) VALUES (?,?,?,?,?,?,?)""",
                    (namespace, key, value, source, 1, expires_at, time.time()))
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise
        return self.get(namespace, key) or {"namespace": namespace, "key": key, "value": value,
                                            "source": source, "version": (current or 0) + 1,
                                            "expires_at": expires_at}

    def delete(self, namespace: str, key: str) -> bool:
        with self.connection:
            cursor = self.connection.execute("DELETE FROM memories WHERE namespace=? AND key=?",
                                             (_id(namespace), _id(key)))
        return cursor.rowcount == 1


def _execute(context: RunContext, path: Path, values: Inputs) -> str:
    context.check_cancelled()
    if values.scenario == "recall_only":
        store = MemoryStore(path, read_only=True) if path.exists() else MemoryStore(Path(":memory:"))
    else:
        store = MemoryStore(path)
    other_scope = "other_learner" if values.namespace != "other_learner" else "another_learner"
    try:
        before = store.get(values.namespace, values.key)
        other_before = store.get(other_scope, values.key)
        if values.scenario == "recall_only":
            context.emit("lesson.memory", {"action": "recall_only", "record": before,
                                            "storage": "temporary" if context.mode == "offline" else "local-persistent"})
            context.emit("lesson.report", {
                "title": "只读恢复", "summary": "读取阶段未写入；live 读取固定教学库，offline 事先在临时库预置受控旧记录。",
                "checks": [{"label": "读取阶段未写入", "passed": True, "detail": "进入读取阶段后只运行 get；offline 预置发生在此前。"},
                           {"label": "恢复结果有来源", "passed": before is None or bool(before["source"]),
                            "detail": "若无记录则明确显示无；有记录时展示保存的来源。"}],
                "metrics": [{"label": "检索结果", "value": "找到" if before else "无"},
                            {"label": "版本", "value": before["version"] if before else "无"},
                            {"label": "学习者备注", "value": context.question or "无"}],
                "table": {"columns": ["范围", "键", "值", "来源", "版本"],
                          "rows": [[values.namespace, values.key, before["value"] if before else "无",
                                    before["source"] if before else "无", before["version"] if before else 0]]},
            })
            return "只读恢复：" + (f"{before['value']}（来源：{before['source']}，版本 {before['version']}）" if before else "该范围与键没有可检索记忆。")
        context.check_cancelled()
        saved = store.put(values.namespace, values.key, values.value, values.source,
                          before["version"] if before else None)
        context.emit("lesson.memory", {"action": "saved", "record": saved, "storage": "temporary" if context.mode == "offline" else "local-persistent"})
        context.check_cancelled()
    finally:
        store.close()
    # 真正关闭并重开 SQLite 连接，不依赖进程内字典。
    reopened = MemoryStore(path)
    try:
        restored = reopened.get(values.namespace, values.key)
        isolated = reopened.get(other_scope, values.key) == other_before
        conflict_rejected = None
        expired_hidden = None
        deleted_and_gone = None
        if values.scenario == "conflict":
            context.check_cancelled()
            try:
                reopened.put(values.namespace, values.key, "过时更新", "过时来源", saved["version"] - 1)
            except ValueError:
                conflict_rejected = True
            else:
                conflict_rejected = False
            if not conflict_rejected:
                raise RuntimeError("过时版本竟然覆盖了记忆。")
            context.check_cancelled()
            updated = reopened.put(values.namespace, values.key, values.value + "（已核对）",
                                   values.source, saved["version"])
            context.emit("lesson.memory", {"action": "conflict_and_update", "stale_rejected": conflict_rejected,
                                            "record": updated})
        elif values.scenario == "expiry_delete":
            context.check_cancelled()
            expired = reopened.put(values.namespace, values.key, values.value,
                                   values.source, saved["version"], expires_at=time.time() - 1)
            expired_hidden = reopened.get(values.namespace, values.key) is None
            context.emit("lesson.memory", {"action": "expired", "version": expired["version"], "hidden": expired_hidden})
            context.check_cancelled()
            deleted = reopened.delete(values.namespace, values.key)
            deleted_and_gone = deleted and reopened.get(values.namespace, values.key) is None
            context.emit("lesson.memory", {"action": "deleted", "deleted": deleted, "absent": deleted_and_gone})
        context.check_cancelled()
    finally:
        reopened.close()
    final = MemoryStore(path)
    try:
        final_record = final.get(values.namespace, values.key)
    finally:
        final.close()
    checks = [
        {"label": "重开连接后恢复", "passed": restored is not None and restored["value"] == values.value,
         "detail": "关闭第一条连接后，使用新连接按 namespace/key 查询。"},
        {"label": "另一个范围未被本次写入改变", "passed": isolated, "detail": "比较另一 namespace 同键的写入前后结果；namespace 是教学分区，不是用户认证。"},
    ]
    if conflict_rejected is not None:
        checks.append({"label": "过时版本被拒绝", "passed": conflict_rejected, "detail": "乐观版本比较在写入前执行。"})
    if expired_hidden is not None:
        checks.extend([
            {"label": "过期记录不可检索", "passed": expired_hidden, "detail": "读取时检查 expires_at。"},
            {"label": "删除后重开仍为空", "passed": deleted_and_gone and final_record is None, "detail": "删除后再次打开 SQLite 连接核对。"},
        ])
    context.emit("lesson.report", {
        "title": "SQLite 记忆生命周期", "summary": "offline 使用一次性临时库；live 写入固定本地教学库。没有模型调用或参数训练。",
        "checks": checks,
        "metrics": [{"label": "初次写入版本", "value": saved["version"]},
                    {"label": "最终可检索", "value": "是" if final_record else "否"},
                    {"label": "存储方式", "value": "临时 SQLite" if context.mode == "offline" else "固定本地 SQLite"},
                    {"label": "学习者备注", "value": context.question or "无"}],
        "table": {"columns": ["阶段", "值", "来源", "版本"],
                  "rows": [["重开恢复", restored["value"] if restored else "无", restored["source"] if restored else "无", restored["version"] if restored else 0],
                           ["最终", final_record["value"] if final_record else "无", final_record["source"] if final_record else "无", final_record["version"] if final_record else 0]]},
    })
    return "已写入 SQLite 并重开连接核对；详情见记忆事件和报告。"


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    if context.mode == "offline":
        with tempfile.TemporaryDirectory(prefix="lesson10-") as directory:
            path = Path(directory) / "memory.sqlite3"
            if values.scenario == "recall_only":
                context.check_cancelled()
                seed = MemoryStore(path)
                try:
                    seed.put(values.namespace, values.key, values.value, values.source, None)
                finally:
                    seed.close()
            return _execute(context, path, values)
    if values.scenario != "recall_only":
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _execute(context, DB_PATH, values)
