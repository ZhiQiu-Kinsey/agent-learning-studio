"""The notes search of the capstone, served over MCP stdio with the official SDK.

The runner starts it as ``python -m lessons.lesson_capstone_study_assistant.notes_server --locale en``: a
separate process that knows nothing about models, learners or approvals. It exposes one read-only tool and
nothing that writes; writes stay in the host, behind the gate and a person's approval, because what a
server can do is decided by the server and the host decides what it lets the model ask for. Stdout is the
protocol channel, so nothing here prints.
"""
import argparse
from typing import Annotated, TypedDict

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from course.i18n import RUNTIME_LOCALES, SOURCE_LOCALE
from lessons.lesson_capstone_study_assistant.locales import texts_for
from lessons.lesson_capstone_study_assistant.notes import MAX_TOP_K, NotesSearch

SERVER_NAME = "study-notes"


class Hit(TypedDict):
    chunk_id: str
    rank: int
    score: float
    doc_id: str
    title: str
    version: str
    supersedes: list[str]
    trust: str
    text: str


# A TypedDict return annotation is what makes the SDK publish an outputSchema and send structuredContent.
class SearchResult(TypedDict):
    hits: list[Hit]


def build_server(locale: str) -> MCPServer:
    t = texts_for(locale)
    notes = NotesSearch(locale)
    server = MCPServer(SERVER_NAME)
    read_only = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

    @server.tool(name="search_notes", description=t.tool_search, annotations=read_only)
    def search_notes(
        query: Annotated[str, Field(description=t.param_query, max_length=200)],
        top_k: Annotated[int, Field(description=t.param_top_k, ge=1, le=MAX_TOP_K)] = 5,
    ) -> SearchResult:
        if not query.strip():
            # An anticipated business error: the SDK sends this text back with isError=true.
            raise ToolError(t.gate_rules["bad_query"])
        return notes.search(query, top_k)

    return server


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Course study notes search over MCP stdio.")
    parser.add_argument("--locale", choices=RUNTIME_LOCALES, default=SOURCE_LOCALE)
    args = parser.parse_args(argv)
    build_server(args.locale).run()


if __name__ == "__main__":
    main()
