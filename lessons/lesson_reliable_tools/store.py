"""The real local tools of reliable-tools: a practice-submission store (SQLite) and an outbox folder.

read_account only reads. submit_practice and cancel_submission change the store, each inside one
transaction, so the effect and its operation record commit together or not at all. write_outbox
writes one file for the grader. Every failure is an exception whose class name becomes error_type
in the tool result; the runner decides what to do from that name alone.
"""
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# The practice exercises that accept submissions; anything else is an argument the tool never accepts.
EXERCISES = ("loop-basics", "safe-divide", "json-output")

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    learner TEXT PRIMARY KEY,
    credits INTEGER NOT NULL CHECK (credits >= 0));
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learner TEXT NOT NULL, exercise TEXT NOT NULL, answer TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active');
CREATE TABLE IF NOT EXISTS operations (
    idempotency_key TEXT PRIMARY KEY,
    tool TEXT NOT NULL, fingerprint TEXT NOT NULL, result TEXT NOT NULL);
"""


class ToolFailure(ValueError):
    """Base of this lesson's tool errors.

    It subclasses ValueError because execute_tool turns only ValueError and TypeError into a
    structured error; any other exception would end the run instead of becoming a tool result.
    """


class StoreTimeout(ToolFailure):
    """Waited timeout_s for the database lock and gave up: the transaction never started."""


class OutboxBusy(ToolFailure):
    """Another writer holds the outbox lock file: nothing was written."""


class InvalidArgument(ToolFailure):
    """An argument this tool never accepts; the same call fails the same way every time."""


class BusinessRejected(ToolFailure):
    """The arguments are fine but a business rule says no (for example, no credits left)."""


class KeyConflict(ToolFailure):
    """The idempotency key was already used for a different request."""


def fingerprint(*parts: str) -> str:
    """What the request asked for; one key may only ever stand for one request."""
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


class PracticeStore:
    def __init__(self, root: Path, texts, timeout_s: float):
        self.database = root / "practice.sqlite3"
        self.outbox = root / "outbox"
        self.t = texts
        self.timeout_s = timeout_s
        self.outbox.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def _connection(self):
        # isolation_level=None: this code issues BEGIN itself, so which lock it waits for is explicit.
        db = sqlite3.connect(self.database, timeout=self.timeout_s, isolation_level=None)
        try:
            yield db
        except sqlite3.OperationalError as error:
            if "locked" not in str(error):
                raise
            raise StoreTimeout(self.t.store_timeout.format(seconds=self.timeout_s)) from None
        finally:
            db.close()

    @contextmanager
    def _write(self):
        """One write transaction: the write lock first, then everything inside commits or rolls back together."""
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.execute("ROLLBACK")
                raise
            db.execute("COMMIT")

    def seed(self, learner: str, credits: int):
        with self._write() as db:
            db.execute("INSERT OR REPLACE INTO accounts VALUES (?, ?)", (learner, credits))

    def read_account(self, learner: str) -> dict:
        """Read only: credits left and active submissions. Running it twice changes nothing."""
        with self._connection() as db:
            row = db.execute("SELECT credits FROM accounts WHERE learner = ?", (learner,)).fetchone()
            if row is None:
                raise InvalidArgument(self.t.unknown_learner.format(learner=learner))
            active = db.execute("SELECT COUNT(*) FROM submissions WHERE learner = ? AND status = 'active'",
                                (learner,)).fetchone()[0]
        return {"learner": learner, "credits": row[0], "active_submissions": active}

    def submit_practice(self, learner: str, exercise: str, answer: str, idempotency_key: str | None = None) -> dict:
        """Write: take one credit and record one submission. With a key, a repeat returns the first result."""
        # 1. Arguments this tool never accepts fail before the store is touched.
        if exercise not in EXERCISES:
            raise InvalidArgument(self.t.unknown_exercise.format(exercise=exercise, known=", ".join(EXERCISES)))
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 500:
            raise InvalidArgument(self.t.bad_answer)
        asked = fingerprint(learner, exercise, answer)
        # 2. The write lock comes first: if it cannot be had within timeout_s, nothing has happened.
        with self._write() as db:
            # 3. A key seen before: hand back the stored result instead of writing again.
            if idempotency_key:
                seen = db.execute("SELECT fingerprint, result FROM operations WHERE idempotency_key = ?",
                                  (idempotency_key,)).fetchone()
                if seen and seen[0] != asked:
                    raise KeyConflict(self.t.key_conflict.format(key=idempotency_key))
                if seen:
                    return {**json.loads(seen[1]), "replayed": True}
            # 4. A business rule: no credits left is a refusal, not a glitch to retry.
            row = db.execute("SELECT credits FROM accounts WHERE learner = ?", (learner,)).fetchone()
            if row is None:
                raise InvalidArgument(self.t.unknown_learner.format(learner=learner))
            if row[0] < 1:
                raise BusinessRejected(self.t.no_credits.format(learner=learner))
            # 5. The effect and its operation record share this transaction: both commit or neither does.
            db.execute("UPDATE accounts SET credits = credits - 1 WHERE learner = ?", (learner,))
            cursor = db.execute("INSERT INTO submissions (learner, exercise, answer) VALUES (?, ?, ?)",
                                (learner, exercise, answer))
            result = {"submission_id": cursor.lastrowid, "credits_left": row[0] - 1}
            if idempotency_key:
                db.execute("INSERT INTO operations VALUES (?, 'submit_practice', ?, ?)",
                           (idempotency_key, asked, json.dumps(result)))
        return {**result, "replayed": False}

    def write_outbox(self, submission_id: int) -> dict:
        """Write the grader's file. Same id, same name, same content: writing it twice still leaves one file."""
        lock = self.outbox / ".lock"
        try:
            handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise OutboxBusy(self.t.outbox_busy) from None
        try:
            with self._connection() as db:
                row = db.execute("SELECT learner, exercise, answer FROM submissions WHERE id = ? AND status = 'active'",
                                 (submission_id,)).fetchone()
            if row is None:
                raise InvalidArgument(self.t.unknown_submission.format(submission_id=submission_id))
            body = json.dumps({"submission_id": submission_id, "learner": row[0], "exercise": row[1],
                               "answer": row[2]}, ensure_ascii=False)
            target = self.outbox / f"{submission_id}.json"
            # Write a temporary file, then rename: the grader never sees half a file.
            temporary = target.with_suffix(".tmp")
            temporary.write_text(body, encoding="utf-8")
            os.replace(temporary, target)
        finally:
            os.close(handle)
            lock.unlink()
        return {"file": f"outbox/{target.name}", "bytes": len(body.encode("utf-8"))}

    def cancel_submission(self, submission_id: int) -> dict:
        """Compensation for submit_practice: refund the credit and mark the row cancelled; the row stays as history.

        The status is checked inside the transaction, so a repeat refunds nothing: the state itself
        makes this call safe to repeat, no key needed.
        """
        with self._write() as db:
            row = db.execute("SELECT learner, status FROM submissions WHERE id = ?", (submission_id,)).fetchone()
            if row is None:
                raise InvalidArgument(self.t.unknown_submission.format(submission_id=submission_id))
            if row[1] == "cancelled":
                return {"submission_id": submission_id, "refunded": False}
            db.execute("UPDATE submissions SET status = 'cancelled' WHERE id = ?", (submission_id,))
            db.execute("UPDATE accounts SET credits = credits + 1 WHERE learner = ?", (row[0],))
        return {"submission_id": submission_id, "refunded": True}

    def tools(self) -> dict:
        """The allowlist the runner calls through: name -> function."""
        return {"read_account": self.read_account, "submit_practice": self.submit_practice,
                "write_outbox": self.write_outbox, "cancel_submission": self.cancel_submission}

    def snapshot(self) -> dict:
        """What is actually stored, read straight from the database and the folder (not from any tool result)."""
        with self._connection() as db:
            accounts = dict(db.execute("SELECT learner, credits FROM accounts ORDER BY learner").fetchall())
            submissions = [{"id": i, "learner": learner, "exercise": exercise, "status": status} for i, learner,
                           exercise, status in db.execute("SELECT id, learner, exercise, status FROM submissions "
                                                          "ORDER BY id")]
            operations = [{"idempotency_key": key, "tool": tool, "result": json.loads(result)} for key, tool, result
                          in db.execute("SELECT idempotency_key, tool, result FROM operations ORDER BY rowid")]
        files = sorted(path.name for path in self.outbox.iterdir() if path.suffix == ".json")
        return {"accounts": accounts, "submissions": submissions, "operations": operations,
                "outbox": [f"outbox/{name}" for name in files]}
