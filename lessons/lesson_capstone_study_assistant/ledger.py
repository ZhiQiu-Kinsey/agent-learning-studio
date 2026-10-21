"""The call ledger of one run: one row per model request, tool call and approval, written at the boundary.

It is the observability-cost lesson's idea (one row per span, usage copied as the provider
reported it, a missing number stays None and is never turned into 0) in a smaller form: the
assistant's cases need to total calls, tokens and time, and the trace-explanation task reads
these rows back. Rows are plain dicts so they go into events and reports unchanged.
"""
import time

from lessons.lesson_observability_cost.runtime import read_usage


class Ledger:
    def __init__(self):
        self.rows: list[dict] = []

    def add(self, case: str, kind: str, name: str, started: float, **extra) -> dict:
        row = {"n": len(self.rows) + 1, "case": case, "kind": kind, "name": name,
               "ms": round((time.perf_counter() - started) * 1000, 1), **extra}
        self.rows.append(row)
        return row

    def model_call(self, context, case: str, body: dict, round_number: int) -> dict:
        """One model request through the platform; usage is read from the response exactly as reported."""
        started = time.perf_counter()
        response = context.complete(body, round_number)
        usage = read_usage(response.get("usage"))
        self.add(case, "llm", context.model, started, status="ok", round=round_number, **usage)
        return response

    def approval(self, case: str, name: str, waited_ms: int, outcome: str) -> None:
        """The time a person took to decide is a row of its own: waiting is not the model's or a tool's time."""
        self.rows.append({"n": len(self.rows) + 1, "case": case, "kind": "approval", "name": name,
                          "ms": float(waited_ms), "status": outcome})

    def mark(self) -> int:
        """A position in the ledger, so one case can read back only its own rows."""
        return len(self.rows)

    def since(self, mark: int) -> list[dict]:
        return self.rows[mark:]


def model_view(rows: list[dict]) -> list[dict]:
    """The rows as the trace-explanation task shows them to the model: code values only, usage null when not reported."""
    view = []
    for row in rows:
        item = {"n": row["n"], "kind": row["kind"], "name": row["name"], "ms": row["ms"], "status": row["status"]}
        if row["kind"] == "llm":
            item["total_tokens"] = row["total_tokens"]
        if row.get("hits") is not None:
            item["hits"] = row["hits"]
        view.append(item)
    return view


def trace_truth(rows: list[dict]) -> dict:
    """What a correct explanation of these rows says: the verifier computes it, it never reads the model's own claim."""
    executed = [row for row in rows if row["kind"] in ("llm", "tool")]
    slowest = min(executed, key=lambda row: (-row["ms"], row["n"])) if executed else None
    llm = [row for row in rows if row["kind"] == "llm"]
    return {"slowest_row": slowest["n"] if slowest else None,
            "search_hits": sum(row.get("hits") or 0 for row in rows if row["kind"] == "tool"),
            "usage_reported": bool(llm) and all(row["total_tokens"] is not None for row in llm)}


def summarize(rows: list[dict]) -> dict:
    llm = [row for row in rows if row["kind"] == "llm"]
    reported = [row["total_tokens"] for row in llm if row["total_tokens"] is not None]
    return {"model_calls": len(llm), "tool_calls": sum(row["kind"] == "tool" for row in rows),
            "approvals": sum(row["kind"] == "approval" for row in rows),
            "tokens": sum(reported) if reported else None, "unreported_calls": len(llm) - len(reported),
            "model_ms": round(sum(row["ms"] for row in llm), 1),
            "tool_ms": round(sum(row["ms"] for row in rows if row["kind"] == "tool"), 1),
            "waited_ms": round(sum(row["ms"] for row in rows if row["kind"] == "approval"), 1)}


def estimate_cost(rows: list[dict], price_input: float, price_output: float) -> dict:
    """Tokens times the learner's price table; only calls that reported both counts are covered."""
    llm = [row for row in rows if row["kind"] == "llm"]
    known = [row for row in llm if row["input_tokens"] is not None and row["output_tokens"] is not None]
    amount = sum(row["input_tokens"] * price_input + row["output_tokens"] * price_output for row in known) / 1_000_000
    return {"amount": round(amount, 6), "covered": len(known), "calls": len(llm)}
