"""Two paired model calls with one declared prompt variable."""
import json
import re
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext


TASKS = {
    "tool_description": ("用户问 19 加 23。需要精确算术时可调用登记的工具。", "计算工具。", "计算两个给定整数之和；a 是第一个加数，b 是第二个加数。缺少任一加数时不要调用。"),
    "flow_rule": ("用户问 19 加 23；回答应给数值，并说明依据。", "请给出答案。", "先识别输入中的两个数字，再计算并核对算术，最后用一句话给出数值与依据。"),
    "missing_input": ("用户只说：帮我计算一个加法，但没有给数字。", "请处理用户请求。", "若缺少任何加数，不要猜测；只询问缺少的数字。"),
}


class Inputs(LessonInputs):
    scenario: Literal["tool_description", "flow_rule", "missing_input"] = "tool_description"
    sample_label: str = Field(default="配对样本", min_length=1, max_length=40)


INPUT_MODEL = Inputs


def _content(response: dict) -> str:
    try:
        value = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("模型响应没有可读取的 message.content") from exc
    if not isinstance(value, str):
        raise ValueError("模型响应内容必须为文本")
    return value


def evaluate(scenario: str, answer: str) -> tuple[bool, str]:
    if scenario == "tool_description":
        return False, "工具预设应检查真实 tool_calls，而非回答文本"
    if scenario == "missing_input":
        passed = (bool(re.search(r"[?？]|请提供|请告知", answer))
                  and bool(re.search(r"加数|数字|输入", answer))
                  and not bool(re.search(r"\d", answer)))
        return passed, ("形式初筛命中：似在询问数字且未写数字；仍需人工复核" if passed
                        else "形式初筛未命中：没有明确询问数字，或写入了数字")
    passed = (bool(re.search(r"(?<!\d)42(?!\d)", answer))
              and not bool(re.search(r"不是\s*42|并非\s*42|不等于\s*42|≠\s*42", answer)))
    return passed, ("关键词初筛命中 42；是否正确表达计算仍需人工复核" if passed
                    else "关键词初筛未命中 42，或明确否定 42")


def evaluate_tool_response(response: dict) -> tuple[str, bool, str]:
    """Inspect a provider tool proposal without executing it."""
    message = response.get("choices", [{}])[0].get("message", {})
    calls = message.get("tool_calls") or []
    if len(calls) != 1:
        return _content(response) if isinstance(message.get("content"), str) else "无工具调用", False, "应有且仅有一个工具调用提议"
    function = calls[0].get("function", {})
    try:
        arguments = json.loads(function.get("arguments", ""))
    except (json.JSONDecodeError, TypeError):
        return str(function), False, "工具参数不是有效 JSON"
    passed = function.get("name") == "add_numbers" and arguments == {"a": 19, "b": 23}
    return json.dumps({"name": function.get("name"), "arguments": arguments}, ensure_ascii=False), passed, (
        "结构初筛命中：调用名称和参数匹配；仅为模型提议，未执行" if passed else "工具名称或参数与任务不符")


def run(context: RunContext) -> str:
    if context.max_model_calls < 2:
        raise RuntimeError("配对实验需要至少两次模型调用预算。")
    scenario = context.inputs["scenario"]
    task, baseline, variant = TASKS[scenario]
    rows = []
    for index, (label, variable) in enumerate((("基线", baseline), ("改写", variant)), 1):
        context.check_cancelled()
        system = "按用户任务选择工具或回答。" if scenario == "tool_description" else variable
        body = {"messages": [{"role": "system", "content": system},
                             {"role": "user", "content": task}], "temperature": 0}
        if scenario == "tool_description":
            body["tools"] = [{"type": "function", "function": {"name": "add_numbers", "description": variable,
                "parameters": {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                               "required": ["a", "b"], "additionalProperties": False}}}]
        response = context.complete(body, index)
        if scenario == "tool_description":
            answer, passed, detail = evaluate_tool_response(response)
        else:
            answer = _content(response)
            passed, detail = evaluate(scenario, answer)
        rows.append({"label": label, "prompt": variable, "answer": answer, "passed": passed, "detail": detail})
    context.emit("lesson.report", {
        "title": "单变量配对实验", "summary": "以下为结构或关键词初筛，保留两次原始输出供人工复核；单次配对不能推断普遍优劣。",
        "checks": [{"label": row["label"] + "初筛", "passed": row["passed"], "detail": row["detail"]} for row in rows],
        "metrics": [{"label": "相同模型", "value": context.model}, {"label": "模型调用数", "value": 2},
                    {"label": "调用预算", "value": context.max_model_calls}, {"label": "采样温度", "value": 0},
                    {"label": "样本标签", "value": context.inputs["sample_label"]},
                    {"label": "学习者备注", "value": context.question or "（空）"},
                    {"label": "唯一改动", "value": "function.description" if scenario == "tool_description" else "system 提示中的流程规则"}],
        "table": {"columns": ["版本", "变更变量的文本", "模型输出或工具提议", "初筛"],
                  "rows": [[row["label"], row["prompt"], row["answer"], "命中" if row["passed"] else "未命中"] for row in rows]},
    })
    return "配对记录已生成；请对照两次 request、response 和报告。此单次结果不能证明提示词普遍有效。"
