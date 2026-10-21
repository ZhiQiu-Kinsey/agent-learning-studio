"""Offline test model for long-running-tasks: serves automated tests only and stands for no real model.

It reads the history it is sent, like a model would: which jobs it started, which results the harness injected,
what a tool returned. The values it reports are copied from the injected messages, never typed in here, so a
result that was not injected yet cannot show up in its report. Each scenario scripts one habit on purpose:
nightly waits for results, late retries a failing job once, deep polls with check_job, cancels, restarts and runs
out of rounds. The scheduler scenario has no model and needs no fixture.
"""
import json
import re

from lessons.lesson_long_running_tasks.locales.fixture import texts_for

# Both the Chinese and the English injection line put a colon after the kind; \uff1a is the full-width one.
LINE = re.compile(r"^- (job-\d+) (\w+)[:\uff1a]", re.MULTILINE)
SCENARIO_OF = {"background-basic": "nightly", "failed-job": "late", "budget-stop": "deep"}


def _history(messages):
    """Starts, cancels, polls, injected results and whether a report was sent, read from the messages."""
    calls, started, cancelled, polls, reported = {}, [], set(), 0, False
    for message in messages:
        if message["role"] == "assistant":
            for call in message.get("tool_calls") or []:
                calls[call["id"]] = call["function"]
        elif message["role"] == "tool":
            function = calls.get(message["tool_call_id"], {})
            result = json.loads(message["content"])
            name = function.get("name")
            if name == "start_background_job" and result.get("ok"):
                started.append((result["result"]["job_id"], result["result"]["kind"]))
            elif name == "cancel_job" and result.get("ok"):
                cancelled.add(result["result"]["job_id"])
            elif name == "check_job":
                polls += 1
            elif name == "submit_report":
                reported = True
    injected = {}
    for message in messages:
        if message["role"] == "user":
            for line in message["content"].splitlines():
                found = LINE.match(line)
                if found:
                    value = re.search(r"value=(\w+)", line)
                    injected[found.group(1)] = {"kind": found.group(2), "value": value.group(1) if value else None}
    return {"started": started, "cancelled": cancelled, "polls": polls, "reported": reported, "injected": injected}


def _decide(scenario, state, words):
    """The script of one scenario: a list of (tool name, arguments), or a string for a reply without tools."""
    starts = lambda kind: [job for job, k in state["started"] if k == kind]  # noqa: E731
    values = {item["kind"]: item["value"] for item in state["injected"].values() if item["value"] is not None}
    failures = lambda kind: [job for job in starts(kind) if job in state["injected"] and state["injected"][job]["value"] is None]  # noqa: E731
    waiting = words.still_waiting if state["injected"] else words.waiting
    if not state["started"]:
        first = {"nightly": [("start_background_job", {"kind": "checksum_pack"}),
                             ("start_background_job", {"kind": "grade_stats"}),
                             ("read_policy", {"topic": "pass_line"})],
                 "late": [("start_background_job", {"kind": "checksum_pack"}),
                          ("start_background_job", {"kind": "late_import"})],
                 "deep": [("start_background_job", {"kind": "deep_scan"}),
                          ("start_background_job", {"kind": "checksum_pack"})]}
        return first[scenario]
    if scenario == "nightly":
        if {"checksum_pack", "grade_stats"} <= set(values) and not state["reported"]:
            return [("submit_report", {"results": [{"kind": kind, "value": values[kind]}
                                                   for kind in ("checksum_pack", "grade_stats")]})]
        return waiting
    if scenario == "late":
        if len(failures("late_import")) == len(starts("late_import")) and len(starts("late_import")) < 2:
            return [("start_background_job", {"kind": "late_import"})]
        if len(failures("late_import")) >= 2:
            return words.gave_up
        return waiting
    # deep: poll twice, cancel the scan once the other result is in, then start it again.
    scan = starts("deep_scan")[0]
    if state["polls"] < 2 and scan not in state["cancelled"]:
        return [("check_job", {"job_id": scan})]
    if "checksum_pack" in values and scan not in state["cancelled"]:
        return [("cancel_job", {"job_id": scan})]
    if scan in state["cancelled"] and len(starts("deep_scan")) < 2:
        return [("start_background_job", {"kind": "deep_scan"})]
    return words.restarted if scan in state["cancelled"] else waiting


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    scenario = (inputs or {}).get("scenario") or SCENARIO_OF.get(exercise_id, "nightly")
    words = texts_for(locale)

    def complete(body, api_key):
        messages = body["messages"]
        action = _decide(scenario, _history(messages), words)
        if isinstance(action, str):
            return {"choices": [{"message": {"role": "assistant", "content": action}, "finish_reason": "stop"}]}
        step = sum(message["role"] == "assistant" for message in messages) + 1
        calls = [{"id": f"call_{step}_{index}", "type": "function",
                  "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}
                 for index, (name, arguments) in enumerate(action, 1)]
        return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": calls},
                             "finish_reason": "tool_calls"}]}

    return complete
