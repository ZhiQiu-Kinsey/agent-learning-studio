"""Offline test model for multi-agent-patterns: serves automated tests only and does not stand for any real model.

It answers by role (the system prompt) and by what is really in the request. A researcher reports one fact per
document in its context and skips d4 only when the old-draft rule is there too. A writer takes, per topic, the last
fact it was handed that the rule (if present) allows. A reviewer returns the draft unchanged. So the minimal handoff
deliberately ends with a question built on d4, to test conflict detection and the verifier's failure path; a real
model may choose differently. Usage is scripted from the request size, and every call pauses 20 ms so that
parallel and serial wall-clock time differ.
"""
import json
import time

from lessons.lesson_multi_agent_patterns.locales import texts_for
from lessons.lesson_multi_agent_patterns.locales.fixture import texts_for as fixture_texts_for
from lessons.lesson_multi_agent_patterns.verifier import DOC_IDS, OUTDATED

# What each document says about which topic; d4 contradicts d2.
DOC_FACTS = {"d1": ("fallback_label", "other"), "d2": ("worker_cap", "4"), "d3": ("max_iters", "3"),
             "d4": ("worker_cap", "6")}
CANDIDATES = {"fallback_label": ("other", "course", "error", "account"), "worker_cap": ("4", "6", "3", "8"),
              "max_iters": ("3", "5", "1", "10")}


def _reply(value: dict, prompt: str) -> dict:
    content = json.dumps(value, ensure_ascii=False)
    prompt_tokens, completion_tokens = len(prompt) // 2 + 8, len(content) // 2 + 4
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                      "total_tokens": prompt_tokens + completion_tokens}}


def _objects(text: str, key: str) -> list:
    """Every JSON object in the request that starts with {"<key>": ...}, in order."""
    found, decoder, marker, start = [], json.JSONDecoder(), f'{{"{key}"', 0
    while (start := text.find(marker, start)) >= 0:
        try:
            value, _ = decoder.raw_decode(text[start:])
            found.append(value[key])
        except (json.JSONDecodeError, KeyError):
            pass
        start += len(marker)
    return found


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    t, f = texts_for(locale), fixture_texts_for(locale)

    def research(text: str, rules: bool) -> list[dict]:
        return [{"topic": DOC_FACTS[doc][0], "value": DOC_FACTS[doc][1], "doc": doc, "quote": f.quotes[doc]}
                for doc in DOC_IDS if t.docs[doc] in text and not (rules and doc in OUTDATED)]

    def write(facts: list[dict], rules: bool) -> list[dict]:
        chosen = {}
        for fact in facts:
            if not (rules and fact.get("doc") in OUTDATED):
                chosen[fact["topic"]] = fact  # the last allowed fact for a topic wins
        return [{"topic": topic, "question": f.questions[topic],
                 "options": [fact["value"], *[c for c in CANDIDATES[topic] if c != fact["value"]][:3]], "answer": 0,
                 "evidence": {"doc": fact["doc"], "quote": fact["quote"]}} for topic, fact in chosen.items()]

    def complete(body, api_key):
        time.sleep(0.02)
        messages = body["messages"]
        role_prompt = messages[0]["content"]
        text = "\n".join(message["content"] for message in messages if isinstance(message.get("content"), str))
        rules = t.outdated_rule in text
        if role_prompt == t.single_system:
            return _reply({"questions": write(research(text, rules), rules)}, text)
        if role_prompt == t.role_prompts["researcher"]:
            return _reply({"facts": research(text, rules)}, text)
        if role_prompt == t.role_prompts["writer"]:
            handed = _objects(text, "facts")
            return _reply({"questions": write(handed[-1] if handed else [], rules)}, text)
        drafts = _objects(text, "questions")
        return _reply({"verdict": "pass", "questions": drafts[-1] if drafts else []}, text)

    return complete
