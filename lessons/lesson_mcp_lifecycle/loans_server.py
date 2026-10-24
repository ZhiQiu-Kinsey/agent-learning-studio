"""Loan desk: an MCP stdio server whose loan records live only in this process's memory.

Started by the runner as ``python -m lessons.lesson_mcp_lifecycle.loans_server --locale en``. It also
has a ``search`` tool, a write (``register_loan``) and a dangerous write (``purge_loans``) that no host
should expose by default. ``--variant v2`` changes ``register_loan``'s schema and adds ``renew_loan``,
so a restarted server can come back with different tools.
"""
from typing import Annotated, TypedDict

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from lessons.lesson_mcp_lifecycle.catalog_server import COPIES
from lessons.lesson_mcp_lifecycle.locales.servers import texts_for
from lessons.lesson_mcp_lifecycle.serving import ServiceInfo, apply_startup_fault, parse_args, service_info

SERVER_NAME = "library-loans"
VARIANTS = ("v1", "v2")
MEMBERS = ("M-07", "M-12")
MemberId = Annotated[str, Field(max_length=20)]
BookId = Annotated[str, Field(max_length=20)]


class Loan(TypedDict):
    loan_id: str
    book_id: str
    member_id: str
    due_days: int


class LoanList(TypedDict):
    member_id: str
    count: int
    loans: list[Loan]


class PurgeResult(TypedDict):
    removed: int


def build_server(locale: str, variant: str = "v1") -> MCPServer:
    t = texts_for(locale)
    # The whole state of this service: gone when the process exits, empty in a restarted one.
    loans: dict[str, Loan] = {}
    server = MCPServer(SERVER_NAME)
    read_only = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
    write = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)

    def check_member(member_id: str):
        if member_id not in MEMBERS:
            raise ToolError(t.unknown_member.format(member_id=member_id))

    def add_loan(book_id: str, member_id: str, due_days: int) -> Loan:
        check_member(member_id)
        if book_id not in COPIES:
            raise ToolError(t.unknown_book.format(book_id=book_id))
        if sum(loan["book_id"] == book_id for loan in loans.values()) >= COPIES[book_id]:
            raise ToolError(t.no_copies.format(book_id=book_id))
        # Ids come from this process's counter: a restarted server starts again at L-0001.
        loan: Loan = {"loan_id": f"L-{len(loans) + 1:04d}", "book_id": book_id, "member_id": member_id,
                      "due_days": due_days}
        loans[loan["loan_id"]] = loan
        return loan

    @server.tool(name="search", description=t.loans_search_description, annotations=read_only)
    def search(member_id: Annotated[MemberId, Field(description=t.member_id_description)]) -> LoanList:
        check_member(member_id)
        mine = [loan for loan in loans.values() if loan["member_id"] == member_id]
        return {"member_id": member_id, "count": len(mine), "loans": mine}

    if variant == "v1":
        @server.tool(name="register_loan", description=t.register_description, annotations=write)
        def register_loan(book_id: Annotated[BookId, Field(description=t.book_id_description)],
                          member_id: Annotated[MemberId, Field(description=t.member_id_description)]) -> Loan:
            return add_loan(book_id, member_id, 14)
    else:
        # v2: the loan period became a required argument; an old client's call no longer fits.
        @server.tool(name="register_loan", description=t.register_description, annotations=write)
        def register_loan_v2(book_id: Annotated[BookId, Field(description=t.book_id_description)],
                             member_id: Annotated[MemberId, Field(description=t.member_id_description)],
                             due_days: Annotated[int, Field(description=t.due_days_description, ge=7, le=30)]) -> Loan:
            return add_loan(book_id, member_id, due_days)

        @server.tool(name="renew_loan", description=t.renew_description, annotations=write)
        def renew_loan(loan_id: Annotated[str, Field(description=t.loan_id_description, max_length=20)]) -> Loan:
            if loan_id not in loans:
                raise ToolError(t.unknown_loan.format(loan_id=loan_id))
            loans[loan_id]["due_days"] += 14
            return loans[loan_id]

    @server.tool(name="purge_loans", description=t.purge_description,
                 annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False))
    def purge_loans() -> PurgeResult:
        removed = len(loans)
        loans.clear()
        return {"removed": removed}

    @server.tool(name="service_info", description=t.info_description, annotations=read_only)
    def info() -> ServiceInfo:
        return service_info(loans=len(loans))

    return server


def main(argv: list[str] | None = None):
    args = parse_args("Library loan desk over MCP stdio.", VARIANTS, argv)
    apply_startup_fault(args.fault)
    build_server(args.locale, args.variant).run()


if __name__ == "__main__":
    main()
