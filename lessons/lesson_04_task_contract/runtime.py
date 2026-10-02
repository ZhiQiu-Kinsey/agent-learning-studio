"""任务卡与独立验收：执行者交来的完成声明，要拿本次记录的工具证据去核对。

本课不调用模型。执行者是运行器里的一段固定脚本，各种故障也由运行器注入；
验收规则对所有场景都一样，变的只有证据。
"""
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext


class Inputs(LessonInputs):
    scenario: Literal["normal", "missing_evidence", "wrong_result", "claim_mismatch", "goal_loop"] = "normal"
    claim: str = Field(default="已完成学习助教的加法任务", min_length=1, max_length=120)
    max_attempts: int = Field(default=3, ge=1, le=3)


INPUT_MODEL = Inputs
# 任务卡在执行前写好；验收只认这张卡，执行者事后怎么描述都改变不了它。
TASK_CARD = {
    "goal": "依据本地计算结果回答 19 + 23",
    "input_scope": "两个给定整数 19 和 23；不读取外部文件或网页",
    "output": "给出数值 42 并说明来自本次计算",
    "evidence": "计算工具成功返回且结果等于 42",
    "failure": "工具失败、证据缺失或数值不符时明确标为未通过",
    "stop": "完成一次计算和验收后停止，不再追加调用",
}
EXPECTED = 42


def add_numbers(a: int, b: int) -> int:
    return a + b


def verify(claim: dict, evidence: dict[str, dict]) -> list[dict]:
    """拿完成声明去核对本次记录的工具结果；声明里的答案只用来比对，不能单独作为依据。"""
    # 只顺着 evidence_ref 找证据：引用不到本次记录的调用，就等于没有证据。
    record = evidence.get(claim.get("evidence_ref") or "")
    result = record["result"] if record else None
    ok = bool(result and result.get("ok"))
    value = result.get("result") if ok else None
    return [
        {"label": "执行过程已结束", "passed": True, "detail": "本地流程运行到验收阶段；这不代表任务成功。"},
        {"label": "声明引用了本次的工具证据", "passed": record is not None,
         "detail": "evidence_ref 指向本次运行中的 tool_result" if record else "声明没有指向任何本次记录的工具结果"},
        {"label": "工具成功返回", "passed": ok, "detail": "ok 为真" if ok else "未执行或失败"},
        {"label": "证据中的值满足任务卡", "passed": value == EXPECTED,
         "detail": f"期望 {EXPECTED}；证据中为 {value if ok else '无'}"},
        # 声明与证据要单独比一次：引用对了、证据也对，声明里的数字仍可能是另写的。
        {"label": "声明与证据一致", "passed": ok and claim.get("answer") == value,
         "detail": f"声明写 {claim.get('answer')}；证据中为 {value if ok else '无'}"},
    ]


def accepted(checks: list[dict]) -> bool:
    # 跳过第一项“执行过程已结束”：流程跑完和任务通过是两件事。
    return all(item["passed"] for item in checks[1:])


def _attempt(context: RunContext, scenario: str, attempt: int, evidence: dict[str, dict]) -> dict:
    """执行者的一次尝试：固定脚本代替 Agent 交声明，故障由运行器注入，不是模型犯的错。"""
    if scenario == "missing_evidence":
        # 只交声明、不调用工具：答案恰好是对的，但没有任何可核对的东西。
        return {"status": "done", "answer": EXPECTED, "evidence_ref": None, "summary": context.inputs["claim"]}
    # goal_loop 只让第 1 次出错，重试时按任务卡重做；真实的目标循环要由模型读验收原因再改。
    wrong = scenario in ("wrong_result", "claim_mismatch") or (scenario == "goal_loop" and attempt == 1)
    call_id = f"task_add_{attempt}"
    result = context.call_tool("add_numbers", {"a": 19, "b": 22 if wrong else 23},
                               {"add_numbers": add_numbers}, round_number=attempt, call_id=call_id)
    evidence[call_id] = {"result": result}
    # claim_mismatch：执行者不管工具返回什么都报 42，模拟“只报好消息”的声明。
    answer = EXPECTED if scenario == "claim_mismatch" else result.get("result")
    return {"status": "done", "answer": answer, "evidence_ref": call_id, "summary": context.inputs["claim"]}


