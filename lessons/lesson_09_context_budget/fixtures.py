"""第 9 课离线测试模型：只服务自动化测试，不代表任何真实服务商的行为。"""
from lessons.lesson_09_context_budget.runtime import FACTS, SUMMARY_INSTRUCTION


class FixtureProviderError(RuntimeError):
    """测试夹具模拟的服务商拒绝；状态码与文案都是夹具写的，不是服务商返回的。"""
    status_code = 400


def _summary(messages):
    shown = str(messages)
    kept = [f"{key}：{fact}" for key, fact in FACTS.items() if fact in shown]
    return "摘要（离线夹具）：目标是查阅资料后回答；已读取 " + "；".join(kept) + "。待办：回答当前问题。"


def create_completion(exercise_id, inputs=None):
    if exercise_id not in {"compare", "more_noise", "alternate", "compaction", "broken-pair"}:
        raise ValueError("未知第 9 课练习。")

    def complete(body, api_key):
        messages = body["messages"]
        if len(messages) > 1 and messages[1].get("role") == "tool":
            raise FixtureProviderError("离线测试夹具：模拟服务商拒绝开头就是 tool、前面没有对应 assistant tool_calls 的请求"
                                       "（HTTP 400）。真实服务商的返回请用真实模型运行查看。")
        if messages[-1].get("content") == SUMMARY_INSTRUCTION:
            answer = _summary(messages)
        else:
            shown = str(messages)
            source = next((key for key, fact in FACTS.items() if fact in shown), None)
            answer = f"来源 {source}：{FACTS[source]} 下一步回答当前问题。" if source else "缺少来源，无法确定关键结论。"
        return {"choices": [{"message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": len(str(messages)) // 3, "completion_tokens": len(answer) // 3}}

    return complete
