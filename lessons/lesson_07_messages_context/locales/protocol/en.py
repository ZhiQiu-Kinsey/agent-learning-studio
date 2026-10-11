"""validate_tool_history runtime text: English."""
from lessons.lesson_07_messages_context.locales.protocol import Texts

TEXTS = Texts(
    result_expected="A tool call must be followed by its tool message first.",
    bad_call_id="A tool call id must be non-empty and unique.",
    orphan_result="Orphaned or duplicate tool message.",
    unknown_role="Unknown message role.",
    result_missing="A tool call has no matching tool message.",
)
