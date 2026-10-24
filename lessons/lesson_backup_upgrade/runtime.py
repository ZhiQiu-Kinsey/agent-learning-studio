"""Backup, restore and upgrade rollback: four exercises on throwaway SQLite files; this lesson calls no model.

Each exercise builds its own data directory in a temporary folder, so the real .runtime/ is never read or written.
The files are real SQLite databases, the writer thread really commits while a copy runs, and every verdict is read
back from the files. The only things made up are the faults, and each one is announced in a lesson.fault event.
Reports are assembled in reports.py; this file is the flow of each exercise.
"""
import tempfile
import time
from pathlib import Path
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_backup_upgrade import reports
from lessons.lesson_backup_upgrade.backup import (RestoreError, create_backup, list_backups, load_manifest,
                                                  prune, restore_files, restore_into, verify_backup)
from lessons.lesson_backup_upgrade.checks import (find_secrets, inspect_memory, inspect_runs, integrity, logical_digest,
                                                  open_readonly, row_counts, service_check)
from lessons.lesson_backup_upgrade.locales import Texts, texts_for
from lessons.lesson_backup_upgrade.migrate import Fault, upgrade_files
from lessons.lesson_backup_upgrade.seed import (FILES, LiveWriter, add_units, build_data_dir, memory_key,
                                                run_id)

SEED_UNITS = 8  # runs and memories in the directory before the exercise starts
WARM_UNITS = 6  # committed after the seed was closed: they sit in the write-ahead log, not yet in runs.sqlite3
DURING_COPY = 6  # units a real writer commits in the middle of the copy of each file
FREE_UNITS = 30  # how many units the free-running writer may commit
BACKUPS = 6  # the retention exercise makes this many backups


class Inputs(LessonInputs):
    scenario: Literal["online_backup", "restore_drill", "upgrade_rollback", "retention"] = "online_backup"
    method: Literal["cold_copy", "naive_copy", "backup_api", "vacuum_into"] = "backup_api"
    schedule: Literal["lockstep", "free"] = "lockstep"
    damage: Literal["none", "bit_flip", "truncated"] = "none"
    scope: Literal["data_only", "whole_directory"] = "data_only"
    verify_manifest: bool = True
    failure: Literal["none", "fail_first_file", "fail_second_file", "bad_result"] = "none"
    safeguard: Literal["none", "transaction", "backup"] = "backup"
    keep: int = Field(default=3, ge=1, le=5)
    corrupt_newest: int = Field(default=0, ge=0, le=3)
    policy: Literal["newest_n", "newest_n_keep_verified"] = "newest_n_keep_verified"


INPUT_MODEL = Inputs


# ---------- Exercise 1: copying a database that is being written ----------

class Interleave:
    """Lets one real writer commit between the steps of a copy: a few units per file, then the copy finishes alone."""

    def __init__(self, writer: LiveWriter, per_file: int):
        self.writer, self.per_file, self.seen = writer, per_file, {}

    def __call__(self, role: str) -> None:
        self.seen[role] = self.seen.get(role, 0) + 1
        if self.seen[role] <= self.per_file:
            self.writer.step()


def online_backup(context: RunContext, t: Texts, root: Path, inputs: Inputs) -> str:
    data = root / "data"
    build_data_dir(data, context.locale, t, units=SEED_UNITS)
    writer = LiveWriter(data, context.locale, t, first=SEED_UNITS + 1).start()
    try:
        # 1. Warm up: units committed after the seed closed. The runs file is in WAL mode, so they exist only in its -wal file.
        for _ in range(WARM_UNITS):
            writer.step()
        committed_runs = [run_id(n) for n in range(1, SEED_UNITS + 1)] + writer.committed_runs
        committed_memories = [memory_key(n) for n in range(1, SEED_UNITS + 1)] + writer.committed_memories
        context.check_cancelled()
        modes = reports.journal_modes(data)
        sidecars = reports.sidecars(data)
        # 2. Pick who writes while the copy runs: nobody (cold), one commit per step (lockstep) or a free-running thread.
        if inputs.method == "cold_copy":
            writer.stop()  # closing the last connection checkpoints the log into runs.sqlite3
            between = None
        elif inputs.schedule == "free":
            writer.release(FREE_UNITS)
            between = lambda role: time.sleep(0.002)  # slows the copy a little so the free writer lands commits in it
        else:
            between = Interleave(writer, DURING_COPY)
        before = writer.committed
        manifest = create_backup(data, root / "backup", method=inputs.method, between=between)
        writes = writer.committed - before
    finally:
        writer.stop()
    context.emit("lesson.backup", reports.backup_event(manifest, modes=modes, sidecars=sidecars, writes=writes,
                                                       committed=len(committed_runs), schedule=inputs.schedule))
    # 3. Read each copy back the way the service would; integrity_check and the row rules are separate verdicts.
    verdicts = [inspect_runs(root / "backup" / FILES["runs"], committed_runs),
                inspect_memory(root / "backup" / FILES["memory"], committed_memories)]
    for verdict in verdicts:
        context.emit("lesson.backup_check", verdict)
    reports.online_report(context, t, inputs, manifest, verdicts, modes, writes, committed_runs)
    answer = t.online_answer_ok if all(v["ok"] for v in verdicts) else t.online_answer_bad
    return answer.format(method=t.method_names[inputs.method])


