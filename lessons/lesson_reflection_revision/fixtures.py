"""Offline test model for reflection-revision: serves automated tests only and does not stand for any real model.

The first draft deliberately misses "the first digit cannot be 0"; the scripted self-review passes it,
while the test review points at s-0420.
"""
import json

from lessons.lesson_reflection_revision.locales import texts_for

FIRST = r"s-\d{4}"
FIXED = r"s-[1-9]\d{3}"
# Text the scripted writer puts before its JSON, so the runner has to find the object inside the reply.
PREAMBLE = {"zh-CN": "好的：\n", "en": "OK:\n"}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    t = texts_for(locale)
    first_request = t.draft_request.format(spec=t.spec)

    def complete(body, api_key):
        system, user = body["messages"][0]["content"], body["messages"][1]["content"]
        if system == t.self_review_system:
            content = json.dumps({"verdict": "pass", "issues": []}, ensure_ascii=False)
        elif user != first_request:
            # Any writer request other than the first draft is a revision request.
            content = json.dumps({"regex": FIXED})
        else:
            content = PREAMBLE[locale] + json.dumps({"regex": FIRST})
        return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}}

    return complete
