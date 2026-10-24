"""Deterministic responses for offline tests only; live runs use the provider.

The scripted model reads the request the adapter built: a request with
tool_choice=required is the structured step, any other is the lookup step. Faults that
an exercise injects happen only on the first call of each step, like the instruction in
the prompt asks. Responses carry model "offline-script" and report no usage, so the
reports show where the data came from.
"""
import json

# The card text the structured-output lesson's fixture uses, in both run languages.
from lessons.lesson_05_structured_output.fixtures import EXERCISES as EXERCISE
from lessons.lesson_05_structured_output.locales import texts_for as structured_texts


SCENARIOS = {"missing-field": "missing_field", "wrong-fact": "wrong_fact", "tool-error": "tool_error"}


def _call(call_id: str, name: str, arguments: dict) -> dict:
    return {"id": call_id, "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}


def _reply(number: int, calls: list) -> dict:
    return {"id": f"offline_response_{number}", "object": "chat.completion", "model": "offline-script",
            "choices": [{"index": 0, "finish_reason": "tool_calls",
                         "message": {"role": "assistant", "content": None, "tool_calls": calls}}]}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    scenario = (inputs or {}).get("scenario") or SCENARIOS.get(exercise_id, "normal")
    state = {"calls": 0, "lookups": 0, "cards": 0}

    def completion(body, api_key):
        state["calls"] += 1
        number = state["calls"]
        if body.get("tool_choice") == "required":
            state["cards"] += 1
            card = {"lesson_id": "task-contract", "lesson_title": structured_texts(locale).facts_lesson_title,
                    "prerequisite": "fail-safely", "exercise": EXERCISE[locale]}
            if state["cards"] == 1 and scenario == "missing_field":
                del card["prerequisite"]
            if state["cards"] == 1 and scenario == "wrong_fact":
                card["prerequisite"] = "dependent-calls"
            return _reply(number, [_call(f"offline_card_{state['cards']}", "TaskCard", card)])
        state["lookups"] += 1
        lesson_id = "task_contract" if scenario == "tool_error" and state["lookups"] == 1 else "task-contract"
        return _reply(number, [_call(f"offline_lookup_{state['lookups']}", "lookup_lesson", {"lesson_id": lesson_id})])

    return completion
