"""Text of the offline test model (fixtures.py) for mcp-basics, one file per run language.

It holds only what the scripted replies put into events: the search terms of the scripted call and the answer
template that quotes the real tool result.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    search_query: str
    answer: str  # {count} {chunk_id} {title}
    no_hits: str
    tool_failed: str  # {error}


texts_for = catalog(__name__, Texts)
