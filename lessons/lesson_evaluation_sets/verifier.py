"""The independent verifier: judges one case from the recorded trajectory and the case spec only.

It never calls a model or a tool and never reads what the agent says about itself. Each
check reports pass, fail, na (does not apply) or unassessable (the verifier lacks what it
would need to decide), and the checks are kept apart: a run can end, call the right tool
and still give a wrong or unsupported answer.
"""
import json
import math
import re

from lessons.lesson_evaluation_sets.cases import COMMUTATIVE, Case

ANSWER_TAG = re.compile(r"<answer>(.*?)</answer>", re.S | re.I)
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
# The answer may round a quotient to two decimals; call arguments must match exactly.
ANSWER_TOLERANCE = 0.005


def parse_answer(content: str | None) -> dict:
    """Read the last <answer> tag: NONE, a list of numbers, or missing (no tag, or a tag with neither)."""
    tags = ANSWER_TAG.findall(content or "")
    if not tags:
        return {"kind": "missing", "numbers": []}
    text = tags[-1].strip()
    numbers = [float(value) for value in NUMBER.findall(text)]
    if numbers:
        return {"kind": "numbers", "numbers": numbers}
    return {"kind": "none" if text.upper() == "NONE" else "missing", "numbers": []}


def parsed_arguments(call: dict) -> dict | None:
    try:
        value = json.loads(call["arguments"] or "{}")
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def resolve(ref: str, calls: list[dict]):
    """The value of tool.field in the first successful result of that tool; None when the run has no such result."""
    name, key = ref.split(".", 1)
    for call in calls:
        result = call["result"]
        if call["name"] == name and result.get("ok") and isinstance(result.get("result"), dict):
            return result["result"].get(key)
    return None


def _same_number(left, right, tolerance=1e-9) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return False
    return abs(left - right) <= tolerance * max(1.0, abs(left), abs(right))


def expected_calls(case: Case, calls: list[dict]) -> list[tuple[str, dict | None]]:
    """Expected calls with every ref replaced by the recorded value; None marks an argument whose source is missing."""
    resolved = []
    for name, arguments in case.calls:
        values = {key: resolve(value["ref"], calls) if isinstance(value, dict) else value
                  for key, value in arguments.items()}
        resolved.append((name, None if any(value is None for value in values.values()) else values))
    return resolved


def same_call(expected: tuple[str, dict | None], call: dict) -> bool:
    """Compare a parsed call with an expected one: names equal, arguments equal as numbers, not as text."""
    name, arguments = expected
    actual = parsed_arguments(call)
    if call["name"] != name or arguments is None or actual is None or set(actual) != set(arguments):
        return False
    if name in COMMUTATIVE:
        values = list(actual.values())
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            return False
        return all(_same_number(a, b) for a, b in zip(sorted(arguments.values()), sorted(values)))
    return all(_same_number(arguments[key], actual[key]) for key in arguments)


def compare_calls(case: Case, calls: list[dict], t) -> tuple[str, str]:
    """Structured comparison of the calls the agent made against the spec, by the case's mode."""
    shown = t.calls_separator.join(f"{call['name']}({call['arguments']})" for call in calls) or t.no_calls
    if case.mode == "none":
        return ("pass", t.detail_no_call_expected) if not calls else ("fail", t.detail_unexpected_calls.format(calls=shown))
    expected = expected_calls(case, calls)
    if any(arguments is None for _, arguments in expected):
        return "fail", t.detail_source_missing.format(calls=shown)
    if len(calls) != len(expected):
        return "fail", t.detail_call_count.format(expected=len(expected), actual=len(calls), calls=shown)
    if case.mode == "sequence":
        matched = all(same_call(spec, call) for spec, call in zip(expected, calls))
    else:
        # unordered: every expected call must be matched by a different actual call.
        remaining = list(calls)
        matched = True
        for spec in expected:
            hit = next((call for call in remaining if same_call(spec, call)), None)
            if hit is None:
                matched = False
                break
            remaining.remove(hit)
    wanted = t.calls_separator.join(f"{name}({json.dumps(arguments)})" for name, arguments in expected)
    return ("pass", t.detail_calls_match) if matched else ("fail", t.detail_calls_differ.format(expected=wanted, calls=shown))


def expected_numbers(case: Case, calls: list[dict]) -> list[float] | None:
    """The numbers a correct answer must give; None when they depend on a tool result this run never produced."""
    spec = case.answer
    if "values" in spec:
        return [float(value) for value in spec["values"]]
    operation, *operands = spec["compute"]
    values = [resolve(item, calls) if isinstance(item, str) else item for item in operands]
    if any(not isinstance(value, (int, float)) for value in values):
        return None
    # The verifier does its own arithmetic: it never trusts the result of the agent's add or divide call.
    return [float(values[0] + values[1]) if operation == "add" else values[0] / values[1]]


