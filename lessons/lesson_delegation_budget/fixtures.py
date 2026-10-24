"""Offline test model for delegation-budget: serves automated tests only and does not stand for any real model.

It reads what is really in the request: which documents the subtask was given and whether its contract asks for
evidence. With the evidence requirement it answers with the document's value and one verbatim sentence; without it,
it gives the value alone, as a model that was never asked for evidence might. Usage is scripted from the request size.
Every call pauses 150 ms, so a 50 ms subtask deadline times out deterministically and parallel subtasks overlap; the
timeout itself is measured by the runner's clock, not simulated here.
"""
import json
import time

from lessons.lesson_delegation_budget.contracts import DOC_IDS
from lessons.lesson_delegation_budget.locales import texts_for
from lessons.lesson_delegation_budget.locales.fixture import texts_for as fixture_texts_for

DELAY_S = 0.15


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    t, f = texts_for(locale), fixture_texts_for(locale)

    def complete(body, api_key):
        time.sleep(DELAY_S)
        text = "\n".join(message["content"] for message in body["messages"] if isinstance(message.get("content"), str))
        docs = [doc for doc in DOC_IDS if t.docs[doc] in text]
        if not docs:
            reply = {"status": "not_found"}
        else:
            reply = {"status": "answered", "value": f.values[docs[0]]}
            if t.output_with_evidence in text:
                reply["evidence"] = [{"doc": docs[0], "quote": f.quotes[docs[0]]}]
        content = json.dumps(reply, ensure_ascii=False)
        prompt_tokens, completion_tokens = len(text) // 2 + 8, len(content) // 2 + 4
        return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                          "total_tokens": prompt_tokens + completion_tokens}}

    return complete
