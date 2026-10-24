"""Evaluation sets: run two versions of the tool agent from the first three lessons over a fixed case suite and compare them case by case.

The agent under test is the same tool loop as tool-selection, dependent-calls and fail-safely,
with their tools. The two versions differ in one thing only: version B adds a paragraph of
rules to the system prompt. An independent verifier (verifier.py) judges each case from the
recorded trajectory; every failed and unassessable case stays in the report. The judge
exercise checks an LLM judge against the author's human labels before trusting it.
Every text that reaches the model or an event is in locales/, one catalog per run language.
"""
import json
import math
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_01_tool_selection.tools import available_tools as basic_tools
from lessons.lesson_01_tool_selection.tools import tool_definitions as basic_definitions
from lessons.lesson_03_fail_safely.tools import available_tools as divide_tools
from lessons.lesson_03_fail_safely.tools import tool_definitions as divide_definitions
from lessons.lesson_evaluation_sets.cases import (CASE_ROUNDS, JUDGE_SAMPLES, SUITE_VERSION, Case, cases_for,
                                                  fingerprint)
from lessons.lesson_evaluation_sets.locales import Texts, texts_for
from lessons.lesson_evaluation_sets.verifier import verify


class Inputs(LessonInputs):
    task: Literal["compare", "judge"] = "compare"
    split: Literal["dev", "holdout"] = "dev"
    versions: Literal["A", "B", "both"] = "both"
    # Each extra repeat runs the whole suite again; two is enough to see a case flip.
    repeats: int = Field(default=1, ge=1, le=2)


INPUT_MODEL = Inputs
# Fewer than this many discordant pairs cannot reach p < 0.05 in a two-sided sign test,
# even if every one of them goes the same way (2 * 0.5**5 = 0.0625).
MIN_DISCORDANT = 6


def system_prompt(t: Texts, version: str) -> str:
    """The only difference between the versions: B inserts t.rules_b; the answer format is shared."""
    rules = t.rules_b if version == "B" else ""
    return t.base_prompt + rules + t.answer_format


class Rounds:
    """One round per model call across the whole run, so every request and its tool events share a round."""

    def __init__(self):
        self.value = 0

    def next(self) -> int:
        self.value += 1
        return self.value


