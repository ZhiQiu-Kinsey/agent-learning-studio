"""Offline test model of the context-budget lesson: serves automated tests only and stands for no real provider."""
from lessons.lesson_09_context_budget.locales.helpers import texts_for as helper_texts

EXERCISES = {"compare", "more_noise", "wide_budget", "broken-pair"}
# Fixed fixture wording per run language; the fact itself comes from the lesson's material.
TEXTS = {
    "zh-CN": {"rejected": "离线测试夹具：模拟服务商拒绝开头就是 tool、前面没有对应 assistant tool_calls 的请求"
                          "（HTTP 400）。真实服务商的返回请用真实模型运行查看。",
              "answer": "来源 {source}：{fact} 下一步回答当前问题。",
              "no_source": "缺少来源，无法确定关键结论。"},
    "en": {"rejected": "Offline test fixture: simulates a provider rejecting a request that starts with tool and has no "
                       "matching assistant tool_calls before it (HTTP 400). Run with a real model to see what a real "
                       "provider returns.",
           "answer": "Source {source}: {fact} Next step: answer the current question.",
           "no_source": "The source is missing, so the key conclusion cannot be determined."},
}


class FixtureProviderError(RuntimeError):
    """A provider rejection simulated by the test fixture; the status and the wording are the fixture's, not a provider's."""
    status_code = 400


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    if exercise_id not in EXERCISES:
        raise ValueError(f"context-budget has no offline exercise {exercise_id!r}")
    facts, text = helper_texts(locale).facts, TEXTS[locale]

    def complete(body, api_key):
        messages = body["messages"]
        if len(messages) > 1 and messages[1].get("role") == "tool":
            raise FixtureProviderError(text["rejected"])
        shown = str(messages)
        source = next((key for key, fact in facts.items() if fact in shown), None)
        answer = text["answer"].format(source=source, fact=facts[source]) if source else text["no_source"]
        return {"choices": [{"message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": len(shown) // 3, "completion_tokens": len(answer) // 3}}

    return complete
