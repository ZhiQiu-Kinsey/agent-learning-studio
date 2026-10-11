"""Tool definitions and implementations: tool-proposals only sends the definitions to the model; tool-selection also runs the functions."""

import math
from datetime import datetime
from functools import partial

from lessons.lesson_01_tool_selection.locales.tools import texts_for


def tool_definitions(locale):
    """The tools sent with every request. Names are code; the descriptions come in the run's language."""
    t = texts_for(locale)
    return [
        {
            "type": "function",
            "function": {
                "name": "add_numbers",
                "description": t.add_numbers,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": t.add_numbers_a},
                        "b": {"type": "number", "description": t.add_numbers_b},
                    },
                    "required": ["a", "b"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": t.get_current_time,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            },
        },
    ]


def add_numbers(t, /, a, b):
    """Check that both numbers are finite, then add them; the sum must be finite too.

    t holds the error messages of the run's language. It is positional-only, so the
    arguments the model sends (always by name) can never replace it.
    """
    if isinstance(a, bool) or not isinstance(a, (int, float)):
        raise ValueError(t.not_a_number.format(name="a"))
    if isinstance(b, bool) or not isinstance(b, (int, float)):
        raise ValueError(t.not_a_number.format(name="b"))
    try:
        finite = math.isfinite(a) and math.isfinite(b) and math.isfinite(a + b)
    except OverflowError:
        # A huge integer like 10**400 cannot become a float. Without this check the exception
        # would escape execute_tool and crash the run.
        finite = False
    if not finite:
        raise ValueError(t.not_finite)
    return a + b


def get_current_time():
    """Read the local clock and time zone of the machine running the Python process."""
    local_now = datetime.now().astimezone()
    # The time zone as a UTC offset: tzname() is worded in the operating system's display
    # language, so the same tool would answer in different languages on different machines.
    offset = local_now.strftime("%z")
    return {
        "local_datetime": local_now.isoformat(timespec="seconds"),
        "timezone": f"UTC{offset[:3]}:{offset[3:]}",
        "hour": local_now.hour,
        "minute": local_now.minute,
    }


def available_tools(locale):
    """The allowlist for one run: the only names execute_tool will run, each mapped to its Python function."""
    return {
        "add_numbers": partial(add_numbers, texts_for(locale)),
        "get_current_time": get_current_time,
    }
