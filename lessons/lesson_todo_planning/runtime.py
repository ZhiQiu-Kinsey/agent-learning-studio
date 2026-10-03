"""TODO 清单与运行层提醒：同一个多步任务在三种条件下运行，由独立验收器判定是否完成。

todo_write 的约束（每项有内容、同一时间最多一项 in_progress）和“连续几轮没更新就提醒”的做法
参考 learn-claude-code s03（TodoWrite，MIT）；本课的工具、提醒文本、验收器与实验由本项目编写。
"""
import json
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext


class Inputs(LessonInputs):
    condition: Literal["no_todo", "todo", "todo_reminder"] = "todo_reminder"
    reminder_after: int = Field(default=2, ge=1, le=5)


INPUT_MODEL = Inputs
# 三课的复习要点，键是课程 slug：显示课号会随课程表插入新课而变化，slug 不会。
# 要点编号没有规律，模型猜不到；编出来的编号拿去和本次查询结果一比就对不上。
NOTES = {
    "messages-context": {"lesson": "messages-context", "note_id": "mc-31",
                         "note": "模型只看到本次请求里的消息，历史要由程序重发。"},
    "application-state": {"lesson": "application-state", "note_id": "as-12",
                          "note": "应用状态记录目标和证据，消息列表不会自动更新它。"},
    "context-budget": {"lesson": "context-budget", "note_id": "cb-47",
                       "note": "压缩上下文时，工具调用和工具结果要成对保留或成对删除。"},
}
REQUIRED = tuple(NOTES)
TASK = ("帮我做一张复习卡：分别查 messages-context（上下文组成与消息协议）、application-state（应用状态与运行生命周期）、"
        "context-budget（上下文预算与截取窗口）三课的要点，把三条要点连同要点编号存进复习卡，然后告诉我完成了。")
BASE_SYSTEM = "你是学习助教。需要资料时调用工具，不要猜测要点内容或编号。全部完成后用一两句话说明结果。"
TODO_RULES = ("开始动手前，先用 todo_write 列出步骤。每完成一步就调用 todo_write 更新状态："
              "pending 未开始，in_progress 进行中，done 已完成；同一时间最多一项 in_progress。")
STATUSES = ("pending", "in_progress", "done")


class Workspace:
    """一次运行的本地状态：TODO 清单与复习卡。每次运行新建，不跨运行保留。"""

    def __init__(self):
        self.todos: list[dict] = []
        self.version = 0
        self.card: list[dict] | None = None

    def todo_write(self, todos: list) -> dict:
        """用完整清单整体替换当前清单；全部校验通过才生效，版本号加一。"""
        if not isinstance(todos, list) or not 1 <= len(todos) <= 12:
            raise ValueError("todos 必须是 1–12 项的列表。")
        cleaned, ids = [], set()
        for item in todos:
            if not isinstance(item, dict) or set(item) - {"id", "content", "status"}:
                raise ValueError("每项只能有 id、content、status 三个字段。")
            todo_id, content, status = item.get("id"), item.get("content"), item.get("status")
            if not isinstance(todo_id, str) or not todo_id or todo_id in ids:
                raise ValueError("每项需要唯一的非空 id。")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("每项需要非空的 content。")
            if status not in STATUSES:
                raise ValueError("status 只能是 pending、in_progress 或 done。")
            ids.add(todo_id)
            cleaned.append({"id": todo_id, "content": content.strip(), "status": status})
        # 同一时间最多一项进行中：清单要反映“现在在做哪一步”，而不是一堆半成品。
        if sum(item["status"] == "in_progress" for item in cleaned) > 1:
            raise ValueError("同一时间最多一项 in_progress。")
        self.todos, self.version = cleaned, self.version + 1
        return {"version": self.version, "todos": cleaned}

    def lookup_note(self, lesson: str) -> dict:
        if lesson not in NOTES:
            raise ValueError("只有 messages-context、application-state、context-budget 三课的要点。")
        return NOTES[lesson]

    def save_card(self, items: list) -> dict:
        if not isinstance(items, list) or not items:
            raise ValueError("items 必须是非空列表。")
        for item in items:
            if not isinstance(item, dict) or not all(isinstance(item.get(key), str) for key in ("lesson", "note_id", "summary")):
                raise ValueError("每条要点需要字符串字段 lesson、note_id、summary。")
        self.card = [{key: item[key] for key in ("lesson", "note_id", "summary")} for item in items]
        return {"saved": len(self.card)}


