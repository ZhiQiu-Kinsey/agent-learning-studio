"""Multi-agent patterns: one course-assistant task done four ways, all judged by one program verifier.

Single agent, fixed workflow, role switching (one agent, one shared message history, the system prompt swapped per
stage) and independent agents (each with its own context and handoff; researchers in parallel, then a merge). The
shared/isolated context split, the handoff package and the failure modes follow ai-agent-book chapter 10 (Apache-2.0)
and learn-claude-code s06/s13 (MIT); the task, documents, verifier and experiments are written by this project.
Every text that reaches the model or an event is in locales/, one catalog per run language.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Literal

from course.execution import LessonInputs, RunContext
from lessons.lesson_multi_agent_patterns.locales import Texts, texts_for
from lessons.lesson_multi_agent_patterns.verifier import DOC_IDS, OUTDATED, TOPICS, verify_quiz


class Inputs(LessonInputs):
    mode: Literal["single", "workflow", "roles", "multi"] = "single"
    # Only independent agents receive a handoff; the other modes always carry the whole brief.
    handoff: Literal["minimal", "with_rules"] = "minimal"


INPUT_MODEL = Inputs
# Fixed shards for the independent researchers: the pack is split by position, so d4 lands next to d3.
SHARDS = {"researcher-1": ("d1",), "researcher-2": ("d2",), "researcher-3": ("d3", "d4")}


def extract_json(content: str):
    """The first JSON object in a reply; text or a code fence around it is allowed, nothing is repaired."""
    start = content.find("{")
    if start < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(content[start:])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def facts_of(content: str) -> list:
    value = extract_json(content)
    return value["facts"] if value and isinstance(value.get("facts"), list) else []


def questions_of(content: str):
    """The questions list as written; a missing list stays None so the verifier reports it, nothing is patched."""
    value = extract_json(content)
    return value.get("questions") if value else None


def docs_text(t: Texts, doc_ids) -> str:
    return "\n\n".join(t.doc_block.format(id=doc, title=t.doc_titles[doc], text=t.docs[doc]) for doc in doc_ids)


def brief(t: Texts, rules: bool, *parts: str) -> str:
    """The task, the old-draft rule when the sender passes it on, then this step's instruction and data."""
    return "\n\n".join([t.task_brief, *([t.outdated_rule] if rules else []), *parts])


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def audit_context(t: Texts, messages: list[dict]) -> dict:
    """What a request's context really holds, read from the messages about to be sent rather than from the plan."""
    text = "\n".join(message["content"] for message in messages if isinstance(message.get("content"), str))
    return {"messages": len(messages), "input_chars": len(text),
            "docs": [doc for doc in DOC_IDS if t.docs[doc] in text], "sees_rule": t.outdated_rule in text,
            "history": sum(message["role"] == "assistant" for message in messages)}


class Ledger:
    """One row per model call: the run identity and role, what the context held, and the usage the provider reported."""

    def __init__(self, context: RunContext, t: Texts):
        self.context, self.t, self.rows = context, t, []

    def call(self, agent: str, role: str, messages: list[dict], round_number: int, branch: str | None = None) -> str:
        audit = audit_context(self.t, messages)
        started = time.perf_counter()
        response = self.context.complete({"messages": messages, "temperature": 0}, round_number, branch=branch)
        usage = response.get("usage")
        tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
        self.rows.append({"agent": agent, "role": role, "branch": branch, "round": round_number, **audit,
                          "tokens": tokens if isinstance(tokens, int) else None,
                          "ms": round((time.perf_counter() - started) * 1000)})
        outdated = [doc for doc in audit["docs"] if doc in OUTDATED]
        # outdated_docs is present only when the context holds the old draft, so a selector can pin that call.
        self.context.emit("lesson.agent", {"agent": agent, "role": role, "role_name": self.t.role_names[role],
                                           **({"branch": branch} if branch else {}), "context": audit,
                                           **({"outdated_docs": outdated} if outdated else {})}, round_number)
        content = response["choices"][0].get("message", {}).get("content")
        return content if isinstance(content, str) else ""

    def total(self) -> str | int:
        reported = [row["tokens"] for row in self.rows if row["tokens"] is not None]
        missing = len(self.rows) - len(reported)
        if not reported:
            return self.t.value_not_reported
        return sum(reported) if not missing else self.t.tokens_partly_reported.format(total=sum(reported), missing=missing)


def system(text: str) -> dict:
    return {"role": "system", "content": text}


def user(text: str) -> dict:
    return {"role": "user", "content": text}


def reviewed(draft, review_text: str):
    """The reviewer's list is final; when it returns no list, the draft goes to the verifier as it was."""
    final = questions_of(review_text)
    return final if isinstance(final, list) else draft


def run_single(ledger: Ledger, t: Texts):
    """Single agent: one context holds the brief, the rule and every document; one request does it all."""
    content = brief(t, True, t.single_instruction, t.docs_header, docs_text(t, DOC_IDS))
    return questions_of(ledger.call("solo", "assistant", [system(t.single_system), user(content)], 1))


