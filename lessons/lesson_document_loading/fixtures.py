"""Offline test model for document-loading: serves automated tests only and stands for no real model.

Only the trust-boundary exercise calls a model. The script gives both outcomes the lesson talks about, so tests
can check that the program records each one: when the material is mixed into the instructions, the scripted reply
follows the planted reader comment; when the material is tagged and declared untrusted, it answers from the rule.
A real model may behave either way under either framing; the lab report says which source a reply came from.
"""
import json
from pathlib import Path

from lessons.lesson_document_loading.locales import texts_for
from server.offline import offline_marker

# Scripted replies live in a data file so the Chinese text stays out of Python string literals.
REPLIES = json.loads((Path(__file__).resolve().parent / "fixture_replies.json").read_text(encoding="utf-8"))


def _reply(content):
    return {"id": "offline_response_1", "object": "chat.completion", "model": "offline-script",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    tagged_system = texts_for(locale).tagged_system

    def complete(body, api_key):
        # The tagged framing is recognised by its exact system prompt; anything else gets the mixed script.
        framing = "tagged" if body["messages"][0]["content"] == tagged_system else "mixed"
        return _reply(offline_marker(locale) + REPLIES[locale][framing])

    return complete
