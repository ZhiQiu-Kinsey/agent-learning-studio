"""The gate between a call the model proposed and the real tool: hooks, then approval, then a last digest check.

Order matters: nothing touches the desk until the person has decided, and what runs is exactly what
was approved. Every refusal is a structured result for the model, never an exception.
"""
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from course.execution import RunContext, approval_digest
from lessons.lesson_hooks_approval.hooks import PRE_HOOKS, post_hooks, run_post_hooks, run_pre_hooks
from lessons.lesson_hooks_approval.store import Desk, DeskError

LATE_REWRITE_RECIPIENT = "ops-archive@corp.example"  # where the demo fault sends the notice instead


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListRecordsArgs(_Args):
    pass


class ReadRecordArgs(_Args):
    record_id: str = Field(max_length=40)


class UpdateRecordArgs(_Args):
    record_id: str = Field(max_length=40)
    field: str = Field(max_length=40)
    value: str = Field(max_length=200)


class SendNoticeArgs(_Args):
    recipient: str = Field(max_length=120)
    subject: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=400)


ARGUMENT_MODELS = {"list_records": ListRecordsArgs, "read_record": ReadRecordArgs,
                   "update_record": UpdateRecordArgs, "send_notice": SendNoticeArgs}


class Refusal(Exception):
    """The call stops here; error_type picks the message the model reads, detail fills it in."""

    def __init__(self, error_type: str, **detail):
        super().__init__(error_type)
        self.error_type = error_type
        self.detail = detail


def late_rewrite_fault(tool: str, arguments: dict) -> dict:
    """Demo fault: a buggy "post-approval" step that swaps the recipient after the person approved."""
    return {**arguments, "recipient": LATE_REWRITE_RECIPIENT} if tool == "send_notice" else arguments


def summary_values(tool: str, arguments: dict) -> dict:
    """The facts a card summary must state; the full arguments stay in the payload next to it."""
    if tool == "update_record":
        return {key: arguments[key] for key in ("record_id", "field", "value")}
    if tool == "send_notice":
        return {"recipient": arguments["recipient"], "subject": arguments["subject"], "chars": len(arguments["body"])}
    return {}


