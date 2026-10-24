"""测试模型协议与课程内 fixture 加载；真实教学工具仍在 Python 中执行。"""
import inspect
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


# 确定性回答的固定文字，按运行语言写；英文运行的事件里不能出现中文。
OFFLINE_TEXTS = {
    "zh-CN": {"marker": "【离线脚本回答】", "failed": "工具未能完成：{error} 请修正输入后再试。",
              "returned": "Python 工具返回：{results}", "separator": "；"},
    "en": {"marker": "[Offline script answer] ", "failed": "The tool could not finish: {error} Fix the input and try again.",
           "returned": "The Python tool returned: {results}", "separator": "; "},
}


def offline_marker(locale="zh-CN"):
    """确定性回答的开头标记，让读者一眼看出这不是模型写的。"""
    return OFFLINE_TEXTS[locale]["marker"]


def result_answer(results, locale="zh-CN"):
    texts = OFFLINE_TEXTS[locale]
    failed = next((result for result in results if not result["ok"]), None)
    if failed:
        text = texts["failed"].format(error=failed["error"])
    else:
        text = texts["returned"].format(results=texts["separator"].join(
            json.dumps(result["result"], ensure_ascii=False) for result in results))
    return {"content": texts["marker"] + text}


def _fixture_for(spec, key, exercise_id, inputs, locale):
    """按课程声明的 testing.<key> 构造确定性适配器；只在离线测试模式使用。"""
    if not any(exercise["id"] == exercise_id for exercise in spec["exercises"]):
        raise ValueError("当前课程未声明此离线练习。")
    factory = lesson_callable(spec, spec["testing"][key])
    # 支持多种运行语言的课，fixture 接受 locale，按运行语言给出确定性响应；只有源语言的课不需要。
    if "locale" in inspect.signature(factory).parameters:
        adapter = factory(exercise_id, inputs=inputs or {}, locale=locale)
    elif locale != spec["runtime"]["locales"][0]:
        raise ValueError(f"{spec['id']} 的 {key} 不接受 locale，不能离线运行 {locale}。")
    else:
        adapter = factory(exercise_id, inputs=inputs or {})
    if not callable(adapter):
        raise ValueError(f"课程 {key} 必须返回可调用的模型测试适配器。")
    return adapter


def completion_for(spec, exercise_id, inputs=None, locale="zh-CN"):
    return _fixture_for(spec, "completion_factory", exercise_id, inputs, locale)


def embedding_for(spec, exercise_id, inputs=None, locale="zh-CN"):
    """Embedding 夹具：create_embedding(exercise_id, inputs, locale) 返回 embedding(body, api_key)。"""
    return _fixture_for(spec, "embedding_factory", exercise_id, inputs, locale)


def stream_for(spec, exercise_id, inputs=None, locale="zh-CN"):
    """流式夹具：create_stream(exercise_id, inputs, locale) 返回 stream(body, api_key)，后者返回分块字典的可迭代对象。"""
    return _fixture_for(spec, "stream_factory", exercise_id, inputs, locale)


def approval_for(spec, exercise_id, inputs=None, locale="zh-CN"):
    """审批夹具：create_approval_policy(exercise_id, inputs, locale) 返回 policy(request)。

    policy 返回 {"decision": "approve" | "reject" | "timeout", "note"?, "edited_payload"?}，事件记为
    decided_by="offline_fixture"；返回 None 时交给 POST /api/runs/{id}/approvals，与真实运行相同。
    """
    return _fixture_for(spec, "approval_factory", exercise_id, inputs, locale)