def check_correct(case: Case, answer: dict, calls: list[dict], t) -> tuple[str, str]:
    if case.answer.get("open"):
        return "unassessable", t.detail_open_answer
    if case.answer.get("none"):
        return ("pass", t.detail_none_expected) if answer["kind"] == "none" else (
            "fail", t.detail_expected_none.format(answer=_shown(answer, t)))
    if answer["kind"] == "missing":
        return "fail", t.detail_no_answer_tag
    expected = expected_numbers(case, calls)
    if expected is None:
        return "unassessable", t.detail_truth_unknown
    remaining = list(answer["numbers"])
    matched = len(remaining) == len(expected)
    for value in expected:
        hit = next((item for item in remaining if abs(item - value) <= ANSWER_TOLERANCE), None)
        if hit is None:
            matched = False
            break
        remaining.remove(hit)
    detail = t.detail_expected_numbers.format(expected=_numbers(expected), actual=_shown(answer, t))
    return ("pass" if matched else "fail"), detail


def _leaves(value) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)) and math.isfinite(value):
        return [float(value)]
    if isinstance(value, dict):
        return [number for item in value.values() for number in _leaves(item)]
    return []


def check_evidence(case: Case, answer: dict, calls: list[dict], question: str, t) -> tuple[str, str]:
    """Is every number in the answer backed by this run: a successful tool result or the question itself?"""
    failed = [call for call in calls if not call["result"].get("ok")]
    if answer["kind"] == "numbers":
        known = [float(value) for value in NUMBER.findall(question)]
        known += [number for call in calls if call["result"].get("ok") for number in _leaves(call["result"].get("result"))]
        unsupported = [value for value in answer["numbers"]
                       if not any(abs(value - item) <= ANSWER_TOLERANCE for item in known)]
        if unsupported:
            return "fail", t.detail_unsupported.format(numbers=_numbers(unsupported))
        return "pass", t.detail_supported
    if answer["kind"] == "none" and case.calls:
        # NONE is only backed when a tool was tried and failed; giving up untried has no evidence.
        return ("pass", t.detail_none_backed) if failed else ("fail", t.detail_none_untried)
    return "na", t.detail_evidence_na


def find_violations(case: Case, answer: dict, calls: list[dict], allowed: set[str], t) -> list[dict]:
    """Process rules that hold whatever the answer is."""
    found = []
    for call in calls:
        if call["name"] not in allowed:
            found.append({"id": "unregistered_tool", "detail": t.violation_unregistered.format(name=call["name"])})
    # A call that needs another tool's result must come in a later step than that result.
    for name, arguments in case.calls:
        sources = {value["ref"].split(".", 1)[0] for value in arguments.values() if isinstance(value, dict)}
        for source in sources:
            ready = next((call["step"] for call in calls if call["name"] == source and call["result"].get("ok")), None)
            early = [call for call in calls if call["name"] == name and (ready is None or call["step"] <= ready)]
            if early:
                found.append({"id": "guessed_dependency", "detail": t.violation_guessed.format(name=name, source=source)})
    if case.answer.get("none") and answer["kind"] == "numbers" and any(not call["result"].get("ok") for call in calls):
        found.append({"id": "number_after_failure", "detail": t.violation_number_after_failure})
    return found


def verify(case: Case, trajectory: dict, question: str, allowed: set[str], t) -> dict:
    """All checks for one case run, and the verdict: passed, failed, or unassessable when nothing failed but correctness cannot be decided."""
    calls = trajectory["calls"]
    answer = parse_answer(trajectory["content"])
    ended = ("pass", t.detail_ended) if trajectory["ended"] else ("fail", t.detail_not_ended.format(rounds=trajectory["model_calls"]))
    results = {
        "ended": ended,
        "calls": compare_calls(case, calls, t),
        "correct": check_correct(case, answer, calls, t) if trajectory["ended"] else ("fail", t.detail_no_final),
        "evidence": check_evidence(case, answer, calls, question, t) if trajectory["ended"] else ("na", t.detail_evidence_na),
    }
    violations = find_violations(case, answer, calls, allowed, t)
    results["violations"] = ("fail", t.reason_separator.join(v["detail"] for v in violations)) if violations else ("pass", t.detail_no_violation)
    checks = [{"id": key, "label": t.check_labels[key], "status": status, "detail": detail}
              for key, (status, detail) in results.items()]
    statuses = [check["status"] for check in checks]
    verdict = "failed" if "fail" in statuses else "unassessable" if "unassessable" in statuses else "passed"
    return {"verdict": verdict, "checks": checks, "violations": violations, "answer": answer}


def _numbers(values) -> str:
    return ", ".join(f"{value:g}" for value in values)


def _shown(answer: dict, t) -> str:
    if answer["kind"] == "numbers":
        return _numbers(answer["numbers"])
    return "NONE" if answer["kind"] == "none" else t.value_missing
