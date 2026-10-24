"""What "the data is fine" means: integrity check, business rules, a content digest and a service start-up check.

PRAGMA integrity_check only knows the file's structure. A copy can pass it and still be missing yesterday's runs,
so every check here also reads the rows the way the service would.
"""
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from lessons.lesson_10_persistent_memory.store import MemoryStore
from lessons.lesson_backup_upgrade.seed import CANARY, FILES, MEMORY_FILE, NAMESPACE, RUNS_FILE
from server.run_store import RunStore

KEY_LIKE = re.compile(rb"sk-[A-Za-z0-9_-]{16,}")


def open_readonly(path: Path, *, immutable: bool = False) -> sqlite3.Connection:
    """Open without writing. immutable=1 also ignores any write-ahead log: right for a backup file, which has none."""
    uri = path.resolve().as_uri() + ("?immutable=1" if immutable else "?mode=ro")
    return sqlite3.connect(uri, uri=True)


def describe_error(error: BaseException, *scrub: Path) -> str:
    text = f"{type(error).__name__}: {error}"
    for path in scrub:
        text = text.replace(str(path), "<data>")
    return text[:200]


def read_version(path: Path) -> int | None:
    try:
        db = open_readonly(path)
        try:
            return db.execute("PRAGMA user_version").fetchone()[0]
        finally:
            db.close()
    except sqlite3.DatabaseError:
        return None


def integrity(path: Path, *, immutable: bool = False) -> str:
    """"ok", or the first problem PRAGMA integrity_check reports and how many more it found."""
    try:
        db = open_readonly(path, immutable=immutable)
        try:
            rows = [row[0] for row in db.execute("PRAGMA integrity_check")]
        finally:
            db.close()
    except sqlite3.DatabaseError as error:
        return describe_error(error)
    return "ok" if rows == ["ok"] else (rows[0] + (f" (+{len(rows) - 1})" if len(rows) > 1 else ""))[:200]


def iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="microseconds")


def logical_rows(directory: Path, *, immutable: bool = False) -> dict:
    """Every row of both files in one version-independent shape, so v1 and v2 data can be compared."""
    out: dict = {}
    db = open_readonly(directory / RUNS_FILE, immutable=immutable)
    try:
        columns = [row[1] for row in db.execute("PRAGMA table_info(runs)")]
        wanted = [name for name in columns if name != "event_count"]
        rename = {"provenance_kind": "provenance"}
        out["runs"] = [dict(zip((rename.get(name, name) for name in wanted), row)) for row in db.execute(
            f"SELECT {', '.join(wanted)} FROM runs ORDER BY run_id")]
        out["events"] = [list(row) for row in db.execute(
            "SELECT run_id, seq, type, event FROM events ORDER BY run_id, seq")]
    finally:
        db.close()
    db = open_readonly(directory / MEMORY_FILE, immutable=immutable)
    try:
        db.row_factory = sqlite3.Row
        memories = []
        for row in db.execute("SELECT * FROM memories ORDER BY namespace, key"):
            item = dict(row)
            # v1 stores a float timestamp, v2 an ISO string; both are read as the ISO string.
            if isinstance(item["updated_at"], float):
                item["updated_at"] = iso(item["updated_at"])
            memories.append(item)
        out["memories"] = memories
        out["versions"] = [list(row) for row in db.execute(
            "SELECT namespace, key, version FROM versions ORDER BY namespace, key")]
    finally:
        db.close()
    return out


