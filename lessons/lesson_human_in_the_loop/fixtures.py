"""Offline test model and approver for human-in-the-loop: they serve automated tests only and stand for no real model or person.

The model answers the two requests of the lesson from a script: the draft request gets a fixed exercise
for the topic it was given, the receipt request gets one sentence built from the facts JSON it was shown.
The approver approves every draft; in edit-state it also edits it (harder, title marked), the way a
person could on the approval card. The bank, the checkpoints and the resume are all real.
"""
import json

from lessons.lesson_human_in_the_loop.locales import texts_for as runtime_texts
from lessons.lesson_human_in_the_loop.locales.fixture import texts_for
from server.offline import offline_marker


def _reply(content: str) -> dict:
    return {"model": "fixture-model", "choices": [{"index": 0, "finish_reason": "stop",
                                                   "message": {"role": "assistant", "content": content}}]}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    t, fixture = runtime_texts(locale), texts_for(locale)

    def complete(body, api_key):
        system, prompt = body["messages"][0]["content"], body["messages"][-1]["content"]
        if system == t.receipt_system:
            facts = json.loads(prompt[prompt.index("{"):])
            return _reply(offline_marker(locale) + fixture.receipt.format(
                title=facts["title"], status=facts["status"], rows=facts["rows"]))
        # The draft request: the script writes about the topic the run was started with.
        return _reply(fixture.draft.format(topic=(inputs or {}).get("topic", "")))

    return complete


def create_approval_policy(exercise_id, inputs=None, locale="zh-CN"):
    fixture = texts_for(locale)

    def policy(request):
        if exercise_id == "edit-state":
            payload = request["payload"]
            return {"decision": "approve", "note": fixture.edit_note,
                    "edited_payload": {**payload, "title": payload["title"] + fixture.edit_title_suffix,
                                       "difficulty": "hard"}}
        return {"decision": "approve"}

    return policy
