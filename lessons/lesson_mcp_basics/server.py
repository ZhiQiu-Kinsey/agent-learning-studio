"""The handbook search of the retrieval lessons, served over MCP stdio with the official SDK (mcp 2.x).

The runner starts it as ``python -m lessons.lesson_mcp_basics.server --locale en``: a separate
process that knows nothing about models or agents. Stdout is the protocol channel, so nothing
here prints; the SDK writes its own logs to stderr, which the runner discards.
"""
import argparse
import os
import re
from typing import Annotated, TypedDict

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from course.i18n import RUNTIME_LOCALES, SOURCE_LOCALE
from lessons.lesson_document_loading.chunking import default_chunks
from lessons.lesson_keyword_retrieval.bm25 import BM25Index
from lessons.lesson_mcp_basics.locales import texts_for

SERVER_NAME = "course-handbook"
# Fault injection for the error-paths exercise only: the process exits in the middle of a call.
FAULTS = ("exit-on-search",)
SECRET_LIKE = re.compile(r"KEY|TOKEN|SECRET|PASSWORD", re.IGNORECASE)


class SearchHit(TypedDict):
    chunk_id: str
    title: str
    anchors: list[str]
    score: float
    text: str


# A TypedDict return annotation is what makes the SDK publish an outputSchema and send structuredContent.
class SearchResult(TypedDict):
    query: str
    count: int
    hits: list[SearchHit]


class ChunkText(TypedDict):
    chunk_id: str
    title: str
    version: str
    trust: str
    text: str


class ServiceStatus(TypedDict):
    pid: int
    locale: str
    chunks: int
    env_names: list[str]
    secret_like_env: list[str]


def build_server(locale: str, fault: str | None = None) -> MCPServer:
    t = texts_for(locale)
    chunks = {chunk.chunk_id: chunk for chunk in default_chunks(locale)}
    index = BM25Index(list(chunks.values()), locale)
    server = MCPServer(SERVER_NAME)
    # A hint for clients, not an enforcement: what the tools can do is decided by the code below.
    read_only = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

    @server.tool(name="search_handbook", description=t.search_description, annotations=read_only)
    def search_handbook(
        query: Annotated[str, Field(description=t.query_description, max_length=200)],
        top_k: Annotated[int, Field(description=t.top_k_description, ge=1, le=5)] = 3,
    ) -> SearchResult:
        if fault == "exit-on-search":
            os._exit(70)  # a crash mid-call: no reply ever reaches the client
        if not query.strip():
            # An anticipated business error: the SDK sends this text back with isError=true.
            raise ToolError(t.empty_query)
        hits = [{"chunk_id": hit.chunk_id, "title": chunks[hit.chunk_id].title,
                 "anchors": list(chunks[hit.chunk_id].anchors), "score": round(hit.score, 4),
                 "text": chunks[hit.chunk_id].text} for hit in index.search(query, top_k)]
        # No hits is a normal result, not an error: the search ran and found nothing.
        return {"query": query, "count": len(hits), "hits": hits}

    @server.tool(name="read_chunk", description=t.read_description, annotations=read_only)
    def read_chunk(chunk_id: Annotated[str, Field(description=t.chunk_id_description, max_length=80)]) -> ChunkText:
        # Only ids from this server's own index resolve; a path is just an unknown id, never opened.
        chunk = chunks.get(chunk_id)
        if chunk is None:
            raise ToolError(t.unknown_chunk.format(chunk_id=chunk_id))
        return {"chunk_id": chunk.chunk_id, "title": chunk.title, "version": chunk.version,
                "trust": chunk.trust, "text": chunk.text}

    @server.tool(name="service_status", description=t.status_description, annotations=read_only)
    def service_status() -> ServiceStatus:
        # Names only, never values: enough to show which variables reached this process.
        names = sorted(os.environ)
        return {"pid": os.getpid(), "locale": locale, "chunks": len(chunks), "env_names": names,
                "secret_like_env": [name for name in names if SECRET_LIKE.search(name)]}

    return server


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Course handbook search over MCP stdio.")
    parser.add_argument("--locale", choices=RUNTIME_LOCALES, default=SOURCE_LOCALE)
    parser.add_argument("--fault", choices=FAULTS)
    args = parser.parse_args(argv)
    build_server(args.locale, args.fault).run()


if __name__ == "__main__":
    main()
