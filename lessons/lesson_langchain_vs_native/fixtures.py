"""Offline test model for langchain-vs-native: serves automated tests only and stands for no real model.

Each side starts a fresh message history, so the same script serves both: no tool result yet
-> propose one call; tool results present -> answer from them. The arguments are written
compactly ('{"a":19,"b":23}'), the way many providers send them, so the test can see the
framework re-serialize them in its second request. The tools still really run.
"""
import json

from server.offline import CompletionScript, result_answer

CALLS = {"sum": ("add_numbers", {"a": 19, "b": 23}), "divide-zero": ("divide_numbers", {"a": 12, "b": 0})}


def compact_call(name, arguments, index):
    return {"id": f"offline_call_{index}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments, separators=(",", ":"))}}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    if exercise_id not in CALLS:
        raise ValueError(f"langchain-vs-native has no offline model exercise {exercise_id!r}")
    name, arguments = CALLS[exercise_id]

    def decide(results):
        if results:
            return result_answer(results, locale)
        return {"tool_calls": [compact_call(name, arguments, 1)]}

    return CompletionScript(decide)
