"""Runtime text of the two MCP servers of mcp-lifecycle: tool descriptions, catalog data and business errors.

Each server process is started with --locale and reads this catalog; tool names, argument names
and ids (B-101, M-07, L-0001) are code and stay the same in every language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # Library catalog server.
    catalog_search_description: str
    query_description: str
    limit_description: str
    get_book_description: str
    book_id_description: str
    # The books: id -> {"title", "author", "topic"}.
    books: dict[str, dict[str, str]]
    empty_query: str
    unknown_book: str  # {book_id}
    # Loan desk server.
    loans_search_description: str
    member_id_description: str
    register_description: str
    due_days_description: str
    purge_description: str
    renew_description: str
    loan_id_description: str
    unknown_member: str  # {member_id}
    no_copies: str  # {book_id}
    unknown_loan: str  # {loan_id}
    # Both servers.
    info_description: str


texts_for = catalog(__name__, Texts)
