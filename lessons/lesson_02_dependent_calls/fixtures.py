"""第 2 课样本从本次真实时钟结果生成依赖调用的参数。"""
from lessons.lesson_01_tool_selection.fixtures import create_completion as selection_completion
from server.offline import CompletionScript, result_answer, tool_call


def create_completion(exercise_id, inputs=None):
    if exercise_id == "both":
        return selection_completion("both", inputs)
    if exercise_id != "chain":
        raise ValueError("第 2 课没有此测试样本。")

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
