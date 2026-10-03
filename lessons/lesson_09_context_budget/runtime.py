"""上下文预算与截取窗口：完整历史、按预算截取的窗口，以及按条数截断拆开工具配对的真实模型对照。

长度一律按本地 JSON 字符数计算，不等于 Token；Token 只看服务商在响应里报告的用量。
"""
from typing import Literal
import json

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_07_messages_context.runtime import rejection_status, validate_tool_history


class Inputs(LessonInputs):
    experiment: Literal["layouts", "broken_pair"] = "layouts"
    source_key: Literal["messages-context", "application-state"] = "messages-context"
    noise_repeats: int = Field(default=8, ge=2, le=25)
    char_budget: int = Field(default=600, ge=400, le=4000)


INPUT_MODEL = Inputs
# 本地资料：键是课程 slug，lookup_lesson 每次真实读取其中一条。
FACTS = {
    "messages-context": "模型只看到本次请求里的消息；历史由应用程序重发。",
    "application-state": "应用 state 记录目标和证据；消息列表不会自动更新 state。",
}
SYSTEM = "只根据本次消息回答；指出证据来源与未完成步骤。缺少来源时明确说明，不要猜测。"
GOAL = "目标：回答课程结论并给出来源；约束：不能把无来源的猜测当事实。"
QUESTION = "根据已见资料，本课关键结论是什么？来源是哪一项？下一步还要做什么？"


def lookup_lesson(source_key: str) -> dict:
    if source_key not in FACTS:
        raise ValueError(f"没有这份资料：{source_key}")
    return {"source": source_key, "fact": FACTS[source_key]}


# ---------- 三种截取写法 ----------

def message_groups(messages: list[dict]) -> list[list[dict]]:
    """把消息分组：tool 消息跟在它的 assistant 调用后面，算同一组。"""
    groups: list[list[dict]] = []
    for message in messages:
        if message.get("role") == "tool" and groups:
            groups[-1].append(message)
        else:
            groups.append([message])
    return groups


def fit_window(messages: list[dict], char_budget: int) -> list[dict]:
    """截取窗口：保留 system 和当前问题，再从最新的消息往回装，装不下就停。"""
    system, *history, question = messages
    # 1. system 和当前问题必须留下；连它们都装不下，就报错，不发残缺的请求。
    if message_chars([system, question]) > char_budget:
        raise ValueError(f"字符预算 {char_budget} 装不下 system 和当前问题。")
    kept: list[dict] = []
    # 2. 从最新的一组往回装；调用和工具结果同组，要么一起装进来，要么一起舍弃。
    for group in reversed(message_groups(history)):
        if message_chars([system, *group, *kept, question]) > char_budget:
            break  # 3. 窗口是连续的最近历史：这一组装不下，更早的也不再看
        kept = [*group, *kept]
    return [system, *kept, question]


def naive_tail(messages: list[dict], keep: int) -> list[dict]:
    """按条数截断：保留 system 和最后 keep 条消息，不看工具调用与工具结果是否成对。"""
    return [messages[0], *messages[1:][-keep:]]


def pair_aware_tail(messages: list[dict], keep: int) -> list[dict]:
    """同样按条数截断，但切点落在配对中间时，往前多保留那条 assistant 调用。"""
    tail = messages[1:][-keep:]
    while tail and tail[0].get("role") == "tool" and keep < len(messages) - 1:
        keep += 1
        tail = messages[1:][-keep:]
    return [messages[0], *tail]


# ---------- 布局对照：完整历史与截取窗口 ----------

def lookup_once(context: RunContext, source_key: str) -> dict:
    """运行器（不是模型）发起一次真实读取；结果与请求的来源不符就停下。"""
    result = context.call_tool("lookup_lesson", {"source_key": source_key},
                               {"lookup_lesson": lookup_lesson}, call_id="budget_lookup")
    checked_fact(result, source_key)
    return result


def build_layouts(source_key: str, noise_repeats: int, char_budget: int, tool_result: dict,
                  question: str = QUESTION) -> dict[str, list[dict]]:
    # 工具交互放在历史开头，旁支讨论跟在后面：窗口从最新往回装，最先舍弃的就是它。
    full = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": GOAL},
            *tool_pair("budget_lookup", source_key, tool_result), *side_talk(noise_repeats),
            {"role": "user", "content": question}]
    window = fit_window(full, char_budget)
    for messages in (full, window):
        validate_tool_history(messages)  # 两种布局发出前都要通过协议检查
    return {"完整历史": full, "截取窗口": window}


