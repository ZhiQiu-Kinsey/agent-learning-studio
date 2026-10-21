"""Business contracts registered as LangChain components: the lookup tool, the task card schema and the business check.

The facts and the TaskCard model come from the structured-output lesson unchanged. This
file only wraps them for the framework, so the business rules stay in plain Python and
can be checked without any framework object.
"""
import json
from typing import Annotated

from langchain_core.tools import ToolException, tool
from pydantic import Field

from lessons.lesson_05_structured_output.locales import texts_for as structured_texts
from lessons.lesson_05_structured_output.runtime import TaskCard, trusted_facts
from lessons.lesson_langchain_tools.locales import texts_for

# The lesson every exercise builds a card for; its facts are the structured-output lesson's trusted facts.
TARGET_LESSON = "task-contract"


def lesson_facts(locale: str) -> dict[str, dict]:
    """The business table the lookup tool reads. Slugs identify lessons; displayed numbers move."""
    t = texts_for(locale)
    target = trusted_facts(structured_texts(locale))
    return {
        target["lesson_id"]: target,
        "structured-output": {"lesson_id": "structured-output", "lesson_title": t.title_structured_output,
                              "prerequisite": "task-contract"},
        "fail-safely": {"lesson_id": "fail-safely", "lesson_title": t.title_fail_safely,
                        "prerequisite": "dependent-calls"},
    }


def make_lookup_tool(locale: str):
    """Build the lookup tool for one run language: names and types are code, descriptions are runtime text."""
    t = texts_for(locale)
    facts = lesson_facts(locale)

    # The decorator reads the name from the function, the parameter schema from the type
    # hints (Annotated + Field), and the description from the argument instead of a docstring.
    @tool(description=t.lookup_description)
    def lookup_lesson(
        lesson_id: Annotated[str, Field(description=t.lookup_parameter, min_length=1, max_length=48)],
    ) -> dict:
        record = facts.get(lesson_id)
        if record is None:
            # An expected business failure: raise ToolException so the adapter returns ok=false.
            raise ToolException(t.lookup_unknown.format(lesson_id=lesson_id, known=", ".join(sorted(facts))))
        return dict(record)

    return lookup_lesson


def handwritten_definition(locale: str) -> dict:
    """The same tool written by hand, the way the native lessons write tool definitions."""
    t = texts_for(locale)
    return {"type": "function", "function": {
        "name": "lookup_lesson",
        "description": t.lookup_description,
        "parameters": {
            "type": "object",
            "properties": {"lesson_id": {"type": "string", "description": t.lookup_parameter,
                                         "minLength": 1, "maxLength": 48}},
            "required": ["lesson_id"],
        },
    }}


def card_schema(locale: str) -> type[TaskCard]:
    """TaskCard as the framework sees it: same fields and validation, plus a description.

    The business model has no docstring, and the framework turns the docstring into the
    tool description, so without this the model would get an empty description. The
    subclass adds no field and no validator.
    """
    return type("TaskCard", (TaskCard,), {"__doc__": texts_for(locale).card_description,
                                          "__module__": __name__})


def differing_paths(left, right, prefix: str = "") -> list[str]:
    """JSON paths where two definitions differ; an empty list means they are the same."""
    if isinstance(left, dict) and isinstance(right, dict):
        paths = []
        for key in sorted(set(left) | set(right)):
            paths += differing_paths(left.get(key), right.get(key), f"{prefix}.{key}" if prefix else key)
        return paths
    return [] if left == right else [prefix or "$"]


def business_checks(card: TaskCard | None, locale: str) -> list[dict]:
    """The program's own check: a schema-valid card must still match the trusted facts.

    It runs only on a parsed card. Without one there is nothing to check, so the item
    carries no ``passed`` value rather than a failure it never measured.
    """
    t = texts_for(locale)
    if card is None:
        return [{"id": "business_facts", "label": t.check_business, "detail": t.detail_business_skipped}]
    expected = trusted_facts(structured_texts(locale))
    wrong = [key for key, value in expected.items() if getattr(card, key) != value]
    return [{"id": "business_facts", "label": t.check_business, "passed": not wrong,
             "detail": t.detail_business_ok if not wrong else t.detail_business_wrong.format(
                 fields=", ".join(wrong), expected=json.dumps({key: expected[key] for key in wrong},
                                                               ensure_ascii=False))}]
