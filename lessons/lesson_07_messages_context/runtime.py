"""对同一追问发送完整历史与合法的消融历史。"""
from typing import Literal
from pydantic import Field

from course.execution import LessonInputs, RunContext


class Inputs(LessonInputs):
    fact: str = Field(default="课程代号是 QH-731。", min_length=4, max_length=160)
    follow_up: str = Field(default="课程代号是什么？", min_length=4, max_length=160)
    comparison: Literal["omit", "full_only"] = "omit"


INPUT_MODEL = Inputs
SYSTEM = "请根据本次请求中可见的消息回答。若缺少依据，明确说无法从当前消息确定；不要猜测。"


def _answer(response: dict) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("模型响应缺少 choices[0]。")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ValueError("模型没有返回可比较的文本回答。")
    return message["content"]


def validate_tool_history(messages: list[dict]) -> None:
    """检查本课展示的标准 assistant-tool 配对，避免伪造孤立 tool 消息。"""
    outstanding: set[str] = set()
    seen: set[str] = set()
    for message in messages:
        role = message.get("role")
        if outstanding and role != "tool":
            raise ValueError("工具调用后必须先提供对应的 tool 消息。")
        if role == "assistant":
            for call in message.get("tool_calls", []):
                call_id = call.get("id")
                if not isinstance(call_id, str) or not call_id or call_id in seen:
                    raise ValueError("工具调用 id 必须非空且唯一。")
                outstanding.add(call_id)
                seen.add(call_id)
        elif role == "tool":
            call_id = message.get("tool_call_id")
            if call_id not in outstanding:
                raise ValueError("孤立或重复的 tool 消息。")
            outstanding.remove(call_id)
        elif role not in {"system", "user"}:
            raise ValueError("未知消息角色。")
    if outstanding:
        raise ValueError("工具调用缺少对应的 tool 消息。")


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    follow_up = context.question.strip() or values.follow_up
    def visible(messages: list[dict], fact: str) -> bool:
        return any(isinstance(message.get("content"), str) and fact in message["content"]
                   for message in messages)
    seed = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"请只确认收到这个事实：{values.fact}"},
    ]
    first = _answer(context.complete({"messages": seed, "temperature": 0}, round_number=1))
    full = [*seed, {"role": "assistant", "content": first},
            {"role": "user", "content": follow_up}]
    validate_tool_history(full)
    full_answer = _answer(context.complete({"messages": full, "temperature": 0}, round_number=2))
    rows = [["完整历史", len(full), visible(full, values.fact), full_answer]]
    if values.comparison == "omit":
        omitted = [seed[0], {"role": "user", "content": follow_up}]
        validate_tool_history(omitted)
        omitted_answer = _answer(context.complete({"messages": omitted, "temperature": 0}, round_number=3))
        rows.append(["移除早先事实", len(omitted), visible(omitted, values.fact), omitted_answer])
    checks = [
        {"label": "所有请求为合法消息历史", "passed": True, "detail": "已对实际发出的消息运行协议检查；本实验没有工具调用。"},
        {"label": "完整历史包含先前事实", "passed": visible(full, values.fact), "detail": "逐条检查实际传给 complete 的消息内容。"},
    ]
    if values.comparison == "omit":
        checks.append({"label": "消融历史不含事实", "passed": not visible(omitted, values.fact),
                       "detail": "逐条检查移除历史后的消息内容。"})
    context.emit("lesson.report", {
        "title": "消息历史对照", "summary": f"同一追问、同一模型；实际追问：{follow_up}。答案以 response 事件为准。",
        "checks": checks,
        "metrics": [{"label": "模型调用数", "value": len(rows) + 1}, {"label": "完整历史消息数", "value": len(full)},
                    {"label": "实际追问", "value": follow_up}],
        "table": {"columns": ["请求", "消息数", "包含早先事实", "模型回答"], "rows": rows},
    })
    return "已保存真实请求与回答。请比较两次追问的 messages 和 response；回答差异本身不证明模型内部记忆。"