def run_layouts(context: RunContext, values: Inputs) -> str:
    # 1. 运行器真实读取一条资料，两种布局用的是同一次工具结果。
    result = lookup_once(context, values.source_key)
    question = context.question.strip() or QUESTION
    # 2. 组装完整历史，再按字符预算截取窗口。
    layouts = build_layouts(values.source_key, values.noise_repeats, values.char_budget, result, question)
    full, window = layouts["完整历史"], layouts["截取窗口"]
    context.emit("lesson.context_variant", {
        "kind": "window", "char_budget": values.char_budget, "full_messages": len(full),
        "kept_messages": len(window), "dropped_messages": len(full) - len(window),
        "tool_result_kept": any(message.get("role") == "tool" for message in window),
        "detail": "消息由运行器组装：assistant 工具调用与旁支回复不是模型生成的，工具结果来自本次真实的 lookup_lesson。"})
    # 3. 同一个追问，两种布局各发一次请求。
    rows = []
    for index, (name, messages) in enumerate(layouts.items(), 1):
        context.check_cancelled()
        response = context.complete({"messages": messages, "temperature": 0}, round_number=index)
        rows.append({"name": name, "messages": messages, "answer": answer_text(response),
                     "usage": usage_text(response), "has_usage": isinstance(response.get("usage"), dict)})
    context.emit("lesson.report", _layout_report(values, result["result"], question, rows))
    return "两种布局的真实请求与回答已记录。请对照 request 里的消息、response 里的回答和服务商用量。"


def _layout_report(values: Inputs, observed: dict, question: str, rows: list[dict]) -> dict:
    window = rows[1]["messages"]
    return {
        "title": "完整历史与截取窗口",
        "summary": "两种布局都由运行器组装，工具结果来自本次真实读取。字符数是本地 JSON 长度，不是 Token；用量只展示服务商实际返回的值。",
        "checks": [
            {"label": "两种布局都通过协议检查", "passed": True, "detail": "发出前对每个布局运行了协议检查。"},
            {"label": "截取窗口在字符预算内", "passed": message_chars(window) <= values.char_budget,
             "detail": f"预算 {values.char_budget} 字符，窗口 {message_chars(window)} 字符。"},
            {"label": "截取窗口保留了来源", "passed": has_text(window, observed["source"]),
             "detail": "在窗口实际发出的消息里查找来源名。"},
        ],
        "metrics": [{"label": "模型调用数", "value": len(rows)}, {"label": "字符预算", "value": values.char_budget},
                    {"label": "返回用量的请求数", "value": sum(row["has_usage"] for row in rows)},
                    {"label": "实际追问", "value": question}],
        "table": {"columns": ["布局", "消息数", "JSON 字符数", "在预算内", "有来源", "有事实", "模型回答", "服务商用量"],
                  "rows": [[row["name"], len(row["messages"]), message_chars(row["messages"]),
                            message_chars(row["messages"]) <= values.char_budget,
                            has_text(row["messages"], observed["source"]), has_text(row["messages"], observed["fact"]),
                            row["answer"], row["usage"]] for row in rows]},
    }


# ---------- 拆开配对：按条数截断后原样发送 ----------

def run_broken_pair(context: RunContext, values: Inputs) -> str:
    result = lookup_once(context, values.source_key)
    question = context.question.strip() or QUESTION
    # 1. 工具交互放在最后：只留最后 2 条时，切点正好落在调用和工具结果之间。
    history = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": GOAL},
               *side_talk(values.noise_repeats), *tool_pair("budget_lookup", values.source_key, result),
               {"role": "user", "content": question}]
    attempts = {"按条数截断（保留最后 2 条）": naive_tail(history, 2),
                "按配对截断（切点不拆开调用与工具结果）": pair_aware_tail(history, 2)}
    rows, checks = [], []
    for index, (name, messages) in enumerate(attempts.items(), 1):
        context.check_cancelled()
        # 2. 先跑本地协议检查并记下结论，但不拦截：请求原样发出，看服务商怎么回应。
        try:
            validate_tool_history(messages)
            local = "合法"
        except ValueError as error:
            local = "拒绝：" + str(error)
        checks.append({"label": f"{name}：本地协议检查", "passed": local == "合法", "detail": local})
        try:
            response = context.complete({"messages": messages, "temperature": 0}, round_number=index)
        except Exception as error:  # 3. 服务商拒绝时如实记录，不重试，也不改写请求
            status = rejection_status(error)
            if status is None:
                raise  # 停止、超时、限流、网络失败都不是服务商对这组消息的判断，照常报错
            source = "offline_fixture" if context.mode == "offline" else "provider"
            context.emit("lesson.provider_error", {
                "status": status, "error_type": type(error).__name__, "message": str(error)[:800],
                "source": source, "layout": name}, index)
            rows.append([name, len(messages), local, _refusal(status, source), "无"])
            continue
        rows.append([name, len(messages), local, "已接受", answer_text(response)])
    context.emit("lesson.report", _pair_report(context, history, checks, rows))
    return "两种截断的请求都已原样发送，服务商的回应见报告与 lesson.provider_error 事件。"


