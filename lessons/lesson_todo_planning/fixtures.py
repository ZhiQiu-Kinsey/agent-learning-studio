"""第 14 课离线测试模型：按固定脚本提出调用，只服务自动化测试，不代表任何真实模型的行为。

无 TODO 的脚本故意漏掉第 9 课却声称完成，用来测试验收器不采信模型的说法。
"""
import json

PLAN = [{"id": "l7", "content": "查第 7 课要点", "status": "in_progress"},
        {"id": "l8", "content": "查第 8 课要点", "status": "pending"},
        {"id": "l9", "content": "查第 9 课要点", "status": "pending"},
        {"id": "card", "content": "保存复习卡", "status": "pending"}]


def _plan(**statuses):
    return [{**item, "status": statuses.get(item["id"], item["status"])} for item in PLAN]


SCRIPTS = {
    "no_todo": [("lookup_note", {"lesson": "7"}), ("lookup_note", {"lesson": "8"}), ("save_card", ["7", "8"]),
                "复习卡已经做好了。"],
    "todo": [("todo_write", {"todos": PLAN}), ("lookup_note", {"lesson": "7"}), ("lookup_note", {"lesson": "8"}),
             ("lookup_note", {"lesson": "9"}), ("save_card", ["7", "8", "9"]), "三条要点都存进复习卡了。"],
    "todo_reminder": [("todo_write", {"todos": PLAN}), ("lookup_note", {"lesson": "7"}), ("lookup_note", {"lesson": "8"}),
                      ("todo_write", {"todos": _plan(l7="done", l8="done", l9="in_progress")}),
                      ("lookup_note", {"lesson": "9"}), ("save_card", ["7", "8", "9"]),
                      ("todo_write", {"todos": _plan(l7="done", l8="done", l9="done", card="done")}),
                      "三条要点都存进复习卡了，清单也已全部完成。"],
}


def _looked_up(messages):
    found = {}
    for message in messages:
        if message["role"] == "tool":
            result = json.loads(message["content"])
            if result.get("ok") and isinstance(result.get("result"), dict) and "note_id" in result["result"]:
                found[result["result"]["lesson"]] = result["result"]
    return found


def create_completion(exercise_id, inputs=None):
    condition = (inputs or {}).get("condition") or {"no-todo": "no_todo", "todo": "todo"}.get(exercise_id, "todo_reminder")
    script = SCRIPTS[condition]

    def complete(body, api_key):
        messages = body["messages"]
        step = sum(1 for message in messages if message["role"] == "assistant" and message.get("tool_calls"))
        action = script[min(step, len(script) - 1)]
        if isinstance(action, str):
            return {"choices": [{"message": {"role": "assistant", "content": action}, "finish_reason": "stop"}]}
        name, arguments = action
        if name == "save_card":
            notes = _looked_up(messages)
            arguments = {"items": [{"lesson": key, "note_id": notes[key]["note_id"], "summary": notes[key]["note"]}
                                   for key in arguments]}
        call = {"id": f"call_{step + 1}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}
        return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [call]},
                             "finish_reason": "tool_calls"}]}

    return complete
