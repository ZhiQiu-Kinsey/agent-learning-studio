"""Send similar requests in a row and compare the cache hits the provider reports for three request layouts.

The three arms use exactly the same rules, handbook and questions; only the position of the "dynamic" line changes,
and whether a warmup request goes first. Hits come only from the cache fields of the responses; the runner checks
locally, with a hash, whether the prefix is identical character for character.
"""
import hashlib
import json
import os
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext
from course.i18n import localized_file
from lessons.lesson_prompt_caching.cache_usage import hit_ratio, normalize_cache_usage
from lessons.lesson_prompt_caching.locales import texts_for


class Inputs(LessonInputs):
    layout: Literal["dynamic_first", "stable_prefix", "warmup"] = "stable_prefix"
    repeats: int = Field(default=4, ge=3, le=5)
    isolate_run: bool = True


INPUT_MODEL = Inputs
HANDBOOKS = Path(__file__).with_name("locales") / "handbook"


def load_handbook(locale: str) -> str:
    """The handbook in the run's language: locales/handbook/<locale>.md."""
    return localized_file(HANDBOOKS, locale, ".md").read_text(encoding="utf-8")


def dynamic_line(t, number: int) -> str:
    """The one line that differs in every request: request number and send time."""
    return t.dynamic_line.format(number=number, sent_at=datetime.now().astimezone().isoformat(timespec="seconds"))


def build_messages(t, handbook: str, layout: str, session: str, question: str, dynamic: str) -> list[dict]:
    """The three arms use exactly the same rules, handbook and question; only the dynamic line moves."""
    stable = f"{t.session_tag.format(session=session)}\n{t.rules}\n\n{handbook}"
    if layout == "dynamic_first":
        # Dynamic line as the first line of the system prompt: the request number already differs, so the
        # identical handbook after it cannot be reused.
        return [{"role": "system", "content": f"{dynamic}\n{stable}"},
                {"role": "user", "content": question}]
    # Dynamic line moved to the end of the last user message: rules and handbook become a start identical every time.
    return [{"role": "system", "content": stable},
            {"role": "user", "content": t.question_with_dynamic.format(question=question, dynamic=dynamic)}]


def _serialize(messages: list[dict]) -> str:
    return json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def prefix_hash(messages: list[dict]) -> str:
    """All messages before the last one (here: system), serialized, first 12 hex digits of sha256."""
    return hashlib.sha256(_serialize(messages[:-1]).encode("utf-8")).hexdigest()[:12]


def shared_prefix_chars(previous: list[dict] | None, current: list[dict]) -> int | None:
    """Characters identical from the start compared with the previous request; the first request has nothing to compare."""
    if previous is None:
        return None
    return len(os.path.commonprefix([_serialize(previous), _serialize(current)]))


def event_kind(cache: dict) -> str:
    """Three outcomes, three events: a hit was reported, 0 was reported, nothing was reported."""
    if cache["cached_tokens"] is None:
        return "lesson.cache_unreported"
    return "lesson.cache_hit" if cache["cached_tokens"] > 0 else "lesson.cache_miss"


