"""Offline test model for streaming-cancel: serves automated tests only and stands for no real model.

create_stream scripts the chunks of one answer (a role-only first chunk, text pieces, a finish chunk, a usage
chunk, the shape of an OpenAI-compatible stream) and sleeps a few milliseconds between them, so the
platform's timers see a first chunk, a first text and a total that differ. create_completion answers the
non-streamed requests: the whole answer at once, a continuation after a cut, a marked continuation.
The timings and the usage numbers here are test data; they only show how the timers behave.

The "plain" continuation is scripted to show the habit the report can catch: the model rewrites the cut item
on a new line from its start, so the glued list repeats that number and keeps a half line. A real model may
instead continue cleanly, and then the same check simply passes.
"""
import re
import time

from lessons.lesson_streaming_cancel.analysis import analyse_partial, parse_items
from lessons.lesson_streaming_cancel.locales.fixture import texts_for

FIRST_CHUNK_DELAY = 0.02
CHUNK_DELAY = 0.003


def answer_lines(locale: str, items: int, detail: str) -> list[str]:
    words = texts_for(locale).items
    separator = "" if locale == "zh-CN" else " "
    lines = []
    for number in range(1, items + 1):
        sentences = words[(number - 1) % len(words)]
        text = separator.join(sentences) if detail == "long" else sentences[0]
        lines.append(f"{number}. {text}")
    return lines


def pieces(text: str, locale: str) -> list[str]:
    """Two characters per chunk in Chinese, one word per chunk in English: small, like a real stream."""
    if locale == "zh-CN":
        return [text[index:index + 2] for index in range(0, len(text), 2)]
    return re.findall(r"\S+\s*", text)


def chunk(content=None, *, role=None, finish=None, usage=None) -> dict:
    delta = {}
    if role:
        delta["role"] = role
    if content is not None:
        delta["content"] = content
    body = {"id": "chatcmpl-offline", "object": "chat.completion.chunk", "created": 1, "model": "offline-script",
            "choices": [] if usage is not None else [{"index": 0, "delta": delta, "finish_reason": finish}]}
    if usage is not None:
        body["usage"] = usage
    return body


def usage_for(parts: int) -> dict:
    return {"prompt_tokens": 48, "completion_tokens": parts, "total_tokens": 48 + parts}


def stream_chunks(text: str, locale: str):
    parts = pieces(text, locale)
    time.sleep(FIRST_CHUNK_DELAY)
    yield chunk("", role="assistant")
    for part in parts:
        time.sleep(CHUNK_DELAY)
        yield chunk(part)
    yield chunk("", finish="stop")
    yield chunk(usage=usage_for(len(parts)))


def create_stream(exercise_id, inputs=None, locale="zh-CN"):
    values = inputs or {}
    text = "\n".join(answer_lines(locale, values.get("items", 6), values.get("detail", "short")))
    return lambda body, api_key: stream_chunks(text, locale)


def reply(text: str, locale: str) -> dict:
    parts = pieces(text, locale)
    time.sleep(CHUNK_DELAY * len(parts))  # a provider that writes the whole answer first replies after all of it
    return {"id": "offline-response", "object": "chat.completion", "model": "offline-script",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": usage_for(len(parts))}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    values = inputs or {}
    lines = answer_lines(locale, values.get("items", 6), values.get("detail", "short"))

    def completion(body, api_key):
        messages = body["messages"]
        cut = [message for message in messages if message["role"] == "assistant"]
        if cut:
            # Plain continuation: the cut text came back as an assistant message; restart the cut item.
            start = analyse_partial(cut[-1]["content"]).next_item
            return reply("\n" + "\n".join(lines[start - 1:]), locale)
        # Marked continuation: the user message lists the items that were written in full, so write the rest.
        # Every other request (the non-streamed side of the comparison) gets the whole answer.
        written = [number for number, _ in parse_items(messages[-1]["content"])]
        return reply("\n".join(lines[written[-1] if written else 0:]), locale)

    return completion