# ---------- Exercise 2: restore drill ----------

def damage_file(path: Path, kind: str, n: int = 3) -> dict:
    """Break one backup file on purpose. bit_flip changes one digit inside a stored value; truncated cuts the tail."""
    data = path.read_bytes()
    if kind == "truncated":
        cut = int(len(data) * 0.6)
        path.write_bytes(data[:cut])
        return {"kind": kind, "file": path.name, "size_before": len(data), "size_after": cut}
    needle = f"plan-{n:04d}".encode()
    offset = data.index(needle) + len(needle) - 1
    flipped = bytearray(data)
    flipped[offset] ^= 0x01
    path.write_bytes(bytes(flipped))
    return {"kind": kind, "file": path.name, "offset": offset, "byte_before": f"{data[offset]:02x}",
            "byte_after": f"{flipped[offset]:02x}"}


def restore_drill(context: RunContext, t: Texts, root: Path, inputs: Inputs) -> str:
    data, backup_dir, target = root / "data", root / "backup", root / "restored"
    build_data_dir(data, context.locale, t, units=SEED_UNITS + WARM_UNITS)
    # 1. Back up, then read the backup directory for anything shaped like a key.
    manifest = create_backup(data, backup_dir, scope=inputs.scope)
    context.emit("lesson.backup", reports.backup_event(manifest))
    found = find_secrets(backup_dir)
    context.emit("lesson.secret_scan", {"scope": inputs.scope, "found": found,
                                        "scanned": sorted(path.name for path in backup_dir.iterdir())})
    context.check_cancelled()
    # 2. A program-made fault, after the backup "succeeded": the backup command itself reported nothing wrong.
    if inputs.damage != "none":
        context.emit("lesson.fault", {"origin": "fault_injection", "note": t.fault_note_backup,
                                      **damage_file(backup_dir / FILES["memory"], inputs.damage)})
    damaged_integrity = integrity(backup_dir / FILES["memory"], immutable=True)
    # 3. Verify against the manifest before restoring, unless the learner switched that off.
    verification = verify_backup(backup_dir) if inputs.verify_manifest else None
    if verification is not None:
        context.emit("lesson.verify", {**verification, "integrity_of_memory_file": damaged_integrity})
    refused = verification is not None and not verification["ok"]
    restored, error, acceptance = [], None, None
    if refused:
        context.emit("lesson.restore", {"performed": False, "reason": "manifest_mismatch"})
    else:
        # 4. Restore into a new directory and start the service against it; this, not the backup, is the real test.
        try:
            restored = restore_files(backup_dir, target, check=inputs.verify_manifest)
        except RestoreError as problem:
            error = str(problem)
        context.emit("lesson.restore", {"performed": not error, "files": restored, "error": error})
        if not error:
            acceptance = service_check(target, 1, context.locale, manifest["content_digest"])
            if acceptance["memory_ok"]:
                context.emit("lesson.memory", reports.recall_event(target, acceptance, t))
    reports.restore_report(context, t, inputs, manifest, found, damaged_integrity, verification, refused, acceptance)
    return reports.restore_answer(t, refused, acceptance, found)


# ---------- Exercise 3: upgrade and roll back ----------

def fault_for(t: Texts, failure: str) -> Fault:
    if failure == "fail_first_file":
        return Fault("abort", "memory", 3, t.fault_abort.format(file=FILES["memory"], rows=3))
    if failure == "fail_second_file":
        return Fault("abort", "runs", 3, t.fault_abort.format(file=FILES["runs"], rows=3))
    if failure == "bad_result":
        return Fault("bug", "memory", 0, t.fault_bug.format(file=FILES["memory"]))
    return Fault()


