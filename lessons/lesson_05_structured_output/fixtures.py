"""Deterministic responses for offline tests only; live runs use the provider."""
import json


def create_completion(exercise_id, inputs=None):
    scenario = (inputs or {}).get("scenario") or {"missing-field": "missing_field", "wrong-fact": "wrong_fact"}.get(exercise_id, "normal")
    calls = 0

    def completion(body, api_key):
        nonlocal calls
        calls += 1
        card = {"lesson_id": "4", "lesson_title": "任务目标与验收", "prerequisite": "3",
                "exercise": "用 19 加 23 的真实工具结果验证任务是否通过。"}
        if calls == 1 and scenario == "missing_field":
            del card["prerequisite"]
        if calls == 1 and scenario == "wrong_fact":
            card["prerequisite"] = "2"
        return {"choices": [{"message": {"content": json.dumps(card, ensure_ascii=False)}}]}

    return completion
