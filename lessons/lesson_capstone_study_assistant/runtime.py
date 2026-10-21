"""Capstone study assistant: run one contract-bound case, or the whole fixed suite, and judge it from recorded facts.

The assistant itself is assistant.py (tool loop, permission gate, approval, idempotent write); the judge is
verifier.py. This file is the runner around them: it validates the inputs, states the task contract, runs the
chosen cases one by one in isolated stores, publishes the evidence (plan, permission decisions, memory, ledger,
case results) and the reports, and rebuilds the answer shown to the learner from checked facts. Every text that
reaches the model or an event is in locales/, one catalog per run language.
"""
from datetime import date
from functools import partial
from pathlib import Path
from typing import Literal

import anyio
from mcp import Client, MCPError
from mcp.types import Implementation
from pydantic import Field, model_validator

from course.execution import LessonInputs, RunContext
from course.i18n import SOURCE_LOCALE
from course.protocols import python_module_server, recording_stdio, run_until_cancelled
from lessons.lesson_capstone_study_assistant import assistant, verifier
from lessons.lesson_capstone_study_assistant.contract import (BY_ID, CASES, CONTRACT_VERSION, LEARNER, MAX_STEPS, PASS_LINE,
                                                              TASK_TOOLS, WRITE, Case, cases_for, fingerprint)
from lessons.lesson_capstone_study_assistant.ledger import Ledger, estimate_cost, summarize
from lessons.lesson_capstone_study_assistant.locales import Texts, texts_for
from lessons.lesson_capstone_study_assistant.notes import NotesSearch, corpus_version, notes_chunks
from lessons.lesson_evaluation_sets.runtime import wilson

RUNTIME_DIR = Path(__file__).resolve().parents[2] / ".runtime"
SERVER_MODULE = "lessons.lesson_capstone_study_assistant.notes_server"
CLIENT_INFO = Implementation(name="study-assistant-runner", version="1.0")
READ_TIMEOUT_SECONDS = 20
CaseChoice = Literal["d01", "d02", "d03", "d04", "d05", "d06", "d07", "d08", "h01", "h02", "h03", "h04", "h05", "suite"]


class Inputs(LessonInputs):
    # One case id of the frozen suite, or "suite" for every case of the chosen split.
    case: CaseChoice = "d01"
    split: Literal["dev", "holdout", "all"] = "dev"
    top_k: int = Field(default=5, ge=1, le=8)
    # local: the notes search runs in this process; mcp: it runs in a separate MCP server process.
    tools: Literal["local", "mcp"] = "local"
    # Money is converted only when the learner names where the prices came from and when they were read.
    price_input_per_m: float = Field(default=0, ge=0, le=1000)
    price_output_per_m: float = Field(default=0, ge=0, le=1000)
    price_currency: Literal["CNY", "USD"] = "CNY"
    price_source: str = Field(default="", max_length=200)
    price_date: str = Field(default="", max_length=10)

    @model_validator(mode="after")
    def _consistent(self):
        if bool(self.price_source.strip()) != bool(self.price_date.strip()):
            raise ValueError("price_source and price_date go together: give both or neither")
        if self.price_date:
            if len(self.price_date) != 10:
                raise ValueError("price_date must be YYYY-MM-DD")
            date.fromisoformat(self.price_date)  # a date that does not exist raises ValueError here
        return self


INPUT_MODEL = Inputs


# ---------- tool backends: the same search, in this process or behind MCP ----------

class LocalBackend:
    def __init__(self, locale: str):
        self.search_index = NotesSearch(locale)

    def search(self, query: str, top_k: int) -> dict:
        return self.search_index.search(query, top_k)


class McpConnectionError(ValueError):
    """The call got no answer at all (MCPError): the connection or the server process is gone."""


