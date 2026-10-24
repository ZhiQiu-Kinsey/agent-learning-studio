"""The lesson.report of each scenario and the program-written answer that goes with it.

Every number is read from what the platform measured or recorded (StreamResult, the response bodies) or from
a check Python ran on the text; nothing is estimated. A value the provider did not send is written as
"not reported", never as 0.
"""
from course.execution import RunContext, StreamResult
from lessons.lesson_streaming_cancel.analysis import (Partial, finish_reason_of, message_of, numbering, only_in_one,
                                                      parse_items, shape_of)
from lessons.lesson_streaming_cancel.locales import Texts

DASH = "—"


def text_of(response: dict) -> str:
    content = message_of(response).get("content")
    return content if isinstance(content, str) else ""


def usage_text(t: Texts, response: dict) -> str:
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return t.not_reported
    return t.usage_line.format(prompt=usage.get("prompt_tokens", DASH), completion=usage.get("completion_tokens", DASH),
                               total=usage.get("total_tokens", DASH))


def ms_or_none(t: Texts, value) -> int | str:
    return value if value is not None else t.not_received


def reason_text(t: Texts, response: dict) -> str:
    return finish_reason_of(response) or t.no_finish_marker


def check(identifier: str, label: str, passed: bool, detail: str) -> dict:
    return {"id": identifier, "label": label, "passed": passed, "detail": detail}


def note_metric(t: Texts, context: RunContext) -> dict:
    return {"label": t.label_note, "value": context.question or t.value_empty}


def stream_metrics(t: Texts, streamed: StreamResult) -> list[dict]:
    return [
        {"id": "status", "label": t.label_status, "value": t.statuses.get(streamed.status, streamed.status)},
        {"id": "chunk_count", "label": t.label_chunks, "value": streamed.chunk_count},
        {"id": "first_chunk_ms", "label": t.label_first_chunk, "value": ms_or_none(t, streamed.first_chunk_ms)},
        {"id": "first_token_ms", "label": t.label_first_token, "value": ms_or_none(t, streamed.first_token_ms)},
        {"id": "stream_ms", "label": t.label_stream_ms, "value": streamed.duration_ms},
        {"id": "chars", "label": t.label_chars, "value": len(streamed.text)},
        {"id": "finish_reason", "label": t.label_finish, "value": reason_text(t, streamed.response)},
        {"id": "usage", "label": t.label_usage, "value": usage_text(t, streamed.response)},
    ]


def compare(t: Texts, context: RunContext, values, streamed: StreamResult, plain: dict, plain_ms: int):
    shape_streamed, shape_plain = shape_of(streamed.response), shape_of(plain)
    only_streamed, only_plain = only_in_one(streamed.response, plain)
    first = streamed.first_token_ms
    checks = [
        check("stream_completed", t.check_completed,
              streamed.status == "completed" and finish_reason_of(streamed.response) is not None,
              t.detail_completed.format(status=t.statuses.get(streamed.status, streamed.status),
                                        reason=reason_text(t, streamed.response))),
        check("first_before_total", t.check_first_before_total, first is not None and first < streamed.duration_ms,
              t.detail_first_before_total.format(first=ms_or_none(t, first), total=streamed.duration_ms)),
        check("shape_match", t.check_shape, shape_streamed == shape_plain and shape_streamed["content_is_text"],
              t.detail_shape_ok if shape_streamed == shape_plain else t.detail_shape_bad.format(
                  streamed=shape_streamed, plain=shape_plain)),
    ]
    rows = [
        [t.row_first_chunk, ms_or_none(t, streamed.first_chunk_ms), DASH],
        [t.row_first_token, ms_or_none(t, first), DASH],
        [t.row_total, streamed.duration_ms, plain_ms],
        [t.row_finish, reason_text(t, streamed.response), reason_text(t, plain)],
        [t.row_usage, usage_text(t, streamed.response), usage_text(t, plain)],
        [t.row_chars, len(streamed.text), len(text_of(plain))],
        [t.row_items, len(parse_items(streamed.text)), len(parse_items(text_of(plain)))],
    ]
    payload = {
        "title": t.report_titles["compare"], "summary": t.report_summaries["compare"], "checks": checks,
        "metrics": stream_metrics(t, streamed) + [
            {"id": "plain_ms", "label": t.label_plain_ms, "value": plain_ms},
            {"id": "only_plain", "label": t.label_only_plain, "value": ", ".join(only_plain) or t.value_none},
            {"id": "only_streamed", "label": t.label_only_streamed, "value": ", ".join(only_streamed) or t.value_none},
            note_metric(t, context)],
        "table": {"columns": list(t.compare_columns), "rows": rows},
    }
    answer = t.answers["compare"].format(first=ms_or_none(t, first), total=streamed.duration_ms, chunks=streamed.chunk_count,
                                         plain=plain_ms)
    return payload, answer


def long_run(t: Texts, context: RunContext, values, streamed: StreamResult):
    whole = numbering(streamed.text, values.items)
    checks = [
        check("stream_completed", t.check_completed,
              streamed.status == "completed" and finish_reason_of(streamed.response) == "stop",
              t.detail_completed.format(status=t.statuses.get(streamed.status, streamed.status),
                                        reason=reason_text(t, streamed.response))),
        check("list_complete", t.check_list, whole["whole"],
              t.detail_list.format(expected=values.items, numbers=whole["numbers"])),
    ]
    payload = {"title": t.report_titles["long"], "summary": t.report_summaries["long"], "checks": checks,
               "metrics": stream_metrics(t, streamed) + [note_metric(t, context)]}
    return payload, t.answers["long"].format(chunks=streamed.chunk_count, chars=len(streamed.text),
                                             first=ms_or_none(t, streamed.first_token_ms), total=streamed.duration_ms)


