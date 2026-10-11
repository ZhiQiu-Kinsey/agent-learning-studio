"""Offline test model for persistent-memory: serves automated tests only and stands for no real model.

It reads the JSON of the <memory> block in the request: with a learning goal it answers from it and cites the key,
with an empty block it says memory has nothing. Only the recall-and-answer exercises call it; saving, reopening and
read-only recovery send no model request.
"""
from lessons.lesson_10_persistent_memory.runtime import memory_block

ANSWERS = {
    "zh-CN": {"found": "你之前定下的学习目标是：{value} [{key}]", "empty": "记忆里没有你的学习目标。"},
    "en": {"found": "The learning goal you set earlier is: {value} [{key}]",
           "empty": "Memory has no learning goal of yours."},
}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    answers = ANSWERS[locale]

    def complete(body, api_key):
        records = memory_block(body["messages"][-1]["content"])
        if records:
            item = next((record for record in records if record["key"] == "learning_goal"), records[0])
            text = answers["found"].format(value=item["value"], key=item["key"])
        else:
            text = answers["empty"]
        return {"choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]}

    return complete
