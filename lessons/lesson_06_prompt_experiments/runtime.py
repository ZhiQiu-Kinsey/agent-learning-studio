"""提示词与工具描述的配对实验：一次只改一处文本，其余条件固定，比较两次真实响应。

另有一个工具描述矩阵：同一个 add_numbers，描述分空白、良好、误导三种，各配两道题，
模型提出的合法调用交给真实代码执行，表格里并列“模型以为会发生的”和“代码实际返回的”。
"""
import json
import re
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext


class Inputs(LessonInputs):
    scenario: Literal["tool_description", "flow_rule", "missing_input", "tool_matrix"] = "tool_description"
    sample_label: str = Field(default="配对样本", min_length=1, max_length=40)


INPUT_MODEL = Inputs
# 配对场景：（用户任务，基线文本，改写文本）。同一场景里任务固定，只有后两项不同。
TASKS = {
    "tool_description": ("用户问 19 加 23。需要精确算术时可调用登记的工具。", "计算工具。", "计算两个给定整数之和；a 是第一个加数，b 是第二个加数。缺少任一加数时不要调用。"),
    "flow_rule": ("用户问 19 加 23；回答应给数值，并说明依据。", "请给出答案。", "先识别输入中的两个数字，再计算并核对算术，最后用一句话给出数值与依据。"),
    "missing_input": ("用户只说：帮我计算一个加法，但没有给数字。", "请处理用户请求。", "若缺少任何加数，不要猜测；只询问缺少的数字。"),
}
# 工具描述场景的 system 固定，变量放在 description 里；其他场景的变量就是 system 本身。
PAIR_SYSTEM = "按用户任务选择工具或回答。"

# 描述矩阵：同一个 add_numbers，三种描述各配两道题。None 表示不写 description 字段。
DESCRIPTIONS = {
    "空白": None,
    "良好": "计算两个整数之和并返回结果。a 是第一个加数，b 是第二个加数。只做加法；用户没有要求求和时不要调用。",
    # 误导描述故意和下面 add_numbers 的实现不一致：描述说拼接，代码做的是加法。
    "误导": "把两个整数按顺序拼接成一个新整数，例如 a=19、b=23 时返回 1923。",
}
PROBES = {
    "求和": ("19 加 23 等于多少？", {"a": 19, "b": 23}),
    # 拼接题用不上这个工具，期望是“不调用”：看模型会不会把工具用在它做不到的事上。
    "拼接": ("把 19 和 23 按顺序拼成一个四位数。", None),
}
MATRIX_SYSTEM = "按用户任务决定是否调用登记的工具；不需要工具时直接回答。"
PARAMETERS = {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
              "required": ["a", "b"], "additionalProperties": False}


def add_numbers(a: int, b: int) -> int:
    return a + b


def tool_spec(description: str | None) -> dict:
    """组装工具定义：参数结构每次都一样，description 是唯一的变量。"""
    function = {"name": "add_numbers", "parameters": PARAMETERS}
    # 空白组直接省略 description 字段，而不是传空字符串。
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
    """回答文本的形式初筛：命中只说明“像”，结论仍要人工读原文。"""
    if scenario == "tool_description":
        return False, "工具预设应检查真实 tool_calls，而非回答文本"
    if scenario == "missing_input":
        # 缺参场景三条同时满足才算命中：像在询问、提到了加数或数字、自己没写出任何数字。
        passed = (bool(re.search(r"[?？]|请提供|请告知", answer))
                  and bool(re.search(r"加数|数字|输入", answer))
                  and not bool(re.search(r"\d", answer)))
        return passed, ("形式初筛命中：似在询问数字且未写数字；仍需人工复核" if passed
                        else "形式初筛未命中：没有明确询问数字，或写入了数字")
    # 流程规则场景：要出现 42，同时排除“不是 42”这类否定表达，减少关键词误判。
    passed = (bool(re.search(r"(?<!\d)42(?!\d)", answer))
              and not bool(re.search(r"不是\s*42|并非\s*42|不等于\s*42|≠\s*42", answer)))
    return passed, ("关键词初筛命中 42；是否正确表达计算仍需人工复核" if passed
                    else "关键词初筛未命中 42，或明确否定 42")


