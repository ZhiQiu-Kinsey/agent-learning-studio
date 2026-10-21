"""Scripted model text of the offline test model: English."""
from lessons.lesson_mcp_lifecycle.locales.fixture import Texts

TEXTS = Texts(
    query="tool calling",
    answer=("The loan of {book} for M-07 was registered (the tool result confirmed it). The loan desk then disconnected "
            "and the confirming lookup got no result; the record may have been lost when the service restarted, "
            "so please check with a librarian. I did not register it again."),
)
