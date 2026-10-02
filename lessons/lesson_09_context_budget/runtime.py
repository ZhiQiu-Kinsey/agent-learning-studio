"""上下文布局、压缩策略与拆开工具配对的真实模型对照；长度指标为字符数。"""
from typing import Literal
import json

from pydantic import Field

from course.execution import LessonInputs, RunContext
from course.runner import RunCancelled
from lessons.lesson_07_messages_context.runtime import validate_tool_history


class Inputs(LessonInputs):
    experiment: Literal["layouts", "compaction", "broken_pair"] = "layouts"
    source_key: Literal["lesson-07", "lesson-08"] = "lesson-07"
    noise_repeats: int = Field(default=8, ge=2, le=25)
    char_budget: int = Field(default=600, ge=400, le=4000)


INPUT_MODEL = Inputs
FACTS = {
    "lesson-07": "模型只看到本次请求里的消息；历史由应用程序重发。",
    "lesson-08": "应用 state 记录目标和证据；消息列表不会自动更新 state。",
}
SYSTEM = "只根据本次消息回答；指出证据来源与未完成步骤。缺少来源时明确说明，不要猜测。"
QUESTION = "根据已见资料，本课关键结论是什么？来源是哪一项？下一步还要做什么？"
# 探针问题只能靠最早那次工具结果回答；用它检查压缩后这条信息还在不在。
PROBE = "最早读取的那份资料来自哪一项？它的原话是什么？"
PROBE_SOURCE = "lesson-07"
PROBE_PHRASE = "历史由应用程序重发"
SUMMARY_SYSTEM = "你负责压缩对话记录，供后续继续工作。"
SUMMARY_INSTRUCTION = ("请把以上对话压缩成一段摘要，供后续继续工作使用。保留目标、约束、"
                       "每次工具调用的来源和结果原文、尚未完成的事项。不超过 200 字。")
CLEARED = {"cleared": True, "note": "旧工具结果已清理；需要时重新调用 lookup_lesson。"}


def lookup_lesson(source_key: str) -> dict:
    return {"source": source_key, "fact": FACTS[source_key]}


def _text(response: dict) -> str:
    try:
        answer = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("模型响应缺少文本回答。") from error
    if not isinstance(answer, str):
        raise ValueError("模型响应没有文本回答。")
    return answer


def _chars(messages: list[dict]) -> int:
    return len(json.dumps(messages, ensure_ascii=False, separators=(",", ":")))


def _visible(messages: list[dict], text: str) -> bool:
    return any(isinstance(message.get("content"), str) and text in message["content"]
               for message in messages)


def _usage(response: dict) -> str:
    usage = response.get("usage")
    return json.dumps(usage, ensure_ascii=False) if isinstance(usage, dict) else "未知"


def _pair(tool_id: str, source_key: str, tool_result: dict) -> list[dict]:
    """一次工具调用与它的回执：assistant 消息由课程程序组装，回执来自本次真实执行。"""
    call = {"role": "assistant", "content": None, "tool_calls": [{"id": tool_id, "type": "function", "function": {
        "name": "lookup_lesson", "arguments": json.dumps({"source_key": source_key})}}]}
    receipt = {"role": "tool", "tool_call_id": tool_id, "content": json.dumps(tool_result, ensure_ascii=False)}
    return [call, receipt]


def _noise(count: int, start: int = 1) -> list[dict]:
    noise = []
    for n in range(start, start + count):
        noise.extend([{"role": "user", "content": f"旁支讨论 {n}：请简短记下这条与本题无关的练习安排。"},
                      {"role": "assistant", "content": f"已记下旁支讨论 {n}。"}])
    return noise


def _checked_fact(tool_result: dict, source_key: str) -> str:
    observed = tool_result.get("result")
    if not isinstance(observed, dict) or observed.get("source") != source_key or not isinstance(observed.get("fact"), str):
        raise ValueError("实际工具结果缺少与请求匹配的来源和事实。")
    return observed["fact"]


