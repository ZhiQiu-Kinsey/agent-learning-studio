"""Offline test model and approval policy for hooks-approval: they serve automated tests only.

The "model" follows a fixed script per task and stands for no real model; the calls it proposes are
real and run through the real gate against a real temporary desk. The "learner" is a stand-in policy
that decides each approval card the way the task needs (approve, reject, time out, or edit), recorded
as decided_by: offline_fixture. Neither has a web entry: a live run is decided by a person.
"""
import json

from lessons.lesson_hooks_approval.hooks import BROADCAST
from lessons.lesson_hooks_approval.locales import texts_for
from server.offline import offline_marker, tool_call

TASKS = {"approve-write": "approve_write", "reject-timeout": "reject_timeout", "edit-recheck": "edit_recheck",
         "swap-guard": "swap_guard"}
OUTSIDE_RECIPIENT = "carol@outside.example"  # what the stand-in learner types into an editable card


def _task(exercise_id, inputs):
    return (inputs or {}).get("task") or TASKS.get(exercise_id, "approve_write")


def _plan(task, t, results):
    """The next call the scripted model proposes, as (tool, arguments); None when the script is over."""
    notice = lambda recipient, record_id, subject=None: ("send_notice", {  # noqa: E731
        "recipient": recipient, "subject": subject or t.script_notice_subject.format(record_id=record_id),
        "body": t.script_notice_body.format(record_id=record_id)})
    if task == "approve_write":
        script = [("list_records", {}), ("read_record", {"record_id": "tkt-102"}),
                  ("update_record", {"record_id": "TKT-102", "field": "status", "value": "resolved"}),
                  notice(" Alice@Corp.Example ", "TKT-102")]
    elif task == "reject_timeout":
        script = [("read_record", {"record_id": "TKT-103"}),
                  ("update_record", {"record_id": "TKT-103", "field": "status", "value": "resolved"}),
                  notice(BROADCAST[0], "TKT-103", t.script_broadcast_subject.format(record_id="TKT-103"))]
        # After the broadcast is rejected, the model reads its note and writes to the owner only.
        if len(results) >= len(script):
            owner = results[0]["result"]["data"]["owner_email"]
            script.append(notice(owner, "TKT-103"))
    elif task == "edit_recheck":
        script = [("read_record", {"record_id": "TKT-104"}), notice("carol@corp.example", "TKT-104")]
    else:
        script = [notice("alice@corp.example", "TKT-102")]
    return script[len(results)] if len(results) < len(script) else None


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    task = _task(exercise_id, inputs)
    t = texts_for(locale)

    def complete(body, api_key):
        results = [json.loads(message["content"]) for message in body["messages"]
                   if message["role"] == "tool"]
        step = _plan(task, t, results)
        if step is None:
            # A result is the platform's {"ok", "result"} wrapper; a failure before the gate has no inner dict.
            inner = [result.get("result", result) for result in results]
            failures = [result["error"] for result in inner if not result["ok"]]
            text = t.script_partial.format(reasons=" ".join(failures)) if failures else t.script_done[task]
            return {"choices": [{"message": {"role": "assistant", "content": offline_marker(locale) + text},
                                 "finish_reason": "stop"}]}
        call = tool_call(step[0], step[1], len(results) + 1)
        return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [call]},
                             "finish_reason": "tool_calls"}]}

    return complete


def create_approval_policy(exercise_id, inputs=None, locale="zh-CN"):
    """Decide each card like the task needs: a deterministic stand-in for the learner."""
    task = _task(exercise_id, inputs)
    t = texts_for(locale)

    def policy(request):
        tool, arguments = request["payload"]["tool"], request["payload"]["arguments"]
        if task == "reject_timeout" and tool == "send_notice":
            if arguments["recipient"] in BROADCAST:
                return {"decision": "reject", "note": t.script_reject_note}
            return {"decision": "timeout"}
        if task == "edit_recheck" and tool == "send_notice" and request["editable"]:
            return {"decision": "approve", "note": None,
                    "edited_payload": {"tool": tool, "arguments": {**arguments, "recipient": OUTSIDE_RECIPIENT}}}
        return {"decision": "approve"}

    return policy
