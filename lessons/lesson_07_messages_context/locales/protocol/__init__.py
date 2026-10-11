"""Runtime text of validate_tool_history: the protocol errors it raises.

The protocol check in runtime.py is shared with context-budget and context-compaction,
so its messages have their own catalog. They reach events: messages-context records
them as the reason a variant was blocked, context-budget puts them into its report.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # A call is still waiting for its result, but the next message is not a tool message.
    result_expected: str
    # A tool call id is empty or used twice.
    bad_call_id: str
    # A tool message answers no call that is waiting.
    orphan_result: str
    # A role other than system, user, assistant, tool.
    unknown_role: str
    # The history ends while a call still has no result.
    result_missing: str


texts_for = catalog(__name__, Texts)
