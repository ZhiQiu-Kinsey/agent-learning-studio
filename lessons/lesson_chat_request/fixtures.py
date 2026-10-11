"""Offline test model: serves automated tests only. Answer and usage are fixed fake data, not any real model."""
from server.offline import offline_marker

ANSWERS = {
    "zh-CN": "Agent 是由模型决定下一步、由程序执行动作的系统。",
    "en": "An agent is a system where the model decides the next step and a program carries out the action.",
}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    if exercise_id not in {"basic", "no-system", "short-limit"}:
        raise ValueError(f"chat-request has no offline exercise {exercise_id!r}")
    answer = offline_marker(locale) + ANSWERS[locale]

    def complete(body, api_key):
        prompt = sum(len(message["content"]) for message in body["messages"])
        limit = body.get("max_tokens")
        # With an output limit, cut by characters to imitate finish_reason=length; real providers cut by tokens.
        content = answer[:limit] if limit and limit < len(answer) else answer
        finish_reason = "length" if content != answer else "stop"
        return {
            "id": "offline_chat_1", "object": "chat.completion", "model": body["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                         "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": prompt, "completion_tokens": len(content),
                      "total_tokens": prompt + len(content)},
        }

    return complete
