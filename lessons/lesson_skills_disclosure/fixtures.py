"""Offline test model for skills-disclosure: serves automated tests only and stands for no real model.

A request with tools is "catalog + on-demand loading", one without is "full injection". With the vague description
the script deliberately makes the "model" skip the skill when organizing notes (a missed trigger) and load
review-cards for the review question (a false trigger), to test that the runner records both honestly. Responses
carry no usage, so prompt tokens show as "not reported".
"""
import json

from lessons.lesson_skills_disclosure.locales import texts_for

ANSWERS = {
    "zh-CN": {
        "cards": ("问：Python 的列表和元组哪个可以修改？\n答：列表可以修改，元组创建后不能修改。\n\n"
                  "问：为什么元组可以当字典的键，列表不行？\n答：字典的键必须是不可变类型，元组不可变，列表可变。\n\n"
                  "问：集合有什么特点？\n答：会自动去重，但不保证元素顺序。"),
        "greeting": "你好！周五快乐，祝你周末愉快。",
        "answer": "列表创建后还能修改，元组创建后不能修改。",
    },
    "en": {
        "cards": ("Q: Which can be changed, a Python list or a tuple?\nA: A list can be changed; a tuple cannot be "
                  "changed after it is created.\n\n"
                  "Q: Why can a tuple be a dictionary key but a list cannot?\nA: Dictionary keys must be immutable; "
                  "a tuple is immutable, a list is mutable.\n\n"
                  "Q: What is special about a set?\nA: It removes duplicates automatically but does not keep the "
                  "order of its elements."),
        "greeting": "Hi! Happy Friday, and have a nice weekend.",
        "answer": "A list can still be changed after it is created; a tuple cannot.",
    },
}


def _reply(content=None, calls=None):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return {"choices": [{"message": message, "finish_reason": "tool_calls" if calls else "stop"}]}


def _load(name):
    return [{"id": "call_load_skill_1", "type": "function",
             "function": {"name": "load_skill", "arguments": json.dumps({"name": name})}}]


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    t, answers = texts_for(locale), ANSWERS[locale]

    def complete(body, api_key):
        messages = body["messages"]
        question = next(message["content"] for message in messages if message["role"] == "user")
        on_demand = "tools" in body
        vague = t.vague_description in messages[0]["content"]
        loaded = any(message["role"] == "tool" for message in messages)
        if question == t.task_messages["make_cards"]:
            if on_demand and not loaded and not vague:
                return _reply(calls=_load("review-cards"))
            return _reply(answers["cards"])
        if question == t.task_messages["review_question"]:
            if on_demand and not loaded and vague:
                return _reply(calls=_load("review-cards"))
            return _reply(answers["answer"])
        return _reply(answers["greeting"])

    return complete
