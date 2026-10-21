"""agentic-rag offline test script text: English."""
from lessons.lesson_agentic_rag.locales.fixtures import Texts

TEXTS = Texts(
    hop_one="B2 research card study rooms level",
    hop_two="When does the Level 3 research area shut?",
    no_answer_queries=("car park", "car park", "library parking spaces"),
    answer_complete=("B2 research cardholders can book the study rooms on Level 3 (R-301 to R-303 and R-305). "
                     "The Level 3 research area shuts at 20:00 on weekdays and with the rest of the building at "
                     "weekends. The 2025 version said 19:30 on weekdays; the 2026-03 version replaces it."),
    answer_first_hop=("B2 research cardholders can book the study rooms on Level 3 (R-301 to R-303 and R-305). "
                      "The search results do not say when Level 3 shuts."),
    missing_first_hop="when Level 3 shuts",
    answer_none="The handbook says nothing about a car park, so this cannot be answered.",
    missing_none="whether the library has a car park",
)
