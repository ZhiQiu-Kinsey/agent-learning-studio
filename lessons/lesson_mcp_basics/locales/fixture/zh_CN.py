"""Offline test model text for mcp-basics: Simplified Chinese."""
from lessons.lesson_mcp_basics.locales.fixture import Texts

TEXTS = Texts(
    search_query="B2 研究证最多能借几册",
    answer="经 MCP 检索到 {count} 个片段，最相关的是 {chunk_id}（{title}），答案以该片段为准。（来源：{chunk_id}）",
    no_hits="经 MCP 检索没有找到相关片段，手册里没有写。",
    tool_failed="工具没有完成：{error}",
)
