"""Backing up the two data files: four ways to copy a live SQLite file, a manifest, verification, restore and retention.

A backup is only worth what a restore can get back out of it, so everything here ends in a check that reads the files
again: the manifest records what landed on disk, verify_backup compares it before a restore, restore_files compares it after.
"""
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from lessons.lesson_backup_upgrade.checks import integrity, logical_digest, read_version, row_counts
from lessons.lesson_backup_upgrade.seed import CONFIG_FILE, FILES

PAGE = 4096
MANIFEST = "manifest.json"
Between = Callable[[str], None]


class RestoreError(RuntimeError):
    """A restored file does not match the manifest, so the restore is stopped instead of serving it."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------- Four ways to copy a live database file ----------

def copy_chunked(source: Path, target: Path, between: Callable[[], None]) -> int:
    """What cp does, slowed to one page at a time; between() is other work happening while the copy runs."""
    chunks = 0
    with source.open("rb") as reader, target.open("wb") as writer:
        while chunk := reader.read(PAGE):
            writer.write(chunk)
            chunks += 1
            between()
    return chunks


def single_file(path: Path) -> None:
    """Both safe copies keep the source's WAL flag; switch it off so a backup is one self-contained file."""
    db = sqlite3.connect(path)
    try:
        db.execute("PRAGMA journal_mode = DELETE")
    finally:
        db.close()


def backup_api(source: Path, target: Path, between: Callable[[], None]) -> dict:
    """SQLite's online backup: a page per step; a write from another connection makes SQLite restart the copy."""
    steps, pages = 0, 0

    def progress(status: int, remaining: int, total: int) -> None:
        nonlocal steps, pages
        steps, pages = steps + 1, total
        between()

    reader, writer = sqlite3.connect(source, timeout=10), sqlite3.connect(target)
    try:
        reader.backup(writer, pages=1, progress=progress, sleep=0)
    finally:
        writer.close()
        reader.close()
    single_file(target)
    # More steps than pages means SQLite threw work away and started over because someone wrote.
    return {"steps": steps, "pages": pages}


def vacuum_into(source: Path, target: Path, between: Callable[[], None]) -> None:
    """One statement, one read transaction: the target is a consistent snapshot of the source."""
    reader = sqlite3.connect(source, timeout=10)
    try:
        # In WAL mode writers keep committing while this statement reads. With a rollback journal they would have to
        # wait for it, so there is nothing to interleave and between() is not called.
        if reader.execute("PRAGMA journal_mode").fetchone()[0] == "wal":
            reader.set_progress_handler(lambda: between() or 0, 50)
        reader.execute("VACUUM INTO ?", (str(target),))
    finally:
        reader.close()
    single_file(target)


# ---------- The manifest ----------

def copy_database(method: str, source: Path, target: Path, between: Callable[[], None]) -> dict:
    if method in ("cold_copy", "naive_copy"):
        return {"chunks": copy_chunked(source, target, between if method == "naive_copy" else lambda: None)}
    if method == "backup_api":
        return backup_api(source, target, between)
    vacuum_into(source, target, between)
    return {}


def describe(role: str, path: Path) -> dict:
    """What actually landed on disk: not what we meant to copy."""
    entry = {"role": role, "name": path.name, "size": path.stat().st_size, "sha256": sha256_file(path),
             "schema_version": read_version(path) if role in FILES else None}
    if role in FILES:
        entry["integrity_check"] = integrity(path, immutable=True)
    return entry


