"""离线测试模型：只服务自动化测试。温度为 0 时固定回答，否则按调用次序轮换几个店名；不代表真实模型。"""

NAMES = ["喵星小铺", "猫爪杂货", "团团猫舍", "喵星小铺", "毛球驿站"]


def create_completion(exercise_id, inputs=None):
    if exercise_id not in {"low-temp", "high-temp"}:
        raise ValueError("“采样与不确定性”没有这个离线练习。")
    calls = []

    def complete(body, api_key):
        calls.append(body)
        name = NAMES[0] if body.get("temperature") == 0 else NAMES[(len(calls) - 1) % len(NAMES)]
        answer = "【离线脚本回答】" + name
        return {
            "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 40, "completion_tokens": len(answer), "total_tokens": 40 + len(answer)},
        }

    return complete
