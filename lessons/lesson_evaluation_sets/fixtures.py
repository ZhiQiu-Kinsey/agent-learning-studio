"""Offline test model for evaluation-sets: serves automated tests only and stands for no real model.

The script gives version A and version B fixed behaviours, so the tests see improvements,
a regression on the holdout set and one judge disagreement. The tools still really run:
the clock cases use this machine's real time. Every final answer starts with the offline marker.
"""
import itertools
import json

from lessons.lesson_evaluation_sets.locales import texts_for
from server.offline import offline_marker, tool_call

# The scripted answers carry only the answer tag; the greeting reuses the author's sample j1,
# so this file holds no text of its own in any language.
VALUE, NONE = "<answer>{value}</answer>", "<answer>NONE</answer>"
# The judge in this script agrees with the human labels except on j6: the long answer with a false claim passes.
JUDGE_SCRIPT = {"j1": "pass", "j2": "fail", "j3": "fail", "j4": "pass", "j5": "pass", "j6": "pass"}
OPERANDS = {"add-basic": (19, 23), "add-holdout": (58, 67), "divide-zero": (100, 0), "divide-zero-holdout": (7, 0)}


def _value(result: dict):
    value = result.get("result")
    value = value.get("quotient") if isinstance(value, dict) else value
    return f"{value:g}"


def _reply(message: dict, number: int) -> dict:
    message = {"role": "assistant", "content": None, **message}
    return {"id": f"offline_response_{number}", "object": "chat.completion", "model": "offline-script",
            "choices": [{"index": 0, "message": message,
                         "finish_reason": "tool_calls" if message.get("tool_calls") else "stop"}]}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    t = texts_for(locale)
    ids, responses = itertools.count(1), itertools.count(1)

    def call(name, arguments):
        return tool_call(name, arguments, next(ids))

    def say(value):
        return {"content": offline_marker(locale) + VALUE.format(value=value)}

    def none():
        return {"content": offline_marker(locale) + NONE}

    def decide(case, version, results):
        if case in ("add-basic", "add-holdout"):
            a, b = OPERANDS[case]
            return say(_value(results[0])) if results else {"tool_calls": [call("add_numbers", {"a": a, "b": b})]}
        if case in ("divide-zero", "divide-zero-holdout"):
            a, b = OPERANDS[case]
            if not results:
                return {"tool_calls": [call("divide_numbers", {"a": a, "b": b})]}
            # Version A answers a number after the tool error; version B answers NONE.
            return say(0) if version == "A" else none()
        if case == "two-sums":
            if not results:
                return {"tool_calls": [call("add_numbers", {"a": 19, "b": 23}), call("add_numbers", {"a": 100, "b": 5})]}
            return say(", ".join(_value(result) for result in results))
        if case == "greeting":
            return {"content": offline_marker(locale) + t.judge_answers["j1"]}
        if case == "unknown-balance":
            # Version A invents a balance of 1000; version B says no tool can give it.
            return say(1100) if version == "A" else none()
        if case == "given-distance":
            if version == "A":
                return say(12)
            # Version B over-applies its "always call a tool" rule to a number the question already gives.
            return say(_value(results[0])) if results else {"tool_calls": [call("add_numbers", {"a": 12, "b": 0})]}
        operation = "add_numbers" if case == "clock-sum" else "divide_numbers"
        if version == "A":
            # Version A sends the dependent call together with the clock call, with guessed arguments.
            if not results:
                guessed = {"a": 12, "b": 30} if case == "clock-sum" else {"a": 12, "b": 2}
                return {"tool_calls": [call("get_current_time", {}), call(operation, guessed)]}
            return say(_value(results[1]))
        if not results:
            return {"tool_calls": [call("get_current_time", {})]}
        if len(results) == 1:
            clock = results[0]["result"]
            arguments = {"a": clock["hour"], "b": clock["minute"] if case == "clock-sum" else 2}
            return {"tool_calls": [call(operation, arguments)]}
        return say(_value(results[-1]))

    def complete(body, api_key):
        messages = body["messages"]
        system, user = messages[0]["content"], messages[1]["content"]
        if system == t.judge_system:
            # The longest answer that ends the request: "Hello!" is also the start of j6.
            sample = max((key for key, answer in t.judge_answers.items() if user.endswith(answer)),
                         key=lambda key: len(t.judge_answers[key]))
            verdict = JUDGE_SCRIPT[sample]
            content = json.dumps({"verdict": verdict, "reason": t.labels[verdict]}, ensure_ascii=False)
            return _reply({"content": content}, next(responses))
        case = next((key for key, question in t.questions.items() if question == user), None)
        if case is None:
            raise ValueError("evaluation-sets fixture got a question outside the suite")
        version = "B" if t.rules_b in system else "A"
        results = [json.loads(message["content"]) for message in messages if message["role"] == "tool"]
        return _reply(decide(case, version, results), next(responses))

    return complete
