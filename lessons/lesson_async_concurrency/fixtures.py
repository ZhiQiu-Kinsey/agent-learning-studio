"""Offline test model for async-concurrency: serves automated tests only and does not stand for any real model.

It answers each summary request with a fixed sentence for the note that is really in the request, after pausing for
the run's tool_delay_ms, so that tool tasks and model requests take about the same time and a test can compute what
each schedule should cost. Nothing about timing or concurrency is simulated here: the pause is real wall-clock time,
and the scheduler measures it like any other. No usage is reported, on purpose: this lesson never reads it.
"""
import time

from lessons.lesson_async_concurrency.locales import texts_for
from lessons.lesson_async_concurrency.locales.fixture import texts_for as fixture_texts_for
from lessons.lesson_async_concurrency.runtime import NOTES


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    t, f = texts_for(locale), fixture_texts_for(locale)
    pause_s = ((inputs or {}).get("tool_delay_ms") or 200) / 1000

    def complete(body, api_key):
        time.sleep(pause_s)
        text = "\n".join(message["content"] for message in body["messages"] if isinstance(message.get("content"), str))
        lesson = next((slug for slug in NOTES if t.notes[slug] in text), None)
        content = f.summaries[lesson] if lesson else ""
        return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}

    return complete
