"""Offline test model for file-edit-evidence: serves automated tests only and does not stand for any real model.

The scripted "model" reads the repository through the real read_file tool and builds its edit arguments from what the
tool returned, then makes the same fix with the strategy of the exercise (one write tool per exercise). The tools,
the tests and the hashes are real; only the decisions are scripted. Two choices are deliberate test data:

- "lines" sends both edits from one read, in file order, so the second one meets the stale line numbers and is
  refused, exactly the failure that exercise exists to show;
- no response carries usage, so the report shows "not reported" instead of an invented number.
"""
import json
import re
from pathlib import Path

# The final message of the scripted model per run language. It lives in a JSON file so that no Chinese string sits in
# this module (the hard-coded Chinese baseline only goes down).
SCRIPT = json.loads((Path(__file__).parent / "fixture_replies.json").read_text(encoding="utf-8"))
PATH = "shop/pricing.py"
OLD_TIER = ('    """Share taken off an order: 15% from 200, 10% from 100, otherwise nothing."""\n'
            "    if amount >= 200:\n        return 0.15\n")
NEW_TIER = ('    """Share taken off an order: 20% from 300, 15% from 200, 10% from 100, otherwise nothing."""\n'
            "    if amount >= 300:\n        return 0.20\n    if amount >= 200:\n        return 0.15\n")
OLD_SHIPPING = "    if amount > FREE_SHIPPING_FROM:"
NEW_SHIPPING = "    if amount >= FREE_SHIPPING_FROM:"
# One response per turn: which tools it calls. "lines" re-reads after its second edit is refused.
TURNS = {
    "rewrite": ["read", "write", "tests", "final"],
    "replace": ["read", "edits", "tests", "final"],
    "lines": ["read", "edits", "read", "second_edit", "tests", "final"],
}


def _file_text(messages: list[dict]) -> tuple[str, dict[str, int]]:
    """The file as the latest read_file result showed it: its text and the line number of each line."""
    for message in reversed(messages):
        if message.get("role") != "tool":
            continue
        result = json.loads(message["content"]).get("result")
        if isinstance(result, dict) and result.get("path") == PATH:
            lines = [re.sub(r"^\s*\d+\| ?", "", row, count=1) for row in result["content"].split("\n")]
            return "\n".join(lines) + "\n", {text: number for number, text in enumerate(lines, 1)}
    raise AssertionError("the scripted model has not read the file yet")


def _call(turn: int, index: int, name: str, arguments: dict) -> dict:
    return {"id": f"call_{turn}_{index}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}


def _reply(calls: list[dict] | None = None, text: str = "") -> dict:
    message = {"role": "assistant", "content": text}
    if calls:
        message["tool_calls"] = calls
    return {"choices": [{"message": message, "finish_reason": "tool_calls" if calls else "stop"}]}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    strategy = exercise_id
    script = SCRIPT[locale]

    def complete(body, api_key):
        if strategy not in TURNS:
            raise AssertionError(f"exercise {strategy} calls no model")
        turns = TURNS[strategy]
        messages = body["messages"]
        turn = sum(1 for message in messages if message["role"] == "assistant")
        step = turns[turn]
        if step == "final":
            return _reply(text=script["final"])
        if step == "tests":
            return _reply([_call(turn, 1, "run_tests", {})])
        if step == "read":
            return _reply([_call(turn, 1, "read_file", {"path": PATH})])
        text, numbers = _file_text(messages)
        if step == "write":
            assert OLD_TIER in text and OLD_SHIPPING in text
            content = text.replace(OLD_TIER, NEW_TIER).replace(OLD_SHIPPING, NEW_SHIPPING)
            return _reply([_call(turn, 1, "write_file", {"path": PATH, "content": content})])
        if strategy == "replace":
            return _reply([_call(turn, 1, "edit_file", {"path": PATH, "old": OLD_TIER, "new": NEW_TIER}),
                           _call(turn, 2, "edit_file", {"path": PATH, "old": OLD_SHIPPING, "new": NEW_SHIPPING})])
        shipping = numbers[OLD_SHIPPING]
        if step == "second_edit":
            return _reply([_call(turn, 1, "edit_lines", {"path": PATH, "start_line": shipping, "end_line": shipping,
                                                        "new_text": NEW_SHIPPING})])
        # "lines", first edits: both from one read, top to bottom, so the numbers of the second are stale.
        first = numbers[OLD_TIER.split("\n")[0]]
        return _reply([_call(turn, 1, "edit_lines", {"path": PATH, "start_line": first, "end_line": first + 2,
                                                    "new_text": NEW_TIER}),
                       _call(turn, 2, "edit_lines", {"path": PATH, "start_line": shipping, "end_line": shipping,
                                                    "new_text": NEW_SHIPPING})])

    return complete


def create_approval_policy(exercise_id, inputs=None, locale="zh-CN"):
    """Offline tests approve the test command; the web page has no such shortcut."""
    return lambda request: {"decision": "approve"}
