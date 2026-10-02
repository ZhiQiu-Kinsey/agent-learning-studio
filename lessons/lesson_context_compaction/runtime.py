"""上下文压缩：规则压缩、清理旧工具结果、模型摘要，用同一个探针问题检查最早的工具结果还在不在。

字符数、本地字符串检查、组装工具配对与旁支讨论、资料读取这些小工具，与“上下文预算”一课共用。
"""
import json
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_07_messages_context.runtime import validate_tool_history
from lessons.lesson_09_context_budget.runtime import (
    answer_text, checked_fact, has_text, lookup_lesson, message_chars, side_talk, tool_pair, usage_text)


class Inputs(LessonInputs):
    noise_repeats: int = Field(default=8, ge=2, le=25)
    char_budget: int = Field(default=300, ge=100, le=2000)
    summary_style: Literal["keep_sources", "brief"] = "keep_sources"


INPUT_MODEL = Inputs
SOURCES = ("messages-context", "application-state")  # 先后读取的两份资料
GOAL = "目标：先后查阅“消息与上下文”和“应用状态”两份资料，再回答问题；约束：不能把无来源的猜测当事实。"
# 探针问题只能靠最早那次工具结果回答：压缩之后还答得出，才说明这条信息没丢。
PROBE = "最早读取的那份资料来自哪一项？它的原话是什么？"
PROBE_SOURCES = ("messages-context", "消息与上下文")  # 那一项的键或名称，答出任一个都算
PROBE_PHRASE = "历史由应用程序重发"
# 这些请求都不带工具定义，提示词说清楚只回答、不调用工具。
SYSTEM = "只根据本次消息回答，不调用工具。缺少依据时明确说明，不要猜测。"
SUMMARY_SYSTEM = "你负责把对话压缩成摘要，供后续继续工作。只写摘要，不调用工具，也不继续执行任务。"
SUMMARY_INSTRUCTIONS = {
    "keep_sources": "请把以上对话压缩成一段摘要，供后续继续工作使用。保留目标、约束、每次工具调用的来源和结果原文、尚未完成的事项。不超过 200 字。",
    "brief": "请用一两句话概括以上对话。",
}
CLEARED = {"cleared": True, "note": "旧工具结果已清理，原内容不在上下文里。"}


