"""仅供离线测试的确定性模型脚本。"""
from lessons.lesson_07_messages_context.runtime import Inputs


def create_completion(exercise_id, inputs=None):
    if exercise_id not in {"compare", "alternate", "full"}:
        raise ValueError("未知第 7 课练习。")
    values = Inputs.model_validate(inputs or {})

    def complete(body, api_key):
        messages = body["messages"]
        if len(messages) == 2 and "确认收到" in messages[-1]["content"]:
            answer = "收到。"
        elif any(isinstance(message.get("content"), str) and values.fact in message["content"] for message in messages):
            answer = values.fact
        else:
            answer = "无法从当前消息确定。"
        return {"choices": [{"message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}]}

    return complete
