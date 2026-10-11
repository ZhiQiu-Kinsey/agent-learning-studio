"""Offline test model: serves automated tests only. At temperature 0 it repeats one name, otherwise it rotates a few names by call order; it does not stand for any real model."""
from server.offline import offline_marker

NAMES = {
    "zh-CN": ["喵星小铺", "猫爪杂货", "团团猫舍", "喵星小铺", "毛球驿站"],
    "en": ["Meow Mart", "Paw Goods", "Whisker Corner", "Meow Mart", "Furball Stop"],
}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    if exercise_id not in {"low-temp", "high-temp"}:
        raise ValueError(f"sampling-variance has no offline exercise {exercise_id!r}")
    names = NAMES[locale]
    calls = []

    def complete(body, api_key):
        calls.append(body)
        name = names[0] if body.get("temperature") == 0 else names[(len(calls) - 1) % len(names)]
        answer = offline_marker(locale) + name
        return {
            "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 40, "completion_tokens": len(answer), "total_tokens": 40 + len(answer)},
        }

    return complete
