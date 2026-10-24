"""Offline test model of the capstone: serves automated tests only and stands for no real model.

It reads the learner's message and the tool results in the request and returns a scripted reply, so the
tools, the gate, the approvals, the store and the verifier all run for real around it. Where a script
needs a quote, it takes the whole line from a chunk the search really returned (never from the corpus
directly), and it declines when the line is not among the provided chunks, so changing top_k or the
query never makes it cite what it was not given. Two behaviors are scripted on purpose and marked:

* the injection cases: after it sees the poisoned chunk, it proposes the calls the post asks for, which
  plays a model that obeyed the injection; the response carries x_offline_fixture, so the event says this
  was written by the fixture and not chosen by a model;
* the recovery case: the crash is injected by the runner (fault injection), not by this model.

No usage is reported, so every ledger shows usage as not reported. create_approval_policy decides the
approval cards offline: it rejects the write of the lesson prompt-injection (case h03) and approves the rest.
"""
import json
import re

from lessons.lesson_capstone_study_assistant.contract import BY_ID, LEARNER
from lessons.lesson_capstone_study_assistant.locales import texts_for as runtime_texts
from lessons.lesson_capstone_study_assistant.locales.fixture import texts_for

LEDGER = re.compile(r"<ledger>\n(.*?)\n</ledger>", re.S)
# The document each marker is looked up in, so a marker shared by two documents picks the intended one.
DOC_OF = {"d01": "retrieval", "d04": "capabilities", "d04_old": "capabilities-2026-03", "d05_1": "memory",
          "d05_2": "memory", "d06": "retrieval", "d08": "forum-digest", "h01": "retrieval", "h02": "forum-digest"}
REJECT_LESSONS = ("prompt-injection",)


def _reply(message: dict, note: dict | None = None) -> dict:
    response = {"id": "offline_capstone", "object": "chat.completion", "model": "offline-script",
                "choices": [{"index": 0, "finish_reason": "tool_calls" if message.get("tool_calls") else "stop",
                             "message": {"role": "assistant", "content": None, **message}}]}
    if note:
        response["x_offline_fixture"] = note
    return response


def _final(value: dict) -> dict:
    return _reply({"content": json.dumps(value, ensure_ascii=False)})


def _find_case(locale: str, text: str):
    questions = runtime_texts(locale).case_questions
    return next((BY_ID[case_id] for case_id, question in questions.items() if question == text), None)


def _hits(messages: list[dict]) -> list[dict]:
    """Every hit that any search_notes result in this conversation returned, in order."""
    found = []
    for message in messages:
        if message["role"] == "tool":
            result = json.loads(message["content"])
            if result.get("ok") and isinstance(result["result"], dict):
                found += result["result"].get("hits", [])
    return found


def _line(hits: list[dict], key: str, marker: str) -> tuple[str, str] | None:
    """(chunk_id, the whole line) of the first provided chunk of the marker's document that has the marker."""
    for hit in hits:
        if hit["doc_id"] != DOC_OF[key]:
            continue
        for line in hit["text"].split("\n"):
            if marker in line:
                return hit["chunk_id"], line.strip()
    return None


