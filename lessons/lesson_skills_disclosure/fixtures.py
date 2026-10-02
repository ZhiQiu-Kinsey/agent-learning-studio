"""Skills 与渐进式披露的离线测试模型：只服务自动化测试，不代表任何真实模型的行为。

请求带 tools 的是“目录 + 按需加载”，不带的是“全量注入”。模糊描述下，脚本故意让“模型”
在整理笔记时不加载技能（漏触发）、在复习提问上加载 review-cards（误触发），
用来测试运行器能不能把这两种情况如实记下来。响应里不带 usage，提示 Token 会显示为“未报告”。
"""
import json

CARDS = ("问：Python 的列表和元组哪个可以修改？\n答：列表可以修改，元组创建后不能修改。\n\n"
         "问：为什么元组可以当字典的键，列表不行？\n答：字典的键必须是不可变类型，元组不可变，列表可变。\n\n"
         "问：集合有什么特点？\n答：会自动去重，但不保证元素顺序。")
GREETING = "你好！周五快乐，祝你周末愉快。"
ANSWER = "列表创建后还能修改，元组创建后不能修改。"


def _reply(content=None, calls=None):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return {"choices": [{"message": message, "finish_reason": "tool_calls" if calls else "stop"}]}


def _load(name):
    return [{"id": "call_load_skill_1", "type": "function",
             "function": {"name": "load_skill", "arguments": json.dumps({"name": name})}}]


def create_completion(exercise_id, inputs=None):
    def complete(body, api_key):
        messages = body["messages"]
        question = next(message["content"] for message in messages if message["role"] == "user")
        on_demand = "tools" in body
        vague = "帮助学习。" in messages[0]["content"]
        loaded = any(message["role"] == "tool" for message in messages)
        if "整理成复习卡" in question:
            if on_demand and not loaded and not vague:
                return _reply(calls=_load("review-cards"))
            return _reply(CARDS)
        if "帮我复习一下" in question:
            if on_demand and not loaded and vague:
                return _reply(calls=_load("review-cards"))
            return _reply(ANSWER)
        return _reply(GREETING)

    return complete
