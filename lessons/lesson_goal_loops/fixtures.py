"""Offline test model for goal-loops: serves automated tests only and does not stand for any real model.

Each exercise is a fixed script of worker steps, played one per model call: a step either proposes
read_note calls or hands in a card with a claim. The read_note calls really run; only the model's
choices are scripted. The false-done script copies stale values from the old minutes, claims done,
and then hands in the same card again, so the repeated-failure rule has something to catch.
"""
import json

from lessons.lesson_goal_loops.locales import texts_for

NOTICE = {"date": "2026-11-14", "room": "B204", "start_time": "14:30"}
# Values from the minutes of the last session: the right shape, the wrong source.
STALE = {"date": "2026-11-14", "room": "A101", "start_time": "14:00"}


def _read(*notes):
    return ("read", notes)


def _submit(card, status, note):
    return ("submit", card, status, note)


def script(exercise_id: str) -> list[tuple]:
    if exercise_id == "missing-info":
        phone = {"contact_phone": ""}
        return [_read("schedule", "booking"),
                _submit({"date": NOTICE["date"], "room": NOTICE["room"], "start_time": "", **phone}, "continue", "partial"),
                _read("speaker", "minutes"),
                _submit({**NOTICE, **phone}, "impossible", "missing")]
    if exercise_id == "false-done":
        return [_read("schedule", "minutes"),
                _submit(STALE, "done", "rushed"),
                _submit(STALE, "done", "rushed")]
    # reachable and tight-budget share one script: one new note per round, done in round 3.
    return [_read("schedule"), _submit({"date": NOTICE["date"], "room": "", "start_time": ""}, "continue", "partial"),
            _read("booking"), _submit({**NOTICE, "start_time": ""}, "continue", "partial"),
            _read("speaker"), _submit(NOTICE, "done", "full")]


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    steps = script(exercise_id)
    notes = texts_for(locale).fixture_notes
    position = 0
    calls = 0

    def complete(body, api_key):
        nonlocal position, calls
        # After the script ends, the last step repeats: a worker that keeps handing in the same card.
        step = steps[min(position, len(steps) - 1)]
        position += 1
        if step[0] == "read":
            tool_calls = []
            for note in step[1]:
                calls += 1
                tool_calls.append({"id": f"call_{calls}", "type": "function",
                                   "function": {"name": "read_note", "arguments": json.dumps({"note_id": note})}})
            message = {"role": "assistant", "content": None, "tool_calls": tool_calls}
            finish = "tool_calls"
        else:
            _, card, status, note = step
            message = {"role": "assistant", "content": json.dumps(
                {"card": card, "status": status, "note": notes[note]}, ensure_ascii=False)}
            finish = "stop"
        return {"choices": [{"message": message, "finish_reason": finish}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150}}

    return complete
