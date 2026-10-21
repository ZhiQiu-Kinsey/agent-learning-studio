"""Hooks and an approval gate in front of four real tools that change a small ticket desk.

The model proposes calls; lessons/lesson_hooks_approval/gate.py decides, in order, what happens to each
one (pre-tool hooks, a person's approval, a digest check, the tool, post-tool hooks) and the ledger
built there, not the model's last sentence, says what was and was not done. The shape follows the
permission and hook chapters of learn-claude-code and the pre-action-gate notes of the Microsoft
course; the code and the experiments are written for this project.
"""
import json
import tempfile
from functools import partial
from pathlib import Path
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_hooks_approval.gate import ARGUMENT_MODELS, Gate
from lessons.lesson_hooks_approval.locales import Texts, texts_for
from lessons.lesson_hooks_approval.store import CORP_DOMAIN, Desk

TOOL_NAMES = tuple(ARGUMENT_MODELS)
WRITE_TOOLS = ("update_record", "send_notice")
EFFECT_FIELDS = ("status", "owner", "note")


class Inputs(LessonInputs):
    task: Literal["approve_write", "reject_timeout", "edit_recheck", "swap_guard"] = "approve_write"
    approval_timeout_s: int = Field(default=30, ge=3, le=300)
    allow_edit: bool = False
    late_rewrite: bool = False


INPUT_MODEL = Inputs


def tool_definitions(locale: str) -> list[dict]:
    """What the model sees. Tool and argument names are code; only the descriptions are translated."""
    t = texts_for(locale)
    names = {"list_records": [], "read_record": ["record_id"], "update_record": ["record_id", "field", "value"],
             "send_notice": ["recipient", "subject", "body"]}
    return [{"type": "function", "function": {
        "name": tool, "description": t.tool_descriptions[tool],
        "parameters": {"type": "object", "additionalProperties": False, "required": params,
                       "properties": {param: {"type": "string", "description": t.param_descriptions[param]}
                                      for param in params}}}} for tool, params in names.items()]


def agent_loop(context: RunContext, gate: Gate, tools: list[dict], system: str, task: str) -> tuple[str | None, int]:
    """Ask the model, hand every proposed call to the gate, return its results, until it stops asking.

    Returns the last reply (None when the model-call budget ran out first) and the number of model calls.
    """
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task}]
    for step_number in range(1, context.max_model_calls + 1):
        # 1. Every request carries the whole history and all four tools.
        response = context.complete({"messages": messages, "tools": tools, "tool_choice": "auto",
                                     "temperature": 0}, step_number)
        message = response["choices"][0].get("message", {})
        calls = message.get("tool_calls") or []
        # 2. No call proposed: the content is the last reply, which is a claim, not a result.
        if not calls:
            return message.get("content") or "", step_number
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
        for call in calls:
            # 3. The gate, not the model, decides whether a call becomes an action; the call id travels with it.
            available = {name: partial(gate.run, name, call["id"]) for name in TOOL_NAMES}
            result = context.execute_proposal(call, available)
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    return None, context.max_model_calls


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    t = texts_for(context.locale)
    context.check_cancelled()
    with tempfile.TemporaryDirectory(prefix="hooks-approval-") as directory:
        desk = Desk(Path(directory), t.record_titles)
        gate = Gate(context, desk, t, timeout_s=values.approval_timeout_s, editable=values.allow_edit,
                    late_rewrite=values.late_rewrite)
        before = desk.records()
        _report_hooks(context, gate, values, t)
        claim, model_calls = agent_loop(context, gate, tool_definitions(context.locale), t.system_prompt,
                                        t.tasks[values.task])
        _report_gate(context, gate, desk, t)
        effects = _effects(desk, before)
        _report_effects(context, gate, effects, claim, t)
    return _answer(gate, effects, claim, context.max_model_calls, t)


# ---------- evidence: everything below reads the ledger and the desk, never the model's words ----------

def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


def _short(digest: str | None) -> str:
    return digest[:19] + "..." if digest else "—"


def _yes_no(flag: bool, t: Texts) -> str:
    return t.value_yes if flag else t.value_no


def _effects(desk: Desk, before: dict) -> dict:
    """What really changed in the desk, read from the files."""
    after = desk.records()
    records = [(rid, key, before[rid][key], after[rid][key]) for rid in after for key in EFFECT_FIELDS
               if before[rid][key] != after[rid][key]]
    return {"records": records, "notices": desk.outbox()}


