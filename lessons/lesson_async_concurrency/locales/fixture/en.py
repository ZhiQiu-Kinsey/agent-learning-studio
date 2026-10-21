"""async-concurrency offline script text: English."""
from lessons.lesson_async_concurrency.locales.fixture import Texts

TEXTS = Texts(
    summaries={
        "messages-context": "Every request carries the full message history, and tool calls and results come in pairs.",
        "application-state": "The program keeps the state; the model sees only what the program puts into the context.",
        "context-budget": "The context has a limit; over budget, keep the system prompt and the latest messages first.",
        "prompt-caching": "Put the unchanging content at the very front of the request so the cache can hit.",
    },
)
