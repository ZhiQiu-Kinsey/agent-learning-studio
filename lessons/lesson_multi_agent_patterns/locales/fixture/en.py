"""multi-agent-patterns offline script text: English."""
from lessons.lesson_multi_agent_patterns.locales.fixture import Texts

TEXTS = Texts(
    questions={
        "fallback_label": "When the first line of a routing reply is not an allowed label, which fallback label does the ticket take?",
        "worker_cap": "At most how many subtasks can the orchestrator split a task into?",
        "max_iters": "What is the largest value of the revision loop's iteration limit max_iters?",
    },
    quotes={
        "d1": "the ticket takes the fallback label other",
        "d2": "There can be at most 4 subtasks",
        "d3": "max_iters is at most 3",
        "d4": "at most 6 subtasks",
    },
)
