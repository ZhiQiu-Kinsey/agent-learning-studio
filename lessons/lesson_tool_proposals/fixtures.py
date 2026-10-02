"""离线测试模型：只服务自动化测试，按练习返回固定的调用提议或回答，不代表真实模型。"""
from server.offline import tool_call


def create_completion(exercise_id, inputs=None):
    if exercise_id not in {"sum", "time", "chat"}:
        raise ValueError("“工具定义与调用提议”没有这个离线练习。")

    def complete(body, api_key):
        if exercise_id == "chat":
            message = {"role": "assistant", "content": "【离线脚本回答】你好，我是教学用助手。"}
        else:
            call = (tool_call("add_numbers", {"a": 19, "b": 23}, 1) if exercise_id == "sum"
                    else tool_call("get_current_time", {}, 1))
            message = {"role": "assistant", "content": None, "tool_calls": [call]}
        return {"choices": [{"index": 0, "message": message,
                             "finish_reason": "tool_calls" if "tool_calls" in message else "stop"}]}

    return complete
