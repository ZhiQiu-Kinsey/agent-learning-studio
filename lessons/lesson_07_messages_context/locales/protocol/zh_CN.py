"""validate_tool_history runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_07_messages_context.locales.protocol import Texts

TEXTS = Texts(
    result_expected="工具调用后必须先提供对应的 tool 消息。",
    bad_call_id="工具调用 id 必须非空且唯一。",
    orphan_result="孤立或重复的 tool 消息。",
    unknown_role="未知消息角色。",
    result_missing="工具调用缺少对应的 tool 消息。",
)
