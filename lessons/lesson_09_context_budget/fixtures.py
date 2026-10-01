"""第 9 课离线测试模型。"""
from lessons.lesson_09_context_budget.runtime import FACTS


def create_completion(exercise_id, inputs=None):
    if exercise_id not in {"compare", "more_noise", "alternate"}:
        raise ValueError("未知第 9 课练习。")

    def complete(body, api_key):
        shown = str(body["messages"])
        source = next((key for key, fact in FACTS.items() if fact in shown), None)
        answer = f"来源 {source}：{FACTS[source]} 下一步回答当前问题。" if source else "缺少来源，无法确定关键结论。"
        return {"choices": [{"message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": len(shown) // 3, "completion_tokens": len(answer) // 3}}

    return complete
