"""TODO 清单与运行层提醒：同一个多步任务在三种条件下运行，由独立验收器判定是否完成。

todo_write 的约束（每项有内容、同一时间最多一项 in_progress）和“连续几轮没更新就提醒”的做法
参考 learn-claude-code s05（MIT）；本课的工具、提醒文本、验收器与实验由本项目编写。
"""
import json
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from course.runner import execute_tool


class Inputs(LessonInputs):
    condition: Literal["no_todo", "todo", "todo_reminder"] = "todo_reminder"
    reminder_after: int = Field(default=2, ge=1, le=5)


INPUT_MODEL = Inputs
NOTES = {
    "7": {"lesson": "7", "note_id": "n7-31", "note": "模型只看到本次请求里的消息，历史要由程序重发。"},
    "8": {"lesson": "8", "note_id": "n8-12", "note": "应用状态记录目标和证据，消息列表不会自动更新它。"},
    "9": {"lesson": "9", "note_id": "n9-47", "note": "压缩上下文时，工具调用和回执要成对保留或成对删除。"},
}
REQUIRED = ("7", "8", "9")
TASK = "帮我做一张复习卡：分别查第 7、8、9 课的要点，把三条要点连同要点编号存进复习卡，然后告诉我完成了。"
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
        if sum(item["status"] == "in_progress" for item in cleaned) > 1:
            raise ValueError("同一时间最多一项 in_progress。")
        self.todos, self.version = cleaned, self.version + 1
        return {"version": self.version, "todos": cleaned}

    def lookup_note(self, lesson: str) -> dict:
        if lesson not in NOTES:
            raise ValueError("只有第 7、8、9 课的要点。")
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


def verify_card(card: list[dict] | None, looked_up: dict[str, str]) -> list[dict]:
    """独立验收：只看复习卡与本次真实查询结果，不看模型怎么说、TODO 怎么标。"""
    lessons = sorted(item["lesson"] for item in card) if card else []
    wrong = [item["lesson"] for item in card or [] if looked_up.get(item["lesson"]) != item["note_id"]]
    return [
        {"label": "复习卡已保存", "passed": card is not None,
         "detail": "save_card 成功返回" if card is not None else "没有成功的 save_card"},
        {"label": "卡片覆盖第 7、8、9 课", "passed": lessons == list(REQUIRED),
         "detail": "卡片里的课：" + ("、".join(lessons) or "无")},
        {"label": "每条要点编号来自本次查询", "passed": card is not None and not wrong,
         "detail": "全部能对上本次 lookup_note 的结果" if card is not None and not wrong
         else "对不上的课：" + ("、".join(wrong) or "（没有卡片）")},
    ]


def tool_specs(condition: str) -> list[dict]:
    def spec(name, description, properties, required):
        return {"type": "function", "function": {"name": name, "description": description, "parameters": {
            "type": "object", "properties": properties, "required": required, "additionalProperties": False}}}
    specs = [
        spec("lookup_note", "查询某一课的复习要点和要点编号。", {"lesson": {"type": "string", "enum": list(REQUIRED)}}, ["lesson"]),
        spec("save_card", "把要点存进复习卡。每条要点写明课号、要点编号和一句话摘要。", {"items": {"type": "array", "items": {
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
    values = Inputs.model_validate(context.inputs)
    condition = values.condition
    workspace = Workspace()
    tools = {"lookup_note": workspace.lookup_note, "save_card": workspace.save_card}
    if condition != "no_todo":
        tools["todo_write"] = workspace.todo_write
    system = BASE_SYSTEM if condition == "no_todo" else BASE_SYSTEM + TODO_RULES
    messages = [{"role": "system", "content": system}, {"role": "user", "content": TASK}]
    looked_up: dict[str, str] = {}
    timeline, answer, reminders, since_update, model_calls = [], None, 0, 0, 0
    for round_number in range(1, context.max_model_calls + 1):
        context.check_cancelled()
        response = context.complete({"messages": messages, "tools": tool_specs(condition), "tool_choice": "auto",
                                     "temperature": 0}, round_number)
        model_calls += 1
        message = response["choices"][0].get("message", {})
        calls = message.get("tool_calls") or []
        if not calls:
            answer = message.get("content") or ""
            break
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
        updated = False
        for call in calls:
            context.check_cancelled()
            name = call.get("function", {}).get("name")
            before = list(workspace.todos)
            context.emit("tool_call", call, round_number)
            result = execute_tool(call, tools, quiet=True)
            context.emit("tool_result", {"tool_call_id": call.get("id"), "name": name, "result": result}, round_number)
            messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": json.dumps(result, ensure_ascii=False)})
            if name == "lookup_note" and result.get("ok"):
                looked_up[result["result"]["lesson"]] = result["result"]["note_id"]
            if name == "todo_write" and result.get("ok"):
                updated = True
                diff = todo_diff(before, workspace.todos)
                context.emit("lesson.todo", {"version": workspace.version, "todos": workspace.todos, "diff": diff},
                             round_number)
                timeline.append([round_number, workspace.version,
                                 sum(item["status"] == "done" for item in workspace.todos), len(workspace.todos),
                                 "；".join(f"{c['id']} {c['from']}→{c['to']}" for c in diff["changed"]) or
                                 ("新增 " + "、".join(diff["added"]) if diff["added"] else "无变化")])
        since_update = 0 if updated else since_update + 1
        if condition == "todo_reminder" and since_update >= values.reminder_after:
            # 提醒作为单独的 user 消息，放在本轮全部 tool 消息之后；OpenAI 兼容接口要求 tool 消息紧跟调用。
            text = reminder_text(since_update)
            messages.append({"role": "user", "content": text})
            context.emit("lesson.harness_injected", {"kind": "todo_reminder", "source": "harness", "text": text,
                                                     "rounds_since_update": since_update}, round_number)
            reminders += 1
            since_update = 0
    checks = verify_card(workspace.card, looked_up)
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