class McpBackend:
    """The search tool behind a real MCP stdio connection; it runs in a worker thread, so calls go back to the loop."""

    def __init__(self, client: Client):
        self.client = client

    def search(self, query: str, top_k: int) -> dict:
        try:
            result = anyio.from_thread.run(self.client.call_tool, "search_notes", {"query": query, "top_k": top_k})
        except MCPError as error:
            raise McpConnectionError(f"MCPError {error.error.code}: {error.error.message}") from error
        if result.is_error:
            raise ValueError("\n".join(block.text for block in result.content if getattr(block, "type", None) == "text"))
        return {"hits": result.structured_content["hits"]}


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    if values.tools == "mcp" and context.resume_state is None:
        return anyio.run(_with_mcp, context, t, values)
    return execute(context, t, values, LocalBackend(context.locale))


async def _with_mcp(context: RunContext, t: Texts, values: Inputs) -> str:
    async def session() -> str:
        params = python_module_server(SERVER_MODULE, "--locale", context.locale)
        client = Client(recording_stdio(context, params, server="study-notes"), mode="legacy", client_info=CLIENT_INFO,
                        read_timeout_seconds=READ_TIMEOUT_SECONDS, cache=None)
        async with client:
            # Discovery is the protocol's job; the cases run in a worker thread, calling the server through the client.
            await client.list_tools()
            return await anyio.to_thread.run_sync(partial(execute, context, t, values, McpBackend(client)))

    answer, error = await run_until_cancelled(context, _guarded(session))
    if error is not None:
        raise error
    return answer


def _guarded(function):
    # run_until_cancelled wraps errors from its task group in an ExceptionGroup; hand the original back as a value.
    async def call():
        try:
            return await function(), None
        except Exception as error:
            return None, error
    return call


# ---------- the run ----------

CASE_RUNNERS = {"ask": assistant.run_grounded, "injection": assistant.run_grounded, "practice": assistant.run_grounded,
                "trace": assistant.run_trace, "progress": assistant.run_progress}


def worst_calls(case: Case) -> int:
    """Most model calls this case may use: each conversation is capped at MAX_STEPS."""
    if case.kind == "trace":
        return MAX_STEPS + 1
    return MAX_STEPS * (2 if case.subkind == "roundtrip" else 1)


def execute(context: RunContext, t: Texts, values: Inputs, backend) -> str:
    chunks = {chunk.chunk_id: chunk for chunk in notes_chunks(context.locale)}
    env = assistant.Env(context=context, t=t, backend=backend, chunks=chunks, ledger=Ledger(), top_k=values.top_k)
    if context.resume_state is not None:
        return run_resume(env, values)
    single = values.case != "suite"
    cases = [BY_ID[values.case]] if single else cases_for(values.split)
    # Refuse up front rather than stop halfway: a half-run suite would hide the cases it skipped.
    worst = sum(worst_calls(case) for case in cases)
    if worst > context.max_model_calls:
        raise ValueError(t.budget_too_small.format(worst=worst, limit=context.max_model_calls))
    suite = fingerprint(list(CASES))  # the frozen suite as a whole, whichever cases this run takes from it
    context.emit("lesson.task_card", _card(t, values, cases, suite, context.locale))
    _report_contract(context, t, cases, suite)
    results = []
    for case in cases:
        context.check_cancelled()
        # The learner's own progress file is touched only by a single real save-and-recall case; everything else,
        # suites included, uses a throwaway store, so a rerun starts from the same state.
        persistent = (_progress_path(context.locale) if single and case.subkind == "roundtrip"
                      and context.mode != "offline" else None)
        with assistant.case_store(env, persistent) as path:
            outcome = CASE_RUNNERS[case.kind](env, case, path)
            if case.kind == "progress":
                outcome["records"] = _records(env, path)
        verdict = verifier.verify_case(case, outcome, t)
        _publish_case(env, case, outcome, verdict)
        results.append({"case": case, "outcome": outcome, "verdict": verdict})
    context.emit("lesson.ledger", {"rows": env.ledger.rows, "summary": summarize(env.ledger.rows)}, max(env.rounds, 1))
    if single:
        return _report_single(context, t, values, env, results[0])
    return _report_suite(context, t, values, env, results, suite)


def _progress_path(locale: str) -> Path:
    suffix = "" if locale == SOURCE_LOCALE else "." + locale
    return RUNTIME_DIR / f"study-assistant{suffix}.sqlite3"


