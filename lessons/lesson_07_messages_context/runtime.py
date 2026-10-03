"""一次请求的上下文由哪几部分组成：一次只拿掉一部分，看回答依赖的是哪一部分。

完整上下文是五条消息：系统提示词、之前的对话、工具调用、工具结果、本轮问题。
工具结果来自本次真实执行的 lookup_score；带 tool_calls 的 assistant 消息由运行器写入，不是模型生成的。
"""
import json
from typing import Literal

from course.execution import LessonInputs, RunContext


class Inputs(LessonInputs):
    student_id: Literal["s-1042", "s-2077"] = "s-1042"
    free_day: Literal["周一", "周二", "周三", "周四", "周五", "周六", "周日"] = "周四"


INPUT_MODEL = Inputs
# 本地成绩表：分数没有规律，模型猜不到；回答里出现这个分数，才说明它用上了工具结果。
SCORES = {
    "s-1042": {"student_id": "s-1042", "score": 73, "pass_line": 60},
    "s-2077": {"student_id": "s-2077", "score": 58, "pass_line": 60},
}
SYSTEM = ("你是课程助教。只根据本次消息回答；缺少依据就说无法确定，不要猜。"
          "回答最后单独写一行“依据：”，说明用到了哪句对话、哪个工具结果。")
QUESTION = "我那次练习及格了吗？这周哪天复习？"
CALL_ID = "lookup_score_1"


def lookup_score(student_id: str) -> dict:
    """本课唯一的工具：按学号查最近一次练习的成绩。"""
    if student_id not in SCORES:
        raise ValueError(f"没有学号为 {student_id} 的记录。")
    return SCORES[student_id]


ORDER = ("system", "conversation", "tool_call", "tool_result", "question")
# 每组只拿掉一部分。工具调用和工具结果要一起拿掉；最后一组故意只拿掉结果。
VARIANTS = {
    "完整上下文": (),
    "去掉系统提示词": ("system",),
    "去掉之前的对话": ("conversation",),
    "去掉工具调用和结果": ("tool_call", "tool_result"),
    "只去掉工具结果": ("tool_result",),
}


def build_parts(values: Inputs, tool_result: dict) -> dict[str, dict]:
    """完整上下文的五条消息，按 ORDER 拼起来就是一次请求的 messages。"""
    call = {"id": CALL_ID, "type": "function", "function": {
        "name": "lookup_score", "arguments": json.dumps({"student_id": values.student_id})}}
    return {
        "system": {"role": "system", "content": SYSTEM},
        # 复习日只在这条之前的对话里出现。
        "conversation": {"role": "user", "content": f"这周我只有{values.free_day}晚上能复习。"
                                                    f"先帮我查一下 {values.student_id} 最近一次练习。"},
        # 运行器写的调用消息，id 与真实执行时用的 CALL_ID 相同。
        "tool_call": {"role": "assistant", "content": None, "tool_calls": [call]},
        # 分数只在这条工具结果里出现，内容是本次真实执行的返回值。
        "tool_result": {"role": "tool", "tool_call_id": CALL_ID,
                        "content": json.dumps(tool_result, ensure_ascii=False)},
        "question": {"role": "user", "content": QUESTION},
    }


def assemble(parts: dict[str, dict], removed: tuple[str, ...]) -> list[dict]:
    """按固定顺序拼消息，只跳过要拿掉的部分，其余消息一字不改。"""
    return [parts[key] for key in ORDER if key not in removed]


def validate_tool_history(messages: list[dict]) -> None:
    """协议检查：每个工具调用后面紧跟同一调用 id 的 tool 消息，不合法就抛 ValueError。"""
    outstanding: set[str] = set()  # 已经提出、还没等到工具结果的调用 id
    seen: set[str] = set()
    for message in messages:
        role = message.get("role")
        # 有调用还没等到结果时，下一条只能是 tool 消息。
        if outstanding and role != "tool":
            raise ValueError("工具调用后必须先提供对应的 tool 消息。")
        if role == "assistant":
            for call in message.get("tool_calls", []):
                call_id = call.get("id")
                # id 是配对的唯一依据，所以不能为空，也不能重复。
                if not isinstance(call_id, str) or not call_id or call_id in seen:
                    raise ValueError("工具调用 id 必须非空且唯一。")
                outstanding.add(call_id)
                seen.add(call_id)
        elif role == "tool":
            call_id = message.get("tool_call_id")
            # 工具结果只能回应一个还在等结果的调用。
            if call_id not in outstanding:
                raise ValueError("孤立或重复的 tool 消息。")
            outstanding.remove(call_id)
        elif role not in {"system", "user"}:
            raise ValueError("未知消息角色。")
    # 历史结束时还有调用没有结果，同样不合法。
    if outstanding:
        raise ValueError("工具调用缺少对应的 tool 消息。")


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    # 1. 真实执行一次工具。这次调用由运行器发起，不是模型提出的。
    result = context.call_tool("lookup_score", {"student_id": values.student_id},
                               {"lookup_score": lookup_score}, call_id=CALL_ID)
    if not result.get("ok"):
        raise RuntimeError("本地成绩查询失败。")
    parts = build_parts(values, result)
    _describe(context, parts)
    rows, sent = [], 0
    for name, removed in VARIANTS.items():
        # 2. 拼出这一组的上下文：比完整上下文只少 removed 里的部分。
        messages = assemble(parts, removed)
        # 3. 发送前做协议检查；不合法就不发请求，只记下被拦下的原因。
        try:
            validate_tool_history(messages)
        except ValueError as error:
            _record(context, name, removed, messages, rejected=str(error))
            rows.append(_row(name, messages, "拒绝：" + str(error), None, values))
            continue
        sent += 1
        _record(context, name, removed, messages, round_number=sent)
        # 4. 同一问题、temperature=0 发给模型；回答原样记下，不在这里判对错。
        answer = _send(context, messages, sent)
        rows.append(_row(name, messages, "通过", answer, values))
    _report(context, values, rows, sent)
    return (f"{sent} 组请求已发送，{len(VARIANTS) - sent} 组在发送前被协议检查拦下。"
            "请对照报告表格和每次 request 的 messages。")


