"""上下文预算一课的离线测试模型：只服务自动化测试，不代表任何真实服务商的行为。"""
from lessons.lesson_09_context_budget.runtime import FACTS

EXERCISES = {"compare", "more_noise", "wide_budget", "broken-pair"}


class FixtureProviderError(RuntimeError):
    """测试夹具模拟的服务商拒绝；状态码与文案都是夹具写的，不是服务商返回的。"""
    status_code = 400


def create_completion(exercise_id, inputs=None):
    if exercise_id not in EXERCISES:
        raise ValueError("未知的上下文预算练习。")

    def complete(body, api_key):
        messages = body["messages"]
        if len(messages) > 1 and messages[1].get("role") == "tool":
            raise FixtureProviderError("离线测试夹具：模拟服务商拒绝开头就是 tool、前面没有对应 assistant tool_calls 的请求"
                                       "（HTTP 400）。真实服务商的返回请用真实模型运行查看。")
        shown = str(messages)
        source = next((key for key, fact in FACTS.items() if fact in shown), None)
        answer = f"来源 {source}：{FACTS[source]} 下一步回答当前问题。" if source else "缺少来源，无法确定关键结论。"
        return {"choices": [{"message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": len(shown) // 3, "completion_tokens": len(answer) // 3}}

    return complete
