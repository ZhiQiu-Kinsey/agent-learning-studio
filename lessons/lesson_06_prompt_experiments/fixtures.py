"""Offline test model of prompt-experiments: serves automated tests only and does not stand for any real model."""
import json

from lessons.lesson_06_prompt_experiments.locales import texts_for

# Fixed reply of each matrix cell, keyed by (description group, probe); test data, not a claim about real models.
MATRIX_SCRIPT = {
    ("blank", "sum"): {"a": 19, "b": 23},
    ("blank", "concat"): "1923",
    ("good", "sum"): {"a": 19, "b": 23},
    ("good", "concat"): "1923",
    ("misleading", "sum"): "19 + 23 = 42",
    ("misleading", "concat"): {"a": 19, "b": 23},
}
# Paired answers by scenario: (baseline reply, rewrite reply).
PAIR_SCRIPT = {
    "zh-CN": {"missing_input": ("19 + 23 = 42", "请提供两个加数？"),
              "flow_rule": ("不确定", "19 + 23 = 42，依据给定数字计算。")},
    "en": {"missing_input": ("19 + 23 = 42", "Please provide the two addends?"),
           "flow_rule": ("Not sure", "19 + 23 = 42, computed from the given numbers.")},
}


def _matrix_reply(body, t, calls):
    from lessons.lesson_06_prompt_experiments.runtime import MATRIX_GROUPS
    description = body["tools"][0]["function"].get("description")
    group = next(name for name in MATRIX_GROUPS if t.descriptions.get(name) == description)
    task = body["messages"][1]["content"]
    probe = next(name for name, text in t.probes.items() if text == task)
    action = MATRIX_SCRIPT[(group, probe)]
    if isinstance(action, str):
        return {"choices": [{"message": {"content": action}}]}
    return {"choices": [{"message": {"content": None, "tool_calls": [{"id": f"call_matrix_{calls}", "type": "function",
            "function": {"name": "add_numbers", "arguments": json.dumps(action)}}]}}]}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    scenario = (inputs or {}).get("scenario") or {"flow-rule": "flow_rule", "missing-input": "missing_input",
                                                  "tool-matrix": "tool_matrix"}.get(exercise_id, "tool_description")
    t = texts_for(locale)
    calls = 0

    def completion(body, api_key):
        nonlocal calls
        calls += 1
        if scenario == "tool_matrix":
            return _matrix_reply(body, t, calls)
        if scenario == "tool_description":
            if calls == 1:
                return {"choices": [{"message": {"content": "19 + 23 = 42", "tool_calls": []}}]}
            return {"choices": [{"message": {"content": None, "tool_calls": [{"id": "call_1", "type": "function",
                "function": {"name": "add_numbers", "arguments": '{"a":19,"b":23}'}}]}}]}
        return {"choices": [{"message": {"content": PAIR_SCRIPT[locale][scenario][min(calls, 2) - 1]}}]}

    return completion