def evaluate_tool_response(response: dict) -> tuple[str, bool, str]:
    """工具提议的结构初筛：只看名称和参数，不执行这次调用。"""
    message = response.get("choices", [{}])[0].get("message", {})
    calls = message.get("tool_calls") or []
    # 应有且仅有一个提议；没有提议时，把模型的文本回答留作记录。
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


def run_pair(context: RunContext) -> str:
    """配对实验：同一模型、同一任务、temperature=0，只改一处文本，各请求一次。"""
    # 配对缺一半就没法比较：预算不够两次就直接拒绝，不会只跑一半。
    if context.max_model_calls < 2:
        raise RuntimeError("配对实验需要至少两次模型调用预算。")
    scenario = context.inputs["scenario"]
    task, baseline, variant = TASKS[scenario]
    rows = []
    for index, (label, variable) in enumerate((("基线", baseline), ("改写", variant)), 1):
        # 1. 组装请求：两次请求只有 variable 这一处不同。
        system = PAIR_SYSTEM if scenario == "tool_description" else variable
        body = {"messages": [{"role": "system", "content": system},
                             {"role": "user", "content": task}], "temperature": 0}
        if scenario == "tool_description":
            body["tools"] = [tool_spec(variable)]
        # 2. 发请求并初筛：工具场景看调用提议，其他场景看回答文本。
        response = context.complete(body, index)
        if scenario == "tool_description":
            answer, passed, detail = evaluate_tool_response(response)
        else:
            answer = _content(response)
            passed, detail = evaluate(scenario, answer)
        # 3. 原文和初筛结论一起留下：初筛只是筛选，判断要回到原文。
        rows.append({"label": label, "prompt": variable, "answer": answer, "passed": passed, "detail": detail})
    _report_pair(context, scenario, rows)
    return "配对记录已生成；请对照两次 request、response 和报告。此单次结果不能证明提示词普遍有效。"


def proposed_call(response: dict) -> dict | None:
    """取出第一个调用提议 {name, arguments}；arguments 不是合法 JSON 时为 None。"""
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
    """判定一格：求和题要恰好提议 add_numbers(19, 23)，拼接题要不调用。"""
    if expected_arguments is None:
        return (proposal is None, "没有调用，符合预期" if proposal is None
                else "这道题不需要求和，却调用了 " + str(proposal["name"]))
    if proposal is None:
        return False, "需要求和，却没有调用工具"
    passed = proposal["name"] == "add_numbers" and proposal["arguments"] == expected_arguments
    return passed, "名称和参数都匹配" if passed else "名称或参数与题目不符"


def run_matrix(context: RunContext) -> str:
    """描述矩阵：三种描述 × 两道题，每格一次请求；合法的提议交给真实代码执行。"""
    cells = len(DESCRIPTIONS) * len(PROBES)
    # 六格缺一格就不成矩阵：预算不足时在第一次请求前拒绝。
    if context.max_model_calls < cells:
        raise RuntimeError(f"描述矩阵需要 {cells} 次模型调用预算。")
    checks, rows, index = [], [], 0
    for label, description in DESCRIPTIONS.items():
        row = [label + "（不写 description）" if description is None else label]
        for probe, (task, expected) in PROBES.items():
            index += 1
            # 1. 发请求：system、题目和 temperature 六次都相同，唯一的变量是 tool_spec(description)。
            body = {"messages": [{"role": "system", "content": MATRIX_SYSTEM}, {"role": "user", "content": task}],
                    "tools": [tool_spec(description)], "temperature": 0}
            response = context.complete(body, index)
            proposal = proposed_call(response)
            # 2. 判定：该调用时是否恰好调用，不该调用时是否没有调用。
            passed, detail = judge_cell(expected, proposal)
            checks.append({"label": f"{label} × {probe}", "passed": passed, "detail": detail})
            # 3. 执行合法的提议，表格里写代码真实返回的值。
            cell = _matrix_cell(context, response, proposal, index)
            row.append(cell + ("（符合预期）" if passed else "（不符合预期）"))
        rows.append(row)
    _report_matrix(context, checks, rows, index)
    return "描述矩阵已记录 6 次请求；被执行的提议附有真实返回值。单次结果不能证明某种描述普遍更好。"


