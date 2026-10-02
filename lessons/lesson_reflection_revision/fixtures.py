"""第 16 课离线测试模型：只服务自动化测试，不代表任何真实模型的行为。

初稿故意漏掉“第一位不能是 0”；脚本里的自评会直接判通过，测试评审则会指出 s-0420。
"""
import json

FIRST = r"s-\d{4}"
FIXED = r"s-[1-9]\d{3}"


def create_completion(exercise_id, inputs=None):
    def complete(body, api_key):
        system, user = body["messages"][0]["content"], body["messages"][1]["content"]
        if system.startswith("你是评审"):
            content = json.dumps({"verdict": "pass", "issues": []}, ensure_ascii=False)
        elif "评审意见" in user:
            content = json.dumps({"regex": FIXED})
        else:
            content = "好的：\n" + json.dumps({"regex": FIRST})
        return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}}

    return complete