def stopped(t: Texts, context: RunContext, values, streamed: StreamResult):
    reached = streamed.status == "stopped"
    items = parse_items(streamed.text)
    checks = [
        check("stop_reached", t.check_stop_reached, reached,
              t.detail_stop_reached.format(limit=values.stop_after_chunks, chunks=streamed.chunk_count,
                                           status=t.statuses.get(streamed.status, streamed.status))),
        check("finish_missing", t.check_finish_missing, finish_reason_of(streamed.response) is None,
              t.detail_finish_missing.format(reason=reason_text(t, streamed.response))),
    ]
    payload = {"title": t.report_titles["stop"], "summary": t.report_summaries["stop"], "checks": checks,
               "metrics": stream_metrics(t, streamed) + [
                   {"id": "stop_after", "label": t.label_stop_after, "value": values.stop_after_chunks},
                   {"id": "items_seen", "label": t.label_items_seen, "value": len(items)},
                   note_metric(t, context)]}
    key = "stop" if reached else "stop_not_reached"
    return payload, t.answers[key].format(limit=values.stop_after_chunks, chunks=streamed.chunk_count,
                                          chars=len(streamed.text), text=streamed.text.strip())


def nothing_to_continue(t: Texts, context: RunContext, values, streamed: StreamResult, reason: str):
    """The stop point was not reached, no text had arrived, or the list was already whole: no gap to continue from."""
    reached = streamed.status == "stopped"
    checks = [check("stop_reached", t.check_stop_reached, reached,
                    t.detail_stop_reached.format(limit=values.stop_after_chunks, chunks=streamed.chunk_count,
                                                 status=t.statuses.get(streamed.status, streamed.status)))]
    payload = {"title": t.report_titles["continue"], "summary": t.report_summaries["continue"], "checks": checks,
               "metrics": stream_metrics(t, streamed) + [
                   {"id": "stop_after", "label": t.label_stop_after, "value": values.stop_after_chunks},
                   note_metric(t, context)]}
    key = {"not_reached": "continue_not_reached", "no_text": "continue_no_text",
           "nothing_missing": "continue_nothing_missing"}[reason]
    return payload, t.answers[key].format(limit=values.stop_after_chunks, chunks=streamed.chunk_count)


def continued(t: Texts, context: RunContext, values, first: StreamResult, partial: Partial, sent_marked: str,
              plain: dict, marked: dict, merged_plain: str, merged_marked: str):
    plain_numbers, marked_numbers = numbering(merged_plain, values.items), numbering(merged_marked, values.items)
    plain_ok = plain_numbers["whole"] and finish_reason_of(plain) == "stop"
    marked_ok = marked_numbers["whole"] and finish_reason_of(marked) == "stop"

    def verdict(numbers: dict, ok: bool) -> str:
        if ok:
            return t.verdict_ok
        return t.verdict_bad.format(duplicates=numbers["duplicates"] or t.value_none, missing=numbers["missing"] or t.value_none,
                                    unfinished=numbers["unfinished"] or t.value_none)

    checks = [
        check("stop_reached", t.check_stop_reached, True,
              t.detail_stop_reached.format(limit=values.stop_after_chunks, chunks=first.chunk_count,
                                           status=t.statuses[first.status])),
        check("finish_missing", t.check_finish_missing, finish_reason_of(first.response) is None,
              t.detail_finish_missing.format(reason=reason_text(t, first.response))),
        check("marked_request", t.check_marked_request, t.marked_phrase in sent_marked,
              t.detail_marked_request.format(next_item=partial.next_item)),
        check("plain_merge", t.check_plain_merge, plain_ok,
              t.detail_merge.format(numbers=plain_numbers["numbers"], verdict=verdict(plain_numbers, plain_ok))),
        check("marked_merge", t.check_marked_merge, marked_ok,
              t.detail_merge.format(numbers=marked_numbers["numbers"], verdict=verdict(marked_numbers, marked_ok))),
    ]
    yes_no = lambda flag: t.flag_yes if flag else t.flag_no  # noqa: E731
    rows = [
        [t.handling_plain, yes_no(False), reason_text(t, plain), str(plain_numbers["numbers"]),
         str(plain_numbers["duplicates"] or t.value_none), str(plain_numbers["missing"] or t.value_none), str(plain_numbers["unfinished"] or t.value_none)],
        [t.handling_marked, yes_no(True), reason_text(t, marked), str(marked_numbers["numbers"]),
         str(marked_numbers["duplicates"] or t.value_none), str(marked_numbers["missing"] or t.value_none), str(marked_numbers["unfinished"] or t.value_none)],
    ]
    payload = {
        "title": t.report_titles["continue"], "summary": t.report_summaries["continue"], "checks": checks,
        "metrics": stream_metrics(t, first) + [
            {"id": "stop_after", "label": t.label_stop_after, "value": values.stop_after_chunks},
            {"id": "kept_count", "label": t.label_kept, "value": partial.kept_count},
            {"id": "next_item", "label": t.label_next_item, "value": partial.next_item},
            {"id": "cut_line", "label": t.label_cut_line, "value": partial.cut_line or t.value_none},
            note_metric(t, context)],
        "table": {"columns": list(t.continue_columns), "rows": rows},
    }
    answer = (t.answers["continue_ok"].format(items=values.items, text=merged_marked) if marked_ok
              else t.answers["continue_bad"])
    return payload, answer
