"""The shared budget every subtask draws from, and cancellation scopes that pass a stop down to every subtask.

The budget belongs to the whole delegation, not to one subtask: calls are granted one at a time in priority order,
tokens are charged only from usage the provider reported, and time is measured from the start of the run. A scope
works like Go's context: cancelling a parent cancels every child. Only the coordinator thread touches either object.
"""
import time


class SubtaskCancelled(Exception):
    """A subtask's scope was cancelled before its request went out."""


class Scope:
    """A cancellation scope; a child reports its parent's reason when it has none of its own."""

    def __init__(self, parent: "Scope | None" = None):
        self.parent, self.own = parent, None

    def child(self) -> "Scope":
        return Scope(self)

    def cancel(self, reason: str):
        self.own = self.own or reason  # the first reason wins; a later one does not rewrite history

    @property
    def reason(self) -> str | None:
        return self.own or (self.parent.reason if self.parent else None)

    def check(self):
        if self.reason:
            raise SubtaskCancelled(self.reason)


class SharedBudget:
    """Calls, reported tokens and time for the whole delegation; grant() says why it refuses, never just no."""

    def __init__(self, calls: int, tokens: int, run_ms: int, clock=time.perf_counter):
        self.clock, self.started = clock, clock()
        self.calls, self.tokens, self.ends_at = calls, tokens, self.started + run_ms / 1000
        self.calls_used, self.tokens_used, self.unreported = 0, 0, 0

    def grant(self) -> str | None:
        """Reserve one model call; return None when granted, or the reason: calls, tokens or time."""
        if self.remaining_ms() <= 0:
            return "time"
        if self.calls_used >= self.calls:
            return "calls"
        if self.tokens_used >= self.tokens:
            return "tokens"
        self.calls_used += 1
        return None

    def refund(self):
        """A granted call whose request never went out does not count."""
        self.calls_used -= 1

    def charge(self, response) -> int | None:
        """Deduct the total_tokens the provider reported; an unreported count is noted, never guessed."""
        usage = response.get("usage") if isinstance(response, dict) else None
        tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
        if type(tokens) is not int or tokens < 0:
            self.unreported += 1
            return None
        self.tokens_used += tokens
        return tokens

    def remaining_ms(self) -> int:
        return round((self.ends_at - self.clock()) * 1000)

    def snapshot(self) -> dict:
        return {"calls_left": self.calls - self.calls_used, "tokens_left": max(self.tokens - self.tokens_used, 0),
                "ms_left": max(self.remaining_ms(), 0), "unreported_calls": self.unreported}
