"""Division samples for fail-safely: a normal division and a zero divisor, to check that the runner returns the failure.

The two fault injections (unregistered tool, broken arguments) call no model; runtime.py's runner
builds them, so they need no sample.
"""
from server.offline import CompletionScript, result_answer, tool_call


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    if exercise_id not in ("divide", "zero"):
        raise ValueError(f"fail-safely has no offline exercise {exercise_id!r}")

    def decide(results):
        if results:
            return result_answer(results, locale)
        return {"tool_calls": [tool_call("divide_numbers", {"a": 12, "b": 0 if exercise_id == "zero" else 3}, 1)]}

    return CompletionScript(decide)
