"""错误处理与安全边界一课的除法练习样本：正常除法与除零，验证运行器回传失败结果。

两组故障注入（未登记的工具、损坏的参数）不调用模型，由 runtime.py 的课程程序构造，不需要样本。
"""
from server.offline import CompletionScript, result_answer, tool_call


def create_completion(exercise_id, inputs=None):
    if exercise_id not in ("divide", "zero"):
        raise ValueError("错误处理与安全边界一课没有此测试样本。")

    def decide(results):
        if results:
            return result_answer(results)
        return {"tool_calls": [tool_call("divide_numbers", {"a": 12, "b": 0 if exercise_id == "zero" else 3}, 1)]}

    return CompletionScript(decide)