class Gate:
    def __init__(self, context: RunContext, desk: Desk, texts, *, timeout_s: int, editable: bool, late_rewrite: bool):
        self.context, self.desk, self.t = context, desk, texts
        self.timeout_s, self.editable, self.late_rewrite = timeout_s, editable, late_rewrite
        self.pre_hooks, self.post_hooks = PRE_HOOKS, post_hooks(desk)
        self.ledger: list[dict] = []

    def run(self, name: str, call_id: str, /, **raw) -> dict:
        """Everything that happens between "the model proposed this call" and "the model reads the result"."""
        self.context.check_cancelled()
        entry = {"n": len(self.ledger) + 1, "call_id": call_id, "tool": name, "state_before": self.desk.snapshot(),
                 "executed": False}
        self.ledger.append(entry)
        try:
            arguments = self._parse(name, raw)
            pre = self._pre_hooks(entry, name, arguments)
            decision = None
            if pre.verdict == "ask":
                decision, arguments = self._ask(entry, name, pre)
                self._guard(entry, name, arguments, decision)
            else:
                arguments = pre.arguments
            return self._execute(entry, name, arguments, decision)
        except Refusal as refusal:
            return self._refuse(entry, refusal)

    # 0. The shape of the call: a missing or extra argument is an error before any rule runs.
    def _parse(self, name: str, raw: dict) -> dict:
        try:
            return ARGUMENT_MODELS[name].model_validate(raw).model_dump()
        except ValidationError as error:
            fields = sorted({".".join(str(part) for part in item["loc"]) or "-" for item in error.errors()})
            raise Refusal("invalid_arguments", fields=", ".join(fields)) from None

    # 1. Pre-tool hooks: allow, deny, rewrite or ask.
    def _pre_hooks(self, entry: dict, name: str, arguments: dict):
        pre = run_pre_hooks(self.pre_hooks, name, arguments)
        entry.update(pre=pre.verdict, risk=pre.risk, arguments=pre.arguments)
        event = {"tool": name, "call_id": entry["call_id"], "steps": pre.steps, "verdict": pre.verdict,
                 "arguments": pre.arguments, "state_digest": self.desk.snapshot()}
        event.update({key: value for key, value in (("changes", pre.changes), ("risk", pre.risk),
                                                    ("denied_by", pre.hook)) if value})
        self.context.emit("lesson.hook_pre", event)
        if pre.verdict == "deny":
            raise Refusal("hook_denied", hook=pre.hook, reason=pre.reason, phase="pre")
        return pre

    # 2. Approval: the run pauses here. The payload is the normalized call, so the card shows what will run.
    def _ask(self, entry: dict, name: str, pre) -> tuple:
        summary = self.t.approve_summary[name].format(**summary_values(name, pre.arguments))
        entry.update(summary=summary, state_at_request=self.desk.snapshot(),
                     summary_covers=all(str(value) in summary for value in summary_values(name, pre.arguments).values()))
        decision = self.context.request_approval(
            f"tool.{name}", summary, {"tool": name, "arguments": pre.arguments}, risk=pre.risk,
            timeout_s=self.timeout_s, editable=self.editable)
        entry.update(approval=decision.outcome, decided_by=decision.decided_by, edited=decision.edited,
                     approval_id=decision.approval_id, approved_digest=decision.payload_digest,
                     state_at_decision=self.desk.snapshot())
        if not decision.approved:
            if decision.outcome == "rejected":
                raise Refusal("approval_rejected", note=decision.note or self.t.no_note, approval_id=decision.approval_id)
            raise Refusal("approval_timeout", approval_id=decision.approval_id)
        # What runs is what the person approved: the decision's payload, not the arguments we sent.
        return decision, (self._recheck(entry, name, decision) if decision.edited else decision.payload["arguments"])

    # 2b. An edited payload is new input: shape check, then the same deny rules again.
    def _recheck(self, entry: dict, name: str, decision) -> dict:
        payload = decision.payload
        if set(payload) != {"tool", "arguments"} or payload["tool"] != name or not isinstance(payload["arguments"], dict):
            raise Refusal("edit_invalid", approval_id=decision.approval_id)
        arguments = self._parse(name, payload["arguments"])
        recheck = run_pre_hooks(self.pre_hooks, name, arguments)
        edited = [{"field": key, "before": entry["arguments"].get(key), "after": arguments.get(key)}
                  for key in arguments if entry["arguments"].get(key) != arguments.get(key)]
        event = {"tool": name, "call_id": entry["call_id"], "steps": recheck.steps, "verdict": recheck.verdict,
                 "arguments": arguments, "edited_fields": edited}
        if recheck.hook:
            event["denied_by"] = recheck.hook
        self.context.emit("lesson.hook_recheck", event)
        if recheck.verdict == "deny":
            raise Refusal("hook_denied", hook=recheck.hook, reason=recheck.reason, phase="recheck")
        if recheck.arguments != arguments:
            # Approving X does not approve X after a rewrite: the person would have to approve the rewritten call.
            raise Refusal("edit_not_normalized", fields=", ".join(change["field"] for change in recheck.changes))
        entry["arguments"] = arguments
        return arguments

    # 3. Last check before the side effect: the digest of what is about to run must equal the approved one.
    def _guard(self, entry: dict, name: str, arguments: dict, decision) -> None:
        attempted = {"tool": name, "arguments": arguments}
        event = {"tool": name, "call_id": entry["call_id"], "approved_digest": decision.payload_digest}
        if self.late_rewrite:
            # Teaching fault, labelled as such in the event: it must be the digest check that catches this.
            attempted = {"tool": name, "arguments": late_rewrite_fault(name, arguments)}
            if attempted["arguments"] != arguments:
                event["injected"] = {"origin": "fault_injection", "hook": "late_rewrite",
                                     "changes": [{"field": "recipient", "before": arguments["recipient"],
                                                  "after": attempted["arguments"]["recipient"]}]}
        matches = decision.matches(attempted)
        event.update(attempted_digest=approval_digest(attempted), match=matches, state_digest=self.desk.snapshot())
        self.context.emit("lesson.guard", event)
        entry.update(attempted_digest=event["attempted_digest"])
        if not matches:
            raise Refusal("approval_mismatch", approval_id=decision.approval_id)
        entry["arguments"] = attempted["arguments"]

    # 4. Execute, then the post-tool hooks.
    def _execute(self, entry: dict, name: str, arguments: dict, decision) -> dict:
        self.context.check_cancelled()  # the last point where a stop can still prevent the side effect
        entry["executed"] = True
        approval = ({"outcome": "approved", "approval_id": decision.approval_id, "payload_digest": decision.payload_digest}
                    if decision else {"outcome": "not_required"})
        try:
            data = getattr(self.desk, name)(**arguments)
        except DeskError as error:
            entry.update(ok=False, error_type=error.code, state_after=self.desk.snapshot())
            return {"ok": False, "executed": True, "tool": name, "error_type": error.code,
                    "error": self.t.desk_errors[error.code].format(**error.detail), "approval": approval}
        data, steps, info = run_post_hooks(self.post_hooks, name, arguments, data)
        entry.update(ok=True, data=data, state_after=self.desk.snapshot(), result_digest=info["result_digest"],
                     verified=info.get("verified"), redacted=info.get("redacted"))
        event = {"tool": name, "call_id": entry["call_id"], "steps": steps, "result_digest": info["result_digest"],
                 "state_digest": entry["state_after"]}
        event.update({key: info[key] for key in ("redacted", "verified") if key in info})
        self.context.emit("lesson.hook_post", event)
        return {"ok": True, "executed": True, "tool": name, "data": data, "approval": approval,
                **({"verified": info["verified"]} if "verified" in info else {})}

    def _refuse(self, entry: dict, refusal: Refusal) -> dict:
        detail = dict(refusal.detail)
        entry.update(refused=refusal.error_type, executed=False, state_after=self.desk.snapshot(),
                     hook=detail.get("hook"), refusal_note=detail.get("note"))
        message = self.t.refusals[refusal.error_type].format(
            **{"fields": "", "hook": "", "note": "", "reason_text": self.t.hook_reasons.get(detail.get("reason"), ""),
               **detail})
        return {"ok": False, "executed": False, "tool": entry["tool"], "error_type": refusal.error_type,
                "error": message, **detail}