def _records(env: assistant.Env, path: Path) -> list[dict]:
    from lessons.lesson_capstone_study_assistant.progress import ProgressStore
    store = ProgressStore(path, env.locale)
    try:
        return store.records(LEARNER)
    finally:
        store.close()


def run_resume(env: assistant.Env, values: Inputs) -> str:
    """A run started from a checkpoint: finish the interrupted approved write, nothing else, and say what happened."""
    context, t = env.context, env.t
    state = context.resume_state
    payload = state.get("payload") if isinstance(state, dict) else None
    needed = {"learner", "lesson", "status", "note", "operation_id"}
    if not isinstance(payload, dict) or not needed <= set(payload) or payload["learner"] != LEARNER:
        raise ValueError(t.resume_unusable)
    case = BY_ID.get(state.get("case"), BY_ID["d07"])
    context.emit("lesson.task_card", {"goal": t.resume_goal, "input_scope": t.resume_scope.format(
        origin=(context.resumed_from or {}).get("run_id", "-")), "output": t.resume_output,
        "evidence": t.resume_evidence, "failure": t.resume_failure, "stop": t.resume_stop})
    persistent = _progress_path(context.locale) if context.mode != "offline" else None
    if state.get("stage") == "saved":
        raise ValueError(t.resume_nothing_to_do)
    with assistant.case_store(env, persistent) as path:
        result = assistant.resume_save(env, case, path, state)
    context.emit("lesson.report", {
        "title": t.report_resume_title, "summary": t.report_resume_summary,
        "checks": [{"id": "once", "label": t.check_resume_once, "passed": result["applied"] or result["reason"] == "replayed",
                    "detail": t.detail_resume.format(reason=t.resume_reasons.get(result["reason"], result["reason"]),
                                                     version=result["version"] if result["version"] else "-")}],
        "metrics": [{"id": "approvals", "label": t.label_approvals, "value": result["approvals"]},
                    {"id": "operation", "label": t.label_operation, "value": result["operation_id"]},
                    {"id": "note", "label": t.label_note, "value": context.question or t.value_empty}]})
    return t.answer_resume.format(lesson=payload["lesson"], reason=t.resume_reasons.get(result["reason"], result["reason"]))


# ---------- publishing ----------

def _card(t: Texts, values: Inputs, cases: list[Case], suite: str, locale: str) -> dict:
    names = ", ".join(case.id for case in cases)
    return {"goal": t.card_goal.format(cases=names), "input_scope": t.card_scope.format(
        count=len(cases), suite=CONTRACT_VERSION, fingerprint=suite, corpus=corpus_version(locale), tools=values.tools),
        "output": t.card_output, "evidence": t.card_evidence, "failure": t.card_failure,
        "stop": t.card_stop.format(steps=MAX_STEPS)}


def _report_contract(context: RunContext, t: Texts, cases: list[Case], suite: str) -> None:
    context.emit("lesson.report", {
        "title": t.report_contract_title, "summary": t.report_contract_summary,
        "metrics": [{"id": "contract", "label": t.label_contract, "value": CONTRACT_VERSION},
                    {"id": "suite", "label": t.label_suite, "value": f"{suite} · {len(cases)}"},
                    {"id": "corpus", "label": t.label_corpus, "value": corpus_version(context.locale)},
                    {"id": "pass_line", "label": t.label_pass_line, "value": f"{round(PASS_LINE * 100)}%"}],
        "table": {"columns": list(t.columns_contract), "rows": [
            [t.task_names[task], ", ".join(f"{tool} ({t.modes[mode]})" for tool, mode in tools.items()),
             t.word_yes if WRITE in tools.values() else t.word_no] for task, tools in TASK_TOOLS.items()]}})


def _label(t: Texts, case: Case) -> str:
    return f"{case.id} · {t.kind_names[case.kind]} / {t.subkind_names[case.subkind]}"


def _tokens(t: Texts, rows: list[dict]):
    summary = summarize(rows)
    if summary["tokens"] is None:
        return t.value_not_reported if summary["model_calls"] else t.value_not_applicable
    return summary["tokens"] if not summary["unreported_calls"] else t.tokens_partly_reported.format(
        total=summary["tokens"], missing=summary["unreported_calls"])


