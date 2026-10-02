"""离线测试模型：只服务自动化测试。只按本次请求里能看到的消息作答，用量是按字符数编的假数据。"""


def create_completion(exercise_id, inputs=None):
    if exercise_id not in {"with-history", "without-history", "three-turns"}:
        raise ValueError("“多轮对话”没有这个离线练习。")

    def complete(body, api_key):
        messages = body["messages"]
        seen = " ".join(m["content"] for m in messages if m["role"] == "user")
        question = messages[-1]["content"]
        if "请只回答" in question:
            answer = "记住了。"
        elif "名字" in question:
            answer = "你的猫叫团子。" if "团子" in seen else "我不知道你的猫叫什么名字。"
        else:
            answer = "它今年三岁。" if "三岁" in seen else "我不知道它几岁。"
        answer = "【离线脚本回答】" + answer
        prompt = sum(len(m["content"]) for m in messages)
        return {
            "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt, "completion_tokens": len(answer), "total_tokens": prompt + len(answer)},
        }

    return complete
