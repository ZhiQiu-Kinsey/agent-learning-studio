"""Deterministic paired responses for offline tests only."""


def create_completion(exercise_id, inputs=None):
    scenario = (inputs or {}).get("scenario") or {"flow-rule": "flow_rule", "missing-input": "missing_input"}.get(exercise_id, "tool_description")
    calls = 0

    def completion(body, api_key):
        nonlocal calls
        calls += 1
        if scenario == "tool_description":
            if calls == 1:
                return {"choices": [{"message": {"content": "19 + 23 = 42", "tool_calls": []}}]}
            return {"choices": [{"message": {"content": None, "tool_calls": [{"id": "call_1", "type": "function",
                "function": {"name": "add_numbers", "arguments": '{"a":19,"b":23}'}}]}}]}
        elif scenario == "missing_input":
            content = "19 + 23 = 42" if calls == 1 else "请提供两个加数？"
        else:
            content = "不确定" if calls == 1 else "19 + 23 = 42，依据给定数字计算。"
        return {"choices": [{"message": {"content": content}}]}

    return completion
