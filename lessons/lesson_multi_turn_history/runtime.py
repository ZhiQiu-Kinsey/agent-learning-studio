"""连问几轮：程序把每轮的问题和回答记在 history 里，下一次请求再把它们发出去。"""
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext

SYSTEM = "你是简洁的助手，每次只用一句话回答。"
# 第一轮说出一个事实，后面的问题都要靠这个事实才能回答。
TURNS = [
    "我养了一只猫，名字叫团子，今年三岁。请只回答“记住了”。",
    "我的猫叫什么名字？",
    "它今年几岁？",
]
FACT = "团子"


class Inputs(LessonInputs):
    # full：每轮带上之前的全部消息；latest_only：只发 system 和这一轮的问题。
    history: Literal["full", "latest_only"] = "full"
    turns: int = Field(default=2, ge=2, le=3)


INPUT_MODEL = Inputs


def reply_text(response: dict) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("模型响应缺少 choices[0]，无法读取回答。")
    return (choices[0].get("message") or {}).get("content") or ""


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    # 1. 消息历史只存在这个 Python 列表里，模型那边什么都不留。
    history = [{"role": "system", "content": SYSTEM}]
    turns = []
    for number, question in enumerate(TURNS[:values.turns], start=1):
        # 2. 这一轮的问题先进历史。
        history.append({"role": "user", "content": question})
        # 3. 决定这次发什么：整段历史，或者只有 system 和这一轮的问题。
        messages = history if values.history == "full" else [history[0], history[-1]]
        response = context.complete({"messages": messages}, round_number=number)
        answer = reply_text(response)
        turns.append({"messages": list(messages), "response": response, "answer": answer})
        # 4. 回答作为 assistant 消息放回历史；不放回去，下一轮就发不出它。
        history.append({"role": "assistant", "content": answer})
    _report(context, values, turns)
    return answer


def _report(context: RunContext, values: Inputs, turns: list[dict]) -> None:
    """平台：把每轮发出的消息数和用量整理成实验报告。"""
    def prompt_tokens(turn):
        return (turn["response"].get("usage") or {}).get("prompt_tokens")

    def completion_tokens(turn):
        return (turn["response"].get("usage") or {}).get("completion_tokens")

    rows = [[number, len(turn["messages"]), "是" if any(FACT in m["content"] for m in turn["messages"]) else "否",
             "未报告" if prompt_tokens(turn) is None else prompt_tokens(turn),
             "未报告" if completion_tokens(turn) is None else completion_tokens(turn), turn["answer"]]
            for number, turn in enumerate(turns, start=1)]
    first, last = prompt_tokens(turns[0]), prompt_tokens(turns[-1])
    second = turns[1]
    context.emit("lesson.report", {
        "title": "每轮发出的消息与用量",
        "summary": ("每轮都把整段历史重发一遍。" if values.history == "full" else "每轮只发 system 和这一轮的问题。")
                   + "数字来自各轮 response 的 usage；没有报告的写“未报告”。",
        "checks": [
            {"label": "第二轮请求里有第一轮说的事实", "passed": any(FACT in m["content"] for m in second["messages"]),
             "detail": f"逐条检查第二轮实际发出的 messages 里有没有“{FACT}”。"},
            {"label": "第二轮回答提到了这个事实", "passed": FACT in second["answer"],
             "detail": "检查第二轮 response 的 content，只说明这一次的回答。"},
        ],
        "metrics": [
            {"label": "模式", "value": "整段历史" if values.history == "full" else "只发本轮问题"},
            {"label": "模型调用数", "value": len(turns)},
            {"label": "最后一轮发出的消息数", "value": len(turns[-1]["messages"])},
            {"label": "提示 Token 从第一轮到最后一轮",
             "value": "未报告" if first is None or last is None else f"{first} → {last}"},
            {"label": "学习者备注", "value": context.question.strip() or "（空）"},
        ],
        "table": {"columns": ["轮", "发出的消息数", "包含事实", "提示 Token", "完成 Token", "回答"], "rows": rows},
    })