def _report_hooks(context: RunContext, gate: Gate, values: Inputs, t: Texts) -> None:
    """Report 1: which hooks stand in front of the tools and which knobs this run has."""
    rows = [[t.phase_pre, hook.name, t.hook_roles[hook.name], t.hook_rules[hook.name]] for hook in gate.pre_hooks]
    rows += [[t.phase_post, hook.name, t.hook_roles[hook.name], t.hook_rules[hook.name]] for hook in gate.post_hooks]
    context.emit("lesson.report", {
        "title": t.hooks_title, "summary": t.hooks_summary.format(domain=CORP_DOMAIN), "checks": [],
        "metrics": [
            {"id": "pre-hooks", "label": t.label_pre_hooks, "value": len(gate.pre_hooks)},
            {"id": "post-hooks", "label": t.label_post_hooks, "value": len(gate.post_hooks)},
            {"id": "approval-timeout", "label": t.label_timeout, "value": values.approval_timeout_s},
            {"id": "editable", "label": t.label_editable, "value": _yes_no(values.allow_edit, t)},
            {"id": "late-rewrite", "label": t.label_late_rewrite, "value": _yes_no(values.late_rewrite, t)},
        ],
        "table": {"columns": list(t.hook_columns), "rows": rows}})


def _approval_cell(entry: dict, t: Texts) -> str:
    if "approval" not in entry:
        return t.approval_labels["not_asked"]
    cell = t.approval_labels[entry["approval"]]
    return cell + t.cell_edited if entry["edited"] else cell


def _outcome_cell(entry: dict, t: Texts) -> str:
    if entry.get("refused"):
        return t.refusal_labels[entry["refused"]].format(hook=entry.get("hook") or "")
    return t.cell_executed if entry["executed"] else t.cell_none


def _report_gate(context: RunContext, gate: Gate, desk: Desk, t: Texts) -> None:
    """Report 2: every call with its hook verdict, approval, digests and what the desk looked like around it."""
    ledger = gate.ledger
    asked = [entry for entry in ledger if "approval" in entry]
    gated_runs = [entry for entry in asked if entry["executed"]]
    refused = [entry for entry in ledger if entry.get("refused")]
    reads = [entry for entry in ledger if entry["tool"] == "read_record" and entry.get("ok")]

    def check(check_id: str, label: str, entries: list, passed: bool, passed_detail: str, failed_detail: str, none_detail: str):
        if not entries:
            return {"id": check_id, "label": label, "detail": none_detail}  # nothing ran: no verdict either way
        return {"id": check_id, "label": label, "passed": passed, "detail": passed_detail if passed else failed_detail}

    def leaked(entry: dict) -> bool:
        raw = desk.records()[entry["arguments"]["record_id"]]
        seen = json.dumps(entry["data"], ensure_ascii=False)
        return raw["customer_phone"] in seen or raw["customer_email"] in seen

    checks = [
        check("no-early-effect", t.check_no_early_effect, asked,
              all(entry["state_at_decision"] == entry["state_at_request"] for entry in asked),
              t.detail_no_early_effect.format(count=len(asked)), t.detail_early_effect, t.detail_no_approvals),
        check("args-match-approval", t.check_args_match, gated_runs,
              all(entry["attempted_digest"] == entry["approved_digest"] for entry in gated_runs),
              t.detail_args_match.format(count=len(gated_runs)), t.detail_args_differ, t.detail_nothing_gated_ran),
        check("refused-not-executed", t.check_refused_not_run, refused,
              all(not entry["executed"] and entry["state_after"] == entry["state_before"] for entry in refused),
              t.detail_refused_not_run.format(count=len(refused)), t.detail_refused_ran, t.detail_nothing_refused),
        check("summary-covers-args", t.check_summary_covers, asked,
              all(entry["summary_covers"] for entry in asked),
              t.detail_summary_covers.format(count=len(asked)), t.detail_summary_misses, t.detail_no_approvals),
        check("customer-data-redacted", t.check_redacted, reads, not any(leaked(entry) for entry in reads),
              t.detail_redacted.format(count=len(reads)), t.detail_leaked, t.detail_no_reads),
    ]
    rows = []
    for entry in ledger:
        rows.append([entry["n"], entry["tool"], t.risk_labels.get(entry.get("risk"), t.cell_none),
                     t.verdict_labels.get(entry.get("pre"), t.cell_none), _approval_cell(entry, t),
                     _outcome_cell(entry, t), _short(entry.get("approved_digest")), _short(entry.get("attempted_digest")),
                     _short(entry.get("result_digest"))])
    count = lambda predicate: sum(1 for entry in ledger if predicate(entry))  # noqa: E731
    context.emit("lesson.report", {
        "title": t.gate_title, "summary": t.gate_summary, "checks": checks,
        "metrics": [
            {"id": "tool-calls", "label": t.label_tool_calls, "value": len(ledger)},
            {"id": "ran-without-approval", "label": t.label_ran_plain,
             "value": count(lambda e: e["executed"] and "approval" not in e)},
            {"id": "approved", "label": t.label_approved, "value": count(lambda e: e.get("approval") == "approved")},
            {"id": "rejected", "label": t.label_rejected, "value": count(lambda e: e.get("approval") == "rejected")},
            {"id": "timeouts", "label": t.label_timeouts, "value": count(lambda e: e.get("approval") == "timeout")},
            {"id": "hook-denied", "label": t.label_hook_denied, "value": count(lambda e: e.get("refused") == "hook_denied")},
            {"id": "guard-blocked", "label": t.label_guard_blocked,
             "value": count(lambda e: e.get("refused") == "approval_mismatch")},
            {"id": "edited", "label": t.label_edited, "value": count(lambda e: e.get("edited"))},
        ],
        "table": {"columns": list(t.gate_columns), "rows": rows}})