def _matrix_cell(context: RunContext, response: dict, proposal: dict | None, index: int) -> str:
    """把一格写成表格文字；名称和参数合法的 add_numbers 提议交给真实代码执行一次。"""
    if proposal is None:
        text = response.get("choices", [{}])[0].get("message", {}).get("content")
        return "没有调用：" + (text if isinstance(text, str) else "（无文本）")
    cell = f"调用 {proposal['name']} {json.dumps(proposal['arguments'], ensure_ascii=False)}"
    # 白名单里只有这一个纯函数；名称不对或参数不是对象的提议只记录，不执行。
    if proposal["name"] == "add_numbers" and isinstance(proposal["arguments"], dict):
        result = context.call_tool("add_numbers", proposal["arguments"], {"add_numbers": add_numbers},
                                   round_number=index, call_id=f"matrix_{index}")
        # 写的是代码真实返回的值，不是描述承诺的值：误导描述在这里露出破绽。
        cell += f" → 实际返回 {result.get('result') if result.get('ok') else result.get('error')}"
    return cell


def run(context: RunContext) -> str:
    if context.inputs["scenario"] == "tool_matrix":
        return run_matrix(context)
    return run_pair(context)


def _report_pair(context: RunContext, scenario: str, rows: list[dict]) -> None:
    """发布配对实验的报告（lesson.report）：两次初筛、固定条件和原始输出。"""
    context.emit("lesson.report", {
        "title": "单变量配对实验", "summary": "以下为结构或关键词初筛，保留两次原始输出供人工复核；单次配对不能推断普遍优劣。",
        "checks": [{"label": row["label"] + "初筛", "passed": row["passed"], "detail": row["detail"]} for row in rows],
        "metrics": [{"label": "相同模型", "value": context.model}, {"label": "模型调用数", "value": 2},
                    {"label": "调用预算", "value": context.max_model_calls}, {"label": "采样温度", "value": 0},
                    {"label": "样本标签", "value": context.inputs["sample_label"]},
                    {"label": "学习者备注", "value": context.question or "（空）"},
                    {"label": "唯一改动", "value": "function.description" if scenario == "tool_description" else "系统提示词中的流程规则"}],
        "table": {"columns": ["版本", "变更变量的文本", "模型输出或工具提议", "初筛"],
                  "rows": [[row["label"], row["prompt"], row["answer"], "命中" if row["passed"] else "未命中"] for row in rows]},
    })


def _report_matrix(context: RunContext, checks: list[dict], rows: list[list], calls: int) -> None:
    """发布描述矩阵的报告（lesson.report）：六格判定与提议、真实返回值并列的表格。"""
    context.emit("lesson.report", {
        "title": "工具描述矩阵", "summary": "同一工具、同一模型、temperature=0，只改 description；每格一次请求，结果只代表这一次。",
        "checks": checks,
        "metrics": [{"label": "相同模型", "value": context.model}, {"label": "模型调用数", "value": calls},
                    {"label": "符合预期的格子", "value": sum(item["passed"] for item in checks)},
                    {"label": "样本标签", "value": context.inputs["sample_label"]},
                    {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": ["工具描述", *(f"{probe}：{task}" for probe, (task, _) in PROBES.items())],
                  "rows": rows},
    })
