"""Streaming a model answer, stopping it, and what to do with the part that arrived.

Four scenarios, one run each. compare sends the same request streamed and not streamed and measures both.
long streams a long answer so the learner can press Stop or detach the event connection while it arrives.
stop ends the stream from the program (stop_when) after N chunks. continue does the same and then sends the
cut text back two ways: as if it were a finished message, and marked as incomplete.

The platform owns the stream: complete_stream records every chunk as it arrives, times the first one, and
turns a Stop request into a recorded "cancelled" response followed by RunCancelled. This runner never reads
the network, never writes the lifecycle events, and cannot report anything after a stop: events written
after a cancel are refused, so what was received before it lives in the platform's response event.
References: ai-agent-book chapter 6 (Apache-2.0: cancellation-based handling, "half-written output is not a legal
prefix") and its streaming-speech interruption manager (mark the turn that was cut). The checks and the
numbered-list task are written for this project.
"""
import time
from typing import Literal

from pydantic import Field

from course.execution import LessonInputs, RunContext, StreamResult
from lessons.lesson_streaming_cancel import reports
from lessons.lesson_streaming_cancel.analysis import analyse_partial, merge_marked, merge_plain
from lessons.lesson_streaming_cancel.locales import Texts, texts_for


class Inputs(LessonInputs):
    scenario: Literal["compare", "long", "stop", "continue"] = "compare"
    items: int = Field(default=6, ge=3, le=12)  # how many numbered items the task asks for
    detail: Literal["short", "long"] = "short"  # one sentence per item, or three
    stop_after_chunks: int = Field(default=12, ge=2, le=400)  # stop and continue: the program's own stop point


INPUT_MODEL = Inputs


def task_messages(t: Texts, values: Inputs) -> list[dict]:
    task = t.task.format(items=values.items, length=t.lengths[values.detail])
    return [{"role": "system", "content": t.system}, {"role": "user", "content": task}]


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    messages = task_messages(t, values)
    flow = {"compare": run_compare, "long": run_long, "stop": run_stop, "continue": run_continue}[values.scenario]
    return flow(context, t, values, messages)


def stop_at(limit: int):
    """stop_when for complete_stream: it sees the text so far and how many chunks arrived."""
    return lambda view: view["chunk_count"] >= limit


def run_compare(context: RunContext, t: Texts, values: Inputs, messages: list[dict]) -> str:
    # 1. Streamed: the platform records each chunk and times the first one and the first text.
    streamed = context.complete_stream({"messages": messages}, 1)
    # 2. The same request, answered in one piece. complete() returns only the body, so the runner times it.
    started = time.perf_counter()
    plain = context.complete({"messages": messages}, 2)
    plain_ms = round((time.perf_counter() - started) * 1000)
    payload, answer = reports.compare(t, context, values, streamed, plain, plain_ms)
    context.emit("lesson.report", payload, 2)
    return answer


def run_long(context: RunContext, t: Texts, values: Inputs, messages: list[dict]) -> str:
    # A Stop request raises RunCancelled out of this call: the received chunks are already recorded by then,
    # and nothing below runs. Only a stream that ends normally gets a report.
    streamed = context.complete_stream({"messages": messages}, 1)
    payload, answer = reports.long_run(t, context, values, streamed)
    context.emit("lesson.report", payload, 1)
    return answer


def run_stop(context: RunContext, t: Texts, values: Inputs, messages: list[dict]) -> str:
    # The program ends the stream itself: status "stopped", the run goes on, the text is what arrived.
    streamed = context.complete_stream({"messages": messages}, 1, stop_when=stop_at(values.stop_after_chunks))
    payload, answer = reports.stopped(t, context, values, streamed)
    context.emit("lesson.report", payload, 1)
    return answer


def run_continue(context: RunContext, t: Texts, values: Inputs, messages: list[dict]) -> str:
    # 1. Stream until the program's own stop point.
    first = context.complete_stream({"messages": messages}, 1, stop_when=stop_at(values.stop_after_chunks))
    partial = analyse_partial(first.text)
    gap = ("not_reached" if first.status != "stopped" else "no_text" if not first.text.strip()
           else "nothing_missing" if partial.next_item > values.items else None)
    if gap:
        # No stop, no text yet (a reasoning model may still be writing its reasoning), or everything was already
        # written: there is nothing to continue from, and no gap is invented.
        payload, answer = reports.nothing_to_continue(t, context, values, first, gap)
        context.emit("lesson.report", payload, 1)
        return answer
    # 2. Wrong way: the cut text goes back as a finished assistant message, and the reply is glued on.
    plain_messages = messages + [{"role": "assistant", "content": first.text},
                                 {"role": "user", "content": t.continue_plain}]
    plain = context.complete({"messages": plain_messages}, 2)
    # 3. Right way: no assistant prefix. One user message says the answer is incomplete, shows what was
    # written in full, and names the first item that is still missing.
    notice = marked_notice(t, values, first, partial)
    marked_messages = [messages[0], {"role": "user", "content": messages[1]["content"] + "\n\n" + notice}]
    marked = context.complete({"messages": marked_messages}, 3)
    merged_plain = merge_plain(first.text, reports.text_of(plain))
    merged_marked = merge_marked(partial, reports.text_of(marked))
    payload, answer = reports.continued(t, context, values, first, partial, marked_messages[1]["content"],
                                        plain, marked, merged_plain, merged_marked)
    context.emit("lesson.report", payload, 3)
    return answer


def marked_notice(t: Texts, values: Inputs, first: StreamResult, partial) -> str:
    if partial.kept_count == 0:
        return t.continue_marked_none.format(chunks=first.chunk_count, next_item=partial.next_item, items=values.items)
    return t.continue_marked.format(chunks=first.chunk_count, kept_count=partial.kept_count, kept=partial.kept,
                                    next_item=partial.next_item, items=values.items)
