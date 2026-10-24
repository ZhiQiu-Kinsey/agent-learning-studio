"""Offline test model for mcp-basics: serves automated tests only and does not stand for any real model.

Round 1 proposes one search_handbook call with fixed search terms; once a tool result is in the history it
answers from the top chunk of that result. The MCP server process, the protocol messages and the BM25 search
are all real; only the model's decisions are scripted.
"""
from server.offline import CompletionScript, offline_marker, tool_call

from lessons.lesson_mcp_basics.locales.fixture import texts_for


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    t = texts_for(locale)

    def decide(results):
        if not results:
            return {"tool_calls": [tool_call("search_handbook", {"query": t.search_query, "top_k": 3}, 1)]}
        last = results[-1]
        if not last.get("ok"):
            return {"content": offline_marker(locale) + t.tool_failed.format(error=last.get("error"))}
        hits = last["result"].get("hits") or []
        if not hits:
            return {"content": offline_marker(locale) + t.no_hits}
        top = hits[0]
        return {"content": offline_marker(locale) + t.answer.format(count=len(hits), chunk_id=top["chunk_id"],
                                                                    title=top["title"])}

    return CompletionScript(decide)
