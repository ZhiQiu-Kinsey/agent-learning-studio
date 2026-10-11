"""Offline test model for orchestrator-evaluator: serves automated tests only and does not stand for any real model.

The evaluator always asks for a revision the first time and passes the second time, to test the revision loop;
every response carries scripted usage.
"""
import json

from lessons.lesson_orchestrator_evaluator.locales import texts_for
from lessons.lesson_orchestrator_evaluator.runtime import LESSONS

# Scripted questions and feedback per run language; the first option is always the lesson's key point.
SCRIPT = {
    "zh-CN": {
        "question": "关于 {lesson} 这一课，下列哪一项正确？", "revised": "（修订版）",
        "distractors": ["模型会自动记住所有历史", "工具结果可以由模型自己写", "上下文越长越好"],
        "explanation": "第一项是该课要点，其余三项都与课程内容相反。",
        "instruction": "为 {lesson} 这一课出一道选择题", "feedback": "干扰项太容易排除",
    },
    "en": {
        "question": "Which statement about the {lesson} lesson is correct?", "revised": " (revised)",
        "distractors": ["The model remembers all history by itself", "The model may write tool results itself",
                        "The longer the context, the better"],
        "explanation": "The first option is the lesson's key point; the other three contradict the lesson.",
        "instruction": "Write one multiple-choice question for the {lesson} lesson", "feedback": "The distractors are too easy to rule out",
    },
}


def _reply(value, tokens):
    content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"total_tokens": tokens}}


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    t, script = texts_for(locale), SCRIPT[locale]
    reviews = 0

    def question(lesson, revised=False):
        return {"question": script["question"].format(lesson=lesson) + (script["revised"] if revised else ""),
                "options": [t.notes[lesson], *script["distractors"]], "answer": 0, "explanation": script["explanation"]}

    def complete(body, api_key):
        nonlocal reviews
        system, user = body["messages"][0]["content"], body["messages"][1]["content"]
        if system == t.single_system:
            return _reply([question(lesson) for lesson in LESSONS], 300)
        if system == t.orchestrator_system:
            return _reply({"subtasks": [{"id": f"w{index}", "lesson": lesson,
                                         "instruction": script["instruction"].format(lesson=lesson)}
                                        for index, lesson in enumerate(LESSONS, 1)]}, 80)
        if system == t.evaluator_system:
            reviews += 1
            if reviews == 1:
                return _reply({"verdict": "revise", "feedback": [script["feedback"]]}, 60)
            return _reply({"verdict": "pass", "feedback": []}, 60)
        lesson = next(key for key in LESSONS if t.notes[key] in user)
        # A generator request that goes on past the first-round request is a revision request.
        first = t.generator_request.format(lesson=lesson, note=t.notes[lesson])
        return _reply(question(lesson, revised=user.startswith(first) and user != first), 120)

    return complete
