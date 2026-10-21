"""Offline test model for agentic-rag: serves automated tests only and does not stand for any real model.

Each exercise has a fixed script: the searches the "model" proposes, one per round, and the final JSON answer
it gives once the script runs out or the runner asks for a final answer (tool_choice none, or no tools at all).
The wording per run language is in locales/fixtures/. The chunk ids cited were read off the real BM25 results
of those searches. Every response carries scripted usage, so the report's token total is a fixture number, not
a measurement. The searches themselves always run for real in search_tool.py.
"""
import json

from lessons.lesson_agentic_rag.locales.fixtures import texts_for
from server.offline import offline_marker, tool_call

# Which chunks each scripted answer cites. The static baseline searches with the whole question, and in
# English the first hop then comes back in rooms:11-19; the second hop sits in different chunks per language.
CITATIONS = {
    "complete": {"zh-CN": ["rooms:7-11", "hours:18-26"], "en": ["rooms:7-11", "hours:26-32"]},
    "first-hop": {"zh-CN": ["rooms:7-11"], "en": ["rooms:7-11"]},
    "static": {"zh-CN": ["rooms:7-11"], "en": ["rooms:11-19"]},
    "none": {"zh-CN": [], "en": []},
}
# exercise -> (searches it proposes, which answer it ends with)
SCRIPTS = {
    "static": ((), "static"),
    "agentic": (("hop_one", "hop_two"), "complete"),
    "one-search": (("hop_one", "hop_two"), "first-hop"),
    "no-answer": ((0, 1, 2), "none"),
}


def _answer(t, key: str) -> tuple[str, str, str]:
    """(status, answer, missing) of a scripted final answer."""
    if key == "complete":
        return "answered", t.answer_complete, ""
    if key == "none":
        return "insufficient", t.answer_none, t.missing_none
    return "partial", t.answer_first_hop, t.missing_first_hop


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    t = texts_for(locale)
    steps, final_key = SCRIPTS.get(exercise_id, ((), "none"))
    queries = [t.no_answer_queries[step] if isinstance(step, int) else getattr(t, step) for step in steps]

    def complete(body, api_key):
        searched = sum(1 for message in body["messages"] if message.get("role") == "tool")
        usage = {"prompt_tokens": 420 + 260 * searched, "completion_tokens": 60}
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        may_search = body.get("tools") and body.get("tool_choice") != "none"
        if may_search and searched < len(queries):
            message = {"role": "assistant", "content": None,
                       "tool_calls": [tool_call("search_handbook", {"query": queries[searched]}, searched + 1)]}
            return {"choices": [{"message": message, "finish_reason": "tool_calls"}], "usage": usage}
        status, answer, missing = _answer(t, final_key)
        content = json.dumps({"status": status, "answer": offline_marker(locale) + answer,
                              "citations": CITATIONS[final_key][locale], "missing": missing}, ensure_ascii=False)
        return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": usage}

    return complete