def run(context: RunContext) -> str:
    t, values = texts_for(context.locale), Inputs.model_validate(context.inputs)
    handbook = load_handbook(context.locale)
    # The session tag stays the same within a run, so the prefix holds; a new one per run makes earlier runs' cache useless.
    session = secrets.token_hex(4) if values.isolate_run else t.not_isolated
    plan = ([t.purpose_warmup] if values.layout == "warmup" else []) + [t.purpose_measure] * values.repeats
    questions = iter(t.questions)
    records, previous = [], None
    for number, purpose in enumerate(plan, 1):
        context.check_cancelled()
        # 1. Assemble: rules, handbook and questions are fixed; only the dynamic line differs each time.
        question = t.warmup_question if purpose == t.purpose_warmup else next(questions)
        messages = build_messages(t, handbook, values.layout, session, question, dynamic_line(t, number))
        # 2. Before sending, note the prefix fingerprint locally and compare with the previous request.
        record = {"round": number, "purpose": purpose, "prefix_hash": prefix_hash(messages),
                  "shared_prefix_chars": shared_prefix_chars(previous, messages)}
        # 3. Send; the answer needs a sentence or two, so cap the output to keep generation time from dominating.
        started = time.perf_counter()
        response = context.complete({"messages": messages, "temperature": 0, "max_tokens": 200},
                                    round_number=number)
        record["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        # 4. Read the cache fields the provider reported: nothing reported is None, not 0.
        cache = normalize_cache_usage(response.get("usage"))
        record.update(cache, ratio=hit_ratio(cache))
        kind = event_kind(cache)
        # The first request that reports a hit carries first_hit; the find-the-error check counts only that one.
        if kind == "lesson.cache_hit" and not any(item.get("first_hit") for item in records):
            record["first_hit"] = True
        context.emit(kind, record, number)
        records.append(record)
        previous = messages
    _report(context, values, session, records)
    return t.answer.format(count=len(records), layout=t.layout_names[values.layout])


def _cells(t, record: dict) -> list:
    ratio = record["ratio"]
    return [record["round"], record["purpose"], record["prefix_hash"],
            "—" if record["shared_prefix_chars"] is None else record["shared_prefix_chars"],
            t.value_not_reported if record["input_tokens"] is None else record["input_tokens"],
            t.value_not_reported if record["cached_tokens"] is None else record["cached_tokens"],
            (t.value_not_reported if record["cached_tokens"] is None else "—") if ratio is None else f"{ratio:.1%}",
            record["elapsed_ms"]]


def _report(context: RunContext, values: Inputs, session: str, records: list[dict]) -> None:
    """Platform: arrange the per-request records into the lab report; every item can be checked in its event."""
    t = texts_for(context.locale)
    measured = [record for record in records if record["purpose"] == t.purpose_measure]
    reported = [record for record in records if record["cached_tokens"] is not None]
    hashes = {record["prefix_hash"] for record in records}
    missing = [str(record["round"]) for record in records if record["cached_tokens"] is None]
    checks = [
        {"id": "prefix_hash", "label": t.check_hash, "passed": len(hashes) == 1,
         "detail": (t.check_hash_detail_one if len(hashes) == 1 else t.check_hash_detail).format(
             count=len(records), distinct=len(hashes),
             suffix=t.hash_suffix_warmup if values.layout == "warmup" else t.hash_suffix_plain)},
        {"label": t.check_reported, "passed": not missing,
         "detail": t.check_reported_all if not missing else
         t.check_reported_missing.format(rounds=t.list_separator.join(missing))},
    ]
    if reported:
        seen, unexplained = set(), []
        for record in records:
            if record["cached_tokens"] and record["prefix_hash"] not in seen:
                unexplained.append(t.unexplained_item.format(round=record["round"], cached=record["cached_tokens"]))
            seen.add(record["prefix_hash"])
        checks.append({
            "label": t.check_explained, "passed": not unexplained,
            "detail": t.check_explained_all if not unexplained else
            t.check_explained_detail.format(items=t.list_separator.join(unexplained))})
    known = [record for record in measured if record["cached_tokens"] is not None and record["input_tokens"]]
    total_ratio = (f"{sum(r['cached_tokens'] for r in known) / sum(r['input_tokens'] for r in known):.1%}"
                   if known else t.value_not_reported)
    hits = (sum(1 for record in measured if record["cached_tokens"]) if any(
        record["cached_tokens"] is not None for record in measured) else t.value_not_reported)
    fields = sorted({record["field"] for record in reported})
    offline = context.mode == "offline"
    layout = t.layout_names[values.layout]
    context.emit("lesson.report", {
        "title": t.report_title.format(layout=layout),
        "summary": t.report_summary + (t.report_summary_offline if offline else ""),
        "checks": checks,
        "metrics": [
            {"label": t.label_mode, "value": t.value_mode_offline if offline else t.value_mode_live},
            {"label": t.label_layout, "value": layout},
            {"label": t.label_model_calls, "value": len(records)},
            {"label": t.label_reported, "value": f"{len(reported)} / {len(records)}"},
            {"label": t.label_hits, "value": hits},
            {"label": t.label_ratio, "value": total_ratio},
            {"label": t.label_fields, "value": t.list_separator.join(fields) or t.value_not_reported},
            {"label": t.label_session, "value": session},
            {"label": t.label_note, "value": context.question or t.value_empty},
        ],
        "table": {
            "columns": list(t.columns),
            "rows": [_cells(t, record) for record in records],
        },
    })