def _report_effects(context: RunContext, gate: Gate, effects: dict, claim: str | None, t: Texts) -> None:
    """Report 3: the desk after the run, set against the ledger; the model's last sentence comes last."""
    ledger = gate.ledger
    updates = [entry for entry in ledger if entry["tool"] == "update_record" and entry.get("ok")
               and entry["data"]["before"] != entry["data"]["after"]]
    sent = [entry for entry in ledger if entry["tool"] == "send_notice" and entry.get("ok")]
    matches = len(updates) == len(effects["records"]) and len(sent) == len(effects["notices"])
    rows = [[t.kind_record, f"{rid}.{key}", before, after] for rid, key, before, after in effects["records"]]
    rows += [[t.kind_notice, notice["notice_id"], notice["recipient"], notice["subject"]] for notice in effects["notices"]]
    context.emit("lesson.report", {
        "title": t.effects_title, "summary": t.effects_summary,
        "checks": [{"id": "effects-match-ledger", "label": t.check_effects_match, "passed": matches,
                    "detail": t.detail_effects_match.format(records=len(updates), notices=len(sent))
                    if matches else t.detail_effects_differ.format(
                        records=len(effects["records"]), notices=len(effects["notices"]),
                        ledger_records=len(updates), ledger_notices=len(sent))}],
        "metrics": [
            {"id": "records-changed", "label": t.label_records_changed, "value": len(effects["records"])},
            {"id": "notices-written", "label": t.label_notices_written, "value": len(effects["notices"])},
            {"id": "agent-claim", "label": t.label_agent_claim, "value": _clip(claim, 600) if claim else t.value_no_claim},
        ],
        "table": {"columns": list(t.effects_columns), "rows": rows}})


def _answer(gate: Gate, effects: dict, claim: str | None, limit: int, t: Texts) -> str:
    """The run's answer: what the ledger and the desk show first, then what the model said."""
    ledger = gate.ledger
    refused = [entry for entry in ledger if entry.get("refused")]
    plain = sum(1 for entry in ledger if entry["executed"] and "approval" not in entry)
    approved = sum(1 for entry in ledger if entry["executed"] and "approval" in entry)
    lines = [t.answer_summary.format(calls=len(ledger), plain=plain, approved=approved, refused=len(refused))]
    if refused:
        lines.append(t.answer_refused_head)
        lines += [t.answer_refused_line.format(n=entry["n"], tool=entry["tool"],
                                               reason=t.refusal_labels[entry["refused"]].format(hook=entry.get("hook") or ""))
                  for entry in refused]
    lines.append(t.answer_effects.format(records=len(effects["records"]), notices=len(effects["notices"])))
    tail = t.answer_claim.format(claim=_clip(claim, 600)) if claim is not None else t.answer_no_claim.format(limit=limit)
    return "\n".join(lines) + "\n\n" + tail
