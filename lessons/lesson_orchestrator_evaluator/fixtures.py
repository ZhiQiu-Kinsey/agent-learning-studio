"""编排与评估课的离线测试模型：只服务自动化测试，不代表任何真实模型的行为。

评估者第一次固定要求修订，第二次通过，用来测试修订循环；每次响应附带脚本写的用量。
"""
import json

from lessons.lesson_orchestrator_evaluator.runtime import EVALUATOR_SYSTEM, NOTES, ORCHESTRATOR_SYSTEM, SINGLE_SYSTEM


def _question(lesson, revised=False):
    return {"question": f"关于 {lesson} 这一课，下列哪一项正确？" + ("（修订版）" if revised else ""),
            "options": [NOTES[lesson], "模型会自动记住所有历史", "工具结果可以由模型自己写", "上下文越长越好"],
            "answer": 0, "explanation": "第一项是该课要点，其余三项都与课程内容相反。"}


def _reply(value, tokens):
    content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"total_tokens": tokens}}


def create_completion(exercise_id, inputs=None):
    reviews = 0

    def complete(body, api_key):
        nonlocal reviews
        system, user = body["messages"][0]["content"], body["messages"][1]["content"]
        if system == SINGLE_SYSTEM:
            return _reply([_question(lesson) for lesson in NOTES], 300)
        if system == ORCHESTRATOR_SYSTEM:
            return _reply({"subtasks": [{"id": f"w{index}", "lesson": lesson, "instruction": f"为 {lesson} 这一课出一道选择题"}
                                        for index, lesson in enumerate(NOTES, 1)]}, 80)
        if system == EVALUATOR_SYSTEM:
            reviews += 1
            if reviews == 1:
                return _reply({"verdict": "revise", "feedback": ["干扰项太容易排除"]}, 60)
            return _reply({"verdict": "pass", "feedback": []}, 60)
        lesson = next(key for key, note in NOTES.items() if note in user)
        return _reply(_question(lesson, revised="评审意见" in user), 120)

    return complete
