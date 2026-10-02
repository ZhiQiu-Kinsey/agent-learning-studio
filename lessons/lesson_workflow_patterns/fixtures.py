"""工作流模式课的离线测试模型：只服务自动化测试，不代表任何真实模型的行为。

路由脚本故意分错两张工单，并对一张输出不在列表里的标签，用来测试准确率、混淆矩阵和兜底。
复述子任务每次停顿 50 毫秒，好让测试能比较串行和并行的墙钟时间。
"""
import json
import time

from lessons.lesson_workflow_patterns.runtime import SUMMARY_SYSTEM, TICKETS

SCRIPTED = {text: gold for _, text, gold in TICKETS}
SCRIPTED[TICKETS[17][1]] = "error"     # t18：进度丢失，标注为账号问题，脚本判成报错
SCRIPTED[TICKETS[19][1]] = "error"     # t20：问备份数据源，标注为课程内容，脚本判成报错
SCRIPTED[TICKETS[11][1]] = "billing"   # t12：不在标签列表里，应该走兜底
CHAIN_OUTPUTS = [
    "- 模型只看到本次请求里的消息\n- 工具调用和工具结果要成对\n- 上下文越长越要挑信息",
    "Q: 模型能看到什么？\nA: 只有本次请求里的消息。\nQ: 工具消息有什么要求？\nA: 调用和工具结果要成对。\n"
    "Q: 上下文长了怎么办？\nA: 只留真正需要的信息。",
    json.dumps(["模型看到什么", "成对的消息", "挑选上下文"], ensure_ascii=False),
]


def _reply(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}


def create_completion(exercise_id, inputs=None):
    chain_step = 0

    def complete(body, api_key):
        nonlocal chain_step
        messages = body["messages"]
        if messages[0]["role"] == "system" and messages[0]["content"] == SUMMARY_SYSTEM:
            time.sleep(0.05)
            return _reply("要点：" + messages[1]["content"][:20])
        if messages[0]["role"] == "system":
            return _reply(SCRIPTED.get(messages[1]["content"], "other"))
        output = CHAIN_OUTPUTS[min(chain_step, len(CHAIN_OUTPUTS) - 1)]
        chain_step += 1
        return _reply(output)

    return complete