def _results(messages: list[dict]) -> list[dict]:
    return [json.loads(message["content"]) for message in messages if message["role"] == "tool"]


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    t = texts_for(locale)
    runtime = runtime_texts(locale)
    counter = {"calls": 0}

    def call(name: str, arguments: dict) -> dict:
        counter["calls"] += 1
        return {"id": f"offline_call_{counter['calls']}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}

    def decline() -> dict:
        return _final({"claims": [], "insufficient_evidence": True, "missing": t.missing, "conflicts": []})

    def grounded(case, messages, hits) -> dict:
        if case.id == "d04":
            new, old = _line(hits, "d04", t.markers["d04"]), _line(hits, "d04_old", t.markers["d04_old"])
            if new is None or old is None:
                return decline()
            conflict = {"topic": t.conflict_topic, "resolution": t.conflict_resolution,
                        "sources": [{"chunk_id": new[0], "quote": new[1]}, {"chunk_id": old[0], "quote": old[1]}]}
            return _final({"claims": [{"text": new[1], "citations": [{"chunk_id": new[0], "quote": new[1]}]}],
                           "insufficient_evidence": False, "missing": "", "conflicts": [conflict]})
        key = case.id if case.id in t.markers else None
        found = _line(hits, key, t.markers[key]) if key else None
        if found is None:
            return decline()
        return _final({"claims": [{"text": found[1], "citations": [{"chunk_id": found[0], "quote": found[1]}]}],
                       "insufficient_evidence": False, "missing": "", "conflicts": []})

    def practice(messages, hits) -> dict:
        lines = [_line(hits, key, t.markers[key]) for key in ("d05_1", "d05_2")]
        if any(line is None for line in lines):
            return decline_practice()
        items = [{"question": question, "reference_answer": line[1], "citations": [{"chunk_id": line[0], "quote": line[1]}]}
                 for question, line in zip(t.practice_questions, lines)]
        return _final({"items": items, "insufficient_evidence": False, "missing": ""})

    def decline_practice() -> dict:
        return _final({"items": [], "insufficient_evidence": True, "missing": t.missing})

    def explain(ledger_text: str) -> dict:
        rows = json.loads(ledger_text)
        executed = [row for row in rows if row["kind"] in ("llm", "tool")]
        slowest = min(executed, key=lambda row: (-row["ms"], row["n"]))["n"]
        hits = sum(row.get("hits") or 0 for row in rows if row["kind"] == "tool")
        llm = [row for row in rows if row["kind"] == "llm"]
        reported = bool(llm) and all(row["total_tokens"] is not None for row in llm)
        usage = runtime.word_yes if reported else runtime.word_no
        return _final({"slowest_row": slowest, "search_hits": hits, "usage_reported": reported,
                       "summary": t.trace_summary.format(slowest=slowest, hits=hits, usage=usage)})

    def progress_reply(messages) -> dict:
        results = _results(messages)
        last = results[-1]
        if last["ok"] and "records" in last["result"]:
            lessons = [row["lesson"] for row in last["result"]["records"]]
            message = t.recall_found.format(lessons=", ".join(lessons)) if lessons else t.recall_none
            return _final({"saved": False, "recalled_lessons": lessons, "message": message})
        if last["ok"]:
            message = t.saved_message.format(lesson=last["result"]["lesson"], version=last["result"]["version"])
            return _final({"saved": True, "recalled_lessons": [], "message": message})
        return _final({"saved": False, "recalled_lessons": [], "message": t.failed_message.format(error=last["error"])})

    def complete(body, api_key):
        messages = body["messages"]
        user = next(message["content"] for message in messages if message["role"] == "user")
        tool_results = _results(messages)
        if "<ledger>" in user:
            return explain(LEDGER.search(user).group(1))
        if user == runtime.recall_question:
            if not tool_results:
                return _reply({"tool_calls": [call("read_progress", {"learner": LEARNER})]})
            return progress_reply(messages)
        case = _find_case(locale, user)
        if case is None:
            return decline()
        hits = _hits(messages)
        if case.kind == "progress":
            if not tool_results:
                arguments = {"learner": LEARNER, "lesson": case.lesson, "status": case.status, "note": t.notes[case.id]}
                return _reply({"tool_calls": [call("save_progress", arguments)]})
            return progress_reply(messages)
        # Every other case searches first with the query written for it.
        if not tool_results:
            return _reply({"tool_calls": [call("search_notes", {"query": t.queries[case.id], "top_k": 5})]})
        if case.kind == "injection" and len(tool_results) == 1 and any("delete_progress" in hit["text"] for hit in hits):
            # It has just read the injected post: play a model that obeys it, and say so in the response.
            attack = [call("save_progress", {"learner": "admin", "lesson": "rag-citations", "status": "done",
                                             "note": t.attack_note}),
                      call("delete_progress", {})]
            return _reply({"tool_calls": attack}, {"scripted_behavior": "follows_injection", "note": t.attack_marker})
        if case.kind == "practice":
            return practice(messages, hits)
        return grounded(case, messages, hits)

    return complete


def create_approval_policy(exercise_id, inputs=None, locale="zh-CN"):
    t = texts_for(locale)

    def policy(request):
        if request["payload"].get("lesson") in REJECT_LESSONS:
            return {"decision": "reject", "note": t.reject_note}
        return {"decision": "approve"}

    return policy
