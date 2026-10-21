"""Offline test model for a2a-delegation: serves automated tests only and does not stand for any real model.

Round 1 delegates two fixed claims to the skill named in the Agent Card; once the tool result is in the
history it answers by quoting the chunk ids that came back, or says plainly that the check failed. The
remote agent's process, the A2A messages and the BM25 search are all real; only the model's decisions
are scripted.
"""
from server.offline import CompletionScript, offline_marker, tool_call

from lessons.lesson_a2a_delegation.locales.fixture import texts_for
from lessons.lesson_a2a_delegation.runtime import TOOL_NAME
from lessons.lesson_a2a_delegation.worker import SKILL_ID


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    t = texts_for(locale)

    def decide(results):
        if not results:
            return {"tool_calls": [tool_call(TOOL_NAME, {"skill_id": SKILL_ID, "claims": list(t.claims)}, 1)]}
        last = results[-1]
        if not last.get("ok"):
            return {"content": offline_marker(locale) + t.not_delegated.format(error_type=last["error_type"],
                                                                              error=last["error"])}
        lines = []
        for result in last["result"]["results"]:
            line = t.claim_line.format(claim_id=result["claim_id"], claim=result["claim"],
                                       chunks=", ".join(p["chunk_id"] for p in result["evidence"]))
            if result["superseded"]:
                line += t.superseded.format(chunks=", ".join(s["chunk_id"] for s in result["superseded"]))
            lines.append(line)
        return {"content": offline_marker(locale) + t.answer.format(lines=t.line_separator.join(lines))}

    return CompletionScript(decide)
