"""把工具定义随请求发给模型，只记录它提出的调用；本课不执行任何工具。"""
import json

from course.execution import RunContext
from lessons.lesson_01_tool_selection.tools import tool_definitions

DEFAULT_QUESTION = "帮我计算 19 加 23。"
SYSTEM_PROMPT = (
    "你是教学用助手。计算两个数字的和时调用 add_numbers；"
    "询问当前时间或日期时调用 get_current_time；其他问题直接回答。"
)


def read_proposals(message: dict) -> list[dict]:
    """把 tool_calls 整理成调用提议列表：只读字段，不查函数，也不执行。"""
    proposals = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        arguments = function.get("arguments")
        try:
            # arguments 是一段 JSON 字符串。这里只检查它能不能解析成对象，解析结果不拿去调用任何函数。
            valid = isinstance(json.loads(arguments or "{}"), dict)
        except (TypeError, json.JSONDecodeError):
            valid = False
        proposals.append({"id": call.get("id"), "name": function.get("name"),
                          "arguments": arguments, "valid_json": valid})
    return proposals


def run(context: RunContext) -> str:
    question = context.question.strip() or DEFAULT_QUESTION
    # 1. 请求体比“一次模型请求”多了 tools 和 tool_choice：工具定义随请求一起发给模型。
    body = {"messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question}],
            "tools": tool_definitions(context.locale), "tool_choice": "auto"}
    # 2. 只发这一次请求。
    response = context.complete(body)
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("模型响应缺少 choices[0]，无法读取调用提议。")
    message = choices[0].get("message") or {}
    # 3. 只读调用提议。本课没有登记任何可执行的函数，所以不会有工具结果。
    proposals = read_proposals(message)
    _report(context, choices[0].get("finish_reason"), message, proposals)
    if not proposals:
        return message.get("content") or "（模型没有提出调用，content 也为空。）"
    lines = [f"{item['name']}({item['arguments']})" for item in proposals]
    return f"模型提出了 {len(proposals)} 个调用：" + "；".join(lines) + "。本课不执行工具，所以没有工具结果。"


def _report(context: RunContext, finish_reason: str | None, message: dict, proposals: list[dict]) -> None:
    """平台：把调用提议整理成实验报告。"""
    context.emit("lesson.report", {
        "title": "模型提出了什么",
        "summary": "表格只列响应里的 tool_calls；本课没有执行任何工具，事件里也就没有 tool_call 和 tool_result。",
        "metrics": [
            {"label": "finish_reason", "value": "未报告" if finish_reason is None else finish_reason},
            {"label": "调用提议数", "value": len(proposals)},
            {"label": "content 长度（字符）", "value": len(message.get("content") or "")},
        ],
        "table": {"columns": ["调用 id", "工具名", "arguments（JSON 字符串）", "能解析成 JSON 对象"],
                  "rows": [[item["id"] or "（无）", item["name"] or "（无）", item["arguments"] or "（空）",
                            item["valid_json"]] for item in proposals]},
    })
