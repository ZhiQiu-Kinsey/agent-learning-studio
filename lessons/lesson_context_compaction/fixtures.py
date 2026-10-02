"""上下文压缩一课的离线测试模型：只服务自动化测试，摘要和回答都是脚本写的，不代表任何真实模型。"""
from lessons.lesson_09_context_budget.runtime import FACTS
from lessons.lesson_context_compaction.runtime import PROBE_PHRASE, PROBE_SOURCES, SUMMARY_INSTRUCTIONS

EXERCISES = {"compare", "tight-budget", "brief-summary"}


def _summary(instruction: str, shown: str) -> str:
    if instruction == SUMMARY_INSTRUCTIONS["brief"]:
        return "摘要（离线夹具）：对话先查了一份资料，之后是多轮旁支讨论。"
    kept = [f"{key}：{fact}" for key, fact in FACTS.items() if fact in shown]
    return "摘要（离线夹具）：目标是查阅资料后回答；已读取 " + "；".join(kept) + "。待办：回答当前问题。"


def create_completion(exercise_id, inputs=None):
    if exercise_id not in EXERCISES:
        raise ValueError("未知的上下文压缩练习。")

    def complete(body, api_key):
        messages = body["messages"]
        shown = str(messages)
        last = messages[-1].get("content")
        if last in SUMMARY_INSTRUCTIONS.values():
            answer = _summary(last, shown)
        elif PROBE_PHRASE in shown:
            answer = f"最早读取的资料来自 {PROBE_SOURCES[0]}，原话是：{FACTS[PROBE_SOURCES[0]]}"
        else:
            answer = "当前上下文里找不到最早那份资料的原话，无法回答。"
        return {"choices": [{"message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": len(shown) // 3, "completion_tokens": len(answer) // 3}}

    return complete
