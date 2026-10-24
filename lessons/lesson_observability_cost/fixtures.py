"""Offline test model for observability-cost: serves automated tests only and stands for no provider.

It answers each classification with the human label and reports scripted usage: about one token per four
characters of the request and of the reply. Tests can switch usage off (usage_style="none"), drop it from the
second response only ("partial"), or make the batched request mislabel some receipts (mislabel) to test the
regression check.
"""
import json

from lessons.lesson_observability_cost.locales import texts_for
from lessons.lesson_observability_cost.runtime import RECEIPTS


def _usage(body: dict, content: str) -> dict:
    prompt = len(json.dumps(body["messages"], ensure_ascii=False)) // 4
    completion = max(1, len(content) // 4)
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion}


def create_completion(exercise_id, inputs=None, locale="zh-CN", usage_style="reported", mislabel=None):
    if usage_style not in ("reported", "none", "partial"):
        raise ValueError(f"unknown usage style: {usage_style}")
    t = texts_for(locale)
    labels = {}
    for receipt in RECEIPTS:
        labels.setdefault(t.receipts[receipt["id"]], receipt["label"])
    calls = 0

    def complete(body, api_key):
        nonlocal calls
        calls += 1
        system, user = body["messages"][0]["content"], body["messages"][1]["content"]
        if system == t.batch_system:
            items = json.loads(user)
            content = json.dumps([{"id": item["id"], "category": (mislabel or {}).get(item["id"], labels[item["description"]])}
                                  for item in items], ensure_ascii=False)
        elif system == t.classify_system:
            content = json.dumps({"category": labels[user]})
        else:
            raise ValueError("observability-cost fixture got an unexpected system prompt")
        response = {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}
        if usage_style == "reported" or (usage_style == "partial" and calls != 2):
            response["usage"] = _usage(body, content)
        return response

    return complete
