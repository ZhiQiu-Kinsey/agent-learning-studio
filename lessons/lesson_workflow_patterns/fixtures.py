"""Offline test model for workflow-patterns: serves automated tests only and does not stand for any real model.

The routing script deliberately misroutes two tickets and answers one with a label that is not in the list,
to test accuracy, the confusion matrix and the fallback. Each restating subtask pauses 50 ms so tests can
compare serial and parallel wall-clock time.
"""
import json
import time

from lessons.lesson_workflow_patterns.locales import texts_for
from lessons.lesson_workflow_patterns.runtime import GOLD

# Scripted router answers that differ from the author's label, by ticket id.
OVERRIDES = {
    "t18": "error",     # lost progress: labelled account, the script says error
    "t20": "error",     # asks about the backup data source: labelled course, the script says error
    "t12": "billing",   # not a label in the list, so it must take the fallback
}
CHAIN_OUTPUTS = {
    "zh-CN": [
        "- 模型只看到本次请求里的消息\n- 工具调用和工具结果要成对\n- 上下文越长越要挑信息",
        "Q: 模型能看到什么？\nA: 只有本次请求里的消息。\nQ: 工具消息有什么要求？\nA: 调用和工具结果要成对。\n"
        "Q: 上下文长了怎么办？\nA: 只留真正需要的信息。",
        json.dumps(["模型看到什么", "成对的消息", "挑选上下文"], ensure_ascii=False),
    ],
    "en": [
        "- The model sees only the messages in this request\n- Tool calls and tool results come in pairs\n"
        "- The longer the context, the more you must choose",
        "Q: What can the model see?\nA: Only the messages in this request.\nQ: What do tool messages require?\n"
        "A: A call and its tool result come in pairs.\nQ: What if the context grows long?\nA: Keep only what is really needed.",
        json.dumps(["What the model sees", "Messages in pairs", "Choosing context"]),
    ],
}
SUMMARY_PREFIX = {"zh-CN": "要点：", "en": "Key point: "}


def _reply(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    t = texts_for(locale)
    scripted = {t.tickets[ticket]: OVERRIDES.get(ticket, gold) for ticket, gold in GOLD.items()}
    chain_step = 0

    def complete(body, api_key):
        nonlocal chain_step
        messages = body["messages"]
        if messages[0]["role"] == "system" and messages[0]["content"] == t.summary_system:
            time.sleep(0.05)
            return _reply(SUMMARY_PREFIX[locale] + messages[1]["content"][:20])
        if messages[0]["role"] == "system":
            return _reply(scripted.get(messages[1]["content"], "other"))
        outputs = CHAIN_OUTPUTS[locale]
        output = outputs[min(chain_step, len(outputs) - 1)]
        chain_step += 1
        return _reply(output)

    return complete