def run_workflow(ledger: Ledger, t: Texts):
    """Fixed workflow: the program runs three steps in order; each is a fresh request with what the program passes on."""
    prompts = t.role_prompts
    # 1. Research: the whole brief and all documents; the step returns facts only.
    research = brief(t, True, t.research_instruction, t.docs_header, docs_text(t, DOC_IDS))
    facts = facts_of(ledger.call("step-research", "researcher", [system(prompts["researcher"]), user(research)], 1))
    # 2. Write: the program hands over the facts, not the research conversation.
    write = brief(t, True, t.write_instruction, t.facts_header, dumps({"facts": facts}))
    draft = questions_of(ledger.call("step-write", "writer", [system(prompts["writer"]), user(write)], 2))
    # 3. Review: the documents again plus the draft.
    review = brief(t, True, t.review_instruction, t.questions_header, dumps({"questions": draft}),
                   t.docs_header, docs_text(t, DOC_IDS))
    return reviewed(draft, ledger.call("step-review", "reviewer", [system(prompts["reviewer"]), user(review)], 3))


def run_roles(ledger: Ledger, t: Texts):
    """Role switching: one agent and one message history; each stage replaces only the system prompt."""
    stages = (("researcher", brief(t, True, t.research_instruction, t.docs_header, docs_text(t, DOC_IDS))),
              ("writer", t.write_instruction), ("reviewer", t.review_instruction))
    history, replies = [], {}
    for number, (role, instruction) in enumerate(stages, 1):
        # 1. The stage's instruction joins the shared history; earlier replies stay in it.
        history.append(user(instruction))
        # 2. Swap the system prompt: same run identity, new role, and everything before is still visible.
        reply = ledger.call("assistant", role, [system(t.role_prompts[role]), *history], number)
        # 3. The reply goes back into the same history, so the next role reads it in full.
        history.append({"role": "assistant", "content": reply})
        replies[role] = reply
    return reviewed(questions_of(replies["writer"]), replies["reviewer"])


def merge_facts(reports: dict[str, list]) -> dict:
    """Collect facts in researcher order. A topic from several researchers is duplicate work; different values conflict."""
    facts, by_topic = [], {}
    for agent, items in reports.items():
        for item in items:
            if isinstance(item, dict) and item.get("topic") in TOPICS:
                fact = {**item, "agent": agent}
                facts.append(fact)
                by_topic.setdefault(item["topic"], []).append(fact)
    duplicates = [topic for topic, items in by_topic.items() if len({fact["agent"] for fact in items}) > 1]
    conflicts = [{"topic": topic, "values": [{key: fact.get(key) for key in ("agent", "value", "doc")} for fact in items]}
                 for topic, items in by_topic.items() if len({str(fact.get("value")).strip().lower() for fact in items}) > 1]
    return {"facts": facts, "duplicates": duplicates, "conflicts": conflicts,
            "missing": [topic for topic in TOPICS if topic not in by_topic]}


def run_multi(ledger: Ledger, t: Texts, rules: bool):
    """Independent agents: each has its own context and gets only its handoff; the program merges in between."""
    prompts = t.role_prompts

    def research(agent: str):
        content = brief(t, rules, t.research_instruction, t.docs_header, docs_text(t, SHARDS[agent]))
        return agent, facts_of(ledger.call(agent, "researcher", [system(prompts["researcher"]), user(content)], 1,
                                           branch=agent))

    # 1. Fan out: three researchers at once, each request with its own branch and only its own shard.
    with ThreadPoolExecutor(max_workers=len(SHARDS)) as pool:
        reports = dict(pool.map(research, SHARDS))
    # 2. Merge: collect every fact and record duplicates and conflicts; the program settles nothing.
    merged = merge_facts(reports)
    ledger.context.emit("lesson.merge", {**merged, "detail": t.merge_detail.format(
        duplicates=len(merged["duplicates"]), conflicts=len(merged["conflicts"]))}, 1)
    # 3. Writer: a new context with the handoff and the merged facts; no documents, no research conversations.
    write = brief(t, rules, t.write_instruction, t.facts_header, dumps({"facts": merged["facts"]}))
    draft = questions_of(ledger.call("writer", "writer", [system(prompts["writer"]), user(write)], 2))
    # 4. Reviewer: an independent context with the draft and only the documents the draft cites.
    cited = [doc for doc in DOC_IDS if isinstance(draft, list) and any(
        isinstance(item, dict) and isinstance(item.get("evidence"), dict) and item["evidence"].get("doc") == doc
        for item in draft)]
    review = brief(t, rules, t.review_instruction, t.questions_header, dumps({"questions": draft}),
                   t.docs_header, docs_text(t, cited))
    return reviewed(draft, ledger.call("reviewer", "reviewer", [system(prompts["reviewer"]), user(review)], 3)), merged


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    ledger = Ledger(context, t)
    steps = plan_steps(t, values.mode)
    context.emit("lesson.plan", {"version": 1, "event": "created", "reason": t.plan_reason, "diff": {}, "steps": steps}, 1)
    started = time.perf_counter()
    merged = None
    if values.mode == "single":
        final = run_single(ledger, t)
    elif values.mode == "workflow":
        final = run_workflow(ledger, t)
    elif values.mode == "roles":
        final = run_roles(ledger, t)
    else:
        final, merged = run_multi(ledger, t, values.handoff == "with_rules")
    wall = round((time.perf_counter() - started) * 1000)
    # The same verifier for every mode, called by the runner as a registered tool after the last model round.
    last = max(row["round"] for row in ledger.rows)
    result = context.call_tool("verify_quiz", {"questions": final}, {"verify_quiz": partial(verify_quiz, t)},
                               round_number=last + 1)
    passed = bool(result.get("ok") and result["result"]["passed"])
    for step in steps:
        step["status"] = ("done" if passed else "failed") if step["id"] == "verify" else "done"
    context.emit("lesson.plan", {"version": 1, "event": "progress", "reason": "", "diff": {}, "steps": steps}, last + 1)
    return _report(context, t, values, ledger, result, merged, wall)


