"""错误处理与安全边界一课的正常与恶意模型响应样本，验证运行器的失败边界。"""
from server.offline import CompletionScript, result_answer, tool_call


def create_completion(exercise_id, inputs=None):
    if exercise_id not in ("divide", "zero", "unknown", "malformed"):
        raise ValueError("错误处理与安全边界一课没有此测试样本。")

    def decide(results):
        if results:
            return result_answer(results)
        if exercise_id == "unknown":
            call = tool_call("unregistered_tool", {}, 1)
        else:
            call = tool_call("divide_numbers", {"a": 12, "b": 0 if exercise_id == "zero" else 3}, 1)
        if exercise_id == "malformed":
            call["function"]["arguments"] = "{bad json"
        return {"tool_calls": [call]}

    return CompletionScript(decide)
