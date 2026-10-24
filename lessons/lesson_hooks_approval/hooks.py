"""Hooks: small functions that run before and after a tool, so no tool has to carry its own checks.

A pre-tool hook looks at the call and returns a verdict: allow, deny, rewrite the arguments, or
ask a person. A post-tool hook looks at what the tool returned and may change or record it.
The chain, not the hooks, decides what the verdicts add up to.
"""
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from course.execution import approval_digest
from lessons.lesson_hooks_approval.store import CORP_DOMAIN, FIELDS, STATUSES

RISKS = ("low", "medium", "high", "critical")
VERDICTS = ("allow", "deny", "rewrite", "ask")
READ_TOOLS = ("list_records", "read_record")
BROADCAST = (f"all@{CORP_DOMAIN}",)
RECORD_ID = re.compile(r"TKT-\d{3}")
RECIPIENT = re.compile(r"[a-z0-9._-]+@" + re.escape(CORP_DOMAIN))


@dataclass(frozen=True)
class HookResult:
    verdict: str
    reason: str = ""
    arguments: dict | None = None  # rewrite only: the complete replacement
    risk: str | None = None  # ask only

    def __post_init__(self):
        if self.verdict not in VERDICTS:
            raise ValueError(f"a hook verdict must be one of {VERDICTS}")
        if (self.verdict == "rewrite") != (self.arguments is not None):
            raise ValueError("only a rewrite carries arguments, and a rewrite must carry them")
        if (self.verdict == "ask") != (self.risk is not None) or (self.risk is not None and self.risk not in RISKS):
            raise ValueError(f"only an ask carries a risk, one of {RISKS}")


ALLOW = HookResult("allow")


@dataclass(frozen=True)
class Hook:
    name: str
    run: Callable[..., Any]


# ---------- pre-tool hooks: (tool, arguments) -> HookResult ----------

def normalize_arguments(tool: str, arguments: dict) -> HookResult:
    """One spelling per meaning, so the rules after it and the approval digest see the same bytes."""
    fixed = dict(arguments)
    if "record_id" in fixed:
        fixed["record_id"] = fixed["record_id"].strip().upper()
    if "recipient" in fixed:
        fixed["recipient"] = fixed["recipient"].strip().lower()
    if "field" in fixed:
        fixed["field"] = fixed["field"].strip().lower()
        if fixed["field"] == "status":
            fixed["value"] = fixed["value"].strip().lower()
    return HookResult("rewrite", "normalized", arguments=fixed) if fixed != arguments else ALLOW


def record_scope(tool: str, arguments: dict) -> HookResult:
    record_id = arguments.get("record_id")
    return HookResult("deny", "record_id_format") if record_id is not None and not RECORD_ID.fullmatch(record_id) else ALLOW


def recipient_domain(tool: str, arguments: dict) -> HookResult:
    recipient = arguments.get("recipient")
    return HookResult("deny", "recipient_outside_domain") if recipient is not None and not RECIPIENT.fullmatch(recipient) else ALLOW


def field_allowlist(tool: str, arguments: dict) -> HookResult:
    if tool != "update_record":
        return ALLOW
    if arguments["field"] not in FIELDS:
        return HookResult("deny", "field_not_allowed")
    if arguments["field"] == "status" and arguments["value"] not in STATUSES:
        return HookResult("deny", "status_not_allowed")
    return ALLOW


def risk_level(tool: str, arguments: dict) -> HookResult:
    """Read tools pass. A write asks, and how risky it is decides what the card says. Unclassified tools never run."""
    if tool in READ_TOOLS:
        return ALLOW
    if tool == "update_record":
        closes = arguments["field"] == "status" and arguments["value"] == "closed"
        return HookResult("ask", "write_needs_approval", risk="high" if closes or arguments["field"] == "owner" else "medium")
    if tool == "send_notice":
        return HookResult("ask", "write_needs_approval", risk="critical" if arguments["recipient"] in BROADCAST else "high")
    return HookResult("deny", "tool_not_classified")


