"""Platform side of the lesson: the facts one run collects and the two lesson.report events built from them.

Every check is computed from the bank's rows and the saved position, never from what a tool result or
the model said. A check that did not apply to this run is left out rather than marked as passed.
"""
from dataclasses import dataclass, field

BODY_PREVIEW = 40


@dataclass
class RunTrace:
    resumed: bool
    stop_at: str
    status: str | None = None
    reason: str | None = None
    stopped_at: str = ""
    draft_requests: int = 0
    receipt_requests: int = 0
    approval: dict | None = None
    lookup: str = "not_asked"
    write: str = "not_asked"
    checkpoints: list = field(default_factory=list)

    @property
    def last_checkpoint(self) -> str:
        return f"{self.checkpoints[-1][1]} ({self.checkpoints[-1][0]})" if self.checkpoints else ""

    def end(self, status: str, reason: str) -> None:
        self.status, self.reason = status, reason

    def stop(self, point: str) -> bool:
        """True when the run is over or must end here; only a fresh run simulates the process dying."""
        if self.status is not None:
            return True
        if not self.resumed and self.stop_at == point:
            self.status, self.reason, self.stopped_at = "suspended", point, point
            return True
        return False

    def save_checkpoint(self, context, name: str, state: dict) -> None:
        self.checkpoints.append((name, context.checkpoint(name, state)))


def preview(text) -> str:
    return text if len(text) <= BODY_PREVIEW else text[:BODY_PREVIEW] + "…"


def publish_reports(context, t, state: dict | None, stored: list[dict], rows: list[dict], trace: RunTrace) -> None:
    """Two reports: what the bank holds, then what this run did and which guarantees held."""
    if stored:
        context.emit("lesson.report", {
            "title": t.ledger_title, "summary": t.ledger_summary,
            "metrics": [{"id": "rows-for-operation", "label": t.label_rows_operation, "value": len(rows)},
                        {"id": "rows-total", "label": t.label_rows_total, "value": len(stored)}],
            "table": {"columns": list(t.ledger_columns),
                      "rows": [[row["id"], row["operation_id"], row["title"], t.difficulty_names[row["difficulty"]],
                                t.origin_names[row["origin"]]] for row in stored]}})
    else:
        context.emit("lesson.report", {
            "title": t.ledger_title, "summary": t.ledger_empty,
            "metrics": [{"id": "rows-for-operation", "label": t.label_rows_operation, "value": 0},
                        {"id": "rows-total", "label": t.label_rows_total, "value": 0}]})
    context.emit("lesson.report", {
        "title": t.run_title, "summary": t.status_summaries[trace.status],
        "checks": _checks(t, state, rows, trace),
        "metrics": _metrics(context, t, state, rows, trace),
        "table": {"columns": list(t.diff_columns), "rows": _diff_rows(t, state, rows)}})


def _checks(t, state, rows, trace) -> list[dict]:
    checks = []
    approved = bool(state and state["step"] in ("approved", "saved"))
    checks.append({"id": "approval-gate", "label": t.check_gate, "passed": approved or not rows,
                   "detail": t.detail_gate.format(approved=t.yes_text if approved else t.no_text, rows=len(rows))})
    if rows or trace.write in ("written", "skipped"):
        checks.append({"id": "written-once", "label": t.check_once, "passed": len(rows) == 1,
                       "detail": t.detail_once.format(operation=state["operation_id"], rows=len(rows))})
    expected = 0 if trace.resumed else 1
    checks.append({"id": "draft-once", "label": t.check_draft, "passed": trace.draft_requests == expected,
                   "detail": t.detail_draft.format(count=trace.draft_requests,
                                                   kind=t.kind_names["resumed" if trace.resumed else "fresh"])})
    if state and state["edited"]:
        landed = all(row["title"] == state["approved"]["title"] and row["difficulty"] == state["approved"]["difficulty"]
                     and row["body"] == state["approved"]["body"] for row in rows)
        checks.append({"id": "edit-traced", "label": t.check_edit,
                       "passed": state["approved"] != state["draft"] and landed,
                       "detail": t.detail_edit.format(saved=t.yes_text if rows else t.no_text)})
    return checks


def _metrics(context, t, state, rows, trace) -> list[dict]:
    source = context.resumed_from
    approval = trace.approval
    if approval:
        approval_text = " / ".join([approval["outcome"], approval["decided_by"],
                                    t.edited_yes if approval["edited"] else t.edited_no])
    elif trace.resumed and state and state["approved_digest"]:
        approval_text = t.approval_carried
    else:
        approval_text = t.value_none
    return [
        {"id": "status", "label": t.label_status, "value": trace.status},
        {"id": "run-kind", "label": t.label_kind, "value": t.kind_names["resumed" if trace.resumed else "fresh"]},
        {"id": "thread", "label": t.label_thread, "value": (context.thread_id or "")[:8] or t.value_none},
        {"id": "resumed-from", "label": t.label_resumed_from,
         "value": f"{source['run_id'][:8]} / {source['checkpoint_id']} ({source['name']})" if source else t.value_none},
        {"id": "operation", "label": t.label_operation, "value": state["operation_id"] if state else t.value_none},
        {"id": "checkpoints", "label": t.label_checkpoints,
         "value": ", ".join(f"{cp} {name}" for name, cp in trace.checkpoints) or t.value_none},
        {"id": "approval", "label": t.label_approval, "value": approval_text},
        {"id": "lookup", "label": t.label_lookup, "value": t.lookup_names[trace.lookup]},
        {"id": "write", "label": t.label_write, "value": t.write_names[trace.write]},
        {"id": "rows", "label": t.label_rows_operation, "value": len(rows)},
        {"id": "model-calls", "label": t.label_model_calls, "value": trace.draft_requests + trace.receipt_requests},
        {"id": "note", "label": t.label_note, "value": context.question or t.value_none},
    ]


def _diff_rows(t, state, rows) -> list[list]:
    """Field by field: the model's draft, what the person approved and what the bank holds."""
    dash = t.value_none
    draft = state["draft"] if state else None
    approved = state["approved"] if state else None
    saved = rows[0] if rows else None
    out = []
    for field_name, label in (("title", t.field_title), ("difficulty", t.field_difficulty), ("body", t.field_body)):
        cells = []
        for source in (draft, approved, saved):
            value = source[field_name] if source else dash
            cells.append(t.difficulty_names[value] if field_name == "difficulty" and source else
                         preview(value) if field_name == "body" and source else value)
        out.append([label, *cells])
    return out
