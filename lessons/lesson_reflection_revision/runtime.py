"""Reflection and bounded revision: one regex task, revised once from the model's self-review and once from real test results.

The artifact is a regular expression; the tests run Python re.fullmatch on fixed cases and never run code the model wrote.
The idea of "self-evaluation and correction" follows Microsoft AI Agents for Beginners 09 (MIT);
the task, tests, review format, stop conditions and experiments are written by this project.
"""
import json
import re
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_reflection_revision.locales import Texts, texts_for


class Inputs(LessonInputs):
    reviewer: Literal["self", "tests"] = "tests"
    max_iters: int = Field(default=3, ge=1, le=3)


INPUT_MODEL = Inputs
# 9 fixed cases: 3 should match, 6 should not, including "first digit is 0", which is easy to miss when reading the spec.
CASES = [("s-1042", True), ("s-9999", True), ("s-1000", True),
         ("s-0420", False), ("S-1042", False), ("s-104", False), ("s-10422", False), ("s1042", False), ("s-12a4", False)]
MAX_PATTERN = 200
# The task (t.spec) and the two system prompts (t.writer_system, t.self_review_system) are in locales/.


def run_tests(t: Texts, pattern: str) -> dict:
    """Run re.fullmatch on the fixed cases for real. If the pattern does not compile, every case fails."""
    # Limit the length before compiling: the model's string is only regex data; no model-written code runs.
    if not isinstance(pattern, str) or not pattern or len(pattern) > MAX_PATTERN:
        return {"compiled": False, "error": t.pattern_invalid.format(limit=MAX_PATTERN), "passed": 0,
                "failed": len(CASES), "cases": []}
    try:
        compiled = re.compile(pattern)
    except re.error as error:
        return {"compiled": False, "error": t.pattern_not_compiled.format(error=error), "passed": 0,
                "failed": len(CASES), "cases": []}
    # Every case is matched once for real; the actual and the expected result are recorded side by side.
    cases = [{"text": text, "expected": expected, "actual": compiled.fullmatch(text) is not None} for text, expected in CASES]
    passed = sum(case["expected"] == case["actual"] for case in cases)
    return {"compiled": True, "error": None, "passed": passed, "failed": len(CASES) - passed, "cases": cases}


def failures_of(t: Texts, tests: dict) -> list[str]:
    """Turn failed cases into review feedback: everything the tests arm hands back to the writer comes from here."""
    if not tests["compiled"]:
        return [tests["error"]]
    word = {True: "match", False: "no_match"}
    return [t.failure.format(text=case["text"], expected=t.expected_words[word[case["expected"]]],
                             actual=t.actual_words[word[case["actual"]]])
            for case in tests["cases"] if case["expected"] != case["actual"]]


def extract_json(t: Texts, content: str) -> dict:
    """Read the first JSON object in a reply; text or a code fence around it is allowed, nothing else is repaired."""
    start = content.find("{")
    if start < 0:
        raise ValueError(t.no_json_object)
    value, _ = json.JSONDecoder().raw_decode(content[start:])
    if not isinstance(value, dict):
        raise ValueError(t.json_not_object)
    return value


def _tokens(response: dict) -> int | None:
    usage = response.get("usage")
    total = usage.get("total_tokens") if isinstance(usage, dict) else None
    return total if isinstance(total, int) else None


class Writer:
    """The model calls of one run: drafts and self-reviews both go through ask, which records the reported usage."""

    def __init__(self, context: RunContext, t: Texts):
        self.context = context
        self.t = t
        self.rounds = 0
        self.usage: list[int | None] = []

    def ask(self, system: str, user: str) -> str:
        self.rounds += 1
        response = self.context.complete({"messages": [{"role": "system", "content": system},
                                                       {"role": "user", "content": user}], "temperature": 0},
                                         self.rounds)
        self.usage.append(_tokens(response))
        content = response["choices"][0].get("message", {}).get("content")
        return content if isinstance(content, str) else ""

    def draft(self, user: str, version: int, previous: str | None) -> str:
        """Ask for one regex and emit lesson.draft; a missing regex field is recorded as "" plus a parse error, not repaired."""
        content = self.ask(self.t.writer_system, user)
        try:
            pattern = extract_json(self.t, content).get("regex")
            pattern = pattern if isinstance(pattern, str) else ""
            error = None if pattern else self.t.missing_regex
        except ValueError as exc:
            pattern, error = "", str(exc)
        self.context.emit("lesson.draft", {"version": version, "regex": pattern, "previous": previous,
                                           "unchanged": previous is not None and pattern == previous,
                                           "parse_error": error, "raw": content}, self.rounds)
        return pattern


