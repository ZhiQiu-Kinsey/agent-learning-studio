"""第 15 课离线测试模型：规划器、周报写手和 ReAct 基线的固定回答，只服务自动化测试。

规划器第一次总是选主数据源；收到失败信息后改用备份。这是脚本行为，不代表任何真实模型。
"""
import json

FIRST_PLAN = {"reason": "先查进度，再查成绩。", "steps": [
    {"id": "s1", "tool": "fetch_progress", "arguments": {"learner": "lin"}, "purpose": "已完成的课"},
    {"id": "s2", "tool": "fetch_quiz_scores", "arguments": {"learner": "lin", "source": "primary"}, "purpose": "每课得分"}]}
REVISED_PLAN = {"reason": "主数据源不可用，改用备份数据源。", "steps": [
    {"id": "s3", "tool": "fetch_quiz_scores", "arguments": {"learner": "lin", "source": "backup"}, "purpose": "每课得分"}]}


def _reply(content=None, calls=None):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return {"choices": [{"message": message, "finish_reason": "tool_calls" if calls else "stop"}]}


def _write_report(user_text):
    data = json.loads(user_text.split("工具结果：", 1)[1])
    scores = data.get("fetch_quiz_scores", {}).get("scores")
    if not scores:
        return "lin 完成了第 7、8、9 课，但这次没有拿到练习成绩。"
    return "lin 完成了第 7、8、9 课，得分：" + "，".join(f"第 {k} 课 {v} 分" for k, v in scores.items()) + "。"


def create_completion(exercise_id, inputs=None):
    def complete(body, api_key):
        messages = body["messages"]
        system = messages[0]["content"]
        if system.startswith("你是规划器"):
            revised = any("失败" in m["content"] for m in messages if m["role"] == "user")
            return _reply(json.dumps(REVISED_PLAN if revised else FIRST_PLAN, ensure_ascii=False))
        if "工具结果：" in messages[-1]["content"]:
            return _reply(_write_report(messages[-1]["content"]))
        # ReAct 基线：按已经看到的工具结果决定下一步。
        results = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        step = len(results)
        if step == 0:
            return _reply(calls=[{"id": "call_1", "type": "function", "function": {
                "name": "fetch_progress", "arguments": json.dumps({"learner": "lin"})}}])
        if step == 1 or (step == 2 and not results[-1]["ok"]):
            source = "primary" if step == 1 else "backup"
            return _reply(calls=[{"id": f"call_{step + 1}", "type": "function", "function": {
                "name": "fetch_quiz_scores", "arguments": json.dumps({"learner": "lin", "source": source})}}])
        scores = results[-1]["result"]["scores"]
        return _reply("lin 完成了第 7、8、9 课，得分：" + "，".join(f"第 {k} 课 {v} 分" for k, v in scores.items()) + "。")

    return complete
