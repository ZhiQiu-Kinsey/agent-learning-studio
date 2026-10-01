"""无模型的类型化教学状态机；消息和状态分别保存。"""
from dataclasses import asdict, dataclass, field
from uuid import uuid4

from pydantic import Field

from course.execution import LessonInputs, RunContext


SOURCES = {
    "lesson-07": "模型只能依据本次请求可见的消息；历史需由程序重发。",
    "lesson-08": "应用状态由程序事件更新，模型文本不能直接证明任务完成。",
}
TRANSITIONS = {
    "ready": {"running", "cancelled"},
    "running": {"waiting", "completed", "failed", "cancelled"},
    "waiting": {"running", "failed", "cancelled"},
    "completed": set(), "failed": set(), "cancelled": set(),
}


class Inputs(LessonInputs):
    goal: str = Field(default="说明消息与应用状态的区别", min_length=4, max_length=160)
    source_key: str = Field(default="lesson-07", pattern="^(lesson-07|lesson-08|missing)$")
    scenario: str = Field(default="success", pattern="^(success|missing|budget)$")
    step_budget: int = Field(default=3, ge=1, le=5)


INPUT_MODEL = Inputs


@dataclass
class TaskState:
    run_id: str
    goal: str
    status: str = "ready"
    evidence: list[dict] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    used_steps: int = 0
    result: str | None = None
    terminal_reason: str | None = None

    def consume_step(self, label: str, budget: int) -> bool:
        if self.status != "running":
            raise ValueError("只有运行中才能执行步骤。")
        if self.used_steps >= budget:
            return False
        self.used_steps += 1
        self.steps.append(label)
        return True

    def transition(self, target: str, reason: str | None = None) -> None:
        if target not in TRANSITIONS[self.status]:
            raise ValueError(f"非法状态转换：{self.status} → {target}")
        if target in {"completed", "failed", "cancelled"} and not reason:
            raise ValueError("终态必须说明原因。")
        if target == "completed" and (not self.evidence or not self.result):
            raise ValueError("缺少已验证证据或实际产物，不可标为完成。")
        self.status = target
        if target in {"completed", "failed", "cancelled"}:
            self.terminal_reason = reason


def _publish(context: RunContext, state: TaskState, action: str) -> None:
    context.emit("lesson.state", {"action": action, "state": asdict(state)})


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    state = TaskState(run_id=uuid4().hex, goal=values.goal)
    messages = [{"role": "user", "content": values.goal}]
    _publish(context, state, "创建独立运行")
    context.check_cancelled()
    state.transition("running")
    state.consume_step("读取本地资料索引", values.step_budget)
    _publish(context, state, "开始读取")
    source = SOURCES.get(values.source_key) if values.scenario != "missing" else None
    if source is None:
        state.transition("waiting")
        _publish(context, state, "资料缺失，进入等待")
        state.transition("failed", "本次预设没有可核验的资料，无法完成目标。")
    else:
        if not state.consume_step("核对资料来源", values.step_budget):
            state.transition("failed", "步骤预算在核对资料来源前耗尽。")
        else:
            state.evidence.append({"source": values.source_key, "excerpt": source})
            _publish(context, state, "已核对来源并记录证据")
            context.check_cancelled()
            if not state.consume_step("生成课内资料要点", values.step_budget):
                state.transition("failed", "步骤预算在生成资料要点前耗尽。")
            else:
                state.result = f"资料 {values.source_key} 的要点：{source}"
                state.transition("completed", "课内资料归纳流程完成；不代表任意自由目标已实现。")
    _publish(context, state, "记录终态")
    context.emit("lesson.report", {
        "title": "应用状态与消息对照",
        "summary": "本课只运行本地 Python；步骤预算在执行前扣减，消息列表不会自动更新状态。学习者备注不改变任务。",
        "checks": [
            {"label": "终态有原因", "passed": bool(state.terminal_reason), "detail": state.terminal_reason or ""},
            {"label": "成功有证据和产物", "passed": state.status != "completed" or bool(state.evidence and state.result), "detail": "资料来自 SOURCES；result 是实际生成的课内要点。"},
            {"label": "消息与状态分开", "passed": len(messages) == 1, "detail": "本地状态更新没有伪装成 assistant 或 tool 消息。"},
        ],
        "metrics": [{"label": "状态", "value": state.status}, {"label": "证据数", "value": len(state.evidence)}, {"label": "消息数", "value": len(messages)},
                    {"label": "步骤预算", "value": values.step_budget}, {"label": "已执行步骤", "value": state.used_steps},
                    {"label": "学习者备注", "value": context.question or "无"}],
        "table": {"columns": ["字段", "本次值"], "rows": [["run_id", state.run_id], ["goal", state.goal], ["status", state.status], ["terminal_reason", state.terminal_reason or ""]]},
    })
    if state.status == "completed":
        return f"课内资料归纳流程已完成：{state.result}；自由目标“{state.goal}”未被单独验收。"
    return f"未完成：{state.terminal_reason}"