def todo_diff(before: list[dict], after: list[dict]) -> dict:
    old = {item["id"]: item for item in before}
    new = {item["id"]: item for item in after}
    return {"added": [key for key in new if key not in old],
            "removed": [key for key in old if key not in new],
            "changed": [{"id": key, "from": old[key]["status"], "to": new[key]["status"]}
                        for key in new if key in old and old[key]["status"] != new[key]["status"]]}


def tool_specs(condition: str) -> list[dict]:
    def spec(name, description, properties, required):
        return {"type": "function", "function": {"name": name, "description": description, "parameters": {
            "type": "object", "properties": properties, "required": required, "additionalProperties": False}}}
    specs = [
        spec("lookup_note", "查询某一课的复习要点和要点编号。", {"lesson": {"type": "string", "enum": list(REQUIRED)}}, ["lesson"]),
        spec("save_card", "把要点存进复习卡。每条要点写明课程（lookup_note 用的 lesson）、要点编号和一句话摘要。", {"items": {"type": "array", "items": {
            "type": "object", "properties": {"lesson": {"type": "string"}, "note_id": {"type": "string"}, "summary": {"type": "string"}},
            "required": ["lesson", "note_id", "summary"], "additionalProperties": False}}}, ["items"]),
    ]
    if condition != "no_todo":
        specs.append(spec("todo_write", "用完整清单替换当前 TODO。", {"todos": {"type": "array", "items": {
            "type": "object", "properties": {"id": {"type": "string"}, "content": {"type": "string"},
                                             "status": {"type": "string", "enum": list(STATUSES)}},
            "required": ["id", "content", "status"], "additionalProperties": False}}}, ["todos"]))
    return specs


TOOLS = tool_specs("todo_reminder")  # 网页“工具”面板展示完整的三个工具


def reminder_text(rounds: int) -> str:
    return f"<reminder>已经 {rounds} 轮没有更新 TODO。请先用 todo_write 更新清单，再继续。</reminder>"


def run(context: RunContext) -> str:
    """同一个任务在三种条件下运行：给不给 todo_write、运行层提不提醒；最后都交给同一个验收器。"""
    values = Inputs.model_validate(context.inputs)
    condition, workspace = values.condition, Workspace()
    tools = {"lookup_note": workspace.lookup_note, "save_card": workspace.save_card}
    # 无 TODO 组既看不到也执行不了 todo_write：工具定义和白名单里都没有它。
    if condition != "no_todo":
        tools["todo_write"] = workspace.todo_write
    system = BASE_SYSTEM if condition == "no_todo" else BASE_SYSTEM + TODO_RULES
    messages = [{"role": "system", "content": system}, {"role": "user", "content": TASK}]
    looked_up: dict[str, str] = {}
    timeline, answer, reminders, since_update, model_calls = [], None, 0, 0, 0
    for round_number in range(1, context.max_model_calls + 1):
        # 1. 发请求：每轮都带完整消息历史和本组可用的工具。
        response = context.complete({"messages": messages, "tools": tool_specs(condition), "tool_choice": "auto",
                                     "temperature": 0}, round_number)
        model_calls += 1
        message = response["choices"][0].get("message", {})
        calls = message.get("tool_calls") or []
        # 2. 没有调用提议就结束。模型说“完成了”只是声明，后面还要验收。
        if not calls:
            answer = message.get("content") or ""
            break
        # 3. 执行调用提议，把工具结果写回历史；记下这一轮有没有成功更新清单。
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
        updated = False
        for call in calls:
            name = call.get("function", {}).get("name")
            before = list(workspace.todos)
            result = context.execute_proposal(call, tools)
            messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": json.dumps(result, ensure_ascii=False)})
            if name == "lookup_note" and result.get("ok"):
                looked_up[result["result"]["lesson"]] = result["result"]["note_id"]
            if name == "todo_write" and result.get("ok"):
                updated = True
                _publish_todo(context, workspace, before, round_number, timeline)
        # 4. 运行层提醒：连续 reminder_after 轮没更新清单，就追加一条 user 消息。
        since_update = 0 if updated else since_update + 1
        if condition == "todo_reminder" and since_update >= values.reminder_after:
            # 提醒排在本轮所有 tool 消息之后：OpenAI 兼容接口要求 tool 消息紧跟带调用的 assistant 消息。
            text = reminder_text(since_update)
            messages.append({"role": "user", "content": text})
            # 第一次提醒带 first，回放时能和之后再次触发的提醒分开。
            context.emit("lesson.harness_injected", {"kind": "todo_reminder", "source": "harness", "text": text,
                                                     "rounds_since_update": since_update,
                                                     **({} if reminders else {"first": True})}, round_number)
            reminders += 1
            since_update = 0
    # 5. 验收：只看复习卡和本次真实查询结果，模型的说法和清单上的 done 都不算数。
    checks = verify_card(workspace.card, looked_up)
    return _report(context, condition, checks, workspace, timeline, reminders, model_calls, answer)


