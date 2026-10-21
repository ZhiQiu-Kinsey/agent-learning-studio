"""Offline test model for mcp-lifecycle: serves automated tests only and does not stand for any real model.

Only the "agent" exercise calls a model. The script searches the catalog, registers the first book it found,
then asks the loan desk to confirm (that call meets the killed server) and answers. The MCP servers and the
host's routing, permissions and reconnects all run for real; only the model's choices are scripted.
"""
import json

from lessons.lesson_mcp_lifecycle.locales.fixture import texts_for
from server.offline import offline_marker


def _call(round_number: int, name: str, arguments: dict) -> dict:
    return {"id": f"call_{round_number}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}


def _reply(content=None, calls=None) -> dict:
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return {"choices": [{"message": message, "finish_reason": "tool_calls" if calls else "stop"}]}


def _first_book(messages: list) -> str:
    """The first book id in the catalog search result, as the real tool returned it."""
    for message in messages:
        if message.get("role") == "tool":
            result = json.loads(message["content"])
            books = (result.get("result") or {}).get("books") if isinstance(result.get("result"), dict) else None
            if books:
                return books[0]["book_id"]
    return "B-101"


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    script = texts_for(locale)
    member = (inputs or {}).get("member_id", "M-07")

    def complete(body, api_key):
        messages = body["messages"]
        round_number = sum(1 for message in messages if message.get("role") == "assistant") + 1
        if round_number == 1:
            return _reply(calls=[_call(1, "catalog__search", {"query": script.query})])
        book = _first_book(messages)
        if round_number == 2:
            return _reply(calls=[_call(2, "loans__register_loan", {"book_id": book, "member_id": member})])
        if round_number == 3:
            return _reply(calls=[_call(3, "loans__search", {"member_id": member})])
        return _reply(content=offline_marker(locale) + script.answer.format(book=book))

    return complete
