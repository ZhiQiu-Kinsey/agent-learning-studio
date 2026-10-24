"""Runtime text of the MCP servers: English."""
from lessons.lesson_mcp_lifecycle.locales.servers import Texts

TEXTS = Texts(
    catalog_search_description="Search the library catalog by keyword in titles, authors and topics. Read-only; changes no record.",
    query_description="Search keyword, for example \"tool calling\".",
    limit_description="How many books to return at most, 1 to 5.",
    get_book_description="Read one book's details and the number of copies available, by book id. Read-only.",
    book_id_description="Book id, for example B-101.",
    books={
        "B-101": {"title": "Agent Tool Calling in Practice", "author": "Lin Chuan", "topic": "tool calling and function definitions"},
        "B-102": {"title": "Writing an Agent Loop from Scratch", "author": "Zhou Lan", "topic": "agent loops and message history"},
        "B-103": {"title": "Getting Started with Retrieval-Augmented Generation", "author": "Chen Mo", "topic": "retrieval and source citations"},
        "B-104": {"title": "Protocols and Servers: MCP at Work", "author": "Xu Ning", "topic": "MCP servers and tool calling"},
        "B-105": {"title": "Evaluating an Agent", "author": "Gao Yuan", "topic": "evaluation sets and regressions"},
    },
    empty_query="The search keyword must not be empty.",
    unknown_book="The catalog has no book {book_id}.",
    loans_search_description="Look up a member's current loans by member id. Read-only; changes no record.",
    member_id_description="Member id, for example M-07.",
    register_description="Register a loan for a member. It changes the loan records: a write.",
    due_days_description="Loan period in days, 7 to 30.",
    purge_description="Delete every loan record. A dangerous write, for librarian maintenance only.",
    renew_description="Renew a loan. It changes the loan records: a write.",
    loan_id_description="Loan id, for example L-0001.",
    unknown_member="There is no member {member_id}.",
    no_copies="Book {book_id} has no copies left to lend.",
    unknown_loan="There is no loan {loan_id}.",
    info_description="Report the server's process id, the loans registered since it started and the names (not values) of the environment variables it received. For host diagnostics.",
)
