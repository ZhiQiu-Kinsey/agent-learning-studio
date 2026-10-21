"""Delegation contracts: what a subtask gets, what it must hand back, and the merge check that judges the results.

A contract fixes the input (one question, the documents assigned to it), the output (a small JSON object), the evidence
(a verbatim quote from those documents) and the stop rule (one call, a deadline, not_found instead of a guess). The idea
of a structured handoff that returns a summary instead of a whole trajectory follows ai-agent-book chapter 10
(Apache-2.0) and learn-claude-code s06 (MIT); the task, documents, checks and experiments are written by this project.
"""
import json
import re
from dataclasses import dataclass

DOC_IDS = ("d1", "d2", "d3", "d4", "d5")
REQUIRED_FIELDS = ("deadline", "team_size", "weight")
MAX_VALUE_CHARS = 40
FULL_STOPS = chr(0x3002) + "."  # an ideographic or ASCII full stop at the end of a value does not make it different
DEFAULT_DEADLINE_MS = 30000
# The plan: (subtask id, field, documents, priority). The deadline is asked twice, from two sources, as a cross-check.
PLAN = (("deadline-syllabus", "deadline", ("d1",), 1), ("team-size", "team_size", ("d3",), 1),
        ("weight", "weight", ("d4",), 1), ("deadline-notice", "deadline", ("d2",), 2),
        ("late-policy", "late_policy", ("d5",), 3))
SUBTASK_IDS = tuple(item[0] for item in PLAN)


@dataclass(frozen=True)
class Contract:
    id: str  # the subtask's identity; its request carries it as the branch
    field: str
    docs: tuple[str, ...]
    priority: int  # 1 goes first
    deadline_ms: int
    evidence: bool  # does the contract ask for verbatim evidence?

    def as_json(self) -> dict:
        return {"id": self.id, "field": self.field, "docs": list(self.docs), "priority": self.priority,
                "deadline_ms": self.deadline_ms, "evidence": self.evidence}


def build_contracts(evidence: bool, tight_subtask: str = "none", tight_deadline_ms: int = 0) -> list[Contract]:
    """One contract per planned subtask; only the chosen subtask gets the tight deadline."""
    return [Contract(sid, field, docs, priority, tight_deadline_ms if sid == tight_subtask else DEFAULT_DEADLINE_MS,
                     evidence) for sid, field, docs, priority in PLAN]


def render(t, contract: Contract) -> list[dict]:
    """The subtask's whole context: a fresh message list holding its contract and its own documents, nothing else."""
    docs = "\n\n".join(t.doc_block.format(id=doc, title=t.doc_titles[doc], text=t.docs[doc]) for doc in contract.docs)
    output = t.output_with_evidence if contract.evidence else t.output_without_evidence
    brief = t.contract_brief.format(id=contract.id, question=t.questions[contract.field],
                                    docs=t.list_separator.join(contract.docs))
    return [{"role": "system", "content": t.subtask_system},
            {"role": "user", "content": "\n\n".join([brief, output, t.stop_rule, t.docs_header, docs])}]


def parse_reply(content) -> dict | None:
    """The first JSON object in a reply; text or a code fence around it is allowed, nothing is repaired."""
    start = content.find("{") if isinstance(content, str) else -1
    if start < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(content[start:])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def check_reply(docs: dict, contract: dict, reply) -> list[str]:
    """Problem codes for one reply under the coordinator's rules; an empty list means it passes."""
    if not isinstance(reply, dict):
        return ["not_json"]
    status = reply.get("status")
    if status not in ("answered", "not_found"):
        return ["bad_status"]
    if status == "not_found":
        return []  # an honest "not found" passes the check, but it answers nothing
    value = reply.get("value")
    if not isinstance(value, str) or not value.strip():
        return ["no_value"]
    problems = ["too_long"] if len(value.strip()) > MAX_VALUE_CHARS else []
    evidence = reply.get("evidence")
    # 1. The coordinator always wants evidence, whether or not the contract asked for it.
    if not isinstance(evidence, list) or not evidence:
        return problems + ["no_evidence"]
    for item in evidence:
        doc = item.get("doc") if isinstance(item, dict) else None
        quote = item.get("quote") if isinstance(item, dict) else None
        # 2. The source must be one of this subtask's own documents: no borrowed context.
        if doc not in contract["docs"]:
            problems.append("doc_out_of_scope")
        # 3. The quote must appear word for word in the document it names.
        elif not isinstance(quote, str) or not quote.strip() or quote.strip() not in docs[doc]:
            problems.append("quote_not_found")
    return list(dict.fromkeys(problems))


def same_value(value: str) -> str:
    """Spaces, case and a final full stop do not make two values different."""
    return re.sub(r"\s+", "", value).lower().rstrip(FULL_STOPS)


def merge_check(t, /, contracts, results):
    """Judge every result that came back, then group accepted values by field; differing values are listed, not settled.

    The runner calls it as a registered tool (origin course_program). Anything malformed is a structured tool error.
    """
    if not isinstance(contracts, list) or not isinstance(results, list):
        raise ValueError(t.merge_not_list)
    by_id = {item["id"]: item for item in contracts if isinstance(item, dict) and isinstance(item.get("id"), str)}
    verdicts, fields = [], {}
    for result in results:
        contract = by_id.get(result.get("id")) if isinstance(result, dict) else None
        if contract is None:
            raise ValueError(t.merge_not_list)
        reply = result.get("reply")
        problems = check_reply(t.docs, contract, reply)
        status = "rejected" if problems else reply["status"] if reply["status"] == "not_found" else "accepted"
        verdicts.append({"id": contract["id"], "field": contract["field"], "status": status, "problems": problems})
        if status == "accepted":
            first = reply["evidence"][0]
            fields.setdefault(contract["field"], []).append(
                {"subtask": contract["id"], "value": reply["value"].strip(), "doc": first["doc"],
                 "quote": first["quote"].strip()})
    # Same field, different values: keep every value with its source and let a person decide.
    conflicts = [{"id": field, "values": items} for field, items in fields.items()
                 if len({same_value(item["value"]) for item in items}) > 1]
    return {"verdicts": verdicts, "fields": [{"id": field, "values": items} for field, items in fields.items()],
            "conflicts": conflicts}
