"""Offline test model for dependent-calls: the dependent call's arguments come from this run's real clock; the tools still really run."""
from server.offline import CompletionScript, offline_marker, result_answer, tool_call

CHAIN_ANSWERS = {
    "zh-CN": "真实本地时间为 {time}。小时 {hour} + 分钟 {minute} = {total}。",
    "en": "The real local time is {time}. Hour {hour} + minute {minute} = {total}.",
}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    if exercise_id == "both":
        return CompletionScript(lambda results: _independent(results, locale))
    if exercise_id != "chain":
        raise ValueError(f"dependent-calls has no offline exercise {exercise_id!r}")

    def decide(results):
        if not results:
            return {"tool_calls": [tool_call("get_current_time", {}, 1)]}
        if len(results) == 1 and results[0]["ok"]:
            clock = results[0]["result"]
            return {"tool_calls": [tool_call("add_numbers", {"a": clock["hour"], "b": clock["minute"]}, 2)]}
        if all(result["ok"] for result in results):
            clock = results[0]["result"]
            answer = CHAIN_ANSWERS[locale].format(time=clock["local_datetime"], hour=clock["hour"],
                                                  minute=clock["minute"], total=results[-1]["result"])
            return {"content": offline_marker(locale) + answer}
        return result_answer(results, locale)

    return CompletionScript(decide)


def _independent(results, locale):
    """The two tasks don't depend on each other: round 1 proposes the sum and the time together, then answers from both results."""
    if results:
        return result_answer(results, locale)
    return {"tool_calls": [tool_call("add_numbers", {"a": 19, "b": 23}, 1), tool_call("get_current_time", {}, 2)]}
