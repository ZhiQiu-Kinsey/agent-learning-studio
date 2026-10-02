"""仅供离线测试的确定性模型脚本：只按本次请求里有哪些消息作答，不保存任何状态。"""
import json

from lessons.lesson_07_messages_context.runtime import Inputs

EXERCISES = {"ablate", "other-student"}


def create_completion(exercise_id, inputs=None):
    if exercise_id not in EXERCISES:
        raise ValueError("未知的“上下文组成与消息协议”练习。")
    values = Inputs.model_validate(inputs or {})

    def complete(body, api_key):
        messages = body["messages"]
        tool = next((message for message in messages if message.get("role") == "tool"), None)
        users = [message["content"] for message in messages if message.get("role") == "user"]
        if tool is not None:
            score = json.loads(tool["content"])["result"]["score"]
            lines = [f"你最近一次练习 {score} 分，" + ("及格了。" if score >= 60 else "没有及格。")]
        else:
            lines = ["这次消息里没有成绩记录，无法确定是否及格。"]
        if any(values.free_day in text for text in users):
            lines.append(f"复习安排在{values.free_day}晚上。")
        else:
            lines.append("消息里没有说哪天有空，无法确定复习日。")
        if any(message.get("role") == "system" for message in messages):
            lines.append("依据：之前的对话与 lookup_score 的工具结果。")
        return {"choices": [{"message": {"role": "assistant", "content": "\n".join(lines)},
                             "finish_reason": "stop"}]}

    return complete
