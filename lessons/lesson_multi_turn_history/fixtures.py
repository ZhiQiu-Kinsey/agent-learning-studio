"""Offline test model: serves automated tests only. It answers only from the messages visible in this request; usage is fake data counted in characters."""
from server.offline import offline_marker

# Per language: the words the script looks for, and its fixed answers.
SCRIPTS = {
    "zh-CN": {
        "remember": "请只回答", "name": "名字", "fact": "团子", "age": "三岁",
        "ok": "记住了。", "named": "你的猫叫团子。", "no_name": "我不知道你的猫叫什么名字。",
        "aged": "它今年三岁。", "no_age": "我不知道它几岁。",
    },
    "en": {
        "remember": "Reply only with", "name": "name", "fact": "Tuanzi", "age": "three years",
        "ok": "Got it.", "named": "Your cat is named Tuanzi.", "no_name": "I don't know your cat's name.",
        "aged": "It is three years old.", "no_age": "I don't know how old it is.",
    },
}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    if exercise_id not in {"with-history", "without-history", "three-turns"}:
        raise ValueError(f"multi-turn-history has no offline exercise {exercise_id!r}")
    script = SCRIPTS[locale]

    def complete(body, api_key):
        messages = body["messages"]
        seen = " ".join(m["content"] for m in messages if m["role"] == "user")
        question = messages[-1]["content"]
        if script["remember"] in question:
            answer = script["ok"]
        elif script["name"] in question:
            answer = script["named"] if script["fact"] in seen else script["no_name"]
        else:
            answer = script["aged"] if script["age"] in seen else script["no_age"]
        answer = offline_marker(locale) + answer
        prompt = sum(len(m["content"]) for m in messages)
        return {
            "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt, "completion_tokens": len(answer), "total_tokens": prompt + len(answer)},
        }

    return complete