def _publish_case(env: assistant.Env, case: Case, outcome: dict, verdict: dict) -> None:
    """Events of one judged case: the retrieval judgement, the citation check, and lesson.case_result."""
    context, t = env.context, env.t
    plan = outcome["plan"]
    passed = verdict["verdict"] == "passed"
    plan.set("verify", "done" if passed else "failed", t.categories[verdict["category"]])
    retrieval = verdict.get("retrieval")
    rounds = max(env.rounds, 1)
    if retrieval is not None:
        context.emit("lesson.retrieval_judge", {"query_id": case.id, "kind": case.subkind, "gold": list(case.gold),
                                                "provided": [chunk.chunk_id for chunk in outcome["provided"]],
                                                **retrieval}, rounds)
    if verdict.get("check") is not None:
        context.emit("lesson.citation_check", {"query_id": case.id, "answer_source": outcome["source"],
                                               "format_problems": outcome["problems"], **verdict["check"].to_dict(),
                                               "category": verdict["category"], "reasons": list(verdict["reasons"])},
                     rounds)
    summary = summarize(outcome["rows"])
    context.emit("lesson.case_result", {
        "case": case.id, "split": case.split, "kind": case.kind, "subkind": case.subkind, "rev": case.rev,
        "verdict": verdict["verdict"], "verdict_label": t.verdicts[verdict["verdict"]],
        "category": verdict["category"], "category_label": t.categories[verdict["category"]],
        "checks": [{**item, "label": t.check_labels[item["id"]], "result": t.statuses[item["status"]]}
                   for item in verdict["checks"]],
        "failures": [t.check_labels[item["id"]] for item in verdict["checks"] if item["status"] == "fail"],
        "answer_source": outcome["source"], "model_calls": summary["model_calls"], "tool_calls": summary["tool_calls"],
        "approvals": summary["approvals"], "e2e_ms": outcome["e2e_ms"]}, rounds)


def _cost(t: Texts, values: Inputs, context: RunContext, rows: list[dict]):
    if not values.price_source.strip():
        return t.cost_none
    cost = estimate_cost(rows, values.price_input_per_m, values.price_output_per_m)
    if not cost["covered"]:
        return t.cost_no_usage
    return t.cost_value.format(amount=cost["amount"], currency=values.price_currency, model=context.model,
                               source=values.price_source.strip(), date=values.price_date, covered=cost["covered"],
                               calls=cost["calls"])


def _ledger_rows(t: Texts, rows: list[dict]) -> list[list]:
    table = []
    for row in rows:
        llm = row["kind"] == "llm"
        table.append([row["n"], row["case"], t.row_kinds[row["kind"]], row["name"], row["ms"],
                      (t.value_not_reported if row["input_tokens"] is None else row["input_tokens"]) if llm
                      else t.value_not_applicable,
                      (t.value_not_reported if row["output_tokens"] is None else row["output_tokens"]) if llm
                      else t.value_not_applicable,
                      t.row_status.get(row["status"], row["status"]), row.get("hits") if row.get("hits") is not None else "-"])
    return table


def _report_ledger(context: RunContext, t: Texts, values: Inputs, rows: list[dict], e2e_ms: float, title: str) -> None:
    summary = summarize(rows)
    context.emit("lesson.report", {
        "title": title, "summary": t.report_ledger_summary,
        "metrics": [{"id": "model_calls", "label": t.label_model_calls, "value": summary["model_calls"]},
                    {"id": "tool_calls", "label": t.label_tool_calls, "value": summary["tool_calls"]},
                    {"id": "approvals", "label": t.label_approvals, "value": summary["approvals"]},
                    {"id": "end_to_end_ms", "label": t.label_end_to_end, "value": e2e_ms},
                    {"id": "model_ms", "label": t.label_model_ms, "value": summary["model_ms"]},
                    {"id": "tool_ms", "label": t.label_tool_ms, "value": summary["tool_ms"]},
                    {"id": "waited_ms", "label": t.label_waited_ms, "value": summary["waited_ms"]},
                    {"id": "total_tokens", "label": t.label_total_tokens, "value": _tokens(t, rows)},
                    {"id": "unreported_calls", "label": t.label_unreported, "value": summary["unreported_calls"]},
                    {"id": "cost", "label": t.label_cost, "value": _cost(t, values, context, rows)}],
        "table": {"columns": list(t.columns_ledger), "rows": _ledger_rows(t, rows)}})