def rejection_status(error: Exception) -> int | None:
    """服务商拒绝了这组消息时返回 HTTP 状态码；别的失败返回 None，由调用方照常抛出。"""
    status = getattr(error, "status_code", None)
    # 只有 4xx 是服务商对请求本身的判断。鉴权失败（401、403）、找不到模型（404）、
    # 超时（408）和限流（429）说的是配置或服务商当时的状态；5xx 是服务端故障。它们都不是这组消息的问题。
    if isinstance(status, int) and 400 <= status < 500 and status not in {401, 403, 404, 408, 429}:
        return status
    return None


def _send(context: RunContext, messages: list[dict], round_number: int) -> str | None:
    """发一次请求，返回回答文本；服务商拒绝时如实记录并返回 None，不重试、不改写请求。"""
    try:
        response = context.complete({"messages": messages, "temperature": 0}, round_number=round_number)
    except Exception as error:
        status = rejection_status(error)
        if status is None:
            raise  # 停止、网络失败、超时、限流、超出调用上限都不是服务商对这组消息的判断，照常报错。
        context.emit("lesson.provider_error", {"status": status, "error_type": type(error).__name__,
                                               "message": str(error)[:800]}, round_number)
        return None
    try:
        answer = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("模型响应缺少 choices[0].message。") from error
    if not isinstance(answer, str):
        raise ValueError("模型没有返回可比较的文本回答。")
    return answer


def _describe(context: RunContext, parts: dict[str, dict]) -> None:
    """平台：说明五条消息分别是谁写的，记为 lesson.context。"""
    context.emit("lesson.context", {
        "kind": "parts", "order": list(ORDER),
        "roles": {key: message["role"] for key, message in parts.items()},
        "detail": "五条消息都由运行器组装：system、两条 user 是本课写好的样本；带 tool_calls 的 assistant "
                  "消息由运行器写入，不是模型提出的；tool 消息的内容是本次真实执行 lookup_score 的返回值。"})


def _record(context: RunContext, name: str, removed: tuple[str, ...], messages: list[dict],
            round_number: int | None = None, rejected: str | None = None) -> None:
    """平台：记下这一组拿掉了什么、剩几条消息、协议检查的结论。"""
    data = {"variant": name, "removed": list(removed), "message_count": len(messages),
            "roles": [message["role"] for message in messages]}
    data.update({"rejected": rejected} if rejected else {"protocol": "通过"})
    context.emit("lesson.context", data, round_number)


def _row(name: str, messages: list[dict], protocol: str, answer: str | None, values: Inputs) -> list:
    """报告表格的一行。“提到……”三列是关键词初筛，要对照回答原文复核。"""
    if answer is None:
        outcome = "未发送" if protocol != "通过" else "服务商拒绝，见 lesson.provider_error"
        return [name, len(messages), protocol, outcome, "—", "—", "—"]
    score = str(SCORES[values.student_id]["score"])
    return [name, len(messages), protocol, answer, score in answer, values.free_day in answer, "依据" in answer]


def _report(context: RunContext, values: Inputs, rows: list[list], sent: int) -> None:
    """平台：组装并发布 lesson.report。"""
    blocked = [row for row in rows if str(row[2]).startswith("拒绝")]
    context.emit("lesson.report", {
        "title": "一次只拿掉一部分",
        "summary": "同一问题、同一模型，每组只比完整上下文少一部分。消息数和协议检查由程序算出；"
                   "“提到分数”“提到复习日”“写了依据行”是关键词初筛，要对照回答原文复核。",
        "checks": [
            {"label": "发出的每组请求都先通过了协议检查", "passed": all(row[2] == "通过" for row in rows if row not in blocked),
             "detail": "validate_tool_history 在每次 complete 之前运行。"},
            {"label": "只去掉工具结果的那组被拦下，没有发送", "passed": any(row[0] == "只去掉工具结果" for row in blocked),
             "detail": blocked[0][2] if blocked else "本次没有组被拦下。"},
        ],
        "metrics": [{"label": "模型调用数", "value": sent}, {"label": "被拦下的组", "value": len(blocked)},
                    {"label": "工具调用数", "value": 1}, {"label": "学号", "value": values.student_id},
                    {"label": "能复习的日子", "value": values.free_day},
                    {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": ["上下文", "消息数", "协议检查", "回答", "提到分数", "提到复习日", "写了依据行"],
                  "rows": rows},
    })
