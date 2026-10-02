"""Paired model calls with one declared prompt variable, plus a tool-description matrix."""
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


# Description matrix: the same add_numbers schema with three descriptions, each asked two probes.
# None means the description key is omitted (blank). The misleading text contradicts the code on purpose.
DESCRIPTIONS = {
    "空白": None,
    "良好": "计算两个整数之和并返回结果。a 是第一个加数，b 是第二个加数。只做加法；用户没有要求求和时不要调用。",
    "误导": "把两个整数按顺序拼接成一个新整数，例如 a=19、b=23 时返回 1923。",
}
PROBES = {
    "求和": ("19 加 23 等于多少？", {"a": 19, "b": 23}),
    "拼接": ("把 19 和 23 按顺序拼成一个四位数。", None),
}
MATRIX_SYSTEM = "按用户任务决定是否调用登记的工具；不需要工具时直接回答。"
PARAMETERS = {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
              "required": ["a", "b"], "additionalProperties": False}


class Inputs(LessonInputs):
    scenario: Literal["tool_description", "flow_rule", "missing_input", "tool_matrix"] = "tool_description"
    sample_label: str = Field(default="配对样本", min_length=1, max_length=40)


INPUT_MODEL = Inputs


def add_numbers(a: int, b: int) -> int:
    return a + b


def tool_spec(description: str | None) -> dict:
    function = {"name": "add_numbers", "parameters": PARAMETERS}
    if description is not None:
        function["description"] = description
    return {"type": "function", "function": function}


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
    if context.inputs["scenario"] == "tool_matrix":
        return run_matrix(context)
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
            body["tools"] = [tool_spec(variable)]
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


def proposed_call(response: dict) -> dict | None:
    """Return the first proposed tool call as {name, arguments}; arguments is None if not valid JSON."""
    message = response.get("choices", [{}])[0].get("message", {})
    calls = message.get("tool_calls") or []
    if not calls:
        return None
    function = calls[0].get("function", {})
    try:
        arguments = json.loads(function.get("arguments", ""))
    except (json.JSONDecodeError, TypeError):
        arguments = None
    return {"name": function.get("name"), "arguments": arguments}


def judge_cell(expected_arguments: dict | None, proposal: dict | None) -> tuple[bool, str]:
    """Compare one proposal with what the probe needs: an exact add_numbers call, or no call at all."""
    if expected_arguments is None:
        return (proposal is None, "没有调用，符合预期" if proposal is None
                else "这道题不需要求和，却调用了 " + str(proposal["name"]))
    if proposal is None:
        return False, "需要求和，却没有调用工具"
    passed = proposal["name"] == "add_numbers" and proposal["arguments"] == expected_arguments
    return passed, "名称和参数都匹配" if passed else "名称或参数与题目不符"


def run_matrix(context: RunContext) -> str:
    cells = len(DESCRIPTIONS) * len(PROBES)
    if context.max_model_calls < cells:
        raise RuntimeError(f"描述矩阵需要 {cells} 次模型调用预算。")
    checks, rows = [], []
    index = 0
    for label, description in DESCRIPTIONS.items():
        row = [label + "（不写 description）" if description is None else label]
        for probe, (task, expected) in PROBES.items():
            index += 1
            context.check_cancelled()
            body = {"messages": [{"role": "system", "content": MATRIX_SYSTEM}, {"role": "user", "content": task}],
                    "tools": [tool_spec(description)], "temperature": 0}
            response = context.complete(body, index)
            proposal = proposed_call(response)
            passed, detail = judge_cell(expected, proposal)
            if proposal is None:
                text = response.get("choices", [{}])[0].get("message", {}).get("content")
                cell = "没有调用：" + (text if isinstance(text, str) else "（无文本）")
            else:
                cell = f"调用 {proposal['name']} {json.dumps(proposal['arguments'], ensure_ascii=False)}"
                if proposal["name"] == "add_numbers" and isinstance(proposal["arguments"], dict):
                    # Run the proposal once so the table shows what the real code returns, not what the
                    # description promised. Only the registered pure function can run.
                    result = context.call_tool("add_numbers", proposal["arguments"], {"add_numbers": add_numbers},
                                               round_number=index, call_id=f"lesson6_matrix_{index}")
                    cell += f" → 实际返回 {result.get('result') if result.get('ok') else result.get('error')}"
            checks.append({"label": f"{label} × {probe}", "passed": passed, "detail": detail})
            row.append(cell + ("（符合预期）" if passed else "（不符合预期）"))
        rows.append(row)
    context.emit("lesson.report", {
        "title": "工具描述矩阵", "summary": "同一工具、同一模型、temperature=0，只改 description；每格一次请求，结果只代表这一次。",
        "checks": checks,
        "metrics": [{"label": "相同模型", "value": context.model}, {"label": "模型调用数", "value": index},
                    {"label": "符合预期的格子", "value": sum(item["passed"] for item in checks)},
                    {"label": "样本标签", "value": context.inputs["sample_label"]},
                    {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": ["工具描述", *(f"{probe}：{task}" for probe, (task, _) in PROBES.items())],
                  "rows": rows},
    })
    return "描述矩阵已记录 6 次请求；被执行的提议附有真实返回值。单次结果不能证明某种描述普遍更好。"
