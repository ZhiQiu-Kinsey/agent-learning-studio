"""Offline test model for text-actions: serves automated tests only and stands for no real model.

Without stop the "model" deliberately goes on to write an Observation and a Final Answer,
to test whether the runner trusts them.
"""
import json

# Deterministic script text per run language. The protocol keywords stay English in both.
SCRIPT = {
    "zh-CN": {
        "action": 'Thought: 需要先查成绩。\nAction: lookup_quiz_score\nAction Input: {"student_id": "%s"}\n',
        "invented": 'Observation: {"score": 88, "attempts": 1}\nThought: 88 分，及格了。\nFinal Answer: 他得了 88 分，及格。',
        "got_result": "Thought: 拿到了真实成绩。\nFinal Answer: ",
        "final": "他最近一次得了 {score} 分，{verdict}。",
        "passed": "及格",
        "failed": "没有及格",
    },
    "en": {
        "action": 'Thought: I need to look up the score first.\nAction: lookup_quiz_score\nAction Input: {"student_id": "%s"}\n',
        "invented": ('Observation: {"score": 88, "attempts": 1}\nThought: 88 points, a pass.\n'
                     'Final Answer: The student scored 88 and passed.'),
        "got_result": "Thought: I have the real score.\nFinal Answer: ",
        "final": "The latest score is {score}, so the student {verdict}.",
        "passed": "passed",
        "failed": "did not pass",
    },
}


def _student(messages):
    question = next(m["content"] for m in messages if m["role"] == "user")
    return "s-2077" if "s-2077" in question else "s-1042"


def _observed(messages):
    """The score in the last real Observation, or None."""
    for message in reversed(messages):
        content = message.get("content")
        if message["role"] == "user" and isinstance(content, str) and content.startswith("Observation: "):
            result = json.loads(content[len("Observation: "):])
            return result["result"]["score"] if result.get("ok") else None
        if message["role"] == "tool":
            result = json.loads(message["content"])
            return result["result"]["score"] if result.get("ok") else None
    return None


def _final(score, script):
    return script["final"].format(score=score, verdict=script["passed"] if score >= 60 else script["failed"])


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    script = SCRIPT[locale]
    protocol = (inputs or {}).get("protocol") or {"text-no-stop": "text_no_stop", "native": "native"}.get(
        exercise_id, "text_stop")

    def complete(body, api_key):
        messages = body["messages"]
        score = _observed(messages)
        if protocol == "native":
            if score is None:
                call = {"id": "call_score_1", "type": "function", "function": {
                    "name": "lookup_quiz_score", "arguments": json.dumps({"student_id": _student(messages)})}}
                return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [call]},
                                     "finish_reason": "tool_calls"}]}
            return {"choices": [{"message": {"role": "assistant", "content": _final(score, script)},
                                 "finish_reason": "stop"}]}
        if score is None:
            content = script["action"] % _student(messages)
            if "stop" not in body:
                content += script["invented"]
            return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}
        content = script["got_result"] + _final(score, script)
        return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}

    return complete