def run(context: RunContext) -> str:
    """按任务卡执行并验收；goal_loop 未通过时带着原因重试，通过或到达上限就停。"""
    scenario = context.inputs["scenario"]
    # 只有目标循环允许多次尝试；其他场景只做一次，每种故障单独可见。
    limit = context.inputs["max_attempts"] if scenario == "goal_loop" else 1
    # 停止条件也是契约的一部分：目标循环把尝试上限写进任务卡的 stop 字段。
    card = {**TASK_CARD, "stop": f"验收通过或尝试 {limit} 次后停止"} if scenario == "goal_loop" else TASK_CARD
    context.emit("lesson.task_card", card)
    evidence: dict[str, dict] = {}
    history, checks = [], []
    for attempt in range(1, limit + 1):
        context.check_cancelled()
        # 1. 执行：执行者交来完成声明，调用过的工具结果记进 evidence。
        claim = _attempt(context, scenario, attempt, evidence)
        context.emit("lesson.completion_claim", {"attempt": attempt, **claim}, attempt)
        # 2. 验收：验收器独立于执行者，只看声明引用的证据和任务卡。
        checks = verify(claim, evidence)
        passed = accepted(checks)
        reasons = [item["label"] + "：" + item["detail"] for item in checks[1:] if not item["passed"]]
        # 3. 决定下一步并记录：未通过的原因就是下一次尝试要交回给执行者的信息。
        if scenario == "goal_loop":
            context.emit("lesson.goal_check", {
                "attempt": attempt, "max_attempts": limit, "passed": passed, "reasons": reasons,
                "next": "stop" if passed or attempt == limit else "retry"}, attempt)
        history.append([attempt, claim["answer"], _evidence_value(evidence, claim), "通过" if passed else "未通过",
                        "；".join(reasons) or "全部检查通过"])
        # 4. 通过就停，不把剩下的尝试次数用完；没通过就进入下一次，直到上限。
        if passed:
            break
    ok = accepted(checks)
    _report(context, scenario, limit, checks, history, len(evidence))
    if ok:
        return f"验收通过：19 + 23 = 42，依据本次工具结果（第 {len(history)} 次尝试）。"
    if scenario == "goal_loop":
        return f"验收未通过：尝试 {len(history)} 次后达到上限，已停止。"
    return "验收未通过：流程已结束，但声明没有得到本次证据的支持。"


def _evidence_value(evidence: dict[str, dict], claim: dict):
    record = evidence.get(claim.get("evidence_ref") or "")
    if not record or not record["result"].get("ok"):
        return "无"
    return record["result"].get("result")


def _report(context: RunContext, scenario: str, limit: int, checks: list[dict], history: list[list],
            tool_calls: int) -> None:
    """发布实验报告（lesson.report）：检查项、指标和每次尝试的记录。"""
    ok = accepted(checks)
    metrics = [{"label": "工具调用数", "value": tool_calls},
               {"label": "场景", "value": scenario},
               {"label": "学习者备注", "value": context.question or "（空）"}]
    if scenario == "goal_loop":
        metrics[1:1] = [{"label": "尝试次数", "value": len(history)}, {"label": "尝试上限", "value": limit},
                        {"label": "停止原因", "value": "验收通过" if ok else "达到尝试上限"}]
    context.emit("lesson.report", {
        "title": "任务卡独立验收", "summary": "验收通过" if ok else "运行结束，但验收未通过",
        "checks": checks,
        "metrics": metrics,
        "table": {"columns": ["尝试", "声明的答案", "证据中的值", "验收结论", "原因"], "rows": history},
    })
