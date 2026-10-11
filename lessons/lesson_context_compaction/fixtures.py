"""Offline test model of the context-compaction lesson: serves automated tests only; the summaries and answers are
written by this script and stand for no real model."""
from lessons.lesson_09_context_budget.locales.helpers import texts_for as helper_texts
from lessons.lesson_context_compaction.locales import texts_for
from lessons.lesson_context_compaction.runtime import SOURCES

EXERCISES = {"compare", "tight-budget", "brief-summary"}
# Fixed fixture wording per run language; facts and instructions come from the lessons' catalogs.
TEXTS = {
    "zh-CN": {"brief": "摘要（离线夹具）：对话先查了一份资料，之后是多轮旁支讨论。",
              "kept": "{key}：{fact}", "separator": "；",
              "summary": "摘要（离线夹具）：目标是查阅资料后回答；已读取 {kept}。待办：回答当前问题。",
              "probe": "最早读取的资料来自 {key}，原话是：{fact}",
              "lost": "当前上下文里找不到最早那份资料的原话，无法回答。"},
    "en": {"brief": "Summary (offline fixture): the conversation looked up one material, then had several rounds of side discussion.",
           "kept": "{key}: {fact}", "separator": "; ",
           "summary": "Summary (offline fixture): the goal is to answer after reading the materials; read {kept} "
                      "Open item: answer the current question.",
           "probe": "The earliest material came from {key}; its original wording is: {fact}",
           "lost": "The original wording of the earliest material is not in the current context, so I cannot answer."},
}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    if exercise_id not in EXERCISES:
        raise ValueError(f"context-compaction has no offline exercise {exercise_id!r}")
    t, facts, text = texts_for(locale), helper_texts(locale).facts, TEXTS[locale]

    def summarize(instruction: str, shown: str) -> str:
        if instruction == t.summary_instructions["brief"]:
            return text["brief"]
        kept = [text["kept"].format(key=key, fact=fact) for key, fact in facts.items() if fact in shown]
        return text["summary"].format(kept=text["separator"].join(kept))

    def complete(body, api_key):
        messages = body["messages"]
        shown = str(messages)
        last = messages[-1].get("content")
        if last in t.summary_instructions.values():
            answer = summarize(last, shown)
        elif t.probe_phrase in shown:
            answer = text["probe"].format(key=SOURCES[0], fact=facts[SOURCES[0]])
        else:
            answer = text["lost"]
        return {"choices": [{"message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": len(shown) // 3, "completion_tokens": len(answer) // 3}}

    return complete