def create_backup(source: Path, backup_dir: Path, *, method: str = "backup_api", scope: str = "data_only",
                  between: Between | None = None, seq: int = 1) -> dict:
    """Copy both data files with `method`, then write manifest.json describing the copies."""
    backup_dir.mkdir(parents=True)
    hooks = between or (lambda role: None)
    details: dict[str, dict] = {}
    # 1. One database at a time; between() is how the exercise lets a real writer commit in the middle of a copy.
    for role, name in FILES.items():
        details[role] = copy_database(method, source / name, backup_dir / name, lambda role=role: hooks(role))
    # 2. The scope decides what else goes in: the decoy config only with scope="whole_directory".
    if scope == "whole_directory":
        shutil.copy2(source / CONFIG_FILE, backup_dir / CONFIG_FILE)
    # 3. Describe the files as they are now; the digest is of the logical rows read from the backup itself.
    files = [describe(role, backup_dir / name) for role, name in FILES.items()]
    if scope == "whole_directory":
        files.append(describe("config", backup_dir / CONFIG_FILE))
    try:
        counts, digest = row_counts(backup_dir, immutable=True), logical_digest(backup_dir, immutable=True)
    except (sqlite3.Error, ValueError):
        counts, digest = None, None  # an unreadable copy still gets a manifest; the check later says why
    manifest = {"manifest_version": 1, "seq": seq, "created_at": datetime.now(timezone.utc).isoformat(),
                "method": method, "scope": scope, "files": files, "counts": counts, "content_digest": digest}
    (backup_dir / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {**manifest, "details": details}


# ---------- Verify, restore, retention ----------

def load_manifest(backup_dir: Path) -> dict | None:
    try:
        return json.loads((backup_dir / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def verify_backup(backup_dir: Path) -> dict:
    """Compare every file with the manifest before trusting it: same size, same sha256."""
    manifest = load_manifest(backup_dir)
    if manifest is None:
        return {"ok": False, "manifest": False, "files": []}
    rows = []
    for entry in manifest["files"]:
        path = backup_dir / entry["name"]
        actual = sha256_file(path) if path.is_file() else None
        rows.append({"name": entry["name"], "size": entry["size"], "sha256": entry["sha256"],
                     "actual_size": path.stat().st_size if path.is_file() else None, "actual_sha256": actual,
                     "ok": actual == entry["sha256"] and path.stat().st_size == entry["size"]})
    return {"ok": all(row["ok"] for row in rows), "manifest": True, "files": rows}


def restore_files(backup_dir: Path, target: Path, *, check: bool = True) -> list[str]:
    """Copy the database files into `target`; with check, compare each with the manifest. The config is never restored."""
    manifest = load_manifest(backup_dir)
    target.mkdir(parents=True, exist_ok=True)
    restored = []
    for entry in manifest["files"]:
        if entry["role"] not in FILES:
            continue
        shutil.copy2(backup_dir / entry["name"], target / entry["name"])
        if check and sha256_file(target / entry["name"]) != entry["sha256"]:
            raise RestoreError(entry["name"])
        restored.append(entry["name"])
    return restored


def restore_into(backup_dir: Path, data_dir: Path) -> list[str]:
    """Roll a live directory back: park the current files aside, then restore. A stale -wal must not meet an old file."""
    parked = data_dir / "_failed_upgrade"
    parked.mkdir(exist_ok=True)
    for name in FILES.values():
        for path in data_dir.glob(name + "*"):
            shutil.move(str(path), parked / path.name)
    return restore_files(backup_dir, data_dir)


def list_backups(root: Path) -> list[dict]:
    """Every backup under root, newest first, ordered by the manifest's own clock (file times change when copied)."""
    found = []
    for directory in sorted(root.iterdir()) if root.exists() else []:
        manifest = load_manifest(directory)
        if manifest:
            found.append({**manifest, "id": directory.name})
    return sorted(found, key=lambda item: (item["created_at"], item["seq"]), reverse=True)


def prune(root: Path, keep: int, *, keep_verified: bool) -> dict:
    """Keep the newest `keep` backups; with keep_verified also keep the newest one that still verifies."""
    ordered = list_backups(root)
    verified = {item["id"]: verify_backup(root / item["id"])["ok"] for item in ordered}
    kept = [item["id"] for item in ordered[:keep]]
    if keep_verified and not any(verified[name] for name in kept):
        newest_good = next((item["id"] for item in ordered if verified[item["id"]]), None)
        if newest_good:
            kept.append(newest_good)
    removed = [item["id"] for item in ordered if item["id"] not in kept]
    for name in removed:
        shutil.rmtree(root / name)
    return {"kept": kept, "removed": removed, "verified": verified}
