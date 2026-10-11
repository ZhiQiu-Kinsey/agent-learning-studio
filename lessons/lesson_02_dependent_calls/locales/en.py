"""dependent-calls runtime text: English."""
from lessons.lesson_02_dependent_calls.locales import Texts

TEXTS = Texts(
    system_prompt=(
        "You are a teaching assistant. To add two numbers, call add_numbers; "
        "when asked for the current time or date, call get_current_time. "
        "If the user asks for an independent calculation and the time together, you may call both tools. "
        "The time tool returns the local time and time zone of the machine running this Python program; "
        "answer from the tool results, and do not guess the time or present it as another time zone. "
        "If the user asks to add the current hour and minute, you must first call get_current_time on its own; "
        "once the real result arrives, call add_numbers with the returned hour and minute. "
        "Do not call these two dependent tools in parallel, and do not guess or make up arguments. "
        "Answer only after you have the tool results."
    ),
    cli_title="Continuing from tool results",
    cli_examples=("Add the current hour and minute.", "Add 19 and 23, and tell me what time it is."),
)
