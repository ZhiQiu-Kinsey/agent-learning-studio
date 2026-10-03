"""不调用模型的类型化状态机：消息和应用状态分开保存，任务走到哪一步由程序事件决定。"""
from dataclasses import asdict, dataclass, field
from typing import Literal
from uuid import uuid4

from pydantic import Field

from course.execution import LessonInputs, RunContext


# 本课内置的两份本地资料；证据只能从这里读，键名就是课程 slug。
SOURCES = {
    "messages-context": "一次请求的上下文由系统提示词、之前的对话、工具调用与工具结果、本轮问题组成；工具调用和工具结果要成对。",
    "application-state": "应用状态由程序事件更新，模型文本不能直接证明任务完成。",
}


class Inputs(LessonInputs):
    goal: str = Field(default="说明消息与应用状态的区别", min_length=4, max_length=160)
    source_key: Literal["messages-context", "application-state", "missing"] = "messages-context"
    step_budget: int = Field(default=3, ge=1, le=5)


INPUT_MODEL = Inputs
# 转换表：每个状态允许进入哪些下一状态，不在表里的转换一律拒绝。
TRANSITIONS = {
    "ready": {"running", "cancelled"},
    "running": {"waiting", "completed", "failed", "cancelled"},
    "waiting": {"running", "failed", "cancelled"},
    "completed": set(), "failed": set(), "cancelled": set(),
}
TERMINAL = {"completed", "failed", "cancelled"}


@dataclass
class TaskState:
    """一次运行的应用状态。每次运行新建一份，和发给模型的 messages 分开存放。"""
    run_id: str
    goal: str
    status: str = "ready"
    evidence: list[dict] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    used_steps: int = 0
    result: str | None = None
    terminal_reason: str | None = None

    def consume_step(self, label: str, budget: int) -> bool:
        """执行一步之前先扣预算；预算不够就返回 False，由调用方决定怎样收尾。"""
        if self.status != "running":
            raise ValueError("只有运行中才能执行步骤。")
        if self.used_steps >= budget:
            return False
        self.used_steps += 1
        self.steps.append(label)
        return True

    def transition(self, target: str, reason: str | None = None) -> None:
        """所有状态变化都走这里：先查转换表，再查终态条件，最后才改 status。"""
        if target not in TRANSITIONS[self.status]:
            raise ValueError(f"非法状态转换：{self.status} → {target}")
        if target in TERMINAL and not reason:
            raise ValueError("终态必须说明原因。")
        # 完成的条件写在状态机里，调用方绕不过去。
        if target == "completed" and (not self.evidence or not self.result):
            raise ValueError("缺少已验证证据或实际产物，不可标为完成。")
        self.status = target
        if target in TERMINAL:
            self.terminal_reason = reason


def run(context: RunContext) -> str:
    values = Inputs.model_validate(context.inputs)
    # 1. 每次运行新建状态和 run_id；messages 只放用户目标，之后不再改动。
    state = TaskState(run_id=uuid4().hex, goal=values.goal)
    messages = [{"role": "user", "content": values.goal}]
    _publish(context, state, "创建独立运行")
    # 2. 进入 running，执行第一步：读取资料索引。
    context.check_cancelled()
    state.transition("running")
    state.consume_step("读取本地资料索引", values.step_budget)
    _publish(context, state, "开始读取")
    source = SOURCES.get(values.source_key)
    if source is None:
        # 3a. 没有资料：先进入 waiting，确认等不到再以 failed 收尾。
        state.transition("waiting")
        _publish(context, state, "资料缺失，进入等待")
        state.transition("failed", "本次预设没有可核验的资料，无法完成目标。")
    elif not state.consume_step("核对资料来源", values.step_budget):
        state.transition("failed", "步骤预算在核对资料来源前耗尽。")
    else:
        # 3b. 证据写进状态，不写进 messages。
        state.evidence.append({"source": values.source_key, "excerpt": source})
        _publish(context, state, "已核对来源并记录证据")
        context.check_cancelled()
        # 4. 第三步同样先扣预算；不够时已有证据保留，状态转为 failed。
        if not state.consume_step("生成课内资料要点", values.step_budget):
            state.transition("failed", "步骤预算在生成资料要点前耗尽。")
        else:
            state.result = f"资料 {values.source_key} 的要点：{source}"
            state.transition("completed", "课内资料归纳流程完成；不代表任意自由目标已实现。")
    # 5. 无论哪种结局，都发布终态快照和报告。
    _publish(context, state, "记录终态")
    _report(context, state, messages, values)
    if state.status == "completed":
        return f"课内资料归纳流程已完成：{state.result}；自由目标“{state.goal}”未被单独验收。"
    return f"未完成：{state.terminal_reason}"


def _publish(context: RunContext, state: TaskState, action: str) -> None:
    """发布一份完整的状态快照（lesson.state），回放时能看到每一步的状态。"""
    context.emit("lesson.state", {"action": action, "state": asdict(state)})


def _report(context: RunContext, state: TaskState, messages: list[dict], values: Inputs) -> None:
    """平台：组装并发布 lesson.report；检查项按状态逐项计算，不看消息内容。"""
    # 没有进入 completed 时，“成功有证据和产物”这一项没有可检查的对象，只说明原因、不标通过。
    success = ({"label": "成功有证据和产物", "passed": bool(state.evidence and state.result),
                "detail": "资料来自 SOURCES；result 是实际生成的课内要点。"} if state.status == "completed" else
               {"label": "成功有证据和产物", "detail": "本次没有进入 completed，此项不适用。"})
    context.emit("lesson.report", {
        "title": "应用状态与消息对照",
        "summary": "本课只运行本地 Python，不调用模型；步骤预算在执行前扣减，消息列表不会自动更新状态。学习者备注不改变任务。",
        "checks": [
            {"label": "终态有原因", "passed": bool(state.terminal_reason), "detail": state.terminal_reason or ""},
            success,
            {"label": "消息与状态分开", "passed": len(messages) == 1, "detail": "本地状态更新没有伪装成 assistant 或 tool 消息。"},
        ],
        "metrics": [{"label": "状态", "value": state.status}, {"label": "证据数", "value": len(state.evidence)},
                    {"label": "消息数", "value": len(messages)}, {"label": "步骤预算", "value": values.step_budget},
                    {"label": "已执行步骤", "value": state.used_steps},
                    {"label": "学习者备注", "value": context.question or "无"}],
        "table": {"columns": ["字段", "本次值"], "rows": [["run_id", state.run_id], ["goal", state.goal],
                                                       ["status", state.status],
                                                       ["terminal_reason", state.terminal_reason or ""]]},
    })
