"""同一个查询任务，分别用文本动作协议（带 / 不带 stop）和原生 tool_calls 完成。

文本协议的格式参考 Hugging Face Agents Course Unit 1（Apache-2.0）的 stop-and-parse 讲解，
提示词、解析器和实验由本项目重写。
"""
import json
import re
from typing import Literal

from course.execution import LessonInputs, RunContext


class Inputs(LessonInputs):
    protocol: Literal["text_stop", "text_no_stop", "native"] = "text_stop"
    student_id: Literal["s-1042", "s-2077"] = "s-1042"


INPUT_MODEL = Inputs

# 本地成绩表：数值没有规律，模型猜不到，编造的 Observation 和真实结果一对比就能看出来。
SCORES = {
    "s-1042": {"student_id": "s-1042", "score": 73, "attempts": 4, "updated": "2026-09-28"},
    "s-2077": {"student_id": "s-2077", "score": 58, "attempts": 2, "updated": "2026-09-30"},
}
PASS_LINE = 60


def lookup_quiz_score(student_id: str) -> dict:
    if student_id not in SCORES:
        raise ValueError(f"没有学号为 {student_id} 的记录。")
    return SCORES[student_id]


AVAILABLE_TOOLS = {"lookup_quiz_score": lookup_quiz_score}
TOOL_SPEC = {"type": "function", "function": {
    "name": "lookup_quiz_score", "description": "查询学生最近一次练习的得分、尝试次数和更新日期。",
    "parameters": {"type": "object", "properties": {"student_id": {"type": "string", "description": "学号，如 s-1042"}},
                   "required": ["student_id"], "additionalProperties": False}}}
TEXT_SYSTEM = """你是学习助教，可以使用下面的工具：
lookup_quiz_score：查询学生最近一次练习的得分、尝试次数和更新日期。输入 JSON：{"student_id": "学号"}

每次只写一步，严格按这个格式：
Thought: 你的思考
Action: 工具名
Action Input: JSON 参数

写完 Action Input 就停下，等系统给你 Observation。拿到 Observation 后，如果已经能回答，写：
Thought: 你的思考
Final Answer: 给用户的回答"""
TOOLS = [TOOL_SPEC]  # 网页“工具”面板展示的定义；原生组的请求也发送它
NATIVE_SYSTEM = "你是学习助教。需要学生成绩时调用 lookup_quiz_score，不要猜测数据。"
STOP = ["Observation:"]

ACTION = re.compile(r"Action:\s*([A-Za-z_][\w-]*)\s*\n\s*Action Input:\s*(.+)", re.S)
FINAL = re.compile(r"Final Answer:\s*(.+)", re.S)


def question_for(student_id: str) -> str:
    return f"学号 {student_id} 最近一次练习得了多少分？及格线是 {PASS_LINE} 分，他及格了吗？"


def parse_step(content: str) -> dict:
    """把一段模型文本解析成一步动作，不做任何猜测式修复。

    返回 kind：action / final / invalid。模型自己写出的 Observation 单独取出，不进入后续上下文。
    """
    # 先在 "Observation:" 处切开：前面是模型该写的部分，后面是它不该写、却可能写出来的部分。
    kept, marker, rest = content.partition("Observation:")
    fabricated = rest.strip() if marker else None
    naive_final = None
    if fabricated is not None:
        # 记下模型在自写结果之后给出的结论，报告里拿它和真实结果对比；这个结论不会被采信。
        found = FINAL.search(rest)
        naive_final = found.group(1).strip() if found else None
        fabricated = re.split(r"\n\s*(?:Thought:|Final Answer:|Action:)", fabricated, maxsplit=1)[0].strip()
    step = {"kept": kept.rstrip(), "fabricated": fabricated, "naive_final": naive_final}
    # 动作优先于 Final Answer：同一段里两样都写了，说明模型没等工具结果就下结论，先执行动作。
    action = ACTION.search(kept)
    if action:
        try:
            # raw_decode 只读开头的一个 JSON 值，允许后面还有换行或其他文字；这是解析器唯一的宽容之处。
            arguments, _ = json.JSONDecoder().raw_decode(action.group(2).strip())
        except json.JSONDecodeError as error:
            return {**step, "kind": "invalid", "action": action.group(1), "error": f"Action Input 不是合法 JSON：{error.msg}"}
        if not isinstance(arguments, dict):
            return {**step, "kind": "invalid", "action": action.group(1), "error": "Action Input 必须是 JSON 对象"}
        return {**step, "kind": "action", "action": action.group(1), "arguments": arguments}
    final = FINAL.search(kept)
    if final:
        return {**step, "kind": "final", "answer": final.group(1).strip()}
    return {**step, "kind": "invalid", "error": "既没有 Action，也没有 Final Answer"}


