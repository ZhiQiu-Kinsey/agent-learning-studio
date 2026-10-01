"""三种合法消息布局的真实模型对照；长度指标为字符数。"""
import json

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_07_messages_context.runtime import validate_tool_history


class Inputs(LessonInputs):
    source_key: str = Field(default="lesson-07", pattern="^(lesson-07|lesson-08)$")
    noise_repeats: int = Field(default=8, ge=2, le=25)
    char_budget: int = Field(default=600, ge=400, le=4000)


INPUT_MODEL = Inputs
FACTS = {
    "lesson-07": "模型只看到本次请求里的消息；历史由应用程序重发。",
    "lesson-08": "应用 state 记录目标和证据；消息列表不会自动更新 state。",
}
SYSTEM = "只根据本次消息回答；指出证据来源与未完成步骤。缺少来源时明确说明，不要猜测。"
QUESTION = "根据已见资料，本课关键结论是什么？来源是哪一项？下一步还要做什么？"


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


def build_variants(source_key: str, noise_repeats: int, char_budget: int, tool_result: dict,
                   question: str = QUESTION):
    observed = tool_result.get("result")
    if not isinstance(observed, dict) or observed.get("source") != source_key or not isinstance(observed.get("fact"), str):
        raise ValueError("实际工具结果缺少与请求匹配的来源和事实。")
    fact = observed["fact"]
    tool_id = "lesson9_lookup"
    call = {"role": "assistant", "content": None, "tool_calls": [{"id": tool_id, "type": "function", "function": {"name": "lookup_lesson", "arguments": json.dumps({"source_key": source_key})}}]}
    receipt = {"role": "tool", "tool_call_id": tool_id, "content": json.dumps(tool_result, ensure_ascii=False)}
    system = {"role": "system", "content": SYSTEM}
    goal = {"role": "user", "content": "目标：回答课程结论并给出来源；约束：不能把无来源的猜测当事实。"}
    noise = []
    for n in range(noise_repeats):
        noise.extend([{"role": "user", "content": f"旁支讨论 {n + 1}：请简短记下这条与本题无关的练习安排。"},
                      {"role": "assistant", "content": f"已记下旁支讨论 {n + 1}。"}])
    final_question = {"role": "user", "content": question}
    full = [system, goal, call, receipt, *noise, final_question]
    window = [system, *noise[-2:], final_question]
    # 规则压缩只使用已读取的来源结果，不让模型在没有依据时生成摘要。
    summary = {"role": "user", "content": f"压缩的任务记录：目标=回答课程结论；约束=必须注明来源；证据来源={source_key}；证据={fact}；待办=回答用户当前问题。"}
    compressed = [system, summary, final_question]
    for candidate in (full, window, compressed):
        validate_tool_history(candidate)
    if _chars(compressed) > char_budget:
        raise ValueError(f"字符预算 {char_budget} 小于保留关键证据所需的 {_chars(compressed)} 字符。")
    return {"完整": full, "窗口": window, "保留证据压缩": compressed}


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
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
                     json.dumps(usage, ensure_ascii=False) if isinstance(usage, dict) else "未知"])
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
