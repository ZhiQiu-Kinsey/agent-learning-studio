"""测试模型协议与课程内 fixture 加载；真实教学工具仍在 Python 中执行。"""
import json

from server.catalog import lesson_callable


def tool_call(name, arguments, index):
    return {"id": "offline_call_" + str(index), "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}


class CompletionScript:
    """只复用响应封装；每门课程自行决定测试响应，不按全局练习 ID 分派。"""

    def __init__(self, decide):
        self.decide = decide
        self.calls = 0

    def __call__(self, body, api_key):
        self.calls += 1
        results = [json.loads(message["content"]) for message in body["messages"] if message["role"] == "tool"]
        message = {"role": "assistant", "content": None, **self.decide(results)}
        return {"id": f"offline_response_{self.calls}", "object": "chat.completion", "model": "offline-script",
                "choices": [{"index": 0, "message": message,
                             "finish_reason": "tool_calls" if message.get("tool_calls") else "stop"}]}


def result_answer(results):
    failed = next((result for result in results if not result["ok"]), None)
    if failed:
        text = "工具未能完成：" + failed["error"] + " 请修正输入后再试。"
    else:
        text = "Python 工具返回：" + "；".join(json.dumps(result["result"], ensure_ascii=False) for result in results)
    return {"content": "【离线脚本回答】" + text}


def completion_for(spec, exercise_id, inputs=None):
    if not any(exercise["id"] == exercise_id for exercise in spec["exercises"]):
        raise ValueError("当前课程未声明此离线练习。")
    factory = lesson_callable(spec, spec["testing"]["completion_factory"])
    completion = factory(exercise_id, inputs=inputs or {})
    if not callable(completion):
        raise ValueError("课程 completion_factory 必须返回可调用的模型测试适配器。")
    return completion