def _message(response: dict) -> tuple[dict, str | None]:
    choice = response["choices"][0]
    return choice.get("message", {}), choice.get("finish_reason")


def run_text(context: RunContext, protocol: str, student_id: str, max_steps: int) -> str:
    """文本协议循环：模型把动作写在文字里，程序解析、执行，再把真实结果写成 Observation 交回。"""
    messages = [{"role": "system", "content": TEXT_SYSTEM}, {"role": "user", "content": question_for(student_id)}]
    rows, parse_failures, fabrications = [], 0, []
    answer = None
    for step_number in range(1, max_steps + 1):
        # 1. 发请求：带 stop 的那组让服务商在模型写出 "Observation:" 时截断输出。
        body = {"messages": messages, "temperature": 0}
        if protocol == "text_stop":
            body["stop"] = STOP
        message, finish_reason = _message(context.complete(body, step_number))
        content = message.get("content") if isinstance(message.get("content"), str) else ""
        # 2. 解析：每次输出都记一条 lesson.parse，原文、解析结果和 finish_reason 一起留下。
        step = parse_step(content)
        context.emit("lesson.parse", {
            "protocol": protocol, "ok": step["kind"] != "invalid", "kind": step["kind"],
            "action": step.get("action"), "arguments": step.get("arguments"), "error": step.get("error"),
            "finish_reason": finish_reason, "model_wrote_observation": step["fabricated"] is not None,
            "raw": content}, step_number)
        rows.append([step_number, finish_reason or "未报告", step["kind"], step.get("error") or "—"])
        # 3. 判断是否结束：解析失败就停，不重试也不修复；拿到 Final Answer 也停。
        if step["kind"] == "invalid":
            parse_failures += 1
            break
        if step["kind"] == "final":
            answer = step["answer"]
            break
        # 4. 执行：工具由程序按解析结果调用，模型只是写下了想调用什么。
        result = context.call_tool(step["action"], step["arguments"], AVAILABLE_TOOLS, round_number=step_number,
                                   call_id=f"text_action_{step_number}")
        if step["fabricated"] is not None:
            fabrications.append(step["fabricated"])
            context.emit("lesson.fabricated_observation", {
                "model_wrote": step["fabricated"], "real_result": result,
                "same_score": result.get("ok") is True and str(result["result"]["score"]) in step["fabricated"],
                "naive_final_answer": step["naive_final"]}, step_number)
        # 5. 回传：只把 Observation 之前的文本还给模型，再接上真实结果；模型自写的部分丢掉。
        messages += [{"role": "assistant", "content": step["kept"]},
                     {"role": "user", "content": "Observation: " + json.dumps(result, ensure_ascii=False)}]
    # 用最终的上下文核对：任何一段模型自写的 Observation 都不应出现在之后发出的消息里。
    leaked = any(text in str(message.get("content")) for text in fabrications for message in messages)
    _report_text(context, protocol, student_id, rows, parse_failures, fabrications, answer, leaked)
    if answer is None:
        return "文本协议没有得到最终回答：" + ("解析失败，已停止。" if parse_failures else f"{max_steps} 步内没有 Final Answer。")
    return answer


