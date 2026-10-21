"""The two local tools of this lesson. They really run; only the waiting time is injected.

read_note stands in for a slow source (a network drive, a rate-limited API): the note it returns is real data, the
delay is the delay_ms argument, so the event shows exactly how long the tool was told to wait. build_sheet is a plain
function that needs other tasks' results, which is what makes it dependent. Both receive the run's message catalog as a
positional-only first argument (bound with functools.partial); a stop signal reaches read_note through ``stop``.
"""
import threading
import time
from functools import partial

from lessons.lesson_async_concurrency.locales import Texts

# A locked note is found out early: the tool notices the lock after this share of its delay, not at the end.
LOCK_PROBE_SHARE = 0.3


class UnknownNote(ValueError):
    """No note exists for this lesson."""


class NoteLocked(ValueError):
    """The note exists but is locked: a failure this lesson can ask for, always named in the call itself."""


class MissingInput(ValueError):
    """The task ran without the values it depends on."""


class TaskStopped(ValueError):
    """The scheduler stopped this task; the tool gave up at its next check instead of finishing."""


def read_note(t: Texts, /, lesson: str, delay_ms: int, lock: bool = False, *, stop: threading.Event) -> dict:
    """Return one lesson's note after waiting delay_ms; stop.wait() ends the wait the moment a stop is requested."""
    if lesson not in t.notes:
        raise UnknownNote(t.unknown_note.format(lesson=lesson))
    started = time.perf_counter()
    # 1. Wait on the stop signal, not with time.sleep: a sleeping thread cannot hear a stop until it wakes up.
    wait_s = delay_ms * (LOCK_PROBE_SHARE if lock else 1) / 1000
    if stop.wait(wait_s):
        raise TaskStopped(t.task_stopped.format(ms=round((time.perf_counter() - started) * 1000)))
    # 2. A locked note fails after the probe; the error says which note and why.
    if lock:
        raise NoteLocked(t.note_locked.format(lesson=lesson))
    note = t.notes[lesson]
    return {"lesson": lesson, "note": note, "chars": len(note),
            "waited_ms": round((time.perf_counter() - started) * 1000)}


def build_sheet(t: Texts, /, lessons: list, entries: list, allow_partial: bool = False) -> dict:
    """Assemble the review sheet from one entry per lesson; a missing entry is an error unless partial is allowed.

    With allow_partial the sheet is still built, but it says complete=false and lists what is missing, so nobody
    downstream can mistake it for the whole sheet.
    """
    if not isinstance(lessons, list) or not isinstance(entries, list):
        raise ValueError(t.sheet_bad_arguments)
    texts = {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("lesson") not in lessons:
            raise ValueError(t.sheet_bad_entry)
        if isinstance(entry.get("text"), str) and entry["text"].strip():
            texts[entry["lesson"]] = entry["text"].strip()
    missing = [lesson for lesson in lessons if lesson not in texts]
    if missing and not allow_partial:
        raise MissingInput(t.sheet_missing_input.format(missing=t.list_separator.join(missing)))
    return {"complete": not missing, "missing": missing,
            "lines": [t.sheet_line.format(lesson=lesson, text=texts[lesson]) for lesson in lessons if lesson in texts]}


def make_tools(t: Texts, stop: threading.Event) -> dict:
    """The allow-list one task may call: the same functions for every task, each with its own stop signal."""
    return {"read_note": partial(read_note, t, stop=stop), "build_sheet": partial(build_sheet, t)}
