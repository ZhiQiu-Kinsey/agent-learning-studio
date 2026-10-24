"""The one program verifier every mode is judged by: checkable evidence, the documented value, one question per topic.

The runner calls it as a registered tool (origin course_program), so its call and result are in the trace like any
other tool. It knows the brief's rules, including that d4 is out of date, but it never sees how a list was produced.
Problem codes are the same in every language; the report turns them into run-language text.
"""
import re

DOC_IDS = ("d1", "d2", "d3", "d4")
OUTDATED = frozenset({"d4"})  # the brief calls d4 an old draft: facts from it must not be evidence
TOPICS = ("fallback_label", "worker_cap", "max_iters")
# The value each topic must test, exactly as the current documents state it (the same in every language).
GOLD = {"fallback_label": "other", "worker_cap": "4", "max_iters": "3"}


def has_value(text, value: str) -> bool:
    """The value as a whole token, so "4" matches "4 subtasks" but not "40"."""
    pattern = rf"(?<![0-9A-Za-z_]){re.escape(value)}(?![0-9A-Za-z_])"
    return isinstance(text, str) and re.search(pattern, text) is not None


def well_formed(item: dict) -> bool:
    """A stem, four distinct non-empty options and an integer answer; bool is excluded on purpose (True == 1)."""
    options = item.get("options")
    return (isinstance(item.get("question"), str) and bool(item["question"].strip())
            and isinstance(options, list) and len(options) == 4
            and all(isinstance(option, str) and option.strip() for option in options) and len(set(options)) == 4
            and type(item.get("answer")) is int and 0 <= item["answer"] <= 3)


def check_question(t, topic: str, item: dict) -> list[str]:
    """Problem codes for one question; an empty list means it passed."""
    if not well_formed(item):
        return ["format"]
    problems = []
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    doc, quote = evidence.get("doc"), evidence.get("quote")
    # 1. Evidence: the quote must appear word for word in the document it names.
    if doc not in DOC_IDS or not isinstance(quote, str) or not quote.strip() or quote.strip() not in t.docs[doc]:
        problems.append("quote_not_found")
    # 2. Current source: a verbatim quote from the old draft is still the wrong evidence.
    if doc in OUTDATED:
        problems.append("outdated_source")
    # 3. Documented value: the correct option states it and no other option does.
    correct, gold = item["answer"], GOLD[topic]
    others = [option for index, option in enumerate(item["options"]) if index != correct]
    if not has_value(item["options"][correct], gold) or any(has_value(option, gold) for option in others):
        problems.append("wrong_answer")
    return problems


def verify_quiz(t, /, questions):
    """Judge a final list of questions; anything but a list is a structured tool error, not a crash."""
    if not isinstance(questions, list):
        raise ValueError(t.verifier_not_list)
    by_topic: dict[str, list[dict]] = {}
    for item in questions:
        if isinstance(item, dict) and item.get("topic") in TOPICS:
            by_topic.setdefault(item["topic"], []).append(item)
    topics = []
    for topic in TOPICS:
        items = by_topic.get(topic, [])
        # A missing or doubled topic fails as a whole; only a single question gets the detailed checks.
        problems = ["missing"] if not items else ["duplicate"] if len(items) > 1 else check_question(t, topic, items[0])
        evidence = items[0].get("evidence") if len(items) == 1 and isinstance(items[0].get("evidence"), dict) else {}
        topics.append({"topic": topic, "passed": not problems, "problems": problems, "doc": evidence.get("doc")})
    passed = sum(item["passed"] for item in topics)
    return {"passed": passed == len(TOPICS), "passed_topics": passed, "total": len(TOPICS), "topics": topics,
            "unmatched": len(questions) - sum(len(items) for items in by_topic.values())}
