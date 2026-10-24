"""The structured answers the assistant must return, one schema per kind of task.

Ask answers reuse the rag-citations lesson's GroundedAnswer unchanged. The other three are
small and follow the same rule: a JSON object, parsed in two layers (JSON, then schema),
with problems reported as short codes plus the field path. Prose around the object is
tolerated, the object itself is never repaired, and nothing outside the schema is shown as
the answer.
"""
import json
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lessons.lesson_rag_citations.citations import Citation, GroundedAnswer, parse_answer

Model = TypeVar("Model", bound=BaseModel)


class PracticeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=300)
    reference_answer: str = Field(min_length=1, max_length=300)
    # The reference answer is a claim like any other: it needs evidence the request really provided.
    citations: list[Citation] = Field(min_length=1, max_length=2)


class PracticeSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[PracticeItem] = Field(max_length=3)
    insufficient_evidence: bool
    missing: str = Field(default="", max_length=300)


class TraceExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slowest_row: int = Field(ge=1)
    search_hits: int = Field(ge=0)
    usage_reported: bool
    summary: str = Field(min_length=1, max_length=400)


class ProgressReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # What the assistant tells the learner about the store: the verifier compares it with the store itself.
    saved: bool
    recalled_lessons: list[str] = Field(default_factory=list, max_length=12)
    message: str = Field(min_length=1, max_length=400)


def parse_model(raw: str, model: type[Model]) -> tuple[Model | None, list[str]]:
    """JSON layer, then schema layer; the same two-layer shape as citations.parse_answer."""
    start = raw.find("{")
    if start < 0:
        return None, ["json: no object"]
    try:
        value, _ = json.JSONDecoder().raw_decode(raw[start:])
    except json.JSONDecodeError as error:
        return None, [f"json: {error.msg}"]
    try:
        return model.model_validate(value), []
    except ValidationError as error:
        return None, [f"schema: {'.'.join(map(str, item['loc'])) or '$'}: {item['type']}" for item in error.errors()][:6]


__all__ = ["GroundedAnswer", "PracticeItem", "PracticeSet", "ProgressReply", "TraceExplanation", "parse_answer",
           "parse_model"]
