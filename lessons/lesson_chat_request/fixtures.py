"""离线测试模型：只服务自动化测试，回答和用量都是固定的假数据，不代表任何真实模型。"""

ANSWER = "【离线脚本回答】Agent 是由模型决定下一步、由程序执行动作的系统。"


def create_completion(exercise_id, inputs=None):
    if exercise_id not in {"basic", "no-system", "short-limit"}:
        raise ValueError("“一次模型请求”没有这个离线练习。")

    def complete(body, api_key):
        prompt = sum(len(message["content"]) for message in body["messages"])
        limit = body.get("max_tokens")
        # 有输出上限时按字符截断，模拟 finish_reason=length；真实服务商按 Token 截断。
        content = ANSWER[:limit] if limit and limit < len(ANSWER) else ANSWER
        finish_reason = "length" if content != ANSWER else "stop"
        return {
            "id": "offline_chat_1", "object": "chat.completion", "model": body["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                         "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": prompt, "completion_tokens": len(content),
                      "total_tokens": prompt + len(content)},
        }

    return complete