def build_variants(source_key: str, noise_repeats: int, char_budget: int, tool_result: dict,
                   question: str = QUESTION):
    fact = _checked_fact(tool_result, source_key)
    system = {"role": "system", "content": SYSTEM}
    goal = {"role": "user", "content": "目标：回答课程结论并给出来源；约束：不能把无来源的猜测当事实。"}
    noise = _noise(noise_repeats)
    final_question = {"role": "user", "content": question}
    full = [system, goal, *_pair("lesson9_lookup", source_key, tool_result), *noise, final_question]
    window = [system, *noise[-2:], final_question]
    # 规则压缩只使用已读取的来源结果，不让模型在没有依据时生成摘要。
    summary = {"role": "user", "content": f"压缩的任务记录：目标=回答课程结论；约束=必须注明来源；证据来源={source_key}；证据={fact}；待办=回答用户当前问题。"}
    compressed = [system, summary, final_question]
    for candidate in (full, window, compressed):
        validate_tool_history(candidate)
    if _chars(compressed) > char_budget:
        raise ValueError(f"字符预算 {char_budget} 小于保留关键证据所需的 {_chars(compressed)} 字符。")
    return {"完整": full, "窗口": window, "保留证据压缩": compressed}


def build_history(noise_repeats: int, results: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """两次真实查阅之间夹着旁支对话；返回（较早部分，最近部分），都不含 system 与探针问题。"""
    for key, result in results.items():
        _checked_fact(result, key)
    older = [{"role": "user", "content": "目标：先后查阅第 7 课和第 8 课的资料，再回答问题；约束：不能把无来源的猜测当事实。"},
             *_pair("lesson9_lookup_1", "lesson-07", results["lesson-07"]), *_noise(noise_repeats)]
    recent = [*_pair("lesson9_lookup_2", "lesson-08", results["lesson-08"]), *_noise(1, noise_repeats + 1)]
    return older, recent


def clear_old_tool_results(messages: list[dict], keep_latest: int = 1) -> list[dict]:
    """把较早的 tool 回执换成占位说明；调用与回执仍成对出现，只是内容被清掉。"""
    tool_indexes = [index for index, message in enumerate(messages) if message.get("role") == "tool"]
    cleared = set(tool_indexes[:-keep_latest] if keep_latest else tool_indexes)
    return [{**message, "content": json.dumps(CLEARED, ensure_ascii=False)} if index in cleared else message
            for index, message in enumerate(messages)]


def probe_hit(answer: str) -> bool:
    return PROBE_SOURCE in answer and PROBE_PHRASE in answer


def naive_tail(messages: list[dict], keep: int) -> list[dict]:
    """按条数截断：保留 system 和最后 keep 条消息，不看工具调用与回执是否成对。"""
    return [messages[0], *messages[1:][-keep:]]


def pair_aware_tail(messages: list[dict], keep: int) -> list[dict]:
    """同样按条数截断，但切点落在配对中间时向前多保留那条 assistant 调用。"""
    tail = messages[1:][-keep:]
    while tail and tail[0].get("role") == "tool" and keep < len(messages) - 1:
        keep += 1
        tail = messages[1:][-keep:]
    return [messages[0], *tail]


def _status(error: Exception):
    status = getattr(error, "status_code", None)
    return status if isinstance(status, int) else None


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    if values.experiment == "compaction":
        return run_compaction(context, values)
    if values.experiment == "broken_pair":
        return run_broken_pair(context, values)
    return run_layouts(context, values)


def run_layouts(context: RunContext, values: Inputs) -> str:
    result = context.call_tool("lookup_lesson", {"source_key": values.source_key},
                               {"lookup_lesson": lookup_lesson}, call_id="lesson9_lookup")
    if not result.get("ok"):
        raise RuntimeError("本地资料读取失败。")
    observed = result["result"]
    question = context.question.strip() or QUESTION
    variants = build_variants(values.source_key, values.noise_repeats, values.char_budget, result, question)
    context.emit("lesson.context_variant", {"kind": "construction", "detail": "三组消息均由课程程序组装为受控样本；assistant 工具调用与旁支回复不是先前模型生成。工具回执来自本次实际 Python lookup_lesson。", "question": question})
    rows = []
    actual_usage = []
    for index, (name, messages) in enumerate(variants.items(), 1):
        context.check_cancelled()
        response = context.complete({"messages": messages, "temperature": 0}, round_number=index)
        answer = _text(response)
        usage = response.get("usage")
        actual_usage.append(usage if isinstance(usage, dict) else None)
        rows.append([name, _chars(messages), _visible(messages, values.source_key), _visible(messages, observed["fact"]), answer,
                     _usage(response)])
    context.emit("lesson.report", {
        "title": "三种上下文布局对照", "summary": "程序组装的受控上下文，工具回执来自实际 Python 读取；字符数不等于 token，usage 仅展示供应商响应实际返回值。",
        "checks": [
            {"label": "三种请求协议合法", "passed": True, "detail": "调用与回执成组保留或成组移除。"},
            {"label": "压缩保留来源和事实", "passed": _visible(variants["保留证据压缩"], observed["source"]) and _visible(variants["保留证据压缩"], observed["fact"]), "detail": "由本次实际工具回执构造。"},
            {"label": "压缩低于字符预算", "passed": rows[2][1] <= values.char_budget, "detail": f"预算 {values.char_budget} 字符。"},
        ],
        "metrics": [{"label": "模型请求数", "value": 3}, {"label": "本地字符预算", "value": values.char_budget},
                    {"label": "返回 usage 的请求数", "value": sum(value is not None for value in actual_usage)},
                    {"label": "实际追问", "value": question}],
        "table": {"columns": ["布局", "JSON 字符数", "有来源", "有事实", "模型回答", "供应商 usage"], "rows": rows},
    })
    return "三种实际模型响应已记录。请比较 request 的信息保留、response 的答案和供应商 usage。"


def run_compaction(context: RunContext, values: Inputs) -> str:
    results = {}
    for key in FACTS:
        result = context.call_tool("lookup_lesson", {"source_key": key}, {"lookup_lesson": lookup_lesson},
                                   call_id=f"lesson9_lookup_{len(results) + 1}")
        if not result.get("ok"):
            raise RuntimeError("本地资料读取失败。")
        results[key] = result
    older, recent = build_history(values.noise_repeats, results)
    system = {"role": "system", "content": SYSTEM}
    probe = {"role": "user", "content": PROBE}
    context.emit("lesson.context_variant", {"kind": "construction", "detail": "历史由课程程序组装：两次 lookup_lesson 的回执来自本次真实执行，assistant 调用消息与旁支回复不是模型生成的。摘要由当前模型生成。", "question": PROBE})
    # 摘要压缩：先让模型把较早部分写成摘要，再用摘要替换它。摘要本身也花一次请求。
    summary_body = {"messages": [{"role": "system", "content": SUMMARY_SYSTEM}, *older,
                                 {"role": "user", "content": SUMMARY_INSTRUCTION}], "temperature": 0}
    validate_tool_history(summary_body["messages"])
    summary_response = context.complete(summary_body, round_number=1)
    summary_text = _text(summary_response)
    layouts = {
        "不压缩": [system, *older, *recent, probe],
        "清理旧工具结果": clear_old_tool_results([system, *older, *recent, probe]),
        "摘要压缩": [system, {"role": "user", "content": "此前对话的摘要：" + summary_text}, *recent, probe],
    }
    rows, checks = [], []
    for index, (name, messages) in enumerate(layouts.items(), 2):
        context.check_cancelled()
        validate_tool_history(messages)
        context.emit("lesson.context_variant", {"kind": "layout", "name": name, "chars": _chars(messages),
                                                "fact_visible": _visible(messages, PROBE_PHRASE)}, index)
        response = context.complete({"messages": messages, "temperature": 0}, round_number=index)
        answer = _text(response)
        hit = probe_hit(answer)
        checks.append({"label": f"{name}：探针初筛", "passed": hit,
                       "detail": f"回答同时含 {PROBE_SOURCE} 与“{PROBE_PHRASE}”" if hit else "回答缺少最早资料的来源或原话；仍需人工复核"})
        rows.append([name, _chars(messages), _visible(messages, PROBE_PHRASE), answer, "命中" if hit else "未命中",
                     _usage(response)])
    context.emit("lesson.report", {
        "title": "三种压缩策略与探针问题",
        "summary": "探针只能靠最早那次工具结果回答。“上下文里还在”由本地字符串检查得出，“回答命中”是关键词初筛；字符数不等于 token。",
        "checks": checks,
        "metrics": [{"label": "模型请求数", "value": 4}, {"label": "摘要请求的 usage", "value": _usage(summary_response)},
                    {"label": "摘要原文", "value": summary_text}, {"label": "探针问题", "value": PROBE},
                    {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": ["策略", "JSON 字符数", "原话还在上下文里", "探针回答", "初筛", "供应商 usage"], "rows": rows},
    })
    return "摘要请求和三次探针请求已记录。请对照每种策略的上下文、探针回答与 usage。"


def run_broken_pair(context: RunContext, values: Inputs) -> str:
    result = context.call_tool("lookup_lesson", {"source_key": values.source_key},
                               {"lookup_lesson": lookup_lesson}, call_id="lesson9_lookup")
    if not result.get("ok"):
        raise RuntimeError("本地资料读取失败。")
    _checked_fact(result, values.source_key)
    question = context.question.strip() or QUESTION
    history = [{"role": "system", "content": SYSTEM},
               {"role": "user", "content": "目标：回答课程结论并给出来源；约束：不能把无来源的猜测当事实。"},
               *_noise(values.noise_repeats), *_pair("lesson9_lookup", values.source_key, result),
               {"role": "user", "content": question}]
    attempts = {"按条数截断（保留最后 2 条）": naive_tail(history, 2),
                "按配对截断（切点不拆开调用与回执）": pair_aware_tail(history, 2)}
    rows, checks = [], []
    for index, (name, messages) in enumerate(attempts.items(), 1):
        context.check_cancelled()
        try:
            validate_tool_history(messages)
            local = "合法"
        except ValueError as error:
            local = "拒绝：" + str(error)
        checks.append({"label": f"{name}：本地校验", "passed": local == "合法", "detail": local})
        try:
            response = context.complete({"messages": messages, "temperature": 0}, round_number=index)
        except RunCancelled:
            raise
        except Exception as error:  # 服务商拒绝请求时如实记录，不重试，也不改写请求。
            source = "offline_fixture" if context.mode == "offline" else "provider"
            status = _status(error)
            context.emit("lesson.provider_error", {
                "status": status, "error_type": type(error).__name__, "message": str(error)[:800],
                "source": source, "layout": name}, index)
            outcome = f"被拒绝（HTTP {status}）" if status else "请求失败（没有 HTTP 状态码，可能是网络问题）"
            if source == "offline_fixture":
                outcome += "，离线夹具模拟"
            rows.append([name, len(messages), local, outcome, "无"])
            continue
        rows.append([name, len(messages), local, "已接受", _text(response)])
    context.emit("lesson.report", {
        "title": "拆开工具调用与回执",
        "summary": "同一段历史按两种方式截断后原样发送。服务商是否拒绝以本次记录为准；离线模式下的拒绝由测试夹具模拟。",
        "checks": checks,
        "metrics": [{"label": "模型请求数", "value": len(attempts)}, {"label": "历史消息数", "value": len(history)},
                    {"label": "运行模式", "value": "离线测试（夹具）" if context.mode == "offline" else "真实模型"}],
        "table": {"columns": ["截断方式", "消息数", "本地校验", "服务商结果", "模型回答"], "rows": rows},
    })
    return "两种截断的请求都已原样发送，服务商的结果见报告与 lesson.provider_error 事件。"
