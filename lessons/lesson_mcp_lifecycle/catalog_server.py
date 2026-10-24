"""Library catalog: a read-only MCP stdio server with a tool called ``search`` (so does the loan desk).

Started by the runner as ``python -m lessons.lesson_mcp_lifecycle.catalog_server --locale en``.
"""
from typing import Annotated, TypedDict

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from lessons.lesson_mcp_lifecycle.locales.servers import texts_for
from lessons.lesson_mcp_lifecycle.serving import ServiceInfo, apply_startup_fault, parse_args, service_info

SERVER_NAME = "library-catalog"
COPIES = {"B-101": 2, "B-102": 1, "B-103": 3, "B-104": 1, "B-105": 2}


class Book(TypedDict):
    book_id: str
    title: str
    author: str
    topic: str
    copies: int


class SearchResult(TypedDict):
    query: str
    count: int
    books: list[Book]


def build_server(locale: str) -> MCPServer:
    t = texts_for(locale)
    books = {book_id: {"book_id": book_id, **fields, "copies": COPIES[book_id]} for book_id, fields in t.books.items()}
    server = MCPServer(SERVER_NAME)
    # A hint for clients, not a permission: the host decides what may run.
    read_only = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

    @server.tool(name="search", description=t.catalog_search_description, annotations=read_only)
    def search(query: Annotated[str, Field(description=t.query_description, max_length=100)],
               limit: Annotated[int, Field(description=t.limit_description, ge=1, le=5)] = 3) -> SearchResult:
        words = query.lower().split()
        if not words:
            raise ToolError(t.empty_query)
        found = [book for book in books.values()
                 if all(word in f"{book['title']} {book['author']} {book['topic']}".lower() for word in words)]
        return {"query": query, "count": len(found[:limit]), "books": found[:limit]}

    @server.tool(name="get_book", description=t.get_book_description, annotations=read_only)
    def get_book(book_id: Annotated[str, Field(description=t.book_id_description, max_length=20)]) -> Book:
        if book_id not in books:
            raise ToolError(t.unknown_book.format(book_id=book_id))
        return books[book_id]

    @server.tool(name="service_info", description=t.info_description, annotations=read_only)
    def info() -> ServiceInfo:
        return service_info(loans=0)

    return server


def main(argv: list[str] | None = None):
    args = parse_args("Library catalog over MCP stdio.", argv=argv)
    apply_startup_fault(args.fault)
    build_server(args.locale).run()


if __name__ == "__main__":
    main()