def upgrade_rollback(context: RunContext, t: Texts, root: Path, inputs: Inputs) -> str:
    data = root / "data"
    build_data_dir(data, context.locale, t, units=SEED_UNITS + WARM_UNITS)
    before, counts_before = logical_digest(data), row_counts(data)
    # 1. Back up first (only with the "backup" safeguard) and read the backup directory for keys.
    manifest = secrets = None
    if inputs.safeguard == "backup":
        manifest = create_backup(data, root / "backup")
        context.emit("lesson.backup", reports.backup_event(manifest))
        secrets = find_secrets(root / "backup")
    # 2. Migrate memory.sqlite3, then runs.sqlite3. Without a transaction every statement commits by itself.
    fault = fault_for(t, inputs.failure)
    if fault.kind != "none":
        context.emit("lesson.fault", {"origin": "fault_injection", "kind": fault.kind, "file": FILES[fault.role],
                                      "note": fault.message})
    context.check_cancelled()
    error = upgrade_files(data, fault, transactional=inputs.safeguard != "none",
                          on_step=lambda step: context.emit("lesson.migration", step))
    # 3. Did the upgrade really work? Start the version-2 service and compare the data with what it was.
    post = service_check(data, 2, context.locale, before) if error is None else None
    upgraded = error is None and post["ok"]
    recovery = None
    if not upgraded:
        context.check_cancelled()
        # 4. Go back: only a backup can undo a migration that already committed or touched two files.
        if inputs.safeguard == "backup":
            try:
                restore_into(root / "backup", data)
                recovery = "backup"
            except RestoreError:
                recovery = "backup_failed"
            context.emit("lesson.rollback", {"method": "restore_from_backup", "ok": recovery == "backup"})
        elif inputs.safeguard == "transaction":
            # An error means the failed file's transaction rolled back; no error means the migration committed a wrong result.
            recovery = "transaction" if error is not None else "committed"
            context.emit("lesson.rollback", {"method": "transaction", "ok": error is not None,
                                             "note": t.rollback_transaction_note if error is not None
                                             else t.rollback_committed_note})
    # 5. The service that should be running now: version 2 after a good upgrade, version 1 after going back.
    final = service_check(data, 2 if upgraded else 1, context.locale, before)
    if final["memory_ok"]:
        context.emit("lesson.memory", reports.recall_event(data, final, t))
    reports.upgrade_report(context, t, inputs, counts_before, post, upgraded, error, recovery, final, secrets, data)
    return reports.upgrade_answer(t, upgraded, error, recovery, final)


# ---------- Exercise 4: keeping the last N backups ----------

def retention(context: RunContext, t: Texts, root: Path, inputs: Inputs) -> str:
    data, backups = root / "data", root / "backups"
    build_data_dir(data, context.locale, t, units=SEED_UNITS)
    # 1. A service that keeps working: one more unit before each backup, so newer backups hold more runs.
    for index in range(1, BACKUPS + 1):
        if index > 1:
            add_units(data, context.locale, t, SEED_UNITS + index - 1, 1)
        create_backup(data, backups / f"backup-{index:03d}", seq=index)
        context.check_cancelled()
    total_runs = SEED_UNITS + BACKUPS - 1
    # 2. Damage the newest ones on purpose, as a full disk or a bad sector would.
    names = [item["id"] for item in list_backups(backups)]
    for name in names[:inputs.corrupt_newest]:
        context.emit("lesson.fault", {"origin": "fault_injection", "note": t.fault_note_backup,
                                      "backup": name, **damage_file(backups / name / FILES["memory"], "bit_flip")})
    # 3. Prune with the chosen policy, then try to restore from the newest backup that is left and still verifies.
    result = prune(backups, inputs.keep, keep_verified=inputs.policy == "newest_n_keep_verified")
    context.emit("lesson.retention", {"policy": inputs.policy, "keep": inputs.keep, "before": names,
                                      "verified": result["verified"], "kept": result["kept"],
                                      "removed": result["removed"]})
    kept = [item for item in list_backups(backups)]
    best = next((item for item in kept if verify_backup(backups / item["id"])["ok"]), None)
    acceptance = None
    if best:
        restore_files(backups / best["id"], root / "restored")
        acceptance = service_check(root / "restored", 1, context.locale, best["content_digest"])
        context.emit("lesson.restore", {"performed": True, "backup": best["id"], "files": list(FILES.values())})
        if acceptance["memory_ok"]:
            context.emit("lesson.memory", reports.recall_event(root / "restored", acceptance, t))
    reports.retention_report(context, t, inputs, kept, result, best, acceptance, total_runs, backups)
    return reports.retention_answer(t, best, acceptance, total_runs)


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    inputs = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    # Real runs and offline tests alike work in a throwaway directory and never touch .runtime/.
    with tempfile.TemporaryDirectory(prefix="backup-upgrade-") as directory:
        root = Path(directory)
        if inputs.scenario == "online_backup":
            return online_backup(context, t, root, inputs)
        if inputs.scenario == "restore_drill":
            return restore_drill(context, t, root, inputs)
        if inputs.scenario == "upgrade_rollback":
            return upgrade_rollback(context, t, root, inputs)
        return retention(context, t, root, inputs)
