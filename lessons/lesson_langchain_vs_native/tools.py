"""The same Python tools, registered the LangChain way.

The native lessons hand-write each tool definition. Here the @tool decorator builds the
definition from the function's name, type hints and the description we pass, and the
function body calls the native implementation unchanged. So any difference between the
two runs comes from what the framework adds or drops, not from different tool code.
"""
from functools import partial

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, ConfigDict

from lessons.lesson_01_tool_selection.locales.tools import texts_for as clock_sum_texts
from lessons.lesson_01_tool_selection.tools import add_numbers, get_current_time
from lessons.lesson_03_fail_safely.locales import texts_for as divide_texts
from lessons.lesson_03_fail_safely.tools import divide_numbers


class StrictNumbers(BaseModel):
    """Arguments of add_numbers with coercion turned off: "23", true and extra keys are rejected."""

    model_config = ConfigDict(strict=True, extra="forbid")
    a: float
    b: float


def add_numbers_tool(locale: str, *, strict: bool = False) -> BaseTool:
    """add_numbers as a LangChain tool; strict=True swaps the inferred schema for StrictNumbers."""
    t = clock_sum_texts(locale)
    native = partial(add_numbers, t)

    # 1. Default: the parameter schema is inferred from the type hints `a: float, b: float`.
    #    Pydantic validates in lax mode, so "23" becomes 23.0 before native() sees it.
    @tool("add_numbers", description=t.add_numbers, args_schema=StrictNumbers if strict else None)
    def add(a: float, b: float) -> float:
        return native(a, b)

    return add


def clock_tool(locale: str) -> BaseTool:
    """get_current_time takes no arguments, so the inferred schema is an empty object."""
    @tool("get_current_time", description=clock_sum_texts(locale).get_current_time)
    def clock() -> dict:
        return get_current_time()

    return clock


def divide_tool(locale: str) -> BaseTool:
    """divide_numbers from fail-safely: a zero divisor still raises the native ValueError."""
    t = divide_texts(locale)
    native = partial(divide_numbers, t)

    @tool("divide_numbers", description=t.divide_numbers)
    def divide(a: float, b: float) -> dict:
        return native(a, b)

    return divide


def langchain_tools(task: str, locale: str) -> list[BaseTool]:
    """The tools of one task, in the order the native setup lists them."""
    if task == "sum":
        return [add_numbers_tool(locale), clock_tool(locale)]
    if task == "divide":
        return [divide_tool(locale)]
    raise ValueError(f"unknown task {task!r}")
