"""The work the background jobs really do.

Every job computes something for real (a SHA-256, a mean, a parse, a duplicate scan) on fixed data, so the same
run always yields the same result and a test can recompute it. Only the time is declared: each step names the
seconds it takes, and executor.py waits for the virtual clock to reach that moment before the step runs.
Texts for errors and details come from the run's language catalog.
"""
import hashlib
from dataclasses import dataclass
from typing import Callable

# Six submission packs, a dozen scores, a late-score sheet with one broken row, eight shards of which two repeat.
PACK = tuple((f"s{n:02d}.zip", (f"submission-{n}|" * 300).encode()) for n in range(1, 7))
SCORES = (88, 92, 45, 71, 60, 59, 77, 83, 38, 95, 66, 74)
PASS_LINE = 60
LATE_ROWS = ("s01,88", "s02,92", "s03,45", "s04,71", "s05,60", "s06,8x",
             "s07,77", "s08,83", "s09,38", "s10,95", "s11,66", "s12,74")
SHARDS = tuple(f"shard-{1 if n in (3, 6) else n}" for n in range(1, 9))


@dataclass(frozen=True)
class JobSpec:
    kind: str
    steps: int
    step_seconds: int  # virtual seconds one step takes
    timeout_seconds: int  # default deadline; the model may ask for another
    work: Callable[[dict, int, object], None]  # one step of real work: (state, step index, texts)
    finish: Callable[[dict, object], dict]  # {"value": short string, "detail": sentence}


def _checksum_step(state, index, t):
    hasher = state.setdefault("hasher", hashlib.sha256())
    for _, body in PACK[index * 2:index * 2 + 2]:
        hasher.update(body)
        state["bytes"] = state.get("bytes", 0) + len(body)
        state["files"] = state.get("files", 0) + 1


def _checksum_finish(state, t):
    digest = state["hasher"].hexdigest()[:12]
    return {"value": digest, "detail": t.detail_checksum.format(files=state["files"], size=state["bytes"], digest=digest)}


def _grades_step(state, index, t):
    for score in SCORES[index * 6:index * 6 + 6]:
        state["sum"] = state.get("sum", 0) + score
        state["passed"] = state.get("passed", 0) + (score >= PASS_LINE)
        state["rows"] = state.get("rows", 0) + 1


def _grades_finish(state, t):
    mean = round(state["sum"] / state["rows"], 1)
    return {"value": str(state["passed"]),
            "detail": t.detail_grades.format(passed=state["passed"], total=state["rows"], line=PASS_LINE, mean=mean)}


def _import_step(state, index, t):
    first, last = (0, 5) if index == 0 else (5, len(LATE_ROWS))
    for number in range(first, last):
        raw = LATE_ROWS[number].split(",")[1]
        try:
            state.setdefault("scores", []).append(int(raw))
        except ValueError:
            # Re-raised in the run's language: the model reads this text in the injected result.
            raise ValueError(t.bad_score.format(row=number + 1, value=raw)) from None


def _import_finish(state, t):
    return {"value": str(len(state["scores"])), "detail": t.detail_import.format(rows=len(state["scores"]))}


def _scan_step(state, index, t):
    digest = hashlib.sha256(SHARDS[index].encode()).hexdigest()
    seen = state.setdefault("seen", set())
    state["duplicates"] = state.get("duplicates", 0) + (digest in seen)
    seen.add(digest)


def _scan_finish(state, t):
    return {"value": str(state["duplicates"]),
            "detail": t.detail_scan.format(shards=len(SHARDS), duplicates=state["duplicates"])}


# The last timeout is shorter than the scan's 80 virtual seconds on purpose: left alone, deep_scan times out.
SPECS = {spec.kind: spec for spec in (
    JobSpec("checksum_pack", 3, 4, 30, _checksum_step, _checksum_finish),
    JobSpec("grade_stats", 2, 3, 30, _grades_step, _grades_finish),
    JobSpec("late_import", 2, 3, 30, _import_step, _import_finish),
    JobSpec("deep_scan", 8, 10, 40, _scan_step, _scan_finish),
)}
