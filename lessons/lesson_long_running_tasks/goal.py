"""The runner's goal check after every round: ok, impossible or continue, with the reason.

It reads only what the executor really ran and what the model submitted: jobs and their delivered results, and the
latest report. What the model says in prose never counts. This is the small version of a loop that decides for
itself when to stop; the budget rule at the end turns "continue" into an explicit stop when the rounds run out.
"""

# What each scenario must produce: one background job kind per required value in the report.
SCENARIOS = {"nightly": ("checksum_pack", "grade_stats"),
             "late": ("checksum_pack", "late_import"),
             "deep": ("checksum_pack", "deep_scan")}


def evaluate_goal(t, required, jobs, report, max_attempts: int) -> dict:
    """Judge one round. A kind counts as done only when a job of it completed AND its result was handed over."""
    checks, attempts, done = [], {}, {}
    for kind in required:
        mine = [job for job in jobs if job.kind == kind]
        attempts[kind] = len(mine)
        finished = [job for job in mine if job.status == "completed" and job.delivered]
        running = [job for job in mine if job.status == "running"]
        if finished:
            done[kind] = finished[-1]
            status, detail = "done", t.goal_done.format(job=finished[-1].id)
        elif running:
            status, detail = "running", t.goal_running.format(job=running[-1].id)
        elif len(mine) >= max_attempts:
            status, detail = "exhausted", t.goal_exhausted.format(attempts=len(mine), limit=max_attempts)
        else:
            status, detail = "open", t.goal_open.format(attempts=len(mine), limit=max_attempts)
        checks.append({"id": kind, "status": status, "detail": detail})
    status_of = {check["id"]: check["status"] for check in checks}
    all_done = all(status == "done" for status in status_of.values())
    checks.append(_report_check(t, required, done, report, all_done))
    report_status = checks[-1]["status"]
    # Order matters: success first, then a goal that can no longer be reached, then what is still to do.
    exhausted = [kind for kind, status in status_of.items() if status == "exhausted"]
    if all_done and report_status == "match":
        code, args = "goal_met", {}
    elif exhausted:
        code, args = "kind_exhausted", {"kind": t.list_separator.join(exhausted), "attempts": attempts[exhausted[0]],
                                        "limit": max_attempts}
    elif all_done:
        code = "report_missing" if report_status == "missing" else "report_mismatch"
        args = {"detail": checks[-1]["detail"]}
    elif "running" in status_of.values():
        code, args = "waiting", {"jobs": t.list_separator.join(
            kind for kind, status in status_of.items() if status == "running")}
    else:
        code, args = "open", {"kinds": t.list_separator.join(kind for kind, status in status_of.items() if status == "open")}
    verdict = {"goal_met": "ok", "kind_exhausted": "impossible"}.get(code, "continue")
    return {"verdict": verdict, "reason_code": code, "reason": t.reasons[code].format(**args),
            "checks": checks, "attempts": attempts}


def _report_check(t, required, done, report, all_done) -> dict:
    if not all_done:
        return {"id": "report", "status": "waiting", "detail": t.report_waiting}
    if report is None:
        return {"id": "report", "status": "missing", "detail": t.report_missing}
    problems = []
    for kind in required:
        submitted = report["items"].get(kind)
        real = done[kind].result["value"]
        if submitted is None:
            problems.append(t.report_lacks.format(kind=kind))
        elif submitted != real:
            problems.append(t.report_differs.format(kind=kind))
    if problems:
        return {"id": "report", "status": "mismatch", "detail": t.list_separator.join(problems)}
    return {"id": "report", "status": "match", "detail": t.report_match}


def decide(goal: dict, round_number: int, max_rounds: int) -> dict:
    """Stop on ok or impossible; otherwise stop only when the round budget is used up, and say so."""
    if goal["verdict"] == "ok":
        return {"stop": True, "outcome": "completed"}
    if goal["verdict"] == "impossible":
        return {"stop": True, "outcome": "abandoned"}
    if round_number >= max_rounds:
        return {"stop": True, "outcome": "budget_exhausted"}
    return {"stop": False, "outcome": None}
