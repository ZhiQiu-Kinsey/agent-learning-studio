"""Bounded retry for one tool operation: classify each failure, decide, back off, record every attempt."""
import itertools
import random
import time
from dataclasses import dataclass, field

# error_type (the exception's class name in the tool result) -> category. This table is the whole policy input.
CATEGORIES = {
    "StoreTimeout": "transient",         # the lock was never acquired: nothing happened
    "OutboxBusy": "transient",
    "ResponseLost": "outcome_unknown",   # it may have happened: safe to repeat only if repeating cannot double it
    "InvalidArgument": "invalid",
    "TypeError": "invalid",              # missing or extra arguments
    "BusinessRejected": "rejected",
    "KeyConflict": "rejected",
}


def classify(error_type: str) -> str:
    # An error nobody has classified is not retried: guessing "transient" could repeat a write.
    return CATEGORIES.get(error_type, "unclassified")


def decide(category: str, repeatable: bool, blind: bool = False) -> tuple[str, str]:
    """(decision, reason) for one failed attempt, before the attempt and time limits are applied.

    repeatable: repeating this exact call cannot apply its effect twice (a read, a keyed write,
    a state-checked compensation). blind is the control arm that treats every write as repeatable.
    """
    if category == "transient":
        return "retry", "transient"
    if category == "outcome_unknown":
        if repeatable or blind:
            return "retry", "repeatable" if repeatable else "blind"
        return "stop", "outcome_unknown"
    return "stop", category


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    timeout_s: float
    base_delay_s: float
    budget_s: float
    max_delay_s: float = 1.0


def backoff_delay(attempt: int, policy: RetryPolicy, rng: random.Random) -> float:
    """Exponential backoff with jitter: 1x, 2x, 4x the base, capped, then scaled by a factor in [0.5, 1)."""
    ceiling = min(policy.max_delay_s, policy.base_delay_s * 2 ** (attempt - 1))
    return ceiling * (0.5 + rng.random() / 2)


class RealClock:
    monotonic = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)


@dataclass
class Outcome:
    status: str          # ok / failed / unknown (a write that may or may not have happened)
    reason: str
    result: dict
    attempts: list[dict] = field(default_factory=list)


def call_with_retry(context, tools, faults, policy, clock, rng, *, operation: str, name: str, arguments: dict,
                    repeatable: bool, writes: bool, round_number: int, blind: bool = False) -> Outcome:
    started = clock.monotonic()
    attempts = []
    for number in itertools.count(1):
        # 1. One real tool call; the injector may have set up a failure for this attempt.
        context.check_cancelled()
        with faults.attempt(context, operation, name, number):
            began = clock.monotonic()
            result = context.call_tool(name, arguments, tools, round_number)
        took_ms = round((clock.monotonic() - began) * 1000)
        if result["ok"]:
            attempts.append({"attempt": number, "ok": True, "took_ms": took_ms})
            return Outcome("ok", "ok", result["result"], attempts)
        # 2. Classify by error_type alone, then decide.
        category = classify(result["error_type"])
        decision, reason = decide(category, repeatable, blind)
        wait = backoff_delay(number, policy, rng) if decision == "retry" else 0.0
        elapsed = clock.monotonic() - started
        # 3. Limits: the attempt count, and a time budget the next attempt (up to timeout_s) must fit in.
        if decision == "retry" and number >= policy.max_attempts:
            decision, reason, wait = "stop", "max_attempts", 0.0
        elif decision == "retry" and elapsed + wait + policy.timeout_s > policy.budget_s:
            decision, reason, wait = "stop", "budget", 0.0
        record = {"operation": operation, "tool": name, "attempt": number, "error_type": result["error_type"],
                  "category": category, "decision": decision, "reason": reason, "took_ms": took_ms,
                  "wait_ms": round(wait * 1000), "elapsed_ms": round(elapsed * 1000),
                  "max_attempts": policy.max_attempts, "budget_ms": round(policy.budget_s * 1000)}
        context.emit("lesson.retry", record, round_number)
        attempts.append({"attempt": number, "ok": False, **record})
        if decision == "stop":
            status = "unknown" if writes and category == "outcome_unknown" else "failed"
            return Outcome(status, reason, result, attempts)
        # 4. Back off before the next attempt; a stop request is honoured first.
        context.check_cancelled()
        clock.sleep(wait)