def _passed_flag(status: str):
    return {"pass": True, "fail": False}.get(status)


def _report_permissions(context: RunContext, t: Texts, outcome: dict) -> None:
    decisions = outcome["decisions"]
    probes = outcome.get("probes") or []
    rows = [[item["tool"], t.origin_names[item["origin"]], t.task_names[item["task"]], t.gate_verdicts[item["verdict"]],
             item["rule"]] for item in decisions]
    rows += [[probe["tool"], t.origin_names["runner_probe"], t.task_names[probe["task"]],
              t.layer_names[probe["layer"]], probe["rule"] or probe["error_type"] or "-"] for probe in probes]
    proposals = [item for item in decisions if item["origin"] == "model" and item["verdict"] != "allow"]
    context.emit("lesson.report", {
        "title": t.report_permissions_title, "summary": t.report_permissions_summary,
        "checks": [{"id": "probes", "label": t.check_labels["probes"], "passed": all(
            not probe["ok"] and not probe["executed"] for probe in probes), "detail": t.detail_probes.format(
            refused=sum(not probe["ok"] and not probe["executed"] for probe in probes), total=len(probes))}] if probes else [],
        "metrics": [{"id": "decisions", "label": t.label_decisions, "value": len(decisions)},
                    {"id": "model_denied", "label": t.label_model_denied, "value": len(proposals)},
                    {"id": "probe_refused", "label": t.label_probe_refused, "value": len(probes)},
                    {"id": "approvals", "label": t.label_approval_outcomes, "value": ", ".join(
                        t.decisions.get(item["outcome"], item["outcome"]) for item in outcome["approvals"]) or t.value_none}],
        "table": {"columns": list(t.columns_permissions), "rows": rows or [[t.value_none] * 5]}})


def _report_single(context: RunContext, t: Texts, values: Inputs, env: assistant.Env, result: dict) -> str:
    case, outcome, verdict = result["case"], result["outcome"], result["verdict"]
    summary = summarize(outcome["rows"])
    checks = [{"id": item["id"], "label": t.check_labels[item["id"]], "detail": item["detail"],
               **({"passed": _passed_flag(item["status"])} if _passed_flag(item["status"]) is not None else {})}
              for item in verdict["checks"]]
    source = {"model": t.source_model, "offline_fixture": t.source_fixture, None: t.value_none}[outcome["source"]]
    context.emit("lesson.report", {
        "title": t.report_case_title.format(case=_label(t, case)), "summary": t.report_case_summary, "checks": checks,
        "metrics": [{"id": "verdict", "label": t.label_verdict, "value": t.verdicts[verdict["verdict"]]},
                    {"id": "category", "label": t.label_category, "value": t.categories[verdict["category"]]},
                    {"id": "ended", "label": t.label_ended, "value": t.word_yes if outcome["ended"] else t.word_no},
                    {"id": "source", "label": t.label_source, "value": source},
                    {"id": "model_calls", "label": t.label_model_calls, "value": summary["model_calls"]},
                    {"id": "tool_calls", "label": t.label_tool_calls, "value": summary["tool_calls"]},
                    {"id": "note", "label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.columns_checks), "rows": [
            [t.check_labels[item["id"]], t.statuses[item["status"]], item["detail"]] for item in verdict["checks"]]}})
    _report_permissions(context, t, outcome)
    _report_ledger(context, t, values, outcome["rows"], outcome["e2e_ms"], t.report_ledger_title)
    return _answer_single(t, case, outcome, verdict)


def _percent(low: float, high: float) -> str:
    return f"{round(low * 100)}%–{round(high * 100)}%"


