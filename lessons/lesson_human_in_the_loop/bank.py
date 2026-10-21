"""The real side effect of human-in-the-loop: a local exercise bank in SQLite, one file per thread.

``exercises`` has no UNIQUE constraint on ``operation_id``, on purpose. A checkpoint does not make
a write safe to repeat, and this lesson shows what protects the bank: the runner asks
``lookup_operation`` before it calls ``save_exercise``. Putting the key inside the store's own
transaction (as reliable-tools does) is the stronger design; here the gap stays visible so a blind
resume really writes a second row.
"""
import re
import sqlite3
from contextlib import closing
from pathlib import Path

DIFFICULTIES = ("easy", "medium", "hard")
OPERATION_ID = re.compile(r"^save-[a-z0-9]{1,16}-[0-9]{1,3}$")
FIELDS = ("title", "difficulty", "body")
TITLE_MAX, BODY_MAX = 80, 1500

SCHEMA = """
CREATE TABLE IF NOT EXISTS exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id TEXT NOT NULL,
    title TEXT NOT NULL, difficulty TEXT NOT NULL, body TEXT NOT NULL,
    origin TEXT NOT NULL);
"""


class BankError(ValueError):
    """A tool failure; ValueError so execute_tool turns it into a structured error (ok=false)."""


def exercise_problems(payload) -> list[str]:
    """Problem codes for one exercise payload; empty means it may be approved and saved.

    The same check runs on the model's draft, on a person's edit and inside the save tool.
    """
    if not isinstance(payload, dict) or set(payload) != set(FIELDS):
        return ["fields"]
    problems = []
    title, difficulty, body = payload["title"], payload["difficulty"], payload["body"]
    if not isinstance(title, str) or not title.strip() or len(title) > TITLE_MAX:
        problems.append("title")
    if difficulty not in DIFFICULTIES:
        problems.append("difficulty")
    if not isinstance(body, str) or not body.strip() or len(body) > BODY_MAX:
        problems.append("body")
    return problems


class ExerciseBank:
    def __init__(self, folder: Path, texts):
        folder.mkdir(parents=True, exist_ok=True)
        self.database = folder / "bank.sqlite3"
        self.t = texts
        with self._connect() as db:
            db.executescript(SCHEMA)

    def _connect(self):
        return closing(sqlite3.connect(self.database, timeout=5, isolation_level=None))

    def lookup_operation(self, operation_id: str) -> dict:
        """Read only: has this operation already written a row? Asking twice changes nothing."""
        if not isinstance(operation_id, str) or not OPERATION_ID.fullmatch(operation_id):
            raise BankError(self.t.bank_bad_operation)
        with self._connect() as db:
            rows = db.execute("SELECT id FROM exercises WHERE operation_id = ? ORDER BY id",
                              (operation_id,)).fetchall()
        return {"found": bool(rows), "exercise_id": rows[0][0] if rows else None, "rows": len(rows)}

    def save_exercise(self, operation_id: str, title: str, difficulty: str, body: str, origin: str) -> dict:
        """Write: append one row. Nothing here stops a second row for the same operation_id."""
        if not isinstance(operation_id, str) or not OPERATION_ID.fullmatch(operation_id):
            raise BankError(self.t.bank_bad_operation)
        if origin not in ("fresh", "resumed"):
            raise BankError(self.t.bank_bad_origin)
        problems = exercise_problems({"title": title, "difficulty": difficulty, "body": body})
        if problems:
            raise BankError(self.t.bank_bad_exercise.format(fields=", ".join(problems)))
        with self._connect() as db:
            cursor = db.execute("INSERT INTO exercises (operation_id, title, difficulty, body, origin) "
                                "VALUES (?, ?, ?, ?, ?)", (operation_id, title, difficulty, body, origin))
        return {"exercise_id": cursor.lastrowid, "operation_id": operation_id}

    def rows(self) -> list[dict]:
        """Everything stored, read straight from the database (not from any tool result)."""
        with self._connect() as db:
            found = db.execute("SELECT id, operation_id, title, difficulty, body, origin FROM exercises "
                               "ORDER BY id").fetchall()
        return [dict(zip(("id", "operation_id", "title", "difficulty", "body", "origin"), row)) for row in found]

    def tools(self) -> dict:
        """The allowlist the runner calls through: name -> function."""
        return {"lookup_operation": self.lookup_operation, "save_exercise": self.save_exercise}
