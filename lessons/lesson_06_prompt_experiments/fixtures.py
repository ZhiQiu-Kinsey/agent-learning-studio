"""提示词实验课的离线测试模型：只服务自动化测试，不代表任何真实模型的行为。"""
import json

# 描述矩阵每一格的固定回答，键是（描述组，题目）；这是测试数据，不是对真实模型行为的断言。
MATRIX_SCRIPT = {
    ("空白", "求和"): {"a": 19, "b": 23},
    ("空白", "拼接"): "1923",
    ("良好", "求和"): {"a": 19, "b": 23},
    ("良好", "拼接"): "1923",
    ("误导", "求和"): "19 + 23 = 42",
    ("误导", "拼接"): {"a": 19, "b": 23},
}


def _matrix_reply(body):
    from lessons.lesson_06_prompt_experiments.runtime import DESCRIPTIONS, PROBES
    description = body["tools"][0]["function"].get("description")
    label = next(name for name, text in DESCRIPTIONS.items() if text == description)
    task = body["messages"][1]["content"]
    probe = next(name for name, (text, _) in PROBES.items() if text == task)
    action = MATRIX_SCRIPT[(label, probe)]
    if isinstance(action, str):
        return {"choices": [{"message": {"content": action}}]}
    return {"choices": [{"message": {"content": None, "tool_calls": [{"id": "call_matrix", "type": "function",
            "function": {"name": "add_numbers", "arguments": json.dumps(action)}}]}}]}


def create_completion(exercise_id, inputs=None):
    scenario = (inputs or {}).get("scenario") or {"flow-rule": "flow_rule", "missing-input": "missing_input",
                                                  "tool-matrix": "tool_matrix"}.get(exercise_id, "tool_description")
    calls = 0

    def completion(body, api_key):
        nonlocal calls
        calls += 1
        if scenario == "tool_matrix":
            return _matrix_reply(body)
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
