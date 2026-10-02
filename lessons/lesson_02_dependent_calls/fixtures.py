"""“依赖式多轮调用”的离线测试模型：依赖调用的参数取自本次真实时钟结果；工具仍真实执行。"""
from server.offline import CompletionScript, result_answer, tool_call


def create_completion(exercise_id, inputs=None):
    if exercise_id == "both":
        return CompletionScript(_independent)
    if exercise_id != "chain":
        raise ValueError("“依赖式多轮调用”没有此测试样本。")

    def decide(results):
        if not results:
            return {"tool_calls": [tool_call("get_current_time", {}, 1)]}
        if len(results) == 1 and results[0]["ok"]:
            clock = results[0]["result"]
            return {"tool_calls": [tool_call("add_numbers", {"a": clock["hour"], "b": clock["minute"]}, 2)]}
        if all(result["ok"] for result in results):
            clock = results[0]["result"]
            return {"content": f"【离线脚本回答】真实本地时间为 {clock['local_datetime']}。小时 {clock['hour']} + 分钟 {clock['minute']} = {results[-1]['result']}。"}
        return result_answer(results)

    return CompletionScript(decide)


def _independent(results):
    """两个任务互不依赖：第一轮同时提出加法和查时间，看到两个结果后作答。"""
    if results:
        return result_answer(results)
    return {"tool_calls": [tool_call("add_numbers", {"a": 19, "b": 23}, 1), tool_call("get_current_time", {}, 2)]}
