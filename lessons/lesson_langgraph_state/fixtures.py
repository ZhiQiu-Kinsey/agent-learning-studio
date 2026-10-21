"""Offline test model for langgraph-state: serves automated tests only and does not stand for any real model.

The planner (a request that carries tools) always proposes estimate_study_days with exactly the
lessons and minutes of the exercise inputs, so the unknown-lesson exercises fail at the real tool,
not in the script. The writer (a request without tools) answers from the tool result it is shown.
"""
import json

from lessons.lesson_langgraph_state.locales.fixture import texts_for
from server.offline import offline_marker


def _reply(message: dict) -> dict:
    return {"model": "fixture-model", "choices": [{"finish_reason": "tool_calls" if message.get("tool_calls") else "stop",
                                                   "message": {"role": "assistant", **message}}]}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    inputs = inputs or {}
    plans = 0

    def complete(body, api_key):
        nonlocal plans
        if body.get("tools"):
            plans += 1
            lessons = [slug.strip() for slug in (inputs.get("lessons") or "").split(",") if slug.strip()]
            arguments = {"lessons": lessons, "minutes_per_day": inputs.get("minutes_per_day")}
            return _reply({"content": None, "tool_calls": [{
                "id": f"call_plan_{plans}", "type": "function",
                "function": {"name": "estimate_study_days", "arguments": json.dumps(arguments)}}]})
        # The writer's last message ends with the checked tool result as JSON.
        prompt = body["messages"][-1]["content"]
        result = json.loads(prompt[prompt.index("{"):])
        return _reply({"content": offline_marker(locale) + texts_for(locale).answer.format(**result)})

    return complete
