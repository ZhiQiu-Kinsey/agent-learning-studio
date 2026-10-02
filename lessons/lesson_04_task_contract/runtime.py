"""A local acceptance harness: a completion claim is checked against recorded evidence."""
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext


class Inputs(LessonInputs):
    scenario: Literal["normal", "missing_evidence", "wrong_result", "claim_mismatch", "goal_loop"] = "normal"
    claim: str = Field(default="已完成学习助教的加法任务", min_length=1, max_length=120)
    max_attempts: int = Field(default=3, ge=1, le=3)


INPUT_MODEL = Inputs
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
    """Check a completion claim against tool results recorded in this run; never trust the claim alone."""
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
        {"label": "声明与证据一致", "passed": ok and claim.get("answer") == value,
         "detail": f"声明写 {claim.get('answer')}；证据中为 {value if ok else '无'}"},
    ]


def accepted(checks: list[dict]) -> bool:
    # The first check only says the program reached this point; it is not part of acceptance.
    return all(item["passed"] for item in checks[1:])


def _attempt(context: RunContext, scenario: str, attempt: int, evidence: dict[str, dict]) -> dict:
    """One execution attempt. Faults are injected by this course program, not made by a model."""
    if scenario == "missing_evidence":
        return {"status": "done", "answer": EXPECTED, "evidence_ref": None, "summary": context.inputs["claim"]}
    # In goal_loop only the first attempt is wrong; the retry redoes the card's inputs.
    # A model-driven loop would read the verifier's reasons instead of a fixed script.
    wrong = scenario in ("wrong_result", "claim_mismatch") or (scenario == "goal_loop" and attempt == 1)
    call_id = f"lesson4_add_{attempt}"
    result = context.call_tool("add_numbers", {"a": 19, "b": 22 if wrong else 23},
                               {"add_numbers": add_numbers}, round_number=attempt, call_id=call_id)
    evidence[call_id] = {"result": result}
    # claim_mismatch: the executor reports the expected value no matter what the tool returned.
    answer = EXPECTED if scenario == "claim_mismatch" else result.get("result")
    return {"status": "done", "answer": answer, "evidence_ref": call_id, "summary": context.inputs["claim"]}


def _evidence_value(evidence: dict[str, dict], claim: dict):
    record = evidence.get(claim.get("evidence_ref") or "")
    if not record or not record["result"].get("ok"):
        return "无"
    return record["result"].get("result")


def run(context: RunContext) -> str:
    context.check_cancelled()
    scenario = context.inputs["scenario"]
    limit = context.inputs["max_attempts"] if scenario == "goal_loop" else 1
    # The stop condition is part of the contract: a goal loop must say when it gives up.
    card = {**TASK_CARD, "stop": f"验收通过或尝试 {limit} 次后停止"} if scenario == "goal_loop" else TASK_CARD
    context.emit("lesson.task_card", card)
    evidence: dict[str, dict] = {}
    history = []
    checks: list[dict] = []
    for attempt in range(1, limit + 1):
        context.check_cancelled()
        claim = _attempt(context, scenario, attempt, evidence)
        context.emit("lesson.completion_claim", {"attempt": attempt, **claim}, attempt)
        checks = verify(claim, evidence)
        passed = accepted(checks)
        reasons = [item["label"] + "：" + item["detail"] for item in checks[1:] if not item["passed"]]
        if scenario == "goal_loop":
            context.emit("lesson.goal_check", {
                "attempt": attempt, "max_attempts": limit, "passed": passed, "reasons": reasons,
                "next": "stop" if passed or attempt == limit else "retry"}, attempt)
        history.append([attempt, claim["answer"], _evidence_value(evidence, claim), "通过" if passed else "未通过",
                        "；".join(reasons) or "全部检查通过"])
        if passed:
            break
    ok = accepted(checks)
    metrics = [{"label": "工具调用数", "value": len(evidence)},
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
    if ok:
        return f"验收通过：19 + 23 = 42，依据本次工具结果（第 {len(history)} 次尝试）。"
    if scenario == "goal_loop":
        return f"验收未通过：尝试 {len(history)} 次后达到上限，已停止。"
    return "验收未通过：流程已结束，但声明没有得到本次证据的支持。"