def review_by_tests(context: RunContext, t: Texts, pattern: str, iteration: int, round_number: int) -> tuple[str, list[str]]:
    """Test review: run the fixed cases once; the failed cases are the feedback."""
    tests = run_tests(t, pattern)
    context.emit("lesson.tests", {"version": iteration - 1, **tests}, round_number)
    issues = failures_of(t, tests)
    verdict = "pass" if not issues else "revise"
    context.emit("lesson.review", {"iteration": iteration, "source": "tests", "verdict": verdict,
                                   "issues": issues}, round_number)
    return verdict, issues


def review_by_model(context: RunContext, writer: Writer, pattern: str, iteration: int) -> tuple[str, list[str]]:
    """Model self-review: one more request; the reviewer sees only the spec and the regex, no run results."""
    t = writer.t
    content = writer.ask(t.self_review_system, t.self_review_request.format(spec=t.spec, pattern=pattern))
    try:
        review = extract_json(t, content)
        # Only pass or revise counts as a verdict; anything else is malformed and stops the loop.
        verdict = review.get("verdict") if review.get("verdict") in ("pass", "revise") else "invalid"
        issues = [str(item) for item in review.get("issues", [])] if isinstance(review.get("issues"), list) else []
    except ValueError:
        verdict, issues = "invalid", []
    context.emit("lesson.review", {"iteration": iteration, "source": "model", "verdict": verdict,
                                   "issues": issues, "raw": content}, writer.rounds)
    return verdict, issues


def run(context: RunContext) -> str:
    """The revision loop: the two arms differ only in the review source; drafting, stopping and the final check are identical."""
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    writer = Writer(context, t)
    # 1. First draft: the spec only.
    pattern = writer.draft(t.draft_request.format(spec=t.spec), 0, None)
    stop, history = "limit", []
    for iteration in range(1, values.max_iters + 1):
        # 2. Review: the tests arm runs the real cases, the self arm asks the model once more.
        if values.reviewer == "tests":
            verdict, issues = review_by_tests(context, t, pattern, iteration, writer.rounds)
        else:
            verdict, issues = review_by_model(context, writer, pattern, iteration)
        history.append([iteration, pattern, t.reviewer_names[values.reviewer], verdict,
                        t.issue_separator.join(issues) or "—"])
        # 3. Stop conditions: review passed, malformed review output, or the limit reached; no revision after any of them.
        if verdict == "pass":
            stop = "passed"
            break
        if verdict == "invalid":
            stop = "invalid"
            break
        if iteration == values.max_iters:
            break
        # 4. Revise: hand the previous version and the feedback back; no new version is a stop reason too.
        previous = pattern
        pattern = writer.draft(t.revision_request.format(spec=t.spec, previous=previous,
                                                         issues=json.dumps(issues, ensure_ascii=False)),
                               iteration, previous)
        if pattern == previous:
            stop = "unchanged"
            break
    # 5. Final check: whatever the review source, the final version is checked against the same real cases.
    final = run_tests(t, pattern)
    context.emit("lesson.tests", {"version": "final", **final}, writer.rounds)
    return _report(context, t, values, t.stop_reasons[stop], history, final, pattern, writer)


def _report(context: RunContext, t: Texts, values: Inputs, stop_reason: str, history: list[list], final: dict,
            pattern: str, writer: Writer) -> str:
    """Emit the lab report (lesson.report) and return the final answer; total_tokens adds only what the provider reported."""
    reported = [value for value in writer.usage if value is not None]
    if len(reported) == len(writer.usage):
        tokens = sum(reported)
    else:
        missing = len(writer.usage) - len(reported)
        tokens = t.tokens_partly_reported.format(total=sum(reported), missing=missing) if reported else t.value_not_reported
    detail = (t.final_detail_error.format(passed=final["passed"], total=len(CASES), error=final["error"])
              if final["error"] else t.final_detail.format(passed=final["passed"], total=len(CASES)))
    context.emit("lesson.report", {
        "title": t.report_titles[values.reviewer],
        "summary": t.report_summary,
        "checks": [{"label": t.check_final, "passed": final["failed"] == 0, "detail": detail}],
        "metrics": [{"label": t.label_stop_reason, "value": stop_reason},
                    {"label": t.label_iterations, "value": len(history)},
                    {"label": t.label_max_iters, "value": values.max_iters},
                    {"label": t.label_model_calls, "value": writer.rounds},
                    {"label": t.label_total_tokens, "value": tokens},
                    {"label": t.label_final_regex, "value": pattern or t.value_empty},
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.table_columns), "rows": history},
    })
    answer = t.answer_passed if final["failed"] == 0 else t.answer_failed
    return answer.format(reason=stop_reason, pattern=pattern or t.value_empty, passed=final["passed"], total=len(CASES))
