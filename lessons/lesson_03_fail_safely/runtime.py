"""Web entry: the division exercises use the native tool loop; the two fault-injection arms call no model.

For a fault injection the runner itself builds a faulty call and hands it to the same checks
a model proposal goes through (execute_tool). A model won't reliably propose such a call, so
we don't rely on one; the events mark the call as runner-initiated instead of passing it off
as a model proposal.
"""
from course.execution import RunContext
from lessons.lesson_03_fail_safely import main
from lessons.lesson_03_fail_safely.locales import texts_for
# The prompt and tools page reads setup(locale) from the entry module: the same setup main.py uses.
from lessons.lesson_03_fail_safely.main import setup  # noqa: F401
from lessons.lesson_03_fail_safely.tools import available_tools

# Exercise id -> the call the program builds: an unregistered tool name, or argument text that won't parse.
FAULTS = {
    "unknown": ("unregistered_tool", "{}"),
    "malformed": ("divide_numbers", "{bad json"),
}


def run(context: RunContext) -> str:
    fault = FAULTS.get(context.exercise_id)
    if fault is None:
        # Division exercises: the same tool loop as a native lesson, at most two model requests.
        return context.run_native(main, max_rounds=2, publish_answer=True)
    name, arguments = fault
    result = context.submit_call(name, arguments, available_tools(context.locale))
    # The program writes the answer from the real result: this arm has no model, so no model answer.
    return texts_for(context.locale).fault_answer.format(
        name=name, arguments=arguments, error_type=result["error_type"], error=result["error"])
