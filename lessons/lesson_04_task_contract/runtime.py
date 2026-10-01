"""A local acceptance harness: ending execution is separate from passing a task."""
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext


class Inputs(LessonInputs):
    scenario: Literal["normal", "missing_evidence", "wrong_result"] = "normal"
    claim: str = Field(default="已完成学习助教的加法任务", min_length=1, max_length=120)


INPUT_MODEL = Inputs
TASK_CARD = {
    "goal": "依据本地计算结果回答 19 + 23",
    "input_scope": "两个给定整数 19 和 23；不读取外部文件或网页",
    "output": "给出数值 42 并说明来自本次计算",
    "evidence": "计算工具成功返回且结果等于 42",
    "failure": "工具失败、证据缺失或数值不符时明确标为未通过",
    "stop": "完成一次计算和验收后停止，不再追加调用",
}


def add_numbers(a: int, b: int) -> int:
    return a + b


def run(context: RunContext) -> str:
    context.check_cancelled()
    scenario = context.inputs["scenario"]
    context.emit("lesson.task_card", TASK_CARD)
    # A fixed fault injection changes the evidence, not the acceptance rule.
    result = None if scenario == "missing_evidence" else context.call_tool(
        "add_numbers", {"a": 19, "b": 22 if scenario == "wrong_result" else 23},
        {"add_numbers": add_numbers},
    )
    checks = [
        {"label": "执行过程已结束", "passed": True, "detail": "本地流程运行到验收阶段；这不代表任务成功。"},
        {"label": "存在成功的工具证据", "passed": bool(result and result.get("ok")),
         "detail": "未执行或失败" if not result or not result.get("ok") else "已收到真实 Python 工具结果"},
        {"label": "计算值满足任务卡", "passed": bool(result and result.get("ok") and result.get("result") == 42),
         "detail": "期望 42；实际 " + (str(result.get("result")) if result else "无证据")},
    ]
    accepted = all(item["passed"] for item in checks[1:])
    context.emit("lesson.report", {
        "title": "任务卡独立验收", "summary": "验收通过" if accepted else "运行结束，但验收未通过",
        "checks": checks,
        "metrics": [{"label": "工具调用数", "value": 0 if result is None else 1},
                    {"label": "场景", "value": scenario},
                    {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": ["用户声称", "验收结论"], "rows": [[context.inputs["claim"], "通过" if accepted else "未通过"]]},
    })
    return "验收通过：19 + 23 = 42，依据本次工具结果。" if accepted else "流程已结束，但任务没有通过独立验收；请检查证据。"
