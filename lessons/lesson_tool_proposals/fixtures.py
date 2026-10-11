"""Offline test model: serves automated tests only. It returns a fixed call proposal or answer per exercise, not any real model."""
from server.offline import offline_marker, tool_call

CHAT_ANSWERS = {
    "zh-CN": "你好，我是教学用助手。",
    "en": "Hello, I am a teaching assistant.",
}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    if exercise_id not in {"sum", "time", "chat"}:
        raise ValueError(f"tool-proposals has no offline exercise {exercise_id!r}")

    def complete(body, api_key):
        if exercise_id == "chat":
            message = {"role": "assistant", "content": offline_marker(locale) + CHAT_ANSWERS[locale]}
        else:
            call = (tool_call("add_numbers", {"a": 19, "b": 23}, 1) if exercise_id == "sum"
                    else tool_call("get_current_time", {}, 1))
            message = {"role": "assistant", "content": None, "tool_calls": [call]}
        return {"choices": [{"index": 0, "message": message,
                             "finish_reason": "tool_calls" if "tool_calls" in message else "stop"}]}

    return complete
