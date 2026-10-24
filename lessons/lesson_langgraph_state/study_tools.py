"""The one tool of this lesson: estimate how many study days a list of lessons takes.

The minutes are a fixed copy of estimated_minutes in curriculum/catalog.json (2026-10-20), so a
run gives the same numbers every time. A slug that is not in the table is a business failure:
the tool raises ValueError, which RunContext turns into a structured error (ok=false).
"""
import math
from functools import partial

from lessons.lesson_langgraph_state.locales import Texts

STUDY_MINUTES = {
    "chat-request": 20,
    "tool-selection": 30,
    "messages-context": 40,
    "application-state": 45,
    "context-budget": 40,
    "workflow-patterns": 50,
    "langchain-tools": 50,
    "langgraph-state": 50,
}


def estimate_study_days(t: Texts, /, lessons: list, minutes_per_day: int) -> dict:
    """Sum the minutes of the requested lessons and divide by the daily budget, rounding up."""
    if not isinstance(lessons, list) or not lessons or not all(isinstance(slug, str) for slug in lessons):
        raise ValueError(t.tool_lessons_invalid)
    if type(minutes_per_day) is not int or minutes_per_day < 1:
        raise ValueError(t.tool_minutes_invalid)
    unknown = [slug for slug in lessons if slug not in STUDY_MINUTES]
    if unknown:
        # Report every unknown slug at once, so one repair can fix them all.
        raise ValueError(t.tool_unknown_lessons.format(unknown=", ".join(unknown),
                                                       known=", ".join(STUDY_MINUTES)))
    total = sum(STUDY_MINUTES[slug] for slug in lessons)
    return {"lessons": lessons, "total_minutes": total, "minutes_per_day": minutes_per_day,
            "days": math.ceil(total / minutes_per_day)}


def tool_definition(t: Texts) -> dict:
    """The OpenAI-style definition bound to the chat model; names are code, descriptions follow the run language."""
    return {"type": "function", "function": {
        "name": "estimate_study_days",
        "description": t.tool_description,
        "parameters": {
            "type": "object",
            "properties": {
                "lessons": {"type": "array", "items": {"type": "string"}, "description": t.tool_lessons_param},
                "minutes_per_day": {"type": "integer", "minimum": 1, "description": t.tool_minutes_param},
            },
            "required": ["lessons", "minutes_per_day"],
        },
    }}


def available_tools(t: Texts) -> dict:
    """Allowlist for RunContext: the message catalog is bound positionally, so the model cannot replace it."""
    return {"estimate_study_days": partial(estimate_study_days, t)}
