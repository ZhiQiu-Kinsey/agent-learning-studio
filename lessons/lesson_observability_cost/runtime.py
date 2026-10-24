"""Observability and cost: trace one fixed multi-step task, keep a per-step ledger, find repeated calls and slow steps.

The task: put four expense receipts into categories (the model), work out each reimbursable amount with two tools
(exchange rate, category limit) and grade the result against human labels. The baseline asks the model once per
receipt and calls the tools every time; each optimization changes exactly one thing (a tool cache, or one batched
request). The ledger follows the span idea of the tracer in ai-agent-book chapter7/agent-cost-analysis (Apache-2.0),
rewritten here: usage is copied from each response as reported, a missing number stays None instead of 0, and every
row carries the round and call id that find its platform events.
"""
import hashlib
import json
import time
from datetime import date
from functools import partial
from typing import Literal

from pydantic import Field, model_validator

from course.execution import LessonInputs, RunContext
from lessons.lesson_observability_cost.locales import Texts, texts_for

# The question set: amount and currency are facts of the task, label is the human answer for the category.
RECEIPTS = (
    {"id": "r1", "amount": 42.0, "currency": "USD", "label": "transport"},
    {"id": "r2", "amount": 260.0, "currency": "USD", "label": "lodging"},
    {"id": "r3", "amount": 380.0, "currency": "CNY", "label": "meals"},
    {"id": "r4", "amount": 38.0, "currency": "USD", "label": "transport"},
)
# A fixed teaching table, not live exchange rates; limits are per receipt, in CNY.
RATES = {"USD": 7.1, "EUR": 7.8, "CNY": 1.0}
LIMITS = {"transport": 300.0, "lodging": 1200.0, "meals": 200.0}


class Inputs(LessonInputs):
    strategy: Literal["baseline", "tool_cache", "batched"] = "baseline"
    compare_with_baseline: bool = False
    rate_latency_ms: int = Field(default=200, ge=0, le=1000)
    # Cost is converted only when the learner names where the prices came from and when they were read.
    price_input_per_m: float = Field(default=0, ge=0, le=1000)
    price_output_per_m: float = Field(default=0, ge=0, le=1000)
    price_currency: Literal["CNY", "USD"] = "CNY"
    price_source: str = Field(default="", max_length=200)
    price_date: str = Field(default="", max_length=10)

    @model_validator(mode="after")
    def _consistent(self):
        if self.compare_with_baseline and self.strategy == "baseline":
            raise ValueError("compare_with_baseline needs strategy tool_cache or batched")
        if bool(self.price_source.strip()) != bool(self.price_date.strip()):
            raise ValueError("price_source and price_date go together: give both or neither")
        if self.price_date:
            if len(self.price_date) != 10:
                raise ValueError("price_date must be YYYY-MM-DD")
            date.fromisoformat(self.price_date)  # a date that does not exist raises ValueError here
        return self


INPUT_MODEL = Inputs


def lookup_rate(t: Texts, latency_ms: int, /, currency: str) -> dict:
    """Rate to CNY. It stands in for a remote service, so it waits latency_ms (an input) before answering."""
    time.sleep(latency_ms / 1000)
    if currency not in RATES:
        raise ValueError(t.unknown_currency.format(currency=currency))
    return {"currency": currency, "rate": RATES[currency], "simulated_latency_ms": latency_ms}


def category_limit(t: Texts, /, category: str) -> dict:
    if category not in LIMITS:
        raise ValueError(t.unknown_category.format(category=category))
    return {"category": category, "limit": LIMITS[category]}