def run_agent_case(context: RunContext, t: Texts, case: Case, version: str, rounds: Rounds) -> dict:
    """The agent under test: the native tool loop, but it records the trajectory and stops at the limit instead of raising."""
    tools = basic_definitions(context.locale) + divide_definitions(context.locale)
    available = {**basic_tools(context.locale), **divide_tools(context.locale)}
    messages = [{"role": "system", "content": system_prompt(t, version)},
                {"role": "user", "content": t.questions[case.id]}]
    calls, content = [], None
    for step in range(1, CASE_ROUNDS + 1):
        # 1. The whole history and the tools go out every step, as in course/runner.py.
        response = context.complete({"messages": messages, "tools": tools, "tool_choice": "auto",
                                     "temperature": 0}, rounds.next())
        message = response["choices"][0]["message"]
        proposals = message.get("tool_calls") or []
        # 2. No proposals: this is the final answer, and the run has ended.
        if not proposals:
            content = message.get("content") or ""
            break
        messages.append(message)
        # 3. Execute each proposal; the trajectory keeps the step, so the verifier can tell
        #    a call made after its source result from one guessed in the same step.
        for proposal in proposals:
            result = context.execute_proposal(proposal, available)
            calls.append({"step": step, "name": proposal["function"]["name"],
                          "arguments": proposal["function"].get("arguments") or "{}", "result": result})
            messages.append({"role": "tool", "tool_call_id": proposal["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    return {"calls": calls, "content": content, "ended": content is not None, "model_calls": step,
            "allowed": set(available)}


def run_suite(context: RunContext, t: Texts, cases: list[Case], version: str, repeats: int,
              rounds: Rounds) -> list[dict]:
    """Run every case of the suite, verify each one, and keep every result: passed, failed and unassessable."""
    results = []
    for repeat in range(1, repeats + 1):
        for case in cases:
            context.check_cancelled()
            trajectory = run_agent_case(context, t, case, version, rounds)
            # The verifier sees the spec and the recorded trajectory, never the agent's own verdict.
            outcome = verify(case, trajectory, t.questions[case.id], trajectory["allowed"], t)
            results.append({"case": case, "repeat": repeat, **outcome})
            _emit_case(context, t, case, version, repeat, trajectory, outcome, rounds.value)
    _suite_report(context, t, cases, version, repeats, results)
    return results


def passes(results: list[dict], case_id: str) -> int:
    return sum(item["verdict"] == "passed" for item in results if item["case"].id == case_id)


def paired(cases: list[Case], results_a: list[dict], results_b: list[dict]) -> list[dict]:
    """Pair the two versions case by case: the same case, the same number of runs, only the version differs."""
    rows = []
    for case in cases:
        a, b = passes(results_a, case.id), passes(results_b, case.id)
        change = "improved" if b > a else "regressed" if b < a else "unchanged"
        rows.append({"case": case, "a": a, "b": b, "change": change})
    return rows


def sign_test(improved: int, regressed: int) -> float:
    """Exact two-sided sign test over the discordant pairs; unchanged cases carry no information about the direction."""
    n = improved + regressed
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(improved, regressed) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def wilson(passed: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a pass rate; unlike p ± 2·SE it stays inside [0, 1] for small samples."""
    if total == 0:
        return 0.0, 1.0
    p = passed / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return max(0.0, centre - half), min(1.0, centre + half)


def run_judge(context: RunContext, t: Texts, rounds: Rounds) -> str:
    """Ask the judge model to grade the author's fixed answers by the rubric, then compare with the human labels."""
    rows = []
    for sample_id, human in JUDGE_SAMPLES:
        context.check_cancelled()
        request = t.judge_request.format(question=t.questions["greeting"], answer=t.judge_answers[sample_id])
        response = context.complete({"messages": [{"role": "system", "content": t.judge_system},
                                                  {"role": "user", "content": request}], "temperature": 0},
                                    rounds.next())
        verdict, reason = parse_judgement(response["choices"][0].get("message", {}).get("content"))
        rows.append({"sample": sample_id, "human": human, "judge": verdict, "reason": reason})
        context.emit("lesson.judgement", {"sample": sample_id, "human": human, "judge": verdict,
                                          "agree": verdict == human, "reason": reason}, rounds.value)
    return _judge_report(context, t, rows)


def parse_judgement(content) -> tuple[str, str]:
    """Only pass or fail in a JSON object is a verdict; anything else is invalid and counts as a disagreement."""
    text = content if isinstance(content, str) else ""
    start = text.find("{")
    try:
        value, _ = json.JSONDecoder().raw_decode(text[start:]) if start >= 0 else (None, 0)
    except ValueError:
        value = None
    if not isinstance(value, dict) or value.get("verdict") not in ("pass", "fail"):
        return "invalid", text[:200]
    return value["verdict"], str(value.get("reason", ""))[:200]


def kappa(rows: list[dict]) -> float | None:
    """Cohen's kappa: agreement beyond what the two label rates would give by chance; None when chance agreement is 1."""
    n = len(rows)
    observed = sum(row["human"] == row["judge"] for row in rows) / n
    labels = {row["human"] for row in rows} | {row["judge"] for row in rows}
    chance = sum((sum(r["human"] == k for r in rows) / n) * (sum(r["judge"] == k for r in rows) / n) for k in labels)
    return None if chance == 1 else (observed - chance) / (1 - chance)


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    rounds = Rounds()
    if values.task == "judge":
        _check_budget(context, t, len(JUDGE_SAMPLES))
        context.emit("lesson.task_card", t.judge_card)
        return run_judge(context, t, rounds)
    cases = cases_for(values.split)
    versions = ["A", "B"] if values.versions == "both" else [values.versions]
    # Refuse up front rather than stop halfway: a half-run suite would hide the cases it skipped.
    _check_budget(context, t, len(cases) * len(versions) * values.repeats * CASE_ROUNDS)
    context.emit("lesson.task_card", _card(t, values, cases, versions))
    results = {version: run_suite(context, t, cases, version, values.repeats, rounds) for version in versions}
    if len(versions) == 1:
        return _single_answer(t, values, cases, results[versions[0]])
    return _compare_report(context, t, values, cases, results["A"], results["B"])


def _check_budget(context: RunContext, t: Texts, worst: int) -> None:
    if worst > context.max_model_calls:
        raise ValueError(t.budget_too_small.format(worst=worst, limit=context.max_model_calls))


def _card(t: Texts, values: Inputs, cases: list[Case], versions: list[str]) -> dict:
    split = t.split_names[values.split]
    return {"goal": t.card_goal.format(versions=t.version_separator.join(versions), split=split),
            "input_scope": t.card_scope.format(split=split, count=len(cases), suite=SUITE_VERSION,
                                               fingerprint=fingerprint(cases)),
            "output": t.card_output, "evidence": t.card_evidence, "failure": t.card_failure,
            "stop": t.card_stop.format(rounds=CASE_ROUNDS, repeats=values.repeats)}


def _emit_case(context, t, case, version, repeat, trajectory, outcome, round_number) -> None:
    """Publish lesson.case_result: every check of one case run, with failures and unassessable checks listed by label."""
    checks = [{**check, "result": t.statuses[check["status"]]} for check in outcome["checks"]]
    context.emit("lesson.case_result", {
        "version": version, "split": case.split, "case": case.id, "category": case.category, "rev": case.rev,
        "repeat": repeat, "verdict": outcome["verdict"], "verdict_label": t.verdicts[outcome["verdict"]],
        "checks": checks, "answer": trajectory["content"], "violations": outcome["violations"],
        "failures": [check["label"] for check in checks if check["status"] == "fail"],
        "unassessable": [check["label"] for check in checks if check["status"] == "unassessable"],
        "model_calls": trajectory["model_calls"], "tool_calls": len(trajectory["calls"]),
    }, round_number)


def _percent(low: float, high: float) -> str:
    return f"{round(low * 100)}%–{round(high * 100)}%"


def _suite_report(context, t, cases, version, repeats, results) -> None:
    """One lab report per version: counts by verdict, how many runs merely ended, and one row per case."""
    total = len(results)
    passed = sum(item["verdict"] == "passed" for item in results)
    ended = sum(item["checks"][0]["status"] == "pass" for item in results)
    unassessable = sum(item["verdict"] == "unassessable" for item in results)
    metrics = [{"id": "ended", "label": t.label_ended, "value": f"{ended}/{total}"},
               {"id": "passed", "label": t.label_passed, "value": f"{passed}/{total}"},
               {"id": "failed", "label": t.label_failed, "value": total - passed - unassessable},
               {"id": "unassessable", "label": t.label_unassessable, "value": unassessable},
               {"id": "interval", "label": t.label_interval, "value": _percent(*wilson(passed, total))},
               {"id": "suite", "label": t.label_suite, "value": f"{SUITE_VERSION} · {fingerprint(cases)}"}]
    if repeats == 1:
        columns = list(t.columns_cases)
        rows = [[item["case"].id, t.categories[item["case"].category],
                 *[t.statuses[check["status"]] for check in item["checks"]], t.verdicts[item["verdict"]],
                 t.reason_separator.join(c["detail"] for c in item["checks"] if c["status"] in ("fail", "unassessable"))
                 or t.value_none] for item in results]
    else:
        columns = list(t.columns_repeats)
        rows, stable, all_passed, any_passed = [], 0, 0, 0
        for case in cases:
            verdicts = [item["verdict"] for item in results if item["case"].id == case.id]
            stable += len(set(verdicts)) == 1
            all_passed += all(v == "passed" for v in verdicts)
            any_passed += any(v == "passed" for v in verdicts)
            rows.append([case.id, t.categories[case.category], *[t.verdicts[v] for v in verdicts],
                         t.word_yes if len(set(verdicts)) == 1 else t.word_no])
        metrics += [{"id": "pass_all", "label": t.label_pass_all.format(k=repeats), "value": f"{all_passed}/{len(cases)}"},
                    {"id": "pass_any", "label": t.label_pass_any.format(k=repeats), "value": f"{any_passed}/{len(cases)}"},
                    {"id": "unstable", "label": t.label_unstable, "value": len(cases) - stable}]
    context.emit("lesson.report", {
        "title": t.suite_title.format(version=version, split=t.split_names[cases[0].split]),
        "summary": t.suite_summary.format(ended=ended, passed=passed, total=total),
        "metrics": metrics, "table": {"columns": columns, "rows": rows},
    })


def _single_answer(t, values, cases, results) -> str:
    passed = sum(item["verdict"] == "passed" for item in results)
    return t.answer_single.format(split=t.split_names[values.split], passed=passed, total=len(results))


def _compare_report(context, t, values, cases, results_a, results_b) -> str:
    """The paired comparison: improvements, regressions, the sign test and what it does not allow us to say."""
    pairs = paired(cases, results_a, results_b)
    improved = sum(row["change"] == "improved" for row in pairs)
    regressed = [row["case"].id for row in pairs if row["change"] == "regressed"]
    p_value = sign_test(improved, len(regressed))
    discordant = improved + len(regressed)
    if discordant < MIN_DISCORDANT:
        verdict = t.too_few_pairs.format(n=discordant, minimum=MIN_DISCORDANT)
    elif p_value < 0.05:
        verdict = t.direction_holds
    else:
        verdict = t.within_noise
    total = len(results_a)
    pass_a = sum(item["verdict"] == "passed" for item in results_a)
    pass_b = sum(item["verdict"] == "passed" for item in results_b)
    runs = values.repeats
    context.emit("lesson.report", {
        "title": t.compare_title.format(split=t.split_names[values.split]),
        "summary": verdict,
        "checks": [{"id": "no_regression", "label": t.check_no_regression, "passed": not regressed,
                    "detail": t.list_separator.join(regressed) or t.value_none}],
        "metrics": [{"id": "pass_a", "label": t.label_pass_version.format(version="A"), "value": f"{pass_a}/{total}"},
                    {"id": "pass_b", "label": t.label_pass_version.format(version="B"), "value": f"{pass_b}/{total}"},
                    {"id": "improved", "label": t.label_improved, "value": improved},
                    {"id": "regressed", "label": t.label_regressed, "value": len(regressed)},
                    {"id": "discordant", "label": t.label_discordant, "value": discordant},
                    {"id": "p_value", "label": t.label_p_value, "value": round(p_value, 3)},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.columns_compare),
                  "rows": [[row["case"].id, t.categories[row["case"].category], f"{row['a']}/{runs}",
                            f"{row['b']}/{runs}", t.changes[row["change"]]] for row in pairs]},
    })
    return t.answer_compare.format(split=t.split_names[values.split], pass_a=pass_a, pass_b=pass_b, total=total,
                                   improved=improved, regressed=len(regressed), verdict=verdict)


def _judge_report(context, t, rows) -> str:
    """Agreement with the human labels, the four cells of the confusion matrix, and Cohen's kappa."""
    agree = sum(row["human"] == row["judge"] for row in rows)
    cell = lambda human, judge: sum(r["human"] == human and r["judge"] == judge for r in rows)  # noqa: E731
    value = kappa(rows)
    context.emit("lesson.report", {
        "title": t.judge_title,
        "summary": t.judge_summary.format(agree=agree, total=len(rows)),
        "metrics": [{"id": "agreement", "label": t.label_agreement, "value": f"{agree}/{len(rows)}"},
                    {"id": "kappa", "label": t.label_kappa, "value": t.value_undefined if value is None else round(value, 2)},
                    {"id": "false_pass", "label": t.label_false_pass, "value": cell("fail", "pass")},
                    {"id": "false_fail", "label": t.label_false_fail, "value": cell("pass", "fail")},
                    {"id": "invalid", "label": t.label_invalid, "value": sum(r["judge"] == "invalid" for r in rows)},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.columns_judge),
                  "rows": [[r["sample"], t.labels[r["human"]], t.labels[r["judge"]],
                            t.word_yes if r["human"] == r["judge"] else t.word_no, r["reason"] or t.value_none] for r in rows]},
    })
    return t.answer_judge.format(agree=agree, total=len(rows))
