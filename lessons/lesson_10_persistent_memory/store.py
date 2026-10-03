"""两门记忆课共用的 SQLite 记忆存储。

“持久记忆”一课读建表、get 与 recall：记忆是程序存下的外部数据，关闭连接再打开仍能读回。
“记忆的更新、过期与召回范围”一课读 put 的版本检查，以及过期、范围与删除。
"""
import re
import sqlite3
import time
from pathlib import Path

# namespace、key、task_id 只接受短的英文标识符；它们总是作为 SQL 参数传入，不拼进语句。
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}\Z")
SCOPES = ("persistent", "current_task")


class VersionConflict(ValueError):
    """写入方声明的版本和库里的当前版本不一致：这是一次过时写入，现值保持不变。"""


def check_id(value: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("namespace、key、task_id 只能用 1–32 位、英文字母开头的字母、数字、下划线或连字符。")
    return value


class MemoryStore:
    def __init__(self, path: Path, *, read_only: bool = False):
        if read_only:
            # mode=ro：这条连接在数据库层面就写不进去；文件不存在时直接报错，不会新建。
            # as_uri 会转义路径里的 # 和 %，否则路径会在 # 处被截断，连到另一个文件上。
            self.connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        else:
            self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        if not read_only:
            # 一行就是一条记忆：值、来源、版本一起存下；同一命名空间里一个 key 只有一行。
            self.connection.execute("""CREATE TABLE IF NOT EXISTS memories (
                namespace TEXT NOT NULL, key TEXT NOT NULL,
                value TEXT NOT NULL, source TEXT NOT NULL,
                version INTEGER NOT NULL, updated_at REAL NOT NULL,
                expires_at REAL, scope TEXT NOT NULL DEFAULT 'persistent', task_id TEXT,
                PRIMARY KEY (namespace, key))""")
            # 每个键写到了第几版另记一张表：删除记忆时不删它，同一个键重新写入时版本接着往上加。
            self.connection.execute("""CREATE TABLE IF NOT EXISTS versions (
                namespace TEXT NOT NULL, key TEXT NOT NULL, version INTEGER NOT NULL,
                PRIMARY KEY (namespace, key))""")
            # 旧库里已有的记忆补记一份版本：先删除再重建同一个键时，过时写入照样被拦下。
            self.connection.execute("INSERT OR IGNORE INTO versions SELECT namespace, key, version FROM memories")
            self.connection.commit()

    def close(self):
        self.connection.close()

    def get(self, namespace: str, key: str, now: float | None = None) -> dict | None:
        """按 namespace + key 读一条；没有这一行或它已经过期，都返回 None。"""
        row = self.connection.execute("SELECT * FROM memories WHERE namespace=? AND key=?",
                                      (check_id(namespace), check_id(key))).fetchone()
        return None if row is None or self.expired(dict(row), now) else dict(row)

    def recall(self, namespace: str, task_id: str | None = None,
               now: float | None = None) -> tuple[list[dict], list[dict]]:
        """召回一个命名空间里这次该带上的记忆，返回（召回的，过滤掉的）。"""
        included, excluded = [], []
        rows = self.connection.execute("SELECT * FROM memories WHERE namespace=? ORDER BY key",
                                       (check_id(namespace),))
        for item in map(dict, rows):
            reason = self.skip_reason(item, task_id, now)
            if reason:
                excluded.append({**item, "reason": reason})
            else:
                included.append(item)
        return included, excluded

    def put(self, namespace: str, key: str, value: str, source: str, expected_version: int | None, *,
            expires_at: float | None = None, scope: str = "persistent", task_id: str | None = None) -> dict:
        """写入一条记忆。expected_version 是写入方上次读到的版本；写新键时传 None。"""
        namespace, key = check_id(namespace), check_id(key)
        if scope not in SCOPES or (scope == "current_task") != (task_id is not None):
            raise ValueError("current_task 记忆必须带 task_id，persistent 记忆不能带 task_id。")
        if task_id is not None:
            check_id(task_id)
        # 1. 先拿写锁再读版本：读到版本和写入之间，别的连接插不进来。
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute("SELECT * FROM memories WHERE namespace=? AND key=?",
                                          (namespace, key)).fetchone()
            current = row["version"] if row else None
            # 2. 版本对不上就是过时写入：拒绝，不覆盖现值。已过期的行允许当作新键（None）重写。
            revive = row is not None and expected_version is None and self.expired(dict(row))
            if current != expected_version and not revive:
                raise VersionConflict(f"版本冲突：写入方读到的是 {expected_version}，库里现在是 {current}。")
            # 3. 版本只增不减：接着这个键写到过的最大版本往上加。重写过期行、删除后重建都不会回到 1，
            #    手里还拿着删除前旧版本的写入方，也就对不上了。
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
        # 过期是读取规则：到期的行还在表里，只是 get 和 recall 把它当作不存在。
        return row["expires_at"] is not None and row["expires_at"] <= (time.time() if now is None else now)

    def skip_reason(self, item: dict, task_id: str | None, now: float | None = None) -> str | None:
        """召回时跳过这条记录的原因；返回 None 表示这次该带上。"""
        if self.expired(item, now):
            return "已过期"
        # 范围也是读取规则：别的任务的 current_task 还在表里，只是这次不带上。
        if item["scope"] == "current_task" and item["task_id"] != task_id:
            return "属于其他任务"
        return None

    def stored(self, namespace: str, key: str) -> bool:
        """不管过没过期，只看表里还有没有这一行：用来区分“读不到”和“已删除”。"""
        return self.connection.execute("SELECT 1 FROM memories WHERE namespace=? AND key=?",
                                       (check_id(namespace), check_id(key))).fetchone() is not None

    def delete(self, namespace: str, key: str) -> bool:
        # 删除是存储操作：这一行从表里移除，之后换哪条连接都读不回来。versions 里的版本计数留着。
        with self.connection:
            cursor = self.connection.execute("DELETE FROM memories WHERE namespace=? AND key=?",
                                             (check_id(namespace), check_id(key)))
        return cursor.rowcount == 1

    def end_task(self, namespace: str, task_id: str) -> int:
        # 任务结束时只删它自己的 current_task 记录；persistent 和别的任务都不动。
        with self.connection:
            cursor = self.connection.execute(
                "DELETE FROM memories WHERE namespace=? AND scope='current_task' AND task_id=?",
                (check_id(namespace), check_id(task_id)))
        return cursor.rowcount

    def count(self, namespace: str) -> int:
        """表里这个命名空间的行数，过期的也算。"""
        return self.connection.execute("SELECT COUNT(*) FROM memories WHERE namespace=?",
                                       (check_id(namespace),)).fetchone()[0]
