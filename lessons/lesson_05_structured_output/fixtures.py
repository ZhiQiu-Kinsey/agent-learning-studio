"""Deterministic responses for offline tests only; live runs use the provider."""
import json

from lessons.lesson_05_structured_output.locales import texts_for

EXERCISES = {
    "zh-CN": "用 19 加 23 的真实工具结果验证任务是否通过。",
    "en": "Use the real tool result of 19 plus 23 to check whether the task passes.",
}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    scenario = (inputs or {}).get("scenario") or {"missing-field": "missing_field", "wrong-fact": "wrong_fact"}.get(exercise_id, "normal")
    calls = 0

    def completion(body, api_key):
        nonlocal calls
        calls += 1
        # The scripted model copies the trusted title in the run's language.
        card = {"lesson_id": "task-contract", "lesson_title": texts_for(locale).facts_lesson_title,
                "prerequisite": "fail-safely", "exercise": EXERCISES[locale]}
        if calls == 1 and scenario == "missing_field":
            del card["prerequisite"]
        if calls == 1 and scenario == "wrong_fact":
            card["prerequisite"] = "dependent-calls"
        return {"choices": [{"message": {"content": json.dumps(card, ensure_ascii=False)}}]}

    return completion
