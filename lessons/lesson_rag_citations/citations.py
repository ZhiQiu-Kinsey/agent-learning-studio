"""Check the citations of a grounded answer against the chunks one request actually provided.

Two questions are kept apart on purpose:

* exists: is the cited chunk id one of the chunks this request put in front of the model?
  A real-looking id that was never provided is as bad as an invented one.
* supported: does the quote really occur in that chunk, and does the claim stay inside it
  (every number the claim states also occurs in its quotes)?

Both are decided by plain string checks, never by asking a model whether it was right.
A passing check still does not prove the claim follows from the quote; it proves the
evidence chain is real and that the claim invents no numbers. The rest needs a person.

Public API, also used by the agentic-rag lesson; keep the names and signatures stable:
GroundedAnswer, parse_answer, check_citation, check_answer, classify, CATEGORIES.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from lessons.lesson_document_loading.chunking import Chunk

# A quote shorter than this (after normalizing) matches almost anywhere and proves nothing.
MIN_QUOTE_CHARS = 4
# Codes such as B2 are names, not quantities, so a digit glued to a letter does not count.
NUMBER = re.compile(r"(?<![a-z0-9])\d+(?:[.:]\d+)*")
# Retrieval failures first, then generation failures, then success; codes are the same in every language.
CATEGORIES = ("invalid_output", "cited_unprovided", "retrieval_miss", "answered_without_evidence",
              "misused", "retrieval_partial", "declined_ok", "ok")


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str = Field(min_length=1, max_length=80)
    quote: str = Field(min_length=1, max_length=300)


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=300)
    citations: list[Citation] = Field(min_length=1, max_length=3)


class Conflict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=1, max_length=200)
    sources: list[Citation] = Field(min_length=2, max_length=4)
    resolution: str = Field(min_length=1, max_length=300)


class GroundedAnswer(BaseModel):
    """The structured answer the model must return; prose outside these fields is never shown as the answer."""
    model_config = ConfigDict(extra="forbid")
    claims: list[Claim] = Field(max_length=6)
    insufficient_evidence: bool
    missing: str = Field(default="", max_length=300)
    conflicts: list[Conflict] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def _say_what_is_missing(self):
        # "Not enough material" is only useful when it says what is missing.
        if self.insufficient_evidence and not self.missing.strip():
            raise ValueError("missing must say what the sources lack when insufficient_evidence is true")
        return self


def parse_answer(raw: str) -> tuple[GroundedAnswer | None, list[str]]:
    """JSON layer, then schema layer; problems are short codes plus the field path, not prose."""
    start = raw.find("{")
    if start < 0:
        return None, ["json: no object"]
    try:
        # A code fence or a sentence around the object is tolerated; the object itself is not repaired.
        value, _ = json.JSONDecoder().raw_decode(raw[start:])
    except json.JSONDecodeError as error:
        return None, [f"json: {error.msg}"]
    try:
        return GroundedAnswer.model_validate(value), []
    except ValidationError as error:
        return None, [f"schema: {'.'.join(map(str, item['loc'])) or '$'}: {item['type']}" for item in error.errors()][:6]


def normalize(text: str) -> str:
    """Compare text, not typing: width, case, spaces, dash and quote styles do not decide support."""
    text = unicodedata.normalize("NFKC", text).casefold()
    chars = []
    for char in text:
        category = unicodedata.category(char)
        if category == "Pd":
            chars.append("-")
        elif category in ("Pi", "Pf"):
            chars.append('"')
        elif not char.isspace():
            chars.append(char)
    return "".join(chars)


def _strip_edges(text: str) -> str:
    # A quote may or may not carry the sentence's final full stop; edge punctuation is not content.
    while text and unicodedata.category(text[0]).startswith("P"):
        text = text[1:]
    while text and unicodedata.category(text[-1]).startswith("P"):
        text = text[:-1]
    return text


def numbers(text: str) -> list[str]:
    # Spaces stay here: they are what separates "to" from "15" in "up to 15 items".
    return NUMBER.findall(unicodedata.normalize("NFKC", text).casefold())


@dataclass(frozen=True)
class CitationCheck:
    chunk_id: str
    quote: str
    exists: bool  # the id is one of the chunks provided in this request
    quote_found: bool | None  # None when there was no provided chunk to look in
    reason: str  # "ok" | "not_provided" | "quote_too_short" | "quote_not_found"
    superseded_by: str | None  # doc_id of a provided document that replaces the cited one

    @property
    def ok(self) -> bool:
        return self.reason == "ok"


@dataclass(frozen=True)
class ClaimCheck:
    text: str
    citations: tuple[CitationCheck, ...]
    unmatched_numbers: tuple[str, ...]  # numbers in the claim found in none of its quotes

    @property
    def numbers_checked(self) -> bool:
        # Numbers are compared with found quotes only; with none found there is nothing to compare.
        return any(c.ok for c in self.citations)

    @property
    def supported(self) -> bool:
        return all(c.ok for c in self.citations) and not self.unmatched_numbers

    @property
    def stale(self) -> bool:
        # Every source of this claim has a newer version in the same request.
        return bool(self.citations) and all(c.superseded_by for c in self.citations)


@dataclass(frozen=True)
class ConflictCheck:
    topic: str
    resolution: str
    sources: tuple[CitationCheck, ...]
    doc_ids: tuple[str, ...]
    current: str | None  # the doc that supersedes the others, read from metadata, not from the model

    @property
    def verified(self) -> bool:
        return all(c.ok for c in self.sources) and len(self.doc_ids) >= 2


@dataclass(frozen=True)
class AnswerCheck:
    claims: tuple[ClaimCheck, ...]
    conflicts: tuple[ConflictCheck, ...]
    insufficient_evidence: bool
    missing: str
    provided: tuple[str, ...]
    version_pairs: tuple[tuple[str, str], ...]  # (newer doc, older doc), both provided and cited

    @property
    def citations(self) -> list[CitationCheck]:
        return [c for claim in self.claims for c in claim.citations] + [c for item in self.conflicts for c in item.sources]

    @property
    def unprovided(self) -> list[str]:
        return list(dict.fromkeys(c.chunk_id for c in self.citations if not c.exists))

    @property
    def conflict_disclosed(self) -> bool | None:
        """None when no two versions of one document were both provided and cited."""
        if not self.version_pairs:
            return None
        disclosed = {pair for item in self.conflicts if item.verified
                     for pair in self.version_pairs if set(pair) <= set(item.doc_ids)}
        return disclosed == set(self.version_pairs)

    def to_dict(self) -> dict:
        claims = [{"text": c.text, "supported": c.supported, "stale": c.stale,
                   "numbers_checked": c.numbers_checked, "unmatched_numbers": list(c.unmatched_numbers),
                   "citations": [asdict(item) for item in c.citations]} for c in self.claims]
        conflicts = [{"topic": c.topic, "resolution": c.resolution, "verified": c.verified,
                      "doc_ids": list(c.doc_ids), "current": c.current,
                      "sources": [asdict(item) for item in c.sources]} for c in self.conflicts]
        return {"claims": claims, "conflicts": conflicts, "insufficient_evidence": self.insufficient_evidence,
                "missing": self.missing, "unprovided": self.unprovided, "conflict_disclosed": self.conflict_disclosed}


def _replacements(provided: Mapping[str, Chunk]) -> dict[str, str]:
    """doc_id -> the provided doc that declares it superseded; only what this request can see."""
    present = {chunk.doc_id for chunk in provided.values()}
    return {old: chunk.doc_id for chunk in provided.values() for old in chunk.supersedes if old in present}


def check_citation(citation: Citation, provided: Mapping[str, Chunk],
                   replaced: Mapping[str, str] | None = None) -> CitationCheck:
    """Existence first, support second: a quote is only looked up in a chunk this request provided."""
    chunk = provided.get(citation.chunk_id)
    if chunk is None:
        return CitationCheck(citation.chunk_id, citation.quote, False, None, "not_provided", None)
    superseded_by = (replaced or {}).get(chunk.doc_id)
    quote = _strip_edges(normalize(citation.quote))
    if len(quote) < MIN_QUOTE_CHARS:
        return CitationCheck(citation.chunk_id, citation.quote, True, None, "quote_too_short", superseded_by)
    found = quote in normalize(chunk.text)
    return CitationCheck(citation.chunk_id, citation.quote, True, found, "ok" if found else "quote_not_found",
                         superseded_by)


def _unmatched(claim: Claim, checks: Sequence[CitationCheck], provided: Mapping[str, Chunk]) -> tuple[str, ...]:
    if not any(c.ok for c in checks):
        return ()  # no found quote, nothing to compare with
    # A number may come from a found quote or from the cited chunk's version label (a year, say).
    allowed = [n for c in checks if c.ok for n in numbers(c.quote) + numbers(provided[c.chunk_id].version)]
    # "21" matches "21:00", but "2" does not match "20".
    return tuple(n for n in dict.fromkeys(numbers(claim.text))
                 if not any(a == n or a.startswith(n + ":") or a.startswith(n + ".") for a in allowed))


def check_answer(answer: GroundedAnswer, provided: Sequence[Chunk]) -> AnswerCheck:
    """Check every claim and conflict note against the chunks this request provided, nothing else."""
    by_id = {chunk.chunk_id: chunk for chunk in provided}
    replaced = _replacements(by_id)
    claims = []
    for claim in answer.claims:
        checks = tuple(check_citation(c, by_id, replaced) for c in claim.citations)
        claims.append(ClaimCheck(claim.text, checks, _unmatched(claim, checks, by_id)))
    conflicts = []
    for item in answer.conflicts:
        checks = tuple(check_citation(c, by_id, replaced) for c in item.sources)
        docs = tuple(dict.fromkeys(by_id[c.chunk_id].doc_id for c in checks if c.exists))
        current = [doc for doc in docs if not any(replaced.get(doc) == other for other in docs)]
        conflicts.append(ConflictCheck(item.topic, item.resolution, checks, docs,
                                       current[0] if len(current) == 1 and len(docs) > 1 else None))
    cited = {by_id[c.chunk_id].doc_id for claim in claims for c in claim.citations if c.exists}
    cited |= {doc for item in conflicts for doc in item.doc_ids}
    pairs = tuple(sorted((new, old) for old, new in replaced.items() if old in cited or new in cited))
    return AnswerCheck(tuple(claims), tuple(conflicts), answer.insufficient_evidence, answer.missing,
                       tuple(by_id), pairs)


def classify(check: AnswerCheck | None, *, hit: bool | None, complete: bool | None) -> tuple[str, tuple[str, ...]]:
    """Name the first broken link: output format, invented sources, retrieval, then use of the evidence.

    hit/complete come from the query set's human annotation (query_set.judge); None means the
    question has no answer in the handbook. Returns (category, reason codes).
    """
    if check is None:
        return "invalid_output", ("invalid_output",)
    reasons = []
    if check.unprovided:
        reasons.append("not_provided")
    for code in ("quote_not_found", "quote_too_short"):
        if any(c.reason == code for c in check.citations):
            reasons.append(code)
    if any(claim.unmatched_numbers for claim in check.claims):
        reasons.append("number_not_in_quote")
    if any(claim.stale for claim in check.claims):
        reasons.append("stale_version")
    if check.conflict_disclosed is False:
        reasons.append("conflict_not_disclosed")
    if check.unprovided:
        return "cited_unprovided", tuple(reasons)
    if hit is False:
        return "retrieval_miss", ("gold_not_retrieved", *reasons)
    if hit is None:
        # Nothing in the handbook answers it: the only right outcome is to say so.
        if not check.insufficient_evidence:
            return "answered_without_evidence", ("claims_without_gold", *reasons)
        return ("misused", tuple(reasons)) if reasons else ("declined_ok", ())
    if complete and check.insufficient_evidence and not check.claims:
        reasons.append("declined_with_evidence")
    if reasons:
        return "misused", tuple(reasons)
    if complete is False:
        return "retrieval_partial", ("gold_partly_retrieved",)
    return "ok", ()
