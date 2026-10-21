"""The notes app's data file: atomic writes and an operation id that makes a retried write harmless.

The same idea as the idempotency key of the reliable-tools lesson, at file scale: a client that never saw the
answer sends the write again with the same ``op_id`` and gets the first result back instead of a second note.
"""
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

OP_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
MAX_TEXT = 200


class InvalidNote(ValueError):
    pass


class LimitReached(Exception):
    pass


class StoreCorrupt(Exception):
    """The data file exists but is not what this app wrote; starting would overwrite evidence, so we refuse."""


class NotesStore:
    def __init__(self, path: Path, limit: int):
        self.path, self.limit = path, limit
        self.lock = threading.Lock()
        self.notes: list[dict] = []
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.notes = list(data["notes"])
                if not all(isinstance(note, dict) and "op_id" in note and "text" in note for note in self.notes):
                    raise ValueError("bad note")
            except (OSError, ValueError, KeyError, TypeError):
                raise StoreCorrupt from None

    def _write(self) -> None:
        # Write a sibling temp file, flush it to disk, then rename over the old file: a crash leaves either the
        # old file or the new one, never half of each.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self.path.parent, prefix=".notes-", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump({"notes": self.notes}, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path)
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise

    def add(self, op_id: object, text: object) -> tuple[dict, bool]:
        """Return (note, duplicate). A repeated op_id returns the stored note and writes nothing."""
        if not isinstance(op_id, str) or not OP_ID.fullmatch(op_id):
            raise InvalidNote("op_id")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            raise InvalidNote("text")
        with self.lock:
            for note in self.notes:
                if note["op_id"] == op_id:
                    return note, True
            if len(self.notes) >= self.limit:
                raise LimitReached
            note = {"op_id": op_id, "text": text.strip(),
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            self.notes.append(note)
            try:
                self._write()
            except BaseException:
                self.notes.pop()  # memory must not claim a note the disk does not have
                raise
            return note, False

    def snapshot(self) -> list[dict]:
        with self.lock:
            return [dict(note) for note in self.notes]
