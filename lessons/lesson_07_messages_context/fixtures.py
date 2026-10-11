"""Deterministic model script for offline tests only: it answers from the messages in this request and keeps no state."""
import json

from lessons.lesson_07_messages_context.locales import texts_for
from lessons.lesson_07_messages_context.runtime import Inputs

EXERCISES = {"ablate", "other-student"}
# Fixed answer lines per run language; the day and the score are filled in from the request.
LINES = {
    "zh-CN": {"score": "你最近一次练习 {score} 分，", "passed": "及格了。", "failed": "没有及格。",
              "no_score": "这次消息里没有成绩记录，无法确定是否及格。", "day": "复习安排在{day}晚上。",
              "no_day": "消息里没有说哪天有空，无法确定复习日。",
              "basis": "依据：之前的对话与 lookup_score 的工具结果。"},
    "en": {"score": "Your latest exercise scored {score}, ", "passed": "so you passed.", "failed": "so you did not pass.",
           "no_score": "These messages contain no score record, so I cannot tell whether you passed.",
           "day": "Review on {day} evening.",
           "no_day": "The messages do not say which day you are free, so I cannot tell the review day.",
           "basis": "Basis: the earlier conversation and the tool result of lookup_score."},
}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    if exercise_id not in EXERCISES:
        raise ValueError(f"messages-context has no offline exercise {exercise_id!r}")
    values = Inputs.model_validate(inputs or {})
    day = texts_for(locale).weekdays[values.free_day]
    text = LINES[locale]

    def complete(body, api_key):
        messages = body["messages"]
        tool = next((message for message in messages if message.get("role") == "tool"), None)
        users = [message["content"] for message in messages if message.get("role") == "user"]
        if tool is not None:
            score = json.loads(tool["content"])["result"]["score"]
            lines = [text["score"].format(score=score) + (text["passed"] if score >= 60 else text["failed"])]
        else:
            lines = [text["no_score"]]
        if any(day in content for content in users):
            lines.append(text["day"].format(day=day))
        else:
            lines.append(text["no_day"])
        if any(message.get("role") == "system" for message in messages):
            lines.append(text["basis"])
        return {"choices": [{"message": {"role": "assistant", "content": "\n".join(lines)},
                             "finish_reason": "stop"}]}

    return complete
