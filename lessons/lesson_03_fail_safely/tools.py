"""Error handling and safety boundaries: a division tool that rejects invalid input explicitly."""

import math
from functools import partial

from lessons.lesson_03_fail_safely.locales import texts_for


def tool_definitions(locale):
    """The tool sent with every request. Names are code; the descriptions come in the run's language."""
    t = texts_for(locale)
    return [
        {
            "type": "function",
            "function": {
                "name": "divide_numbers",
                "description": t.divide_numbers,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": t.divide_numbers_a},
                        "b": {"type": "number", "description": t.divide_numbers_b},
                    },
                    "required": ["a", "b"],
                    "additionalProperties": False,
                },
            },
        }
    ]


def divide_numbers(t, /, a, b):
    """Validate the input and report business-rule errors as ValueError.

    t holds the error messages of the run's language. It is positional-only, so the
    arguments the model sends (always by name) can never replace it.
    """
    for name, value in (("a", a), ("b", b)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(t.not_a_number.format(name=name))

    try:
        finite_inputs = math.isfinite(a) and math.isfinite(b)
    except OverflowError:
        finite_inputs = False
    if not finite_inputs:
        raise ValueError(t.not_finite)

    if b == 0:
        raise ValueError(t.zero_divisor)

    try:
        quotient = a / b
    except OverflowError:
        raise ValueError(t.out_of_range) from None
    if not math.isfinite(quotient):
        raise ValueError(t.out_of_range)
    return {"quotient": quotient}


def available_tools(locale):
    """The allowlist for one run: the only names execute_tool will run, each mapped to its Python function."""
    return {"divide_numbers": partial(divide_numbers, texts_for(locale))}
