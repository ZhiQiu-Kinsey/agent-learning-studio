"""“执行工具与回传结果”的离线测试模型：第一轮固定提出一个调用，看到工具结果后作答；工具仍真实执行。"""
from server.offline import CompletionScript, result_answer, tool_call


def create_completion(exercise_id, inputs=None):
    if exercise_id not in ("sum", "time"):
        raise ValueError("“执行工具与回传结果”没有此测试样本。")

    def decide(results):
        if results:
            return result_answer(results)
        if exercise_id == "sum":
            return {"tool_calls": [tool_call("add_numbers", {"a": 19, "b": 23}, 1)]}
        return {"tool_calls": [tool_call("get_current_time", {}, 1)]}

    return CompletionScript(decide)