# ---------- Task graph and report ----------
def plan_steps(t: Texts, mode: str) -> list[dict]:
    """The task graph of a mode as lesson.plan steps: one per model call or program step, verifier last."""
    names = t.role_names
    layout = {
        "single": [("solo", "solo", "assistant", "solo")],
        "workflow": [("step-research", "step-research", "researcher", "research_all"),
                     ("step-write", "step-write", "writer", "write_from_facts"),
                     ("step-review", "step-review", "reviewer", "review_with_docs")],
        "roles": [("stage-1", "assistant", "researcher", "stage_research"),
                  ("stage-2", "assistant", "writer", "stage_write"),
                  ("stage-3", "assistant", "reviewer", "stage_review")],
        "multi": [*((agent, agent, "researcher", "research_shard") for agent in SHARDS),
                  ("merge", "merge", "program", "merge"), ("writer", "writer", "writer", "write_merged"),
                  ("reviewer", "reviewer", "reviewer", "review_cited")],
    }[mode] + [("verify", "verify_quiz", "program", "verify")]
    return [{"id": step_id, "status": "pending", "content": t.plan_step.format(
        agent=agent, role=names[role],
        detail=t.plan_details[detail].format(docs=t.list_separator.join(SHARDS.get(agent, ()))))}
        for step_id, agent, role, detail in layout]


def _report(context: RunContext, t: Texts, values: Inputs, ledger: Ledger, result: dict, merged: dict | None,
            wall: int) -> str:
    """Emit the lab report (lesson.report): verifier checks, calls, usage, time, identities and the per-call ledger."""
    if result.get("ok"):
        verdict = result["result"]
        checks = [{"id": item["topic"], "label": t.check_topic.format(topic=item["topic"], name=t.topic_names[item["topic"]]),
                   "passed": item["passed"],
                   "detail": t.list_separator.join(t.problem_labels[code] for code in item["problems"]) or t.check_ok}
                  for item in verdict["topics"]]
        passed, total = verdict["passed_topics"], verdict["total"]
    else:
        checks = [{"id": "verifier", "label": t.check_verifier, "passed": False, "detail": result.get("error", "")}]
        passed, total = 0, len(TOPICS)
    rows = sorted(ledger.rows, key=lambda row: (row["round"], row["branch"] or ""))
    multi = values.mode == "multi"
    context.emit("lesson.report", {
        "title": t.mode_names[values.mode], "summary": t.report_summary, "checks": checks,
        "metrics": [
            {"id": "task", "label": t.label_task, "value": t.value_task.format(passed=passed, total=total)},
            {"id": "model_calls", "label": t.label_model_calls, "value": len(rows)},
            {"id": "total_tokens", "label": t.label_total_tokens, "value": ledger.total()},
            {"id": "wall_ms", "label": t.label_wall_ms, "value": wall},
            {"id": "identities", "label": t.label_identities, "value": t.value_identities.format(
                identities=len({row["agent"] for row in rows}), roles=len({row["role"] for row in rows}))},
            {"id": "input_chars", "label": t.label_input_chars, "value": sum(row["input_chars"] for row in rows)},
            *([{"id": "conflicts", "label": t.label_conflicts, "value": len(merged["conflicts"])},
               {"id": "duplicates", "label": t.label_duplicates, "value": len(merged["duplicates"])}] if merged else []),
            {"id": "handoff", "label": t.label_handoff,
             "value": t.handoff_names[values.handoff] if multi else t.handoff_not_used},
            {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": list(t.ledger_columns), "rows": [
            [row["agent"], t.role_names[row["role"]], row["branch"] or "—", row["round"], row["messages"],
             row["input_chars"], t.list_separator.join(row["docs"]) or t.value_none,
             t.value_yes if row["sees_rule"] else t.value_no,
             row["tokens"] if row["tokens"] is not None else t.value_not_reported, row["ms"]] for row in rows]},
    }, max(row["round"] for row in rows) + 1)
    return t.answer.format(mode=t.mode_names[values.mode], passed=passed, total=total, calls=len(rows), wall=wall)