def build_history(noise_repeats: int, results: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """两次真实读取之间夹着旁支讨论；返回（较早部分，最近部分），都不含 system 与探针问题。"""
    first, second = SOURCES
    for key in SOURCES:
        checked_fact(results[key], key)  # 读取失败或来源不符就停下，不拿错误结果去压缩
    older = [{"role": "user", "content": GOAL}, *tool_pair("compaction_lookup_1", first, results[first]),
             *side_talk(noise_repeats)]
    recent = [*tool_pair("compaction_lookup_2", second, results[second]), *side_talk(1, noise_repeats + 1)]
    return older, recent


def rule_record(reads: list[tuple[str, dict]], char_budget: int) -> dict:
    """规则压缩：程序按固定字段拼一条记录，不调用模型。reads 是较早部分里按先后排好的读取。"""
    sources = "；".join(f"第 {number} 次读取 {key}" for number, (key, _) in enumerate(reads, 1))
    facts = "；".join(checked_fact(result, key) for key, result in reads)  # 事实只取自真实的工具结果
    record = {"role": "user", "content": (
        "此前对话的压缩记录（程序按规则生成）\n目标：先后查阅两份资料，再回答问题\n"
        f"约束：不能把无来源的猜测当事实\n来源：{sources}\n事实：{facts}\n待办：继续回答用户的问题")}
    # 装不下关键证据就报错，不悄悄删掉来源或事实。
    if message_chars([record]) > char_budget:
        raise ValueError(f"字符预算 {char_budget} 小于保留关键证据所需的 {message_chars([record])} 字符。")
    return record


def clear_old_tool_results(messages: list[dict], keep_latest: int = 1) -> list[dict]:
    """清理旧工具结果：较早的 tool 消息留在原位，内容换成“已清理”的说明。"""
    tool_indexes = [index for index, message in enumerate(messages) if message.get("role") == "tool"]
    cleared = set(tool_indexes[:-keep_latest] if keep_latest else tool_indexes)
    # 只换内容，不删消息：调用与工具结果仍然成对，协议检查照样通过。
    return [{**message, "content": json.dumps(CLEARED, ensure_ascii=False)} if index in cleared else message
            for index, message in enumerate(messages)]


def summary_body(older: list[dict], style: str) -> dict:
    """摘要压缩的那次额外请求：较早的历史原样交给模型，再附一条压缩指令。"""
    messages = [{"role": "system", "content": SUMMARY_SYSTEM}, *older,
                {"role": "user", "content": SUMMARY_INSTRUCTIONS[style]}]
    validate_tool_history(messages)
    return {"messages": messages, "temperature": 0}


def probe_hit(answer: str) -> bool:
    """关键词初筛：来源（键或名称）和原话都出现才算答出；命中不等于语义正确，要回到原文核对。"""
    return any(name in answer for name in PROBE_SOURCES) and PROBE_PHRASE in answer


def ask_probe(context: RunContext, name: str, messages: list[dict], round_number: int) -> dict:
    """用一组上下文问一次探针问题；“原话在不在上下文里”和“回答有没有答出”分开记。"""
    context.check_cancelled()
    validate_tool_history(messages)  # 压缩不能破坏协议：每组发出前都检查
    context.emit("lesson.compaction", {"kind": "layout", "name": name, "messages": len(messages),
                                       "chars": message_chars(messages),
                                       "phrase_in_context": has_text(messages, PROBE_PHRASE)}, round_number)
    response = context.complete({"messages": messages, "temperature": 0}, round_number=round_number)
    answer = answer_text(response)
    return {"name": name, "messages": messages, "answer": answer, "usage": usage_text(response)}


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    # 1. 运行器先后真实读取两份资料，组装出“较早部分 + 最近部分”的历史。
    results = {key: context.call_tool("lookup_lesson", {"source_key": key}, {"lookup_lesson": lookup_lesson},
                                      call_id=f"compaction_lookup_{number}")
               for number, key in enumerate(SOURCES, 1)}
    older, recent = build_history(values.noise_repeats, results)
    system, probe = {"role": "system", "content": SYSTEM}, {"role": "user", "content": PROBE}
    # 2. 对照组：不压缩，带上全部历史。后面每种压缩只替换较早部分，最近部分原样保留。
    rows = [ask_probe(context, "不压缩", [system, *older, *recent, probe], 1)]
    # 3. 规则压缩：较早部分换成一条记录；装不下关键证据就拒绝，这一组不发请求。
    try:
        record, refused = rule_record([(SOURCES[0], results[SOURCES[0]])], values.char_budget), None
    except ValueError as error:
        record, refused = None, str(error)
    if record:
        rows.append(ask_probe(context, "规则压缩", [system, record, *recent, probe], 2))
    else:
        context.emit("lesson.compaction", {"kind": "refused", "name": "规则压缩", "reason": refused}, 2)
    # 4. 清理旧工具结果：消息条数不变，较早那次工具结果的内容换成说明。
    rows.append(ask_probe(context, "清理旧工具结果", clear_old_tool_results([system, *older, *recent, probe]), 3))
    # 5. 摘要压缩：先多发一次请求拿到摘要，再用摘要替换较早部分。
    summary_response = context.complete(summary_body(older, values.summary_style), round_number=4)
    summary = {"role": "user", "content": "此前对话的摘要：" + answer_text(summary_response)}
    rows.append(ask_probe(context, "摘要压缩", [system, summary, *recent, probe], 5))
    context.emit("lesson.report", _report(context, values, rows, refused, summary_response))
    return "摘要请求和各组的探针请求都已记录。请对照每组的上下文、探针回答和服务商用量。"


def _report(context: RunContext, values: Inputs, rows: list[dict], refused: str | None,
            summary_response: dict) -> dict:
    checks = [{"label": "各组上下文都通过协议检查", "passed": True, "detail": "发出前对每一组运行了协议检查。"},
              {"label": "规则压缩装下了关键证据", "passed": refused is None,
               "detail": refused or f"记录不超过字符预算 {values.char_budget}。"}]
    checks += [{"label": f"{row['name']}：探针初筛", "passed": probe_hit(row["answer"]),
                "detail": "回答同时含来源名与原话" if probe_hit(row["answer"]) else "回答缺少来源名或原话；仍需读原文复核"}
               for row in rows]
    return {
        "title": "三种压缩与同一个探针问题",
        "summary": "历史由运行器组装，两次工具结果来自本次真实读取，摘要由当前模型生成。“原话还在上下文里”是本地字符串检查，“答出来源与原话”是关键词初筛，两者分开看；字符数不是 Token。",
        "checks": checks,
        "metrics": [{"label": "模型调用数", "value": len(rows) + 1},
                    {"label": "摘要请求的用量", "value": usage_text(summary_response)},
                    {"label": "摘要指令", "value": values.summary_style},
                    {"label": "摘要原文", "value": answer_text(summary_response)},
                    {"label": "探针问题", "value": PROBE}, {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": ["做法", "消息数", "JSON 字符数", "原话还在上下文里", "探针回答", "答出来源与原话（初筛）", "服务商用量"],
                  "rows": [[row["name"], len(row["messages"]), message_chars(row["messages"]),
                            has_text(row["messages"], PROBE_PHRASE), row["answer"],
                            "命中" if probe_hit(row["answer"]) else "未命中", row["usage"]] for row in rows]},
    }
