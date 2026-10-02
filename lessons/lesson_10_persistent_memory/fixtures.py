"""持久记忆的离线测试模型：只服务自动化测试，不代表任何真实模型的行为。

它读请求里 <memory> 数据块的 JSON：有学习目标就照着回答并标出 key，数据块为空就说记忆里没有。
只有“召回后回答”类练习会调用它；保存、重开和只读恢复不发模型请求。
"""
from lessons.lesson_10_persistent_memory.runtime import memory_block


def create_completion(exercise_id, inputs=None):
    def complete(body, api_key):
        records = memory_block(body["messages"][-1]["content"])
        if records:
            item = next((record for record in records if record["key"] == "learning_goal"), records[0])
            text = f"你之前定下的学习目标是：{item['value']} [{item['key']}]"
        else:
            text = "记忆里没有你的学习目标。"
        return {"choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]}

    return complete
