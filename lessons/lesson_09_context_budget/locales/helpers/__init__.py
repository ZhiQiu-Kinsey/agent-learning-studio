"""Runtime text of the helpers in runtime.py that context-compaction imports too.

The local material (facts), the side discussion, and the wording of answer_text,
usage_text, checked_fact and lookup_lesson reach the model or the report in both
lessons, so they have their own catalog. Source keys are lesson slugs: code, the same
in every language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The local material lookup_lesson reads: source key -> fact.
    facts: dict[str, str]
    # lookup_lesson error for an unknown key, and checked_fact when a result does not match.
    unknown_source: str  # {source_key}
    fact_mismatch: str
    # side_talk: one question and one reply per round ({n} is the round number).
    side_question: str
    side_reply: str
    # answer_text: malformed responses, and a response that proposes calls instead of answering.
    missing_message: str
    content_not_text: str
    unknown_tool: str
    proposed_calls: str  # {names}
    name_separator: str
    # usage_text when the response has no usage.
    usage_not_reported: str


texts_for = catalog(__name__, Texts)
