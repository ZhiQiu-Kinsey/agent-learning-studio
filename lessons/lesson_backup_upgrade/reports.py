"""Evidence assembly for backup-upgrade: lesson.report and the helper events. These functions only arrange what the
exercises measured; they read files for display (journal mode, key lists) but never write or repair anything."""
from pathlib import Path

from course.execution import RunContext
from lessons.lesson_backup_upgrade.checks import open_readonly, read_version, row_counts
from lessons.lesson_backup_upgrade.locales import Texts
from lessons.lesson_backup_upgrade.seed import FILES, MEMORY_FILE, NAMESPACE


def _note(context: RunContext, t: Texts) -> dict:
    return {"label": t.label_note, "value": context.question or t.value_none}


def _yes(t: Texts, flag: bool | None) -> str:
    return t.value_not_applicable if flag is None else t.value_yes if flag else t.value_no


def journal_modes(data: Path) -> dict:
    modes = {}
    for role, name in FILES.items():
        db = open_readonly(data / name)
        try:
            modes[role] = db.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            db.close()
    return modes


def sidecars(data: Path) -> list[dict]:
    return [{"name": path.name, "size": path.stat().st_size} for path in sorted(data.glob("*.sqlite3-*"))]


def backup_event(manifest: dict, *, modes: dict | None = None, sidecars: list | None = None,
                 writes: int | None = None, committed: int | None = None, schedule: str | None = None) -> dict:
    """The manifest as an event: file names and hashes, never paths. The keyword arguments only exist in exercise 1."""
    data = {key: manifest[key] for key in ("method", "scope", "files", "counts", "content_digest", "created_at")}
    data["details"] = manifest.get("details", {})
    extra = {"journal_mode": modes, "sidecar_files": sidecars, "writes_during_copy": writes,
             "committed_before_copy": committed, "schedule": schedule}
    return {**data, **{key: value for key, value in extra.items() if value is not None}}


def recall_event(directory: Path, facts: dict, t: Texts) -> dict:
    """lesson.memory in the shape the generic memory view reads: which keys came back from the restored file."""
    db = open_readonly(directory / MEMORY_FILE)
    try:
        keys = [row[0] for row in db.execute("SELECT key FROM memories WHERE namespace = ? ORDER BY key",
                                             (NAMESPACE,))]
    finally:
        db.close()
    return {"action": "recalled", "storage": "scratch", "included": keys, "excluded": [],
            "recalled_count": facts["memories_recalled"]}


# ---------- Exercise 1 ----------

def online_report(context: RunContext, t: Texts, inputs, manifest: dict, verdicts: list[dict], modes: dict,
                  writes: int, committed_runs: list[str]) -> None:
    checks, rows = [], []
    for verdict in verdicts:
        file = FILES[verdict["role"]]
        checks.append({"id": f"integrity_{verdict['role']}", "label": t.check_integrity.format(file=file),
                       "passed": verdict["integrity"] == "ok", "detail": verdict["integrity"]})
        checks.append({"id": f"rows_{verdict['role']}", "label": t.check_rows.format(file=file),
                       "passed": verdict["readable"] and not verdict["broken"] and not verdict["missing"],
                       "detail": verdict.get("error") or t.rows_detail.format(
                           rows=verdict["rows"], missing=verdict["missing"], broken=verdict["broken"])})
        rows.append([file, modes[verdict["role"]], verdict["integrity"], verdict["rows"], verdict["missing"],
                     verdict["broken"], t.verdict_ok if verdict["ok"] else t.verdict_bad])
    context.emit("lesson.report", {
        "title": t.online_title.format(method=t.method_names[inputs.method]),
        "summary": t.online_summary,
        "checks": checks,
        "metrics": [{"id": "method", "label": t.label_method, "value": t.method_names[inputs.method]},
                    {"id": "writes_during_copy", "label": t.label_writes, "value": writes},
                    {"id": "committed_before", "label": t.label_committed_before, "value": len(committed_runs)},
                    {"label": t.label_schedule, "value": t.schedule_names[inputs.schedule]},
                    {"label": t.label_model_calls, "value": 0}, _note(context, t)],
        "table": {"columns": list(t.online_columns), "rows": rows},
    })


# ---------- Exercise 2 ----------

