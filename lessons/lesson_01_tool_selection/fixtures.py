"""Offline test model for tool-selection: round 1 always proposes one call, then it answers from the tool result. The tools still really run."""
from server.offline import CompletionScript, result_answer, tool_call


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    if exercise_id not in ("sum", "time"):
        raise ValueError(f"tool-selection has no offline exercise {exercise_id!r}")

    def decide(results):
        if results:
            return result_answer(results, locale)
        if exercise_id == "sum":
            return {"tool_calls": [tool_call("add_numbers", {"a": 19, "b": 23}, 1)]}
        return {"tool_calls": [tool_call("get_current_time", {}, 1)]}

    return CompletionScript(decide)
