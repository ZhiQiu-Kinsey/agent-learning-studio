"""tools.py runtime text: English."""
from lessons.lesson_01_tool_selection.locales.tools import Texts

TEXTS = Texts(
    add_numbers="Add two numbers. Call it when you need the sum of two numbers.",
    add_numbers_a="The first number",
    add_numbers_b="The second number",
    get_current_time=(
        "Read the current local date and time of the machine running the Python program. "
        "Returns the fields local_datetime, timezone, hour and minute. "
        "Call it when asked what time it is or what today's date is."
    ),
    not_a_number="Argument {name} must be a number.",
    not_finite="Both arguments and their sum must be finite numbers within the floating-point range.",
)