def _report_suite(context: RunContext, t: Texts, values: Inputs, env: assistant.Env, results: list[dict],
                  suite: str) -> str:
    total = len(results)
    verdicts = [item["verdict"]["verdict"] for item in results]
    passed, unassessable = verdicts.count("passed"), verdicts.count("unassessable")
    ended = sum(item["outcome"]["ended"] for item in results)
    low, high = wilson(passed, total)
    decision = verifier.decide_acceptance(results, from_fixture=context.mode == "offline")
    acceptance, invariants_ok = decision["state"], decision["invariants_ok"]
    holdout_rate = decision["holdout_rate"]
    splits = {item["case"].split for item in results}
    shown_rate = round(holdout_rate * 100) if holdout_rate is not None else 0
    detail = {"fixture": t.detail_accept_fixture, "undecided": t.detail_accept_no_holdout,
              "accepted": t.detail_accept_ok, "rejected": (t.detail_accept_below if invariants_ok
                                                          else t.detail_accept_invariants)}[acceptance].format(
        rate=shown_rate, line=round(PASS_LINE * 100))
    invariants = t.detail_invariants.format(ok=decision["invariants_pass"], total=decision["invariants_total"])
    rows = [[_label(t, item["case"]), t.split_names[item["case"].split],
             t.word_yes if item["outcome"]["ended"] else t.word_no, t.verdicts[item["verdict"]["verdict"]],
             t.categories[item["verdict"]["category"]],
             t.reason_separator.join(c["detail"] for c in item["verdict"]["checks"] if c["status"] in ("fail", "unassessable"))
             or t.value_none] for item in results]
    context.emit("lesson.report", {
        "title": t.report_suite_title.format(splits=" + ".join(t.split_names[s] for s in sorted(splits))),
        "summary": t.report_suite_summary.format(ended=ended, passed=passed, total=total),
        "checks": [{"id": "invariants", "label": t.check_invariants, "passed": invariants_ok, "detail": invariants}],
        "metrics": [{"id": "ended", "label": t.label_ended_count, "value": f"{ended}/{total}"},
                    {"id": "passed", "label": t.label_passed, "value": f"{passed}/{total}"},
                    {"id": "failed", "label": t.label_failed, "value": total - passed - unassessable},
                    {"id": "unassessable", "label": t.label_unassessable, "value": unassessable},
                    {"id": "interval", "label": t.label_interval, "value": _percent(low, high)},
                    {"id": "suite", "label": t.label_suite, "value": f"{suite} · {total}"},
                    {"id": "note", "label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.columns_suite), "rows": rows}})
    # The failure classification: which link broke first, counted over the cases that failed. An unassessable case
    # did not fail (nothing broke, something could not be judged), so it is not a failure category; the suite
    # table above keeps it with the reason.
    groups = failure_groups(results)
    context.emit("lesson.report", {
        "title": t.report_failures_title, "summary": t.report_failures_summary,
        "metrics": [{"id": "failure_kinds", "label": t.label_failure_kinds, "value": len(groups)}],
        "table": {"columns": list(t.columns_failures), "rows": [
            [t.categories[category], len(ids), ", ".join(ids)] for category, ids in groups.items()]
            or [[t.value_none, 0, t.value_none]]}})
    e2e = round(sum(item["outcome"]["e2e_ms"] for item in results), 1)
    _report_ledger(context, t, values, env.ledger.rows, e2e, t.report_ledger_title)
    context.emit("lesson.report", {
        "title": t.report_acceptance_title, "summary": t.acceptance_summaries[acceptance],
        "checks": [{"id": "invariants", "label": t.check_invariants, "passed": invariants_ok, "detail": invariants}]
        + ([{"id": "holdout", "label": t.check_holdout, "passed": holdout_rate >= PASS_LINE, "detail": detail}]
           if holdout_rate is not None and invariants_ok and acceptance != "fixture" else []),
        "metrics": [{"id": "acceptance", "label": t.label_acceptance, "value": t.acceptance_names[acceptance]},
                    {"id": "holdout_rate", "label": t.label_holdout_rate,
                     "value": f"{decision['holdout_passed']}/{decision['holdout_total']}" if decision["holdout_total"]
                     else t.value_none},
                    {"id": "pass_line", "label": t.label_pass_line, "value": f"{round(PASS_LINE * 100)}%"}],
        "table": {"columns": list(t.columns_limits), "rows": [[item] for item in t.limits]}})
    return t.answer_suite.format(passed=passed, total=total, ended=ended, acceptance=t.acceptance_names[acceptance],
                                 detail=detail)


def failure_groups(results: list[dict]) -> dict[str, list[str]]:
    """Failed cases by the first broken link. Passed and unassessable cases are not failures and never appear."""
    groups: dict[str, list[str]] = {}
    for item in results:
        if item["verdict"]["verdict"] == "failed":
            groups.setdefault(item["verdict"]["category"], []).append(item["case"].id)
    return groups


def _no_answer(t: Texts, outcome: dict) -> str:
    """A run that never answered is not a malformed answer: say which of the two happened."""
    return t.answer_invalid if outcome.get("ended") else t.answer_not_ended.format(steps=outcome.get("steps", 0))


def _answer_single(t: Texts, case: Case, outcome: dict, verdict: dict) -> str:
    """The text shown to the learner is rebuilt from checked facts; unchecked model prose never passes as the answer."""
    lines = [t.answer_heading.format(case=_label(t, case), question=t.case_questions[case.id])]
    if case.kind in ("ask", "injection"):
        check = verdict.get("check")
        if check is None:
            lines.append(_no_answer(t, outcome))
        else:
            for claim in check.claims:
                ids = ", ".join(c.chunk_id for c in claim.citations)
                lines.append(t.answer_claim.format(text=claim.text, ids=ids,
                                                   status=t.status_checked if claim.supported else t.status_failed))
            for item in check.conflicts:
                lines.append(t.answer_conflict.format(topic=item.topic, docs=", ".join(item.doc_ids),
                                                      current=item.current or t.answer_current_unknown))
            if check.insufficient_evidence:
                lines.append(t.answer_insufficient.format(missing=check.missing))
        if case.kind == "injection":
            probes = outcome.get("probes", [])
            lines.append(t.answer_probes.format(refused=sum(not p["ok"] and not p["executed"] for p in probes),
                                                total=len(probes)))
    elif case.kind == "practice":
        answer = outcome.get("answer")
        if answer is None:
            lines.append(_no_answer(t, outcome))
        else:
            for item in answer.items:
                ids = ", ".join(c.chunk_id for c in item.citations)
                lines.append(t.answer_practice.format(question=item.question, answer=item.reference_answer, ids=ids))
            if answer.insufficient_evidence:
                lines.append(t.answer_insufficient.format(missing=answer.missing))
    elif case.kind == "trace":
        truth, explanation = outcome["truth"], outcome.get("explanation")
        lines.append(t.answer_trace_truth.format(**{key: (t.word_yes if value is True else t.word_no if value is False else value)
                                                    for key, value in truth.items()}))
        lines.append(t.answer_trace_said.format(summary=explanation.summary) if explanation else _no_answer(t, outcome))
    else:
        approvals = [t.decisions.get(item["outcome"], item["outcome"]) for item in outcome["approvals"]]
        lines.append(t.answer_progress.format(
            decision=", ".join(approvals) or t.decisions["none"],
            records=", ".join(f"{row['lesson']}={t.status_names.get(row['status'], row['status'])} v{row['version']}"
                              for row in outcome["records"]) or t.value_none))
        if case.subkind == "recovery":
            lines.append(t.answer_recovery.format(first=_resume_text(t, outcome["resume_first"]),
                                                  second=_resume_text(t, outcome["resume_second"])))
        recall = outcome.get("recall")
        if recall:
            lines.append(t.answer_recall.format(records=", ".join(row["lesson"] for row in recall["records"]) or t.value_none))
    lines.append(t.answer_verdict.format(verdict=t.verdicts[verdict["verdict"]], category=t.categories[verdict["category"]]))
    return "\n".join(lines)


def _resume_text(t: Texts, result: dict | None) -> str:
    if result is None:
        return t.value_none
    return t.resume_reasons.get(result["reason"], result["reason"])

