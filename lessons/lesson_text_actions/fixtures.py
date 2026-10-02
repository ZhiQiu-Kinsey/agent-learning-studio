"""第 13 课离线测试模型：只服务自动化测试，不代表任何真实模型的行为。

不带 stop 的分支故意让“模型”接着写出一段 Observation 和 Final Answer，用来测试运行器会不会采信它。
"""
import json

ACTION = 'Thought: 需要先查成绩。\nAction: lookup_quiz_score\nAction Input: {"student_id": "%s"}\n'
INVENTED = 'Observation: {"score": 88, "attempts": 1}\nThought: 88 分，及格了。\nFinal Answer: 他得了 88 分，及格。'


def _student(messages):
    question = next(m["content"] for m in messages if m["role"] == "user")
    return "s-2077" if "s-2077" in question else "s-1042"


def _observed(messages):
    """取最后一条真实 Observation 里的分数；没有就返回 None。"""
    for message in reversed(messages):
        content = message.get("content")
        if message["role"] == "user" and isinstance(content, str) and content.startswith("Observation: "):
            result = json.loads(content[len("Observation: "):])
            return result["result"]["score"] if result.get("ok") else None
        if message["role"] == "tool":
            result = json.loads(message["content"])
            return result["result"]["score"] if result.get("ok") else None
    return None


def _final(score):
    return f"他最近一次得了 {score} 分，{'及格' if score >= 60 else '没有及格'}。"


def create_completion(exercise_id, inputs=None):
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
            return {"choices": [{"message": {"role": "assistant", "content": _final(score)}, "finish_reason": "stop"}]}
        if score is None:
            content = ACTION % _student(messages)
            if "stop" not in body:
                content += INVENTED
            return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}
        content = f"Thought: 拿到了真实成绩。\nFinal Answer: {_final(score)}"
        return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}

    return complete
