"""rag-citations offline script text: English."""
from lessons.lesson_rag_citations.locales.fixture import Texts

TEXTS = Texts(
    claims={
        "fee_cap": "The overdue charge for one item is capped at 20 yuan.",
        "fee_daily": "Overdue items are charged 0.5 yuan per item per day.",
        "sunday": "On Sunday the library opens 9:00–18:00 and closes at 18:00.",
        "b2_limit": "A B2 research card can borrow up to 15 items.",
        "pickup": "A reserved item waits on the pickup shelf for 5 opening days.",
    },
    quotes={
        "fee_cap": "The overdue charge for any single item is capped at 20 yuan.",
        "fee_daily": "charged 0.5 yuan per item per day",
        "sunday": "Saturday and Sunday: 9:00–18:00.",
        "sunday_old": "Sunday 10:00–17:00",
        "b2_limit": "B2 research card: up to 15 items",
        "pickup": "kept on the pickup shelf beside the Level 1 service desk for 5 opening days",
    },
    conflict_topic="Sunday opening hours",
    conflict_resolution="hours (2026-03) declares that it supersedes hours-2025 (2025-01), so the 2026 edition applies.",
    missing="None of the provided chunks answers this question.",
    error_notes={
        "q01": "The offline fixture deliberately invented a chunk id that was not provided; this is not model output.",
        "q10": "The offline fixture deliberately changed 5 to 7 in the quote and the claim; this is not model output.",
    },
    quote_edit=("5 opening days", "7 opening days"),
)