def fingerprint(kind: str, payload) -> str:
    """Same kind and same canonical JSON give the same fingerprint: that is what "repeated" means in this lesson."""
    text = json.dumps([kind, payload], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


class Tracer:
    """The lesson's ledger: one row per span (model request, tool call or cache hit), written at the call boundary."""

    def __init__(self, context: RunContext, strategy: str):
        self.context, self.strategy = context, strategy
        self.rows: list[dict] = []
        self.first_seen: dict[str, int] = {}

    def _row(self, kind: str, name: str, step: int, receipt: str, key: str, started: float, **extra) -> dict:
        row = {"pass": self.strategy, "step": step, "kind": kind, "name": name, "receipt": receipt,
               "fingerprint": key, "ms": round((time.perf_counter() - started) * 1000, 1),
               "repeat_of": self.first_seen.get(key), **extra}
        self.first_seen.setdefault(key, len(self.rows))
        self.rows.append(row)
        return row

    def llm(self, body: dict, step: int, receipt: str) -> dict:
        key, started = fingerprint("llm", body), time.perf_counter()
        response = self.context.complete(body, step)
        usage = response.get("usage")
        self._row("llm", self.context.model, step, receipt, key, started, call_id=None, status="ok",
                  usage=usage if isinstance(usage, dict) else None, **read_usage(usage))
        return response

    def tool(self, name: str, arguments: dict, step: int, receipt: str, tools: dict, cache: dict | None) -> dict:
        key, started = fingerprint(name, arguments), time.perf_counter()
        if cache is not None and key in cache:
            # Served from the run's own cache: no tool event is emitted, and the row says it was a cache hit.
            self._row("cache", name, step, receipt, key, started, call_id=None, status="ok")
            return cache[key]
        call_id = f"obs_{self.strategy}_{len(self.rows) + 1}"  # the tool_call event carries this id
        result = self.context.call_tool(name, arguments, tools, step, call_id=call_id)
        self._row("tool", name, step, receipt, key, started, call_id=call_id, status="ok" if result["ok"] else "error")
        if cache is not None and result["ok"]:
            cache[key] = result
        return result


def classify_body(system: str, user: str) -> dict:
    return {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 0}


def _json_in(response: dict):
    """The first JSON value in the reply; text or a code fence around it is allowed, nothing else is repaired."""
    content = response.get("choices", [{}])[0].get("message", {}).get("content")
    starts = [i for i in (content.find("{"), content.find("[")) if i >= 0] if isinstance(content, str) else []
    try:
        return json.JSONDecoder().raw_decode(content[min(starts):])[0] if starts else None
    except ValueError:
        return None


def parse_one(response: dict) -> str | None:
    value = _json_in(response)
    category = value.get("category") if isinstance(value, dict) else None
    return category if isinstance(category, str) else None


def parse_batch(response: dict) -> dict[str, str]:
    value = _json_in(response)
    items = value if isinstance(value, list) else []
    return {item["id"]: item["category"] for item in items if isinstance(item, dict)
            and isinstance(item.get("id"), str) and isinstance(item.get("category"), str)}


def run_pass(context: RunContext, t: Texts, values: Inputs, strategy: str, first_step: int) -> dict:
    """Run the four receipts once with one strategy; return the ledger rows, the graded cases and the end-to-end time."""
    tracer, started = Tracer(context, strategy), time.perf_counter()
    tools = {"lookup_rate": partial(lookup_rate, t, values.rate_latency_ms), "category_limit": partial(category_limit, t)}
    cache = {} if strategy == "tool_cache" else None  # the one change of the tool_cache strategy
    step, categories = first_step, {}
    # 1. Classify. batched sends all four receipts in one request (the one change of that strategy).
    if strategy == "batched":
        items = [{"id": r["id"], "description": t.receipts[r["id"]]} for r in RECEIPTS]
        reply = tracer.llm(classify_body(t.batch_system, json.dumps(items, ensure_ascii=False)), step, "all")
        categories, step = parse_batch(reply), step + 1
    cases = []
    for receipt in RECEIPTS:
        context.check_cancelled()
        # 2. The other strategies ask once per receipt; r4 has r1's description, so its request body is identical.
        if strategy != "batched":
            reply = tracer.llm(classify_body(t.classify_system, t.receipts[receipt["id"]]), step, receipt["id"])
            categories[receipt["id"]] = parse_one(reply)
        category = categories.get(receipt["id"])
        # 3. Tools: rate and limit. Without a cache the same question is asked again every time it comes up.
        rate = tracer.tool("lookup_rate", {"currency": receipt["currency"]}, step, receipt["id"], tools, cache)
        limit = (tracer.tool("category_limit", {"category": category}, step, receipt["id"], tools, cache)
                 if category is not None else None)
        cases.append(grade(receipt, category, rate, limit))
        step += 1
    return {"strategy": strategy, "rows": tracer.rows, "cases": cases, "next_step": step,
            "end_to_end_ms": round((time.perf_counter() - started) * 1000, 1)}


def grade(receipt: dict, category: str | None, rate: dict, limit: dict | None) -> dict:
    """Compare with the human label; reason names the first thing that went wrong (failure attribution)."""
    expected = min(round(receipt["amount"] * RATES[receipt["currency"]], 2), LIMITS[receipt["label"]])
    amount = None
    if category is None:
        reason = "unparsed"
    elif not rate["ok"] or limit is None or not limit["ok"]:
        reason = "tool_error"
    else:
        amount = min(round(receipt["amount"] * rate["result"]["rate"], 2), limit["result"]["limit"])
        reason = ("wrong_category" if category != receipt["label"]
                  else "ok" if amount == expected else "wrong_amount")
    return {"receipt": receipt["id"], "category": category, "expected_category": receipt["label"],
            "amount": amount, "expected_amount": expected, "passed": reason == "ok", "reason": reason}


def _count(value) -> int | None:
    # bool is a subclass of int; True is not one token. Strings and negatives are not guessed into numbers.
    return value if type(value) is int and value >= 0 else None


def read_usage(usage) -> dict:
    """Token counts as the provider reported them; a missing field stays None (not reported), never 0."""
    if not isinstance(usage, dict):
        return {"input_tokens": None, "output_tokens": None, "total_tokens": None}
    # OpenAI-compatible names first (Bailian, LiteLLM), then Anthropic-style names.
    first = _count(usage.get("prompt_tokens"))
    inputs = first if first is not None else _count(usage.get("input_tokens"))
    first = _count(usage.get("completion_tokens"))
    outputs = first if first is not None else _count(usage.get("output_tokens"))
    total = _count(usage.get("total_tokens"))
    if total is None and inputs is not None and outputs is not None:
        total = inputs + outputs  # the sum of two reported numbers is still reported data, not an estimate
    return {"input_tokens": inputs, "output_tokens": outputs, "total_tokens": total}


def repeated_groups(rows: list[dict]) -> list[dict]:
    """Executed spans whose fingerprint ran before; a cache hit is a repeat avoided and is not counted."""
    groups: dict[str, dict] = {}
    for row in rows:
        if row["kind"] == "cache" or row["repeat_of"] is None:
            continue
        first = rows[row["repeat_of"]]
        group = groups.setdefault(row["fingerprint"], {"kind": first["kind"], "name": first["name"],
                                                       "steps": [first["step"]], "extra_ms": 0.0,
                                                       "extra_tokens": 0, "unreported": 0})
        group["steps"].append(row["step"])
        group["extra_ms"] = round(group["extra_ms"] + row["ms"], 1)
        if row["kind"] == "llm":
            # Tokens of a repeated request count only when the provider reported them.
            if row["total_tokens"] is None:
                group["unreported"] += 1
            else:
                group["extra_tokens"] += row["total_tokens"]
    return list(groups.values())


def slowest(rows: list[dict], limit: int = 5) -> list[dict]:
    """Executed spans, slowest first; ties keep run order so the ranking is stable."""
    executed = [row for row in rows if row["kind"] != "cache"]
    return sorted(executed, key=lambda row: -row["ms"])[:limit]


def token_total(rows: list[dict]) -> tuple[int | None, int]:
    """Reported total and how many model calls did not report; None when nothing was reported at all."""
    calls = [row for row in rows if row["kind"] == "llm"]
    reported = [row["total_tokens"] for row in calls if row["total_tokens"] is not None]
    return (sum(reported) if reported else None), len(calls) - len(reported)


def estimate_cost(rows: list[dict], values: Inputs) -> dict | None:
    """Tokens times the learner's price table; only calls that reported both input and output are covered."""
    if not values.price_source.strip():
        return None
    calls = [row for row in rows if row["kind"] == "llm"]
    known = [row for row in calls if row["input_tokens"] is not None and row["output_tokens"] is not None]
    amount = sum(row["input_tokens"] * values.price_input_per_m + row["output_tokens"] * values.price_output_per_m
                 for row in known) / 1_000_000
    return {"amount": round(amount, 6), "covered": len(known), "calls": len(calls)}


def regressions(before: dict, after: dict) -> tuple[list[str], list[str]]:
    """Same question set, two passes: items that went from passed to failed, and from failed to passed."""
    old = {case["receipt"]: case["passed"] for case in before["cases"]}
    worse = [case["receipt"] for case in after["cases"] if old.get(case["receipt"]) and not case["passed"]]
    better = [case["receipt"] for case in after["cases"] if old.get(case["receipt"]) is False and case["passed"]]
    return worse, better


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    order = ["baseline", values.strategy] if values.compare_with_baseline else [values.strategy]
    passes, step = [], 1
    for strategy in order:
        result = run_pass(context, t, values, strategy, step)
        step = result["next_step"]
        _report_pass(context, t, values, result)
        passes.append(result)
    final = passes[-1]
    answer = t.answer.format(
        strategy=t.strategy_names[final["strategy"]], total=len(final["cases"]),
        passed=sum(case["passed"] for case in final["cases"]),
        calls=sum(row["kind"] == "llm" for row in final["rows"]), tools=sum(row["kind"] == "tool" for row in final["rows"]),
        hits=sum(row["kind"] == "cache" for row in final["rows"]), ms=final["end_to_end_ms"])
    if len(passes) == 2:
        worse = _report_compare(context, t, passes[0], passes[1])
        answer += " " + t.answer_compare.format(baseline=t.strategy_names["baseline"],
                                                strategy=t.strategy_names[final["strategy"]], regressions=worse)
    return answer


def _tokens_text(t: Texts, rows: list[dict]):
    total, missing = token_total(rows)
    if total is None:
        return t.value_not_reported
    return total if not missing else t.tokens_partly_reported.format(total=total, missing=missing)


def _cell(t: Texts, row: dict, field: str):
    if row["kind"] != "llm":
        return t.value_not_applicable  # tools have no token usage: not applicable, which is not "not reported"
    return t.value_not_reported if row[field] is None else row[field]


def _report_pass(context: RunContext, t: Texts, values: Inputs, result: dict) -> None:
    """Platform: publish the raw ledger (lesson.ledger) and the two reports of one pass; every number is in the rows."""
    rows, cases, strategy = result["rows"], result["cases"], t.strategy_names[result["strategy"]]
    context.emit("lesson.ledger", {"pass": result["strategy"], "end_to_end_ms": result["end_to_end_ms"],
                                   "rows": rows, "cases": cases})
    offline = context.mode == "offline"
    llm_rows = [row for row in rows if row["kind"] == "llm"]
    missing = [str(row["step"]) for row in llm_rows if row["total_tokens"] is None]
    passed = sum(case["passed"] for case in cases)
    failures = t.list_separator.join(t.failure_item.format(receipt=case["receipt"], reason=t.reason_names[case["reason"]])
                                     for case in cases if not case["passed"])
    cost = estimate_cost(rows, values)
    if cost is None:
        cost_text = t.cost_none
    elif not cost["covered"]:
        cost_text = t.cost_no_usage
    else:
        cost_text = t.cost_value.format(amount=cost["amount"], currency=values.price_currency, model=context.model,
                                        source=values.price_source.strip(), date=values.price_date,
                                        covered=cost["covered"], calls=cost["calls"])
    context.emit("lesson.report", {
        "title": t.ledger_title.format(strategy=strategy),
        "summary": t.ledger_summary + (" " + t.offline_note if offline else ""),
        "checks": [
            {"id": "quality", "label": t.check_quality, "passed": passed == len(cases),
             "detail": t.check_quality_detail.format(passed=passed, total=len(cases), failures=failures)},
            {"id": "usage_reported", "label": t.check_usage, "passed": not missing,
             "detail": t.check_usage_all if not missing else t.check_usage_missing.format(
                 steps=t.list_separator.join(missing))},
        ],
        "metrics": [
            {"id": "mode", "label": t.label_mode, "value": t.mode_offline if offline else t.mode_live},
            {"id": "model", "label": t.label_model, "value": context.model},
            {"id": "model_calls", "label": t.label_model_calls, "value": len(llm_rows)},
            {"id": "tool_calls", "label": t.label_tool_calls, "value": sum(row["kind"] == "tool" for row in rows)},
            {"id": "cache_hits", "label": t.label_cache_hits, "value": sum(row["kind"] == "cache" for row in rows)},
            {"id": "end_to_end_ms", "label": t.label_end_to_end, "value": result["end_to_end_ms"]},
            {"id": "step_ms_sum", "label": t.label_step_sum, "value": round(sum(row["ms"] for row in rows), 1)},
            {"id": "total_tokens", "label": t.label_total_tokens, "value": _tokens_text(t, rows)},
            {"id": "unreported_calls", "label": t.label_unreported, "value": len(missing)},
            {"id": "quality", "label": t.label_quality, "value": t.quality_value.format(passed=passed, total=len(cases))},
            {"id": "cost", "label": t.label_cost, "value": cost_text},
            {"id": "note", "label": t.label_note, "value": context.question or t.value_empty},
        ],
        "table": {"columns": list(t.columns_ledger), "rows": [
            [row["step"], t.kind_names[row["kind"]], row["name"], row["receipt"], row["call_id"] or t.value_not_applicable,
             row["fingerprint"], row["ms"], _cell(t, row, "input_tokens"), _cell(t, row, "output_tokens"),
             t.status_names[row["status"]],
             t.value_not_applicable if row["repeat_of"] is None else t.repeat_cell.format(step=rows[row["repeat_of"]]["step"])]
            for row in rows]},
    })
    _report_bottleneck(context, t, result, strategy)


def _report_bottleneck(context: RunContext, t: Texts, result: dict, strategy: str) -> None:
    """Platform: rank the executed spans by time and list repeated fingerprints."""
    rows, total_ms = result["rows"], result["end_to_end_ms"]
    ranked, groups = slowest(rows), repeated_groups(rows)
    share = (lambda ms: f"{ms / total_ms:.0%}" if total_ms else t.value_not_applicable)
    top = ranked[0] if ranked else None
    extra_tokens = sum(group["extra_tokens"] for group in groups)
    unreported = sum(group["unreported"] for group in groups)
    context.emit("lesson.report", {
        "title": t.bottleneck_title.format(strategy=strategy),
        "summary": t.bottleneck_summary,
        "checks": [{"id": "no_repeats", "label": t.check_no_repeats, "passed": not groups,
                    "detail": t.check_no_repeats_ok if not groups else t.check_no_repeats_found.format(count=len(groups))}],
        "metrics": [
            {"id": "slowest_step", "label": t.label_slowest, "value": t.slowest_value.format(
                step=top["step"], name=top["name"], ms=top["ms"], share=share(top["ms"])) if top else t.value_none},
            {"id": "repeated_calls", "label": t.label_repeated, "value": t.list_separator.join(
                t.repeat_item.format(kind=t.kind_names[g["kind"]], name=g["name"], count=len(g["steps"]),
                                     steps=", ".join(map(str, g["steps"]))) for g in groups) or t.value_none},
            {"id": "repeat_ms", "label": t.label_extra_ms, "value": round(sum(g["extra_ms"] for g in groups), 1)},
            {"id": "repeat_tokens", "label": t.label_extra_tokens, "value": (
                t.value_not_reported if unreported and not extra_tokens else extra_tokens if not unreported
                else t.tokens_partly_reported.format(total=extra_tokens, missing=unreported))},
        ],
        "table": {"columns": list(t.columns_bottleneck), "rows": [
            [rank, row["step"], t.kind_names[row["kind"]], row["name"], row["ms"], share(row["ms"]),
             t.value_not_applicable if row["repeat_of"] is None else t.repeat_cell.format(step=rows[row["repeat_of"]]["step"])]
            for rank, row in enumerate(ranked, 1)]},
    })


def _report_compare(context: RunContext, t: Texts, before: dict, after: dict) -> str:
    """Platform: the before/after report on the same question set; returns the regression text for the answer."""
    worse, better = regressions(before, after)

    def summary(result: dict) -> dict:
        rows = result["rows"]
        return {"quality": sum(case["passed"] for case in result["cases"]),
                "model_calls": sum(row["kind"] == "llm" for row in rows),
                "tool_calls": sum(row["kind"] == "tool" for row in rows), "ms": result["end_to_end_ms"],
                "tokens": token_total(rows)[0], "unreported": token_total(rows)[1],
                "repeats": sum(len(g["steps"]) - 1 for g in repeated_groups(rows))}

    a, b = summary(before), summary(after)
    change = (lambda x, y: t.value_not_reported if x is None or y is None else round(y - x, 1))
    shown = (lambda value: t.value_not_reported if value is None else value)
    rows = [[t.row_quality, f"{a['quality']}/{len(before['cases'])}", f"{b['quality']}/{len(after['cases'])}",
             b["quality"] - a["quality"]]]
    for label, key in ((t.row_model_calls, "model_calls"), (t.row_tool_calls, "tool_calls"),
                       (t.row_end_to_end, "ms"), (t.row_tokens, "tokens"), (t.row_unreported, "unreported"),
                       (t.row_repeats, "repeats")):
        rows.append([label, shown(a[key]), shown(b[key]), change(a[key], b[key])])
    failed = (lambda result: sum(not case["passed"] for case in result["cases"]))
    worse_text = t.check_no_regression_ok if not worse else t.check_no_regression_found.format(
        items=t.list_separator.join(worse))
    context.emit("lesson.report", {
        "title": t.compare_title.format(baseline=t.strategy_names["baseline"], strategy=t.strategy_names[after["strategy"]]),
        "summary": t.compare_summary,
        "checks": [
            {"id": "no_regression", "label": t.check_no_regression, "passed": not worse, "detail": worse_text},
            {"id": "no_more_failures", "label": t.check_failures, "passed": failed(after) <= failed(before),
             "detail": t.check_failures_detail.format(before=failed(before), after=failed(after))},
        ],
        "metrics": [
            {"id": "regressions", "label": t.label_regressions, "value": t.list_separator.join(worse) or t.value_none},
            {"id": "fixes", "label": t.label_fixes, "value": t.list_separator.join(better) or t.value_none},
            {"id": "token_change", "label": t.label_token_change, "value": change(a["tokens"], b["tokens"])},
            {"id": "latency_change", "label": t.label_latency_change, "value": change(a["ms"], b["ms"])},
        ],
        "table": {"columns": list(t.columns_compare), "rows": rows},
    })
    return worse_text