def verify_card(card: list[dict] | None, looked_up: dict[str, str]) -> list[dict]:
    """独立验收：只看复习卡与本次真实查询结果，不看模型怎么说、TODO 怎么标。"""
    lessons = sorted(item["lesson"] for item in card) if card else []
    # 编号必须和本次 lookup_note 的返回一致；没查过的课，填什么编号都不算。
    wrong = [item["lesson"] for item in card or [] if looked_up.get(item["lesson"]) != item["note_id"]]
    return [
        {"label": "复习卡已保存", "passed": card is not None,
         "detail": "save_card 成功返回" if card is not None else "没有成功的 save_card"},
        {"label": "卡片覆盖全部三课", "passed": lessons == sorted(REQUIRED),
         "detail": "卡片里的课：" + ("、".join(lessons) or "无")},
        {"label": "每条要点编号来自本次查询", "passed": card is not None and not wrong,
         "detail": "全部能对上本次 lookup_note 的结果" if card is not None and not wrong
         else "对不上的课：" + ("、".join(wrong) or "（没有卡片）")},
    ]


def _publish_todo(context: RunContext, workspace: Workspace, before: list[dict], round_number: int,
                  timeline: list[list]) -> None:
    """清单每变一次，就发布一版快照和差异（lesson.todo），并在报告的时间线里记一行。"""
    diff = todo_diff(before, workspace.todos)
    context.emit("lesson.todo", {"version": workspace.version, "todos": workspace.todos, "diff": diff}, round_number)
    timeline.append([round_number, workspace.version,
                     sum(item["status"] == "done" for item in workspace.todos), len(workspace.todos),
                     "；".join(f"{c['id']} {c['from']}→{c['to']}" for c in diff["changed"]) or
                     ("新增 " + "、".join(diff["added"]) if diff["added"] else "无变化")])


def _report(context: RunContext, condition: str, checks: list[dict], workspace: Workspace, timeline: list[list],
            reminders: int, model_calls: int, answer: str | None) -> str:
    """发布实验报告（lesson.report）并返回最终回答：验收结论在前，模型的说法只作记录。"""
    accepted = all(check["passed"] for check in checks)
    done = sum(item["status"] == "done" for item in workspace.todos)
    context.emit("lesson.report", {
        "title": {"no_todo": "无 TODO", "todo": "有 TODO，无提醒", "todo_reminder": "有 TODO，有提醒"}[condition],
        "summary": "验收只看复习卡和本次真实查询结果；模型的说法和 TODO 状态都是自报，不计入验收。",
        "checks": checks,
        "metrics": [{"label": "验收结论", "value": "通过" if accepted else "未通过"},
                    {"label": "模型调用数", "value": model_calls},
                    {"label": "todo_write 次数", "value": len(timeline)},
                    {"label": "运行层提醒次数", "value": reminders},
                    {"label": "TODO 自报完成", "value": f"{done}/{len(workspace.todos)}" if workspace.todos else "无清单"},
                    {"label": "模型的最后说法", "value": answer if answer is not None else "（达到调用上限，没有结束）"},
                    {"label": "学习者备注", "value": context.question or "（空）"}],
        "table": {"columns": ["轮次", "TODO 版本", "done", "总数", "变化"], "rows": timeline},
    })
    verdict = "验收通过" if accepted else "验收未通过"
    if answer is None:
        return f"{verdict}：{context.max_model_calls} 次调用内没有结束。"
    return f"{verdict}。模型最后说：{answer}"
