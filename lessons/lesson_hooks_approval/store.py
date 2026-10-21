"""A small ticket desk in a temporary directory: the real, local side effects the gate protects.

Records are JSON files and "sending" a notice appends a line to an outbox file, so a write really
changes something a test can read back, and nothing leaves the directory. The functions know
nothing about hooks or approval; that is the point: the gate sits in front of them.
"""
import hashlib
import json
from pathlib import Path

STATUSES = ("open", "in_progress", "resolved", "closed")
FIELDS = ("status", "owner", "note")
OWNERS = ("alice", "bob", "carol")
CORP_DOMAIN = "corp.example"
# (id, status, owner, customer phone, customer email). The customer data is made up; it exists so a
# post-tool hook has something real to mask before the result goes back to the model.
SEED = (
    ("TKT-101", "open", "alice", "13800001111", "li.wei@customer.example"),
    ("TKT-102", "in_progress", "alice", "13800002222", "wang.fang@customer.example"),
    ("TKT-103", "open", "bob", "13800003333", "zhao.min@customer.example"),
    ("TKT-104", "open", "carol", "13800004444", "chen.jie@customer.example"),
)


class DeskError(Exception):
    """A tool failure with a stable code; the gate turns it into a structured error for the model."""

    def __init__(self, code: str, **detail):
        super().__init__(code)
        self.code = code
        self.detail = detail


class Desk:
    def __init__(self, root: Path, titles: dict[str, str]):
        self.root = Path(root)
        (self.root / "records").mkdir(parents=True, exist_ok=True)
        for record_id, status, owner, phone, email in SEED:
            self._write(record_id, {"id": record_id, "title": titles[record_id], "status": status, "owner": owner,
                                    "note": "", "customer_phone": phone, "customer_email": email})
        (self.root / "outbox.jsonl").touch()

    # ---- read-only tools ----
    def list_records(self) -> list[dict]:
        records = (self._read(path.stem) for path in sorted((self.root / "records").glob("*.json")))
        return [{key: record[key] for key in ("id", "title", "status", "owner")} for record in records]

    def read_record(self, record_id: str) -> dict:
        record = self._read(record_id)
        return {**record, "owner_email": f"{record['owner']}@{CORP_DOMAIN}"}

    # ---- writing tools ----
    def update_record(self, record_id: str, field: str, value: str) -> dict:
        record = self._read(record_id)
        if field == "owner" and value not in OWNERS:
            raise DeskError("unknown_owner", owner=value)
        before, record[field] = record[field], value
        self._write(record_id, record)
        return {"record_id": record_id, "field": field, "before": before, "after": value}

    def send_notice(self, recipient: str, subject: str, body: str) -> dict:
        notice = {"notice_id": f"N-{len(self.outbox()) + 1:03d}", "recipient": recipient, "subject": subject,
                  "body": body}
        with (self.root / "outbox.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(notice, ensure_ascii=False) + "\n")
        return notice

    # ---- evidence for tests and reports ----
    def outbox(self) -> list[dict]:
        text = (self.root / "outbox.jsonl").read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def records(self) -> dict[str, dict]:
        return {path.stem: self._read(path.stem) for path in sorted((self.root / "records").glob("*.json"))}

    def snapshot(self) -> str:
        """sha256 of every file under the desk: two equal snapshots mean nothing was written in between."""
        digest = hashlib.sha256()
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                digest.update(path.relative_to(self.root).as_posix().encode("utf-8"))
                digest.update(path.read_bytes())
        return "sha256:" + digest.hexdigest()

    # ---- files ----
    def _read(self, record_id: str) -> dict:
        path = self.root / "records" / f"{record_id}.json"
        # The id is checked by a hook before it gets here; this guard keeps the tool safe on its own.
        if path.parent != self.root / "records" or not path.is_file():
            raise DeskError("record_not_found", record_id=record_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, record_id: str, record: dict) -> None:
        (self.root / "records" / f"{record_id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
