"""Offline test model for plan-and-replan: fixed answers for the planner, the report writer and the ReAct baseline; serves automated tests only.

The planner always picks the primary source first and switches to the backup after a failure.
That is script behavior and stands for no real model.
"""
import json

from lessons.lesson_plan_and_replan.locales import texts_for

# What the scripted "model" writes, per run language.
WORDS = {
    "zh-CN": {"first_reason": "先查进度，再查成绩。", "revised_reason": "主数据源不可用，改用备份数据源。",
              "purpose_progress": "已完成的课", "purpose_scores": "每课得分", "separator": "、", "some_lessons": "若干课",
              "no_scores": "lin 完成了 {lessons}，但这次没有拿到练习成绩。", "report": "lin 完成了 {lessons}，得分：{scores}。",
              "score": "{lesson} {value} 分", "score_separator": "，"},
    "en": {"first_reason": "Look up the progress first, then the scores.",
           "revised_reason": "The primary source is unavailable, so use the backup source.",
           "purpose_progress": "completed lessons", "purpose_scores": "score of each lesson", "separator": ", ",
           "some_lessons": "some lessons", "no_scores": "lin completed {lessons}, but no quiz scores came back this time.",
           "report": "lin completed {lessons}. Scores: {scores}.", "score": "{lesson} {value}", "score_separator": ", "},
}


def _plans(words):
    first = {"reason": words["first_reason"], "steps": [
        {"id": "s1", "tool": "fetch_progress", "arguments": {"learner": "lin"}, "purpose": words["purpose_progress"]},
        {"id": "s2", "tool": "fetch_quiz_scores", "arguments": {"learner": "lin", "source": "primary"},
         "purpose": words["purpose_scores"]}]}
    revised = {"reason": words["revised_reason"], "steps": [
        {"id": "s3", "tool": "fetch_quiz_scores", "arguments": {"learner": "lin", "source": "backup"},
         "purpose": words["purpose_scores"]}]}
    return first, revised


def _reply(content=None, calls=None):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return {"choices": [{"message": message, "finish_reason": "tool_calls" if calls else "stop"}]}


def _scores(scores, words):
    return words["score_separator"].join(words["score"].format(lesson=lesson, value=value)
                                          for lesson, value in scores.items())


def _write_report(user_text, words):
    # The task text has no braces, so the tool results are the JSON object from the first "{".
    data, _ = json.JSONDecoder().raw_decode(user_text[user_text.index("{"):])
    lessons = words["separator"].join(data.get("fetch_progress", {}).get("completed", [])) or words["some_lessons"]
    scores = data.get("fetch_quiz_scores", {}).get("scores")
    if not scores:
        return words["no_scores"].format(lessons=lessons)
    return words["report"].format(lessons=lessons, scores=_scores(scores, words))


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    words, t = WORDS[locale], texts_for(locale)
    first_plan, revised_plan = _plans(words)

    def complete(body, api_key):
        messages = body["messages"]
        system = messages[0]["content"]
        if system == t.planner_system:
            # A plan already in the planner's history means this request is a revision.
            revised = any(m["role"] == "assistant" for m in messages)
            return _reply(json.dumps(revised_plan if revised else first_plan, ensure_ascii=False))
        if system == t.writer_system:
            return _reply(_write_report(messages[-1]["content"], words))
        # ReAct baseline: decide the next step from the tool results seen so far.
        results = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        step = len(results)
        if step == 0:
            return _reply(calls=[{"id": "call_1", "type": "function", "function": {
                "name": "fetch_progress", "arguments": json.dumps({"learner": "lin"})}}])
        if step == 1 or (step == 2 and not results[-1]["ok"]):
            source = "primary" if step == 1 else "backup"
            return _reply(calls=[{"id": f"call_{step + 1}", "type": "function", "function": {
                "name": "fetch_quiz_scores", "arguments": json.dumps({"learner": "lin", "source": source})}}])
        lessons = words["separator"].join(results[0]["result"]["completed"])
        return _reply(words["report"].format(lessons=lessons, scores=_scores(results[-1]["result"]["scores"], words)))

    return complete
