"""先规划后执行：静态计划、失败后重新规划、ReAct 基线，三种策略做同一份学习周报。

主数据源 fetch_quiz_scores(source="primary") 在本课固定失败，这是运行器写死的受控故障，
不是网络故障；备份数据源 backup 能正常返回。三种策略用同一个验收器判定。
任务分解与“结果影响后续步骤时迭代规划”的讲法参考 Microsoft AI Agents for Beginners 07（MIT），
规划器提示词、计划格式、执行器与实验由本项目编写。
"""
import json
from typing import Literal

from course.execution import LessonInputs, RunContext


class Inputs(LessonInputs):
    strategy: Literal["static", "replan", "react"] = "replan"


INPUT_MODEL = Inputs
LEARNER = "lin"
# 课程用 slug 记录：显示课号会随课程表插入新课而变化，slug 不会。
PROGRESS = {"learner": LEARNER, "completed": ["messages-context", "application-state", "context-budget"],
            "in_progress": "persistent-memory"}
SCORES = {"learner": LEARNER, "scores": {"messages-context": 82, "application-state": 67, "context-budget": 91},
          "source": "backup"}
MAX_REVISIONS = 2


def fetch_progress(learner: str) -> dict:
    if learner != LEARNER:
        raise ValueError(f"没有学习者 {learner} 的记录。")
    return PROGRESS


def fetch_quiz_scores(learner: str, source: str = "primary") -> dict:
    if learner != LEARNER:
        raise ValueError(f"没有学习者 {learner} 的记录。")
    # 受控故障：主数据源每次都失败。错误信息写明可以改用备份，修订计划时有据可依。
    if source == "primary":
        raise ValueError("成绩主数据源暂时不可用（受控故障：本课固定失败）。可以改用 source=backup。")
    if source != "backup":
        raise ValueError("source 只能是 primary 或 backup。")
    return SCORES


AVAILABLE_TOOLS = {"fetch_progress": fetch_progress, "fetch_quiz_scores": fetch_quiz_scores}
TASK = f"给学习者 {LEARNER} 写一份学习周报：列出已完成的课和每课的练习得分。"
PLANNER_SYSTEM = """你是规划器，只负责写计划，不执行工具。可用工具：
- fetch_progress(learner)：查询已完成和正在学的课程。
- fetch_quiz_scores(learner, source)：查询每课练习得分；source 为 primary（主数据源）或 backup（备份，数据相同）。

只输出一个 JSON 对象，不要输出其他文字：
{"reason": "为什么这样计划（修订时写明修订原因）", "steps": [{"id": "s1", "tool": "工具名", "arguments": {...}, "purpose": "这一步要得到什么"}]}
修订计划时，只列出还需要执行的步骤，id 不要和已有步骤重复。"""


def parse_plan(content: str) -> dict:
    """读取规划器输出的 JSON 计划；允许 JSON 前后有说明文字或代码围栏，其余不做修复。"""
    start = content.find("{")
    if start < 0:
        raise ValueError("计划里没有 JSON 对象。")
    plan, _ = json.JSONDecoder().raw_decode(content[start:])
    steps = plan.get("steps") if isinstance(plan, dict) else None
    if not isinstance(steps, list) or not steps:
        raise ValueError("计划必须有非空的 steps 列表。")
    seen = set()
    for item in steps:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in seen:
            raise ValueError("每个步骤需要唯一的字符串 id。")
        if item.get("tool") not in AVAILABLE_TOOLS:
            raise ValueError(f"步骤 {item['id']} 使用了未登记的工具：{item.get('tool')}")
        if not isinstance(item.get("arguments"), dict):
            raise ValueError(f"步骤 {item['id']} 的 arguments 必须是 JSON 对象。")
        seen.add(item["id"])
    return {"reason": str(plan.get("reason") or ""), "steps": steps}


TOOLS = [
    {"type": "function", "function": {"name": "fetch_progress", "description": "查询学习者已完成和正在学的课程。",
     "parameters": {"type": "object", "properties": {"learner": {"type": "string"}}, "required": ["learner"],
                    "additionalProperties": False}}},
    {"type": "function", "function": {"name": "fetch_quiz_scores",
     "description": "查询学习者每课的练习得分。source 为 primary（主数据源）或 backup（备份，数据相同）。",
     "parameters": {"type": "object", "properties": {"learner": {"type": "string"},
                                                     "source": {"type": "string", "enum": ["primary", "backup"]}},
                    "required": ["learner", "source"], "additionalProperties": False}}},
]
WRITER_SYSTEM = "你是学习助教。根据给出的工具结果写一段不超过三句话的学习周报，写出每课分数。缺少的数据就直说缺少，不要编造。"
REACT_SYSTEM = "你是学习助教。需要数据时调用工具，不要猜测。拿到数据后写一段不超过三句话的学习周报，写出每课分数。"