def _refusal(status: int, source: str) -> str:
    return f"被拒绝（HTTP {status}）" + ("，离线夹具模拟" if source == "offline_fixture" else "")


def _pair_report(context: RunContext, history: list[dict], checks: list[dict], rows: list) -> dict:
    return {
        "title": "拆开工具调用与工具结果",
        "summary": "同一段历史按两种方式截断后原样发送。服务商是否拒绝以本次记录为准；离线测试模式下的拒绝由测试夹具模拟。",
        "checks": checks,
        "metrics": [{"label": "模型调用数", "value": len(rows)}, {"label": "历史消息数", "value": len(history)},
                    {"label": "运行模式", "value": "离线测试（夹具）" if context.mode == "offline" else "真实模型"}],
        "table": {"columns": ["截断方式", "消息数", "本地协议检查", "服务商结果", "模型回答"], "rows": rows},
    }


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    if values.experiment == "broken_pair":
        return run_broken_pair(context, values)
    return run_layouts(context, values)


# ---------- 共用的小工具：上下文压缩一课也从这里导入 ----------

def message_chars(messages: list[dict]) -> int:
    """本课的长度单位：紧凑 JSON 的字符数。它只用来比较大小，不是 Token。"""
    return len(json.dumps(messages, ensure_ascii=False, separators=(",", ":")))


def has_text(messages: list[dict], text: str) -> bool:
    """本地字符串检查：这段文字是否原样出现在某条消息的 content 里。"""
    return any(isinstance(message.get("content"), str) and text in message["content"]
               for message in messages)


def answer_text(response: dict) -> str:
    """回答文本。模型没写文本、改为提出工具调用时，如实写明：这些请求不带工具，运行器不执行它们。"""
    try:
        message = response["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("模型响应缺少 choices[0].message。") from error
    content = message.get("content")
    if content is not None and not isinstance(content, str):
        raise ValueError("模型响应的 content 不是文本。")
    calls = [call.get("function", {}).get("name", "未知") for call in message.get("tool_calls") or []]
    if calls and not (content or "").strip():
        return f"（没有文本回答：模型提出调用 {'、'.join(calls)}，运行器没有执行）"
    return content or ""


def usage_text(response: dict) -> str:
    """服务商报告的用量原样展示；没报告就写“未报告”，不记成零。"""
    usage = response.get("usage")
    return json.dumps(usage, ensure_ascii=False) if isinstance(usage, dict) else "未报告"


def tool_pair(call_id: str, source_key: str, tool_result: dict) -> list[dict]:
    """一次工具调用与它的工具结果：assistant 消息由运行器组装，工具结果来自本次真实执行。"""
    call = {"role": "assistant", "content": None, "tool_calls": [{"id": call_id, "type": "function", "function": {
        "name": "lookup_lesson", "arguments": json.dumps({"source_key": source_key})}}]}
    result = {"role": "tool", "tool_call_id": call_id, "content": json.dumps(tool_result, ensure_ascii=False)}
    return [call, result]


def side_talk(count: int, start: int = 1) -> list[dict]:
    """旁支讨论：与本题无关的填充对话，只用来拉长历史。"""
    talk = []
    for n in range(start, start + count):
        talk += [{"role": "user", "content": f"旁支讨论 {n}：请简短记下这条与本题无关的练习安排。"},
                 {"role": "assistant", "content": f"已记下旁支讨论 {n}。"}]
    return talk


def checked_fact(tool_result: dict, source_key: str) -> str:
    """工具结果必须成功，且来源与请求一致；否则不拿它去组装上下文。"""
    observed = tool_result.get("result")
    if not isinstance(observed, dict) or observed.get("source") != source_key or not isinstance(observed.get("fact"), str):
        raise ValueError("实际工具结果缺少与请求匹配的来源和事实。")
    return observed["fact"]
