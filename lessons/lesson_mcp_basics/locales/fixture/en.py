"""Offline test model text for mcp-basics: English."""
from lessons.lesson_mcp_basics.locales.fixture import Texts

TEXTS = Texts(
    search_query="B2 research card items",
    answer="The search over MCP found {count} chunks; the most relevant is {chunk_id} ({title}), and the answer follows it. (source: {chunk_id})",
    no_hits="The search over MCP found no relevant chunk; the handbook does not cover this.",
    tool_failed="The tool did not finish: {error}",
)
