"""第 1 课确定性模型样本；工具依旧执行真实 Python。"""
from server.offline import CompletionScript, result_answer, tool_call


def create_completion(exercise_id, inputs=None):
    if exercise_id not in ("sum", "time", "both"):
        raise ValueError("第 1 课没有此测试样本。")

    def decide(results):
        if results:
            return result_answer(results)
        calls = []
        if exercise_id in ("sum", "both"):
            calls.append(tool_call("add_numbers", {"a": 19, "b": 23}, 1))
        if exercise_id in ("time", "both"):
            calls.append(tool_call("get_current_time", {}, len(calls) + 1))
        return {"tool_calls": calls}

    return CompletionScript(decide)
