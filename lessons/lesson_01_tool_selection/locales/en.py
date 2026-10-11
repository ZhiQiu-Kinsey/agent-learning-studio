"""tool-selection runtime text: English."""
from lessons.lesson_01_tool_selection.locales import Texts

TEXTS = Texts(
    system_prompt=(
        "You are a teaching assistant. To add two numbers, call add_numbers; "
        "when asked for the current time or date, call get_current_time. "
        "Answer from the tool results and never guess the time."
    ),
    cli_title="Executing tools and returning results",
    cli_examples=("Add 19 and 23 for me.", "What is the local time now?"),
)