def restore_report(context: RunContext, t: Texts, inputs, manifest: dict, found: list[str], damaged_integrity: str,
                   verification: dict | None, refused: bool, acceptance: dict | None) -> None:
    checks = [{"id": "no_secrets", "label": t.check_no_secrets, "passed": not found,
               "detail": t.separator.join(found) if found else t.detail_no_secrets}]
    if verification is not None:
        bad = [row["name"] for row in verification["files"] if not row["ok"]]
        checks.append({"id": "manifest_verified", "label": t.check_manifest, "passed": verification["ok"],
                       "detail": t.detail_manifest_bad.format(files=t.separator.join(bad)) if bad
                       else t.detail_manifest_ok})
    if inputs.damage != "none":
        caught = refused or (acceptance is not None and not acceptance["ok"])
        checks.append({"id": "damage_caught", "label": t.check_damage_caught, "passed": caught,
                       "detail": t.detail_caught_by_manifest if refused else t.detail_caught_by_acceptance if caught
                       else t.detail_not_caught})
    if acceptance is not None:
        checks += [
            {"id": "runs_readable", "label": t.check_runs_readable, "passed": acceptance["runs_ok"],
             "detail": acceptance["runs_error"] or t.detail_runs.format(count=acceptance["runs_read"])},
            {"id": "memory_recallable", "label": t.check_memory_recallable, "passed": acceptance["memory_ok"],
             "detail": acceptance["memory_error"] or t.detail_memory.format(
                 recalled=acceptance["memories_recalled"], stored=acceptance["memories_stored"])},
            {"id": "integrity", "label": t.check_integrity_both, "passed": acceptance["integrity_ok"],
             "detail": t.separator.join(f"{FILES[role]}: {value}" for role, value in acceptance["integrity"].items())},
            {"id": "digest_matches", "label": t.check_digest, "passed": bool(acceptance["digest_ok"]),
             "detail": t.detail_digest_ok if acceptance["digest_ok"] else t.detail_digest_bad},
        ]
    verified = {row["name"]: row["ok"] for row in verification["files"]} if verification else {}
    rows = [[entry["name"], entry["role"], entry["size"], entry["sha256"][:12],
             entry["schema_version"] if entry["schema_version"] is not None else t.value_not_applicable,
             entry.get("integrity_check", t.value_not_applicable),
             _yes(t, verified.get(entry["name"]) if verification else None)] for entry in manifest["files"]]
    context.emit("lesson.report", {
        "title": t.restore_title, "summary": t.restore_summary, "checks": checks,
        "metrics": [{"id": "scope", "label": t.label_scope, "value": t.scope_names[inputs.scope]},
                    {"label": t.label_damage, "value": t.damage_names[inputs.damage]},
                    {"label": t.label_verify, "value": _yes(t, inputs.verify_manifest)},
                    {"label": t.label_runs_restored, "value": acceptance["runs_read"] if acceptance else 0},
                    {"label": t.label_model_calls, "value": 0}, _note(context, t)],
        "table": {"columns": list(t.restore_columns), "rows": rows},
    })


def restore_answer(t: Texts, refused: bool, acceptance: dict | None, found: list[str]) -> str:
    if refused:
        return t.restore_answer_refused
    answer = t.restore_answer_ok if acceptance and acceptance["ok"] else t.restore_answer_bad
    return t.restore_answer_secrets.format(answer=answer, files=t.separator.join(found)) if found else answer


# ---------- Exercise 3 ----------

def _final_versions(data: Path) -> str:
    return "/".join(str(read_version(data / name)) for name in FILES.values())


def upgrade_report(context: RunContext, t: Texts, inputs, counts_before: dict, post: dict | None, upgraded: bool,
                   error: Exception | None, recovery: str | None, final: dict, secrets: list[str] | None,
                   data: Path) -> None:
    if error is not None:
        outcome = t.detail_upgrade_error.format(error=str(error))
    elif not upgraded:
        outcome = t.detail_upgrade_check.format(before=counts_before["memories"], after=post["memories_stored"])
    else:
        outcome = t.detail_upgrade_ok
    checks = [
        {"id": "upgrade_completed", "label": t.check_upgrade, "passed": upgraded, "detail": outcome},
        {"id": "service_available", "label": t.check_service.format(version=final["version"]),
         "passed": final["ok"], "detail": _service_detail(t, final)},
        {"id": "data_unchanged", "label": t.check_data_unchanged, "passed": bool(final["digest_ok"]),
         "detail": t.detail_digest_ok if final["digest_ok"] else t.detail_digest_bad},
    ]
    if secrets is not None:
        checks.append({"id": "no_secrets", "label": t.check_no_secrets, "passed": not secrets,
                       "detail": t.separator.join(secrets) if secrets else t.detail_no_secrets})
    after = _safe_counts(data)
    context.emit("lesson.report", {
        "title": t.upgrade_title, "summary": t.upgrade_summary, "checks": checks,
        "metrics": [{"id": "failure", "label": t.label_failure, "value": t.failure_names[inputs.failure]},
                    {"id": "safeguard", "label": t.label_safeguard, "value": t.safeguard_names[inputs.safeguard]},
                    {"id": "final_versions", "label": t.label_final_versions, "value": _final_versions(data)},
                    {"label": t.label_recovery, "value": t.recovery_names[recovery or "none"]},
                    {"label": t.label_model_calls, "value": 0}, _note(context, t)],
        "table": {"columns": list(t.upgrade_columns), "rows": [
            [FILES["memory"], counts_before["memories"], after["memories"] if after else t.value_unreadable],
            [FILES["runs"], counts_before["runs"], after["runs"] if after else t.value_unreadable]]},
    })