def _text(response: dict) -> str:
    content = response["choices"][0].get("message", {}).get("content")
    return content if isinstance(content, str) else ""


def _step_view(step: dict) -> dict:
    arguments = ", ".join(f"{key}={value}" for key, value in step["arguments"].items())
    return {"id": step["id"], "content": f"{step['tool']}({arguments})", "purpose": step.get("purpose", ""),
            "status": step.get("status", "pending")}


def verify(results: dict[str, dict], report: str) -> list[dict]:
    """只依据本次真实工具结果和最终周报判定，不看计划写得好不好。"""
    progress = results.get("fetch_progress")
    scores = results.get("fetch_quiz_scores")
    numbers = [str(value) for value in (scores or {}).get("scores", {}).values()]
    return [
        {"label": "学习进度来自成功的工具结果", "passed": progress is not None,
         "detail": "fetch_progress 成功" if progress else "没有成功的 fetch_progress"},
        {"label": "练习成绩来自成功的工具结果", "passed": scores is not None,
         "detail": f"来源 {scores['source']}" if scores else "没有成功的 fetch_quiz_scores"},
        {"label": "周报写出了真实的分数（关键词初筛）", "passed": bool(numbers) and all(n in report for n in numbers),
         "detail": "周报包含 " + "、".join(numbers) if numbers and all(n in report for n in numbers)
         else "周报没有写全真实分数，或本次没有成绩数据"},
    ]


class Planner:
    """规划器：只写计划，不执行工具。消息历史保留每一版计划和每次失败，修订时看得到来龙去脉。"""

    def __init__(self, context: RunContext):
        self.context = context
        self.messages = [{"role": "system", "content": PLANNER_SYSTEM}, {"role": "user", "content": TASK}]
        self.rounds = 0

    def ask(self) -> dict | None:
        """请求一版计划；不合格式就如实记录并返回 None，不替规划器补全。"""
        self.rounds += 1
        content = _text(self.context.complete({"messages": self.messages, "temperature": 0}, self.rounds))
        self.messages.append({"role": "assistant", "content": content})
        try:
            return parse_plan(content)
        except ValueError as error:
            self.context.emit("lesson.plan_error", {"error": str(error), "raw": content}, self.rounds)
            return None

    def revise(self, steps: list[dict], failed: dict, error) -> dict | None:
        """把步骤状态和失败步骤的真实错误交回规划器，请它只列出还需要执行的步骤。"""
        self.messages.append({"role": "user", "content": "执行情况：" + json.dumps(
            [{"id": s["id"], "tool": s["tool"], "status": s["status"]} for s in steps], ensure_ascii=False)
            + f"\n步骤 {failed['id']} 失败：{error}\n请修订计划，只列出还需要执行的步骤，并在 reason 里写明修订原因。"})
        return self.ask()


class Executor:
    """执行器：只照计划调用工具，不做决定；记下每一步的真实结果。"""

    def __init__(self, context: RunContext):
        self.context = context
        self.results: dict[str, dict] = {}
        self.calls = 0

    def run_step(self, step: dict, round_number: int) -> dict:
        self.calls += 1
        result = self.context.call_tool(step["tool"], step["arguments"], AVAILABLE_TOOLS,
                                        round_number=round_number, call_id=f"plan_{step['id']}_{self.calls}")
        # 只保存成功的结果：写周报时只能用真实拿到的数据。
        if result.get("ok"):
            self.results[step["tool"]] = result["result"]
        return result


def plan_and_execute(context: RunContext, revise: bool) -> tuple[str, dict, list[list]]:
    """先规划后执行；revise=True 时某步失败就带着真实错误回去修订，最多 MAX_REVISIONS 次。"""
    planner, executor = Planner(context), Executor(context)
    # 1. 规划：拿到一份校验过的计划才开始执行；计划不合格式就到此为止。
    plan = planner.ask()
    if plan is None:
        return "", _outcome(executor, planner.rounds, 0, 0), [[0, "规划失败", "计划不是合格的 JSON", 0]]
    steps, version, revisions = [{**item, "status": "pending"} for item in plan["steps"]], 1, 0
    _publish(context, version, steps, planner.rounds, reason=plan["reason"], event="created")
    history = [[version, "创建", plan["reason"] or "—", len(steps)]]
    index = 0
    while index < len(steps):
        # 2. 执行：执行器照计划调用工具，步骤状态只由真实工具结果决定。
        step = steps[index]
        step["status"] = "in_progress"
        result = executor.run_step(step, planner.rounds)
        step["status"] = "done" if result.get("ok") else "failed"
        _publish(context, version, steps, planner.rounds)
        index += 1
        # 3. 成功、静态计划或修订次数已用完，就接着执行下一步。
        if result.get("ok") or not revise or revisions >= MAX_REVISIONS:
            continue
        # 4. 修订：把真实失败交回规划器，只替换还没执行的步骤；已执行的步骤原样保留。
        revisions += 1
        revised = planner.revise(steps, step, result.get("error"))
        if revised is None:
            break
        old_pending = [s["id"] for s in steps[index:]]
        new_steps = [{**item, "status": "pending"} for item in revised["steps"]]
        steps, version = steps[:index] + new_steps, version + 1
        diff = {"removed": old_pending, "added": [s["id"] for s in new_steps], "failed_step": step["id"]}
        _publish(context, version, steps, planner.rounds, reason=revised["reason"], diff=diff, event="revised")
        history.append([version, "修订", revised["reason"] or "—", len(steps)])
    # 5. 写周报：只把成功的工具结果交给写手，缺的数据让它直说缺少。
    report = write_report(context, executor.results, planner.rounds + 1)
    return report, _outcome(executor, planner.rounds + 1, version, revisions), history