PRE_HOOKS = (
    Hook("normalize_arguments", normalize_arguments),
    Hook("record_scope", record_scope),
    Hook("recipient_domain", recipient_domain),
    Hook("field_allowlist", field_allowlist),
    Hook("risk_level", risk_level),
)


@dataclass
class PreOutcome:
    verdict: str  # allow | deny | ask
    arguments: dict  # after every rewrite
    risk: str | None = None
    hook: str | None = None  # the hook that denied
    reason: str | None = None
    steps: list = field(default_factory=list)
    changes: list = field(default_factory=list)  # [{field, before, after}] over all rewrites


def run_pre_hooks(hooks: tuple[Hook, ...], tool: str, arguments: dict) -> PreOutcome:
    """Run the hooks in order. Deny stops the chain, rewrite feeds its arguments to the next hook, ask is remembered."""
    outcome = PreOutcome("allow", dict(arguments))
    for hook in hooks:
        result = hook.run(tool, outcome.arguments)
        step = {"id": hook.name, "verdict": result.verdict}
        if result.reason:
            step["reason"] = result.reason
        if result.verdict == "rewrite":
            step["changes"] = _diff(outcome.arguments, result.arguments)
            outcome.changes += step["changes"]
            outcome.arguments = result.arguments
        outcome.steps.append(step)
        if result.verdict == "deny":
            outcome.verdict, outcome.hook, outcome.reason = "deny", hook.name, result.reason
            return outcome
        if result.verdict == "ask":
            outcome.verdict = "ask"
            if outcome.risk is None or RISKS.index(result.risk) > RISKS.index(outcome.risk):
                outcome.risk = result.risk
    return outcome


def _diff(before: dict, after: dict) -> list[dict]:
    return [{"field": key, "before": before.get(key), "after": after.get(key)}
            for key in dict.fromkeys([*before, *after]) if before.get(key) != after.get(key)]


# ---------- post-tool hooks: (tool, arguments, data) -> (data, info) ----------

def mask_phone(phone: str) -> str:
    return phone[:3] + "*" * (len(phone) - 7) + phone[-4:] if len(phone) >= 8 else "*" * len(phone)


def mask_email(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:1]}***@{domain}"


def redact_customer_data(tool: str, arguments: dict, data: Any) -> tuple[Any, dict]:
    """The model never needs a customer's phone or email to change a ticket, so it never gets them."""
    if tool != "read_record":
        return data, {}
    masked = {"customer_phone": mask_phone, "customer_email": mask_email}
    redacted = {key: masked[key](value) if key in masked else value for key, value in data.items()}
    return redacted, {"redacted": sorted(masked)}


def make_verify_effect(desk) -> Callable:
    def verify_effect(tool: str, arguments: dict, data: Any) -> tuple[Any, dict]:
        """Read the effect back from disk instead of trusting the tool's own return value."""
        if tool == "update_record":
            return data, {"verified": desk.records()[arguments["record_id"]][arguments["field"]] == arguments["value"]}
        if tool == "send_notice":
            return data, {"verified": desk.outbox()[-1:] == [data]}
        return data, {}
    return verify_effect


def audit_trail(tool: str, arguments: dict, data: Any) -> tuple[Any, dict]:
    """Record a digest of exactly what goes back to the model; it runs last, after masking."""
    return data, {"result_digest": approval_digest({"data": data})}


def post_hooks(desk) -> tuple[Hook, ...]:
    return (Hook("redact_customer_data", redact_customer_data), Hook("verify_effect", make_verify_effect(desk)),
            Hook("audit_trail", audit_trail))


def run_post_hooks(hooks: tuple[Hook, ...], tool: str, arguments: dict, data: Any) -> tuple[Any, list, dict]:
    """Run the hooks in order; each sees the previous one's data. Returns (data, steps, merged info)."""
    steps, merged = [], {}
    for hook in hooks:
        data, info = hook.run(tool, arguments, data)
        steps.append({"id": hook.name, "applied": bool(info), **({"detail": info} if info else {})})
        merged.update(info)
    return data, steps, merged