def _safe_counts(data: Path) -> dict | None:
    try:
        return row_counts(data)
    except Exception:  # a half-migrated directory may not be readable at all
        return None


def _service_detail(t: Texts, facts: dict) -> str:
    problems = []
    if not facts["versions_ok"]:
        problems.append(t.problem_versions.format(runs=facts["versions"]["runs"], memory=facts["versions"]["memory"],
                                                  version=facts["version"]))
    if facts["runs_error"]:
        problems.append(t.problem_runs.format(error=facts["runs_error"]))
    if facts["memory_error"]:
        problems.append(t.problem_memory.format(error=facts["memory_error"]))
    if not facts["integrity_ok"]:
        problems.append(t.problem_integrity)
    return t.separator.join(problems) if problems else t.detail_service_ok.format(
        runs=facts["runs_read"], memories=facts["memories_recalled"])


def upgrade_answer(t: Texts, upgraded: bool, error: Exception | None, recovery: str | None, final: dict) -> str:
    state = t.final_answer_ok if final["ok"] else t.final_answer_bad
    if upgraded:
        return t.answer_success.format(head=t.upgrade_answer_ok, state=state)
    tail = {"backup": t.recovery_answer_backup, "transaction": t.recovery_answer_transaction,
            "committed": t.recovery_answer_committed,
            "backup_failed": t.recovery_answer_backup_failed}.get(recovery or "", t.recovery_answer_none)
    return t.answer_failure.format(head=t.upgrade_answer_failed, recovery=tail, state=state)


# ---------- Exercise 4 ----------

def retention_report(context: RunContext, t: Texts, inputs, kept: list[dict], result: dict, best: dict | None,
                     acceptance: dict | None, total_runs: int, backups: Path) -> None:
    kept_ids = {item["id"] for item in kept}
    ordered = sorted(result["verified"], reverse=True)
    rows = []
    for position, name in enumerate(ordered, 1):
        counts = next((item["counts"] for item in kept if item["id"] == name), None)
        rows.append([name, position, _yes(t, result["verified"][name]), _yes(t, name in kept_ids),
                     counts["runs"] if counts else t.value_removed])
    restorable = best is not None and acceptance is not None and acceptance["ok"]
    runs_in_best = best["counts"]["runs"] if best and best["counts"] else 0
    context.emit("lesson.report", {
        "title": t.retention_title, "summary": t.retention_summary,
        "checks": [
            {"id": "restorable_after_prune", "label": t.check_restorable,
             "passed": restorable, "detail": t.detail_restorable.format(backup=best["id"]) if restorable
             else t.detail_not_restorable},
            {"id": "newest_kept_verified", "label": t.check_newest_verified,
             "passed": bool(kept) and result["verified"][kept[0]["id"]],
             "detail": t.detail_newest_verified if kept and result["verified"][kept[0]["id"]]
             else t.detail_newest_damaged},
        ],
        "metrics": [{"id": "kept", "label": t.label_kept, "value": len(result["kept"])},
                    {"id": "removed", "label": t.label_removed, "value": len(result["removed"])},
                    {"id": "runs_lost", "label": t.label_runs_lost,
                     "value": total_runs - runs_in_best if best else t.value_not_applicable},
                    {"label": t.label_policy, "value": t.policy_names[inputs.policy]},
                    {"label": t.label_model_calls, "value": 0}, _note(context, t)],
        "table": {"columns": list(t.retention_columns), "rows": rows},
    })


def retention_answer(t: Texts, best: dict | None, acceptance: dict | None, total_runs: int) -> str:
    if best is None or acceptance is None or not acceptance["ok"]:
        return t.retention_answer_none
    lost = total_runs - (best["counts"]["runs"] if best["counts"] else 0)
    return t.retention_answer.format(backup=best["id"], lost=lost)