def write_report(context: RunContext, results: dict[str, dict], round_number: int) -> str:
    data = {tool: value for tool, value in results.items()}
    response = context.complete({"messages": [{"role": "system", "content": WRITER_SYSTEM},
                                              {"role": "user", "content": TASK + "\n工具结果：" + json.dumps(data, ensure_ascii=False)}],
                                 "temperature": 0}, round_number)
    return _text(response)


def _outcome(executor: Executor, model_calls: int, versions: int, revisions: int) -> dict:
    return {"results": executor.results,
            "stats": {"模型调用数": model_calls, "工具调用数": executor.calls, "计划版本数": versions, "修订次数": revisions}}


def _publish(context: RunContext, version: int, steps: list[dict], round_number: int, *, reason: str = "",
             diff: dict | None = None, event: str = "progress"):
    """发布一版计划（lesson.plan）：完整步骤与状态，修订时附原因和差异。"""
    context.emit("lesson.plan", {"version": version, "event": event, "reason": reason, "diff": diff or {},
                                 "steps": [_step_view(step) for step in steps]}, round_number)


def react(context: RunContext) -> tuple[str, dict, list[list]]:
    """ReAct 基线：不写计划，模型每一步看到工具结果再决定下一步。"""
    messages = [{"role": "system", "content": REACT_SYSTEM}, {"role": "user", "content": TASK}]
    results, calls, history = {}, 0, []
    for round_number in range(1, context.max_model_calls + 1):
        response = context.complete({"messages": messages, "tools": TOOLS, "tool_choice": "auto", "temperature": 0},
                                    round_number)
        message = response["choices"][0].get("message", {})
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            stats = {"模型调用数": round_number, "工具调用数": calls, "计划版本数": 0, "修订次数": 0}
            return message.get("content") or "", {"results": results, "stats": stats}, history
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls})
        for call in tool_calls:
            calls += 1
            result = context.execute_proposal(call, AVAILABLE_TOOLS)
            name = call.get("function", {}).get("name")
            if result.get("ok"):
                results[name] = result["result"]
            history.append([round_number, name, "成功" if result.get("ok") else "失败：" + str(result.get("error")), "—"])
            messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": json.dumps(result, ensure_ascii=False)})
    stats = {"模型调用数": context.max_model_calls, "工具调用数": calls, "计划版本数": 0, "修订次数": 0}
    return "", {"results": results, "stats": stats}, history


def run(context: RunContext) -> str:
    strategy = Inputs.model_validate(context.inputs).strategy
    context.check_cancelled()
    if strategy == "react":
        report, outcome, history = react(context)
        columns = ["轮次", "工具", "结果", "备注"]
    else:
        report, outcome, history = plan_and_execute(context, revise=strategy == "replan")
        columns = ["计划版本", "事件", "原因", "步骤数"]
    checks = verify(outcome["results"], report)
    return _report(context, strategy, checks, outcome, history, columns, report)


def _report(context: RunContext, strategy: str, checks: list[dict], outcome: dict, history: list[list],
            columns: list[str], report: str) -> str:
    """发布实验报告（lesson.report）并返回最终回答：验收结论在前，周报原文在后。"""
    accepted = all(check["passed"] for check in checks)
    context.emit("lesson.report", {
        "title": {"static": "静态计划", "replan": "失败后重新规划", "react": "ReAct 基线"}[strategy],
        "summary": "主数据源固定失败（受控故障）。验收只看真实工具结果和周报里的分数，不看计划本身。",
        "checks": checks,
        "metrics": [{"label": "验收结论", "value": "通过" if accepted else "未通过"},
                    *({"label": key, "value": value} for key, value in outcome["stats"].items()),
                    {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": columns, "rows": history},
    })
    return ("验收通过。" if accepted else "验收未通过。") + (report or "没有生成周报。")
