"""Offline test model for todo-planning: proposes calls from a fixed script; serves automated tests only and stands for no real model.

The no-TODO script deliberately skips the context-budget lesson yet claims to be done, to test
that the acceptance check does not trust the model's claim.
"""
import json

MC, AS, CB = "messages-context", "application-state", "context-budget"
# What the scripted "model" writes, per run language: the plan items and its last words.
WORDS = {
    "zh-CN": {"ctx": "查 messages-context 要点", "state": "查 application-state 要点",
              "budget": "查 context-budget 要点", "card": "保存复习卡",
              "no_todo": "复习卡已经做好了。", "todo": "三条要点都存进复习卡了。",
              "todo_reminder": "三条要点都存进复习卡了，清单也已全部完成。"},
    "en": {"ctx": "Look up the messages-context point", "state": "Look up the application-state point",
           "budget": "Look up the context-budget point", "card": "Save the review card",
           "no_todo": "The review card is done.", "todo": "All three points are on the review card.",
           "todo_reminder": "All three points are on the review card, and every item on the list is done."},
}


def _scripts(words):
    plan = [{"id": key, "content": words[key], "status": "in_progress" if key == "ctx" else "pending"}
            for key in ("ctx", "state", "budget", "card")]

    def updated(**statuses):
        return [{**item, "status": statuses.get(item["id"], item["status"])} for item in plan]

    return {
        "no_todo": [("lookup_note", {"lesson": MC}), ("lookup_note", {"lesson": AS}), ("save_card", [MC, AS]),
                    words["no_todo"]],
        "todo": [("todo_write", {"todos": plan}), ("lookup_note", {"lesson": MC}), ("lookup_note", {"lesson": AS}),
                 ("lookup_note", {"lesson": CB}), ("save_card", [MC, AS, CB]), words["todo"]],
        "todo_reminder": [("todo_write", {"todos": plan}), ("lookup_note", {"lesson": MC}),
                          ("lookup_note", {"lesson": AS}),
                          ("todo_write", {"todos": updated(ctx="done", state="done", budget="in_progress")}),
                          ("lookup_note", {"lesson": CB}), ("save_card", [MC, AS, CB]),
                          ("todo_write", {"todos": updated(ctx="done", state="done", budget="done", card="done")}),
                          words["todo_reminder"]],
    }


def _looked_up(messages):
    found = {}
    for message in messages:
        if message["role"] == "tool":
            result = json.loads(message["content"])
            if result.get("ok") and isinstance(result.get("result"), dict) and "note_id" in result["result"]:
                found[result["result"]["lesson"]] = result["result"]
    return found


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    condition = (inputs or {}).get("condition") or {"no-todo": "no_todo", "todo": "todo"}.get(exercise_id, "todo_reminder")
    script = _scripts(WORDS[locale])[condition]

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
