"""同一个请求原样发几次：数一数回答有几种，看清输出来自采样。"""
from pydantic import Field

from course.execution import LessonInputs, RunContext

DEFAULT_QUESTION = "给一家卖猫咪用品的小店起一个中文店名。"
SYSTEM = "你是起名助手。只输出一个店名，不加解释和标点。"


class Inputs(LessonInputs):
    # 实验条件：两组只改这一个数。
    temperature: float = Field(default=0, ge=0, le=2)
    # 同一个请求连发几次；lesson.json 的 max_rounds 是 5，平台最多放行 5 次请求。
    repeats: int = Field(default=5, ge=2, le=5)


INPUT_MODEL = Inputs


def reply_text(response: dict) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("模型响应缺少 choices[0]，无法读取回答。")
    return (choices[0].get("message") or {}).get("content") or ""


def count_distinct(answers: list[str]) -> int:
    """去掉首尾空白后逐字比较：只差一个标点也算两种，意思相近也不合并。"""
    return len({answer.strip() for answer in answers})


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    question = context.question.strip() or DEFAULT_QUESTION
    # 1. 请求体只拼一次，每次发出的 messages 一字不差。
    body = {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}],
            "temperature": values.temperature}
    responses = []
    for number in range(1, values.repeats + 1):
        # 2. 原样再发一次。每次请求都是独立的，前几次的回答不会带进来。
        responses.append(context.complete(body, round_number=number))
    answers = [reply_text(response) for response in responses]
    # 3. 不同回答数由程序统计，不靠人眼判断。
    distinct = count_distinct(answers)
    _report(context, values, answers, responses, distinct)
    return f"同一个请求发了 {values.repeats} 次，得到 {distinct} 种不同的回答（去掉首尾空白后逐字比较）。"


def _report(context: RunContext, values: Inputs, answers: list[str], responses: list[dict], distinct: int) -> None:
    """平台：把每次回答和用量整理成实验报告；有一次没报告用量，合计就写“未报告”。"""
    usages = [response.get("usage") or {} for response in responses]

    def total(key):
        numbers = [usage.get(key) for usage in usages]
        return "未报告" if any(number is None for number in numbers) else sum(numbers)

    counts = {}
    for answer in answers:
        counts[answer.strip()] = counts.get(answer.strip(), 0) + 1
    context.emit("lesson.report", {
        "title": f"temperature={values.temperature:g}：{values.repeats} 次回答",
        "summary": "同一个请求体原样发出；回答都来自各次 response。不同回答数按去掉首尾空白后逐字比较统计。",
        "metrics": [
            {"label": "temperature", "value": values.temperature},
            {"label": "重复次数", "value": values.repeats},
            {"label": "不同回答数", "value": distinct},
            {"label": "出现最多的回答", "value": f"{max(counts.values())} 次"},
            {"label": "提示 Token 合计", "value": total("prompt_tokens")},
            {"label": "完成 Token 合计", "value": total("completion_tokens")},
            {"label": "总 Token 合计", "value": total("total_tokens")},
        ],
        "table": {"columns": ["次", "回答", "完成 Token"],
                  "rows": [[number, answer, "未报告" if usage.get("completion_tokens") is None
                            else usage["completion_tokens"]]
                           for number, (answer, usage) in enumerate(zip(answers, usages), start=1)]},
    })