def run_native(context: RunContext, student_id: str, max_steps: int) -> str:
    """原生工具调用：动作由服务商放在 tool_calls 字段里结构化返回，程序不解析自由文本。"""
    messages = [{"role": "system", "content": NATIVE_SYSTEM}, {"role": "user", "content": question_for(student_id)}]
    rows, answer = [], None
    for step_number in range(1, max_steps + 1):
        # 1. 发请求：工具定义放进 tools，不再要求模型遵守文本格式，也不需要 stop。
        response = context.complete({"messages": messages, "tools": TOOLS, "tool_choice": "auto",
                                     "temperature": 0}, step_number)
        message, finish_reason = _message(response)
        calls = message.get("tool_calls") or []
        rows.append([step_number, finish_reason or "未报告", f"{len(calls)} 个 tool_calls" if calls else "文本回答"])
        # 2. 判断是否结束：没有调用提议，content 就是最终回答。
        if not calls:
            answer = message.get("content") or ""
            break
        # 3. 执行并回传：先放回带调用提议的 assistant 消息，再按模型给的调用 id 逐个写回 tool 消息。
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
        for call in calls:
            result = context.execute_proposal(call, AVAILABLE_TOOLS)
            messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": json.dumps(result, ensure_ascii=False)})
    _report_native(context, student_id, rows, answer, max_steps)
    return answer if answer is not None else f"原生调用在 {max_steps} 步内没有得到最终回答。"


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    context.check_cancelled()
    if values.protocol == "native":
        return run_native(context, values.student_id, context.max_model_calls)
    return run_text(context, values.protocol, values.student_id, context.max_model_calls)


def _report_text(context: RunContext, protocol: str, student_id: str, rows: list[list], parse_failures: int,
                 fabrications: list[str], answer: str | None, leaked: bool) -> None:
    """发布文本协议的报告（lesson.report）：两项检查、解析统计和逐步表格。"""
    context.emit("lesson.report", {
        "title": "文本动作协议" + ("（带 stop）" if protocol == "text_stop" else "（不带 stop）"),
        "summary": "每次模型输出都经过解析并记成 lesson.parse；解析失败就停止，不猜测修复。工具由程序按解析结果执行，模型自己写的 Observation 不进入上下文。",
        "checks": [
            {"label": "模型自写的 Observation 没有进入后续上下文", "passed": not leaked,
             "detail": f"本次模型自己写了 {len(fabrications)} 段 Observation。"},
            {"label": "得到了 Final Answer", "passed": answer is not None,
             "detail": "达到步数上限或解析失败时没有最终回答。" if answer is None else "最终回答来自模型看到真实 Observation 之后的输出。"},
        ],
        "metrics": [{"label": "协议", "value": protocol}, {"label": "模型调用数", "value": len(rows)},
                    {"label": "解析失败", "value": parse_failures},
                    {"label": "模型自写 Observation", "value": len(fabrications)},
                    {"label": "学号", "value": student_id}, {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": ["步", "finish_reason", "解析结果", "错误"], "rows": rows},
    })


def _report_native(context: RunContext, student_id: str, rows: list[list], answer: str | None, max_steps: int) -> None:
    """发布原生调用的报告（lesson.report）。"""
    context.emit("lesson.report", {
        "title": "原生工具调用", "summary": "动作由服务商在 tool_calls 字段里结构化返回，程序不解析自由文本。",
        "checks": [{"label": "得到了最终回答", "passed": answer is not None,
                    "detail": "最终回答来自模型看到 tool 消息之后的输出。" if answer is not None else f"{max_steps} 步内没有结束。"}],
        "metrics": [{"label": "协议", "value": "native"}, {"label": "模型调用数", "value": len(rows)},
                    {"label": "学号", "value": student_id}, {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": ["步", "finish_reason", "模型输出"], "rows": rows},
    })