def logical_digest(directory: Path, *, immutable: bool = False) -> str:
    """sha256 of the logical rows: equal digests mean the same data, whatever the file bytes look like."""
    payload = json.dumps(logical_rows(directory, immutable=immutable), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def row_counts(directory: Path, *, immutable: bool = False) -> dict:
    rows = logical_rows(directory, immutable=immutable)
    return {"runs": len(rows["runs"]), "events": len(rows["events"]), "memories": len(rows["memories"])}


# ---------- Business checks for one copied file (the online-backup exercise) ----------

def inspect_runs(path: Path, committed: list[str]) -> dict:
    """Read a copied runs file like the service would: complete event sequences, done <=> completed, nothing missing."""
    facts = {"role": "runs", "integrity": integrity(path), "readable": False, "rows": 0, "broken": 0,
             "missing": len(committed)}
    try:
        db = open_readonly(path)
        try:
            runs = db.execute("SELECT run_id, status FROM runs").fetchall()
            broken = 0
            for rid, status in runs:
                kinds = db.execute("SELECT seq, type FROM events WHERE run_id = ? ORDER BY seq", (rid,)).fetchall()
                contiguous = [seq for seq, _ in kinds] == list(range(1, len(kinds) + 1))
                finished = bool(kinds) and kinds[-1][1] == "done"
                broken += 0 if contiguous and finished == (status == "completed") else 1
            facts.update(readable=True, rows=len(runs), broken=broken,
                         missing=len(set(committed) - {rid for rid, _ in runs}))
        finally:
            db.close()
    except sqlite3.DatabaseError as error:
        facts["error"] = describe_error(error)
    return {**facts, "ok": facts["readable"] and facts["integrity"] == "ok" and not facts["broken"]
            and not facts["missing"]}


def inspect_memory(path: Path, committed: list[str]) -> dict:
    """Read a copied memory file: every memory has its version row, and nothing committed before the copy is gone."""
    facts = {"role": "memory", "integrity": integrity(path), "readable": False, "rows": 0, "broken": 0,
             "missing": len(committed)}
    try:
        db = open_readonly(path)
        try:
            memories = db.execute("SELECT namespace, key, version FROM memories").fetchall()
            versions = {(ns, key): version for ns, key, version in db.execute(
                "SELECT namespace, key, version FROM versions")}
            broken = sum(1 for ns, key, version in memories if versions.get((ns, key)) != version)
            broken += abs(len(versions) - len(memories))
            facts.update(readable=True, rows=len(memories), broken=broken,
                         missing=len(set(committed) - {key for _, key, _ in memories}))
        finally:
            db.close()
    except sqlite3.DatabaseError as error:
        facts["error"] = describe_error(error)
    return {**facts, "ok": facts["readable"] and facts["integrity"] == "ok" and not facts["broken"]
            and not facts["missing"]}


# ---------- Service start-up check (the restore drill and the upgrade) ----------

def _runs_readable(directory: Path, version: int) -> tuple[int, str | None]:
    """Read the runs the way the service of that version does; returns (runs read, error)."""
    path = directory / RUNS_FILE
    try:
        if version == 1:
            store = RunStore(path)  # the real v1 reader: it selects columns the v2 migration renames
            try:
                runs = store.list_runs(limit=10_000)
                for run in runs:
                    seqs = [seq for seq, _, _ in store.events(run["run_id"])]
                    if seqs != list(range(1, len(seqs) + 1)):
                        raise ValueError(f"event sequence of {run['run_id']} has a gap")
                    for _, _, text in store.events(run["run_id"]):
                        json.loads(text)
            finally:
                store.close()
            return len(runs), None
        db = open_readonly(path)
        try:
            runs = db.execute("SELECT run_id, provenance_kind, event_count FROM runs").fetchall()
            for rid, _, expected in runs:
                actual = db.execute("SELECT COUNT(*) FROM events WHERE run_id = ?", (rid,)).fetchone()[0]
                if expected != actual:
                    raise ValueError(f"event_count of {rid} is {expected}, the table has {actual}")
            return len(runs), None
        finally:
            db.close()
    except Exception as error:  # the check reports what broke instead of raising
        return 0, describe_error(error, directory)


def _memory_recallable(directory: Path, version: int, locale: str) -> tuple[int, int, str | None]:
    """Recall the way the service of that version does; returns (rows stored, rows recalled, error)."""
    path = directory / MEMORY_FILE
    try:
        db = open_readonly(path)
        try:
            stored = db.execute("SELECT COUNT(*) FROM memories WHERE namespace = ?", (NAMESPACE,)).fetchone()[0]
            if version == 2:
                stamps = [row[0] for row in db.execute("SELECT updated_at FROM memories")]
                for stamp in stamps:
                    datetime.fromisoformat(stamp)
                return stored, stored, None
        finally:
            db.close()
        store = MemoryStore(path, locale=locale)  # the real v1 recall from the memory lessons
        try:
            included, _ = store.recall(NAMESPACE)
        finally:
            store.close()
        return stored, len(included), None
    except Exception as error:
        return 0, 0, describe_error(error, directory)


def service_check(directory: Path, version: int, locale: str, expected_digest: str | None = None) -> dict:
    """Start the service of `version` against a data directory and report what it can and cannot do."""
    versions = {role: read_version(directory / name) for role, name in FILES.items()}
    integrity_map = {role: integrity(directory / name) for role, name in FILES.items()}
    runs_read, runs_error = _runs_readable(directory, version)
    stored, recalled, memory_error = _memory_recallable(directory, version, locale)
    try:
        digest = logical_digest(directory)
    except Exception as error:
        digest, digest_error = None, describe_error(error, directory)
    else:
        digest_error = None
    facts = {
        "version": version, "versions": versions, "versions_ok": set(versions.values()) == {version},
        "integrity": integrity_map, "integrity_ok": all(value == "ok" for value in integrity_map.values()),
        "runs_read": runs_read, "runs_error": runs_error, "runs_ok": runs_error is None and runs_read > 0,
        "memories_stored": stored, "memories_recalled": recalled, "memory_error": memory_error,
        "memory_ok": memory_error is None and stored > 0 and recalled == stored,
        "digest": digest, "digest_error": digest_error,
        "digest_ok": None if expected_digest is None else digest == expected_digest,
    }
    facts["ok"] = all([facts["versions_ok"], facts["integrity_ok"], facts["runs_ok"], facts["memory_ok"],
                       facts["digest_ok"] is not False])
    return facts


def find_secrets(directory: Path) -> list[str]:
    """Names of files under `directory` that contain the canary or anything shaped like an API key."""
    found = []
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            if CANARY.encode() in data or KEY_LIKE.search(data):
                found.append(path.relative_to(directory).as_posix())
    return found
