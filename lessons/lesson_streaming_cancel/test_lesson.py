"""Behavior tests for streaming-cancel: deterministic stream data, real Python checks, the platform's real stop paths.

The offline stream fixture sleeps a few milliseconds between chunks so the platform's timers have something to
measure; the cancel tests use their own slow or gated streams. Nothing here calls a real model.
"""
import asyncio
import json
import re
import threading
import time
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_streaming_cancel import analysis, runtime
from lessons.lesson_streaming_cancel.fixtures import answer_lines, chunk, create_completion, create_stream, pieces
from lessons.lesson_streaming_cancel.locales import texts_for

ZH, EN = texts_for("zh-CN"), texts_for("en")
CJK = re.compile(r"[　-〿㐀-鿿＀-￯]")
SPEC = {"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}
EXERCISE_INPUTS = {
    "stream-vs-block": {"scenario": "compare", "items": 6, "detail": "short"},
    "long-stream": {"scenario": "long", "items": 10, "detail": "long"},
    "stop-after-n": {"scenario": "stop", "items": 8, "detail": "short", "stop_after_chunks": 12},
    "partial-continue": {"scenario": "continue", "items": 8, "detail": "short", "stop_after_chunks": 40},
}


def run_case(exercise_id=None, inputs=None, locale="zh-CN", stream=None, completion=None, cancelled=lambda: False,
             on_event=None, cancel_reason=lambda: None):
    """Run the lesson once against the fixture (or the given stream and completion) and return (answer, events)."""
    events = []
    values = validate_inputs(runtime, inputs if inputs is not None else EXERCISE_INPUTS[exercise_id])
    stream = stream or create_stream(exercise_id, values, locale)
    completion = completion or create_completion(exercise_id, values, locale)

    def emit(kind, data, number):
        events.append((kind, data, number))
        if on_event:
            on_event(kind, data, number)

    context = RunContext(
        lesson_id="streaming-cancel", exercise_id=exercise_id or "custom", question="", mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="", completion=completion,
        stream_completion=stream, emit_event=emit, cancelled=cancelled, cancel_reason=cancel_reason,
        max_model_calls=3, locale=locale)
    answer = execute_lesson(SPEC, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def report(events):
    return of(events, "lesson.report")[-1]


def checks(events):
    return {item["id"]: item for item in report(events)["checks"]}


def metrics(events):
    return {item["id"]: item["value"] for item in report(events)["metrics"] if "id" in item}


def streamed_text(events):
    return "".join(data["text"] for data in of(events, "response_delta"))


def requests(events):
    return [data["body"] for data in of(events, "request")]


def reply(text, reason="stop"):
    return {"choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": reason}]}


class InputTests(unittest.TestCase):
    def test_inputs_are_validated_and_unknown_fields_rejected(self):
        for bad in ({"scenario": "other"}, {"items": 2}, {"items": 13}, {"detail": "medium"},
                    {"stop_after_chunks": 1}, {"stop_after_chunks": 401}, {"surprise": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                runtime.Inputs.model_validate(bad)
        values = runtime.Inputs.model_validate({})
        self.assertEqual((values.scenario, values.items, values.detail, values.stop_after_chunks),
                         ("compare", 6, "short", 12))

    def test_every_exercise_preset_is_valid(self):
        spec = json.load(open("lessons/lesson_streaming_cancel/lesson.json", encoding="utf-8"))
        defaults = spec["input_defaults"]
        self.assertEqual({item["id"] for item in spec["exercises"]}, set(EXERCISE_INPUTS))
        for item in spec["exercises"]:
            validate_inputs(runtime, {**defaults, **item["inputs"]})
            self.assertEqual(item["inputs"], EXERCISE_INPUTS[item["id"]])
        self.assertEqual(spec["runtime"]["max_rounds"], 3)
        self.assertEqual(set(spec["testing"]), {"completion_factory", "stream_factory"})


class AnalysisTests(unittest.TestCase):
    def test_items_are_numbered_lines_only(self):
        text = "1. 第一条。\n2) 第二条。\n3、第三条。\n没有编号的行\nx 4. 不在行首"
        self.assertEqual([number for number, _ in analysis.parse_items(text)], [1, 2, 3])
        self.assertEqual(analysis.parse_items("1. a b\n  2. c")[1], (2, "c"))

    def test_clean_end_covers_both_languages(self):
        for text in ("完了。", "Done.", "Done!  ", "好吗？", "Really?"):
            self.assertTrue(analysis.clean_end(text), text)
        for text in ("没写完", "not finished", "", "1. step"):
            self.assertFalse(analysis.clean_end(text), text)

    def test_partial_cut_in_the_middle_keeps_only_whole_lines(self):
        partial = analysis.analyse_partial("1. 第一条。\n2. 第二条。\n3. 第三条写到一")
        self.assertEqual((partial.kept, partial.kept_count, partial.next_item), ("1. 第一条。\n2. 第二条。", 2, 3))
        self.assertEqual(partial.cut_line, "3. 第三条写到一")

    def test_partial_that_stops_at_a_sentence_end_keeps_everything(self):
        partial = analysis.analyse_partial("1. 第一条。\n2. 第二条。\n")
        self.assertEqual((partial.kept_count, partial.next_item, partial.cut_line), (2, 3, None))
        self.assertEqual(partial.kept, "1. 第一条。\n2. 第二条。")

    def test_partial_without_any_item_asks_for_the_first(self):
        partial = analysis.analyse_partial("好的，下面是")
        self.assertEqual((partial.kept, partial.kept_count, partial.next_item), ("", 0, 1))
        self.assertEqual(analysis.analyse_partial("").cut_line, None)

    def test_numbering_names_duplicates_missing_and_unfinished_lines(self):
        whole = analysis.numbering("1. a.\n2. b.\n3. c.", 3)
        self.assertTrue(whole["whole"])
        broken = analysis.numbering("1. a.\n3. c\n3. c.\n", 4)
        self.assertEqual((broken["duplicates"], broken["missing"], broken["unfinished"], broken["whole"]),
                         ([3], [2, 4], [3], False))
        self.assertFalse(analysis.numbering("1. a.\n2. b.", 3)["whole"])

    def test_merges_differ_in_what_they_keep(self):
        partial = analysis.analyse_partial("1. 甲。\n2. 乙写到")
        self.assertEqual(analysis.merge_plain(partial.text, "\n2. 乙。"), "1. 甲。\n2. 乙写到\n2. 乙。")
        self.assertEqual(analysis.merge_marked(partial, "\n2. 乙。\n3. 丙。\n"), "1. 甲。\n2. 乙。\n3. 丙。")
        self.assertEqual(analysis.merge_marked(analysis.analyse_partial("1. 写到"), "1. 甲。"), "1. 甲。")

    def test_response_shape_helpers(self):
        streamed = {**reply("x."), "created": 1}
        plain = {**reply("x."), "object": "chat.completion"}
        self.assertEqual(analysis.shape_of(streamed), analysis.shape_of(plain))
        self.assertEqual(analysis.only_in_one(streamed, plain), (["created"], ["object"]))
        self.assertEqual(analysis.shape_of({"choices": [{"message": {"role": "assistant", "content": None}}]}),
                         {"role": "assistant", "content_is_text": False, "finish_reason_is_text": False})
        self.assertEqual(analysis.finish_reason_of({}), None)


class FixtureTests(unittest.TestCase):
    def test_answer_lines_follow_the_requested_shape(self):
        for locale in ("zh-CN", "en"):
            short, long = answer_lines(locale, 5, "short"), answer_lines(locale, 5, "long")
            self.assertEqual([number for number, _ in analysis.parse_items("\n".join(short))], [1, 2, 3, 4, 5])
            self.assertTrue(all(len(b) > len(a) for a, b in zip(short, long)))
            self.assertEqual(len(answer_lines(locale, 12, "short")), 12)
        self.assertIsNone(CJK.search("\n".join(answer_lines("en", 12, "long"))))

    def test_stream_has_the_shape_of_a_compatible_stream(self):
        chunks = list(create_stream("x", {"items": 3, "detail": "short"}, "en")(None, None))
        self.assertEqual(chunks[0]["choices"][0]["delta"], {"role": "assistant", "content": ""})
        self.assertEqual(chunks[-2]["choices"][0]["finish_reason"], "stop")
        self.assertEqual(chunks[-1]["choices"], [])
        self.assertIn("total_tokens", chunks[-1]["usage"])
        joined = "".join(item["choices"][0]["delta"].get("content", "") for item in chunks[:-1])
        self.assertEqual(joined, "\n".join(answer_lines("en", 3, "short")))
        self.assertEqual("".join(pieces(joined, "en")), joined)


class OfflineRunTests(unittest.TestCase):
    def test_every_exercise_runs_in_both_languages_with_real_checks(self):
        for exercise_id in EXERCISE_INPUTS:
            for locale in ("zh-CN", "en"):
                with self.subTest(exercise=exercise_id, locale=locale):
                    answer, events = run_case(exercise_id, locale=locale)
                    self.assertTrue(answer)
                    self.assertEqual(events[0][0], "request")
                    self.assertTrue(events[0][1]["stream"])
                    self.assertEqual([kind for kind, _, _ in events][-2:], ["lesson.report", "answer"])
                    self.assertTrue(report(events)["checks"])
                    if locale == "en":
                        self.assertIsNone(CJK.search(json.dumps([answer, events], ensure_ascii=False)))
                    else:
                        self.assertTrue(CJK.search(answer))

    def test_compare_streams_first_then_asks_again_without_streaming(self):
        for locale, t in (("zh-CN", ZH), ("en", EN)):
            answer, events = run_case("stream-vs-block", locale=locale)
            sent = requests(events)
            self.assertEqual([body.get("stream") for body in sent], [True, None])
            self.assertEqual(sent[0]["stream_options"], {"include_usage": True})
            self.assertNotIn("stream_options", sent[1])
            self.assertEqual(sent[0]["messages"], sent[1]["messages"])
            self.assertEqual([number for kind, _, number in events if kind == "request"], [1, 2])
            found = checks(events)
            self.assertEqual(set(found), {"stream_completed", "first_before_total", "shape_match"})
            self.assertTrue(all(item["passed"] for item in found.values()), found)
            values = metrics(events)
            streamed = of(events, "response")[0]["stream"]
            # The numbers in the report are the platform's own measurements of the stream, copied unchanged.
            self.assertEqual(values["first_chunk_ms"], streamed["first_chunk_ms"])
            self.assertEqual(values["first_token_ms"], streamed["first_token_ms"])
            self.assertEqual(values["chunk_count"], streamed["chunk_count"])
            self.assertLessEqual(values["first_chunk_ms"], values["first_token_ms"])
            self.assertLess(values["first_token_ms"], values["stream_ms"])
            self.assertEqual(values["only_plain"], "object")
            table = report(events)["table"]
            self.assertEqual(len(table["columns"]), 3)
            self.assertEqual(table["rows"][2][1], values["stream_ms"])
            self.assertEqual(table["rows"][2][2], values["plain_ms"])
            self.assertIn(str(values["first_token_ms"]), answer)

    def test_compare_reports_a_different_shape_and_a_missing_usage_honestly(self):
        script = reply(None)
        script["choices"][0]["message"]["content"] = None
        _, events = run_case("stream-vs-block", completion=lambda body, key: script)
        found = checks(events)
        self.assertFalse(found["shape_match"]["passed"])
        self.assertIn("content_is_text", found["shape_match"]["detail"])
        no_usage = reply("1. a.\n2. b.")
        _, events = run_case("stream-vs-block", completion=lambda body, key: no_usage)
        table = report(events)["table"]
        self.assertEqual(table["rows"][4][2], ZH.not_reported)
        self.assertNotEqual(table["rows"][4][1], ZH.not_reported)
        _, events = run_case("stream-vs-block", locale="en", completion=lambda body, key: no_usage)
        self.assertEqual(report(events)["table"]["rows"][4][2], "not reported")

    def test_stream_without_usage_chunk_is_reported_as_not_reported(self):
        def stream(body, key):
            yield chunk("", role="assistant")
            yield chunk("1. 一。\n2. 二。", finish="stop")
        for locale, t in (("zh-CN", ZH), ("en", EN)):
            _, events = run_case(inputs={"scenario": "long", "items": 3}, locale=locale, stream=stream)
            self.assertEqual(metrics(events)["usage"], t.not_reported)
            self.assertNotIn("usage", of(events, "response")[0]["body"])
            self.assertEqual(metrics(events)["usage"], "not reported" if locale == "en" else "未报告")

    def test_long_stream_reports_a_whole_list_only_when_it_is_whole(self):
        _, events = run_case("long-stream")
        self.assertTrue(checks(events)["stream_completed"]["passed"])
        self.assertTrue(checks(events)["list_complete"]["passed"])
        self.assertEqual(metrics(events)["finish_reason"], "stop")

        def short_list(body, key):
            yield chunk("1. 只有一条。", role="assistant")
            yield chunk("", finish="length")
        _, events = run_case(inputs={"scenario": "long", "items": 10}, stream=short_list)
        found = checks(events)
        self.assertFalse(found["stream_completed"]["passed"])
        self.assertFalse(found["list_complete"]["passed"])
        self.assertEqual(metrics(events)["finish_reason"], "length")

    def test_stop_ends_the_stream_in_the_program_and_the_run_goes_on(self):
        answer, events = run_case("stop-after-n")
        response = of(events, "response")[0]
        self.assertEqual((response["stream"]["status"], response["stream"]["stop_reason"]), ("stopped", "lesson"))
        self.assertEqual(response["stream"]["chunk_count"], 12)
        self.assertIsNone(response["body"]["choices"][0]["finish_reason"])
        self.assertNotIn("usage", response["body"])
        self.assertNotIn("cancel_reason", response["stream"])
        received = [item for data in of(events, "response_delta") for item in data["chunks"]]
        self.assertEqual(len(received), 12)
        expected = "".join(item["choices"][0]["delta"].get("content", "") for item in
                           list(create_stream("x", EXERCISE_INPUTS["stop-after-n"], "zh-CN")(None, None))[:12])
        self.assertEqual(response["body"]["choices"][0]["message"]["content"], expected)
        self.assertIn(expected, answer)
        self.assertIn("部分结果", answer)
        found = checks(events)
        self.assertTrue(found["stop_reached"]["passed"] and found["finish_missing"]["passed"])
        self.assertEqual(metrics(events)["usage"], "未报告")
        self.assertEqual(metrics(events)["stop_after"], 12)

    def test_stop_point_past_the_end_leaves_a_whole_stream(self):
        inputs = {**EXERCISE_INPUTS["stop-after-n"], "items": 3, "stop_after_chunks": 400}
        for locale in ("zh-CN", "en"):
            answer, events = run_case(inputs=inputs, locale=locale)
            self.assertEqual(of(events, "response")[0]["stream"]["status"], "completed")
            self.assertFalse(checks(events)["stop_reached"]["passed"])
            self.assertNotIn(streamed_text(events).strip(), answer)

    def test_continue_sends_the_cut_text_back_two_ways(self):
        for locale, t in (("zh-CN", ZH), ("en", EN)):
            answer, events = run_case("partial-continue", locale=locale)
            first, plain, marked = requests(events)
            partial = of(events, "response")[0]["body"]["choices"][0]["message"]["content"]
            info = analysis.analyse_partial(partial)
            self.assertIsNotNone(info.cut_line, "the preset stops in the middle of a line")
            # The plain way puts the cut text back as a finished assistant message, then says "continue".
            self.assertEqual(plain["messages"][-2:], [{"role": "assistant", "content": partial},
                                                     {"role": "user", "content": t.continue_plain}])
            self.assertNotIn("stream", plain)
            # The marked way has no assistant prefix: one user message names what was written and what is missing.
            self.assertEqual([m["role"] for m in marked["messages"]], ["system", "user"])
            notice = marked["messages"][1]["content"]
            self.assertTrue(notice.startswith(first["messages"][1]["content"]))
            self.assertIn(t.marked_phrase, notice)
            self.assertIn(info.kept, notice)
            self.assertNotIn(info.cut_line, notice)
            self.assertIn(str(info.next_item), notice)
            found = checks(events)
            self.assertTrue(found["marked_request"]["passed"])
            self.assertFalse(found["plain_merge"]["passed"])
            self.assertTrue(found["marked_merge"]["passed"])
            rows = report(events)["table"]["rows"]
            self.assertEqual([row[1] for row in rows], [t.flag_no, t.flag_yes])
            self.assertEqual(rows[0][4], f"[{info.next_item}]")
            self.assertIn("1. ", answer)
            self.assertEqual([number for number, _ in analysis.parse_items(answer)], list(range(1, 9)))
            self.assertEqual([number for kind, _, number in events if kind == "request"], [1, 2, 3])

    def test_the_plain_merge_passes_when_the_model_really_continues_cleanly(self):
        # The check is not rigged against the plain way: a reply that finishes the cut line passes it.
        def completion(body, key):
            if any(m["role"] == "assistant" for m in body["messages"]):
                cut = body["messages"][-2]["content"].split("\n")[-1]
                full = answer_lines("zh-CN", 8, "short")[int(cut.split(".")[0]) - 1]
                return reply(full[len(cut):] + "\n" + "\n".join(answer_lines("zh-CN", 8, "short")[int(cut.split(".")[0]):]))
            return create_completion("partial-continue", EXERCISE_INPUTS["partial-continue"])(body, key)
        _, events = run_case("partial-continue", completion=completion)
        self.assertTrue(checks(events)["plain_merge"]["passed"])
        self.assertTrue(checks(events)["marked_merge"]["passed"])

    def test_a_marked_reply_that_restarts_fails_its_check_and_is_not_offered_as_the_answer(self):
        def completion(body, key):
            if any(m["role"] == "assistant" for m in body["messages"]):
                return create_completion("partial-continue", EXERCISE_INPUTS["partial-continue"])(body, key)
            return reply("\n".join(answer_lines("zh-CN", 8, "short")))  # starts over at item 1
        answer, events = run_case("partial-continue", completion=completion)
        self.assertFalse(checks(events)["marked_merge"]["passed"])
        self.assertEqual(answer, ZH.answers["continue_bad"])
        # A continuation request that did not finish normally cannot pass either, whatever the numbers say.
        _, events = run_case("partial-continue", completion=lambda body, key: reply("1. a.", reason="length"))
        self.assertFalse(checks(events)["marked_merge"]["passed"])

    def test_continue_stops_early_when_there_is_nothing_to_continue_from(self):
        inputs = {**EXERCISE_INPUTS["partial-continue"], "stop_after_chunks": 400}
        for locale in ("zh-CN", "en"):
            answer, events = run_case(inputs=inputs, locale=locale)
            self.assertEqual(len(requests(events)), 1, "no continuation request without a cut")
            self.assertFalse(checks(events)["stop_reached"]["passed"])
            self.assertIsNone(report(events).get("table"))
        # The stop point lands exactly when the last item is written, before the finish chunk arrives.
        items = 3
        limit = 1 + len(pieces("\n".join(answer_lines("zh-CN", items, "short")), "zh-CN"))
        _, events = run_case(inputs={**inputs, "items": items, "stop_after_chunks": limit})
        self.assertEqual(of(events, "response")[0]["stream"]["status"], "stopped")
        self.assertEqual(len(requests(events)), 1, "the list is already whole: nothing is missing")

    def test_continue_does_not_invent_a_gap_when_only_reasoning_has_arrived(self):
        def stream(body, key):
            yield chunk("", role="assistant")
            for _ in range(10):
                yield {"id": "x", "object": "chat.completion.chunk",
                       "choices": [{"index": 0, "delta": {"reasoning_content": "hm"}, "finish_reason": None}]}
            yield chunk("1. a.", finish="stop")
        for locale, t in (("zh-CN", ZH), ("en", EN)):
            inputs = {**EXERCISE_INPUTS["partial-continue"], "stop_after_chunks": 5}
            answer, events = run_case(inputs=inputs, locale=locale, stream=stream)
            self.assertEqual(len(requests(events)), 1, "an empty cut text is never sent back as an assistant message")
            self.assertEqual(answer, t.answers["continue_no_text"].format(limit=5, chunks=5))
            self.assertEqual(of(events, "response")[0]["stream"]["status"], "stopped")
            # Reasoning text counts as the first token: the platform measured it, so the report shows a number.
            self.assertIsInstance(metrics(events)["first_token_ms"], int)
            self.assertEqual(metrics(events)["chars"], 0)

    def test_continue_with_no_whole_item_uses_the_short_notice(self):
        _, events = run_case(inputs={**EXERCISE_INPUTS["partial-continue"], "stop_after_chunks": 6})
        marked = requests(events)[2]["messages"][1]["content"]
        self.assertIn(ZH.marked_phrase, marked)
        self.assertNotIn("已完整写出的前", marked)
        self.assertEqual(metrics(events)["kept_count"], 0)
        self.assertEqual(metrics(events)["next_item"], 1)
        self.assertTrue(checks(events)["marked_merge"]["passed"])

    def test_model_budget_is_three_calls(self):
        # compare uses 2 and continue uses 3; a fourth request would be refused by the platform.
        for exercise_id, count in (("stream-vs-block", 2), ("partial-continue", 3), ("long-stream", 1)):
            _, events = run_case(exercise_id)
            self.assertEqual(len(requests(events)), count, exercise_id)


class StopTests(unittest.TestCase):
    """A Stop request raised by the platform: what was received stays recorded, nothing after it does."""

    def slow(self, late):
        def stream(body, key):
            yield chunk("", role="assistant")
            for piece in ("1. 一。", "\n2. 二", "。\n3. 三"):
                yield chunk(piece)
            time.sleep(2.0)  # far later than the idle flush (0.25 s) that triggers the stop, even on a loaded machine
            yield chunk(late)
            yield chunk("", finish="stop")
        return stream

    def cancel_after_chunk(self, number):
        state = {"cancelled": False}

        def on_event(kind, data, _):
            if kind == "response_delta" and data["chunk_range"][1] >= number:
                state["cancelled"] = True
        return state, on_event

    def test_user_stop_mid_stream_records_what_arrived_and_runs_nothing_after(self):
        for scenario in ("long", "stop", "compare"):
            with self.subTest(scenario=scenario):
                state, on_event = self.cancel_after_chunk(4)
                with self.assertRaises(RunCancelled):
                    run_case(inputs={"scenario": scenario, "stop_after_chunks": 400}, stream=self.slow("迟到的文字"),
                             cancelled=lambda: state["cancelled"], on_event=on_event,
                             cancel_reason=lambda: "user_stop")
        state, on_event = self.cancel_after_chunk(4)
        events = []
        with self.assertRaises(RunCancelled):
            run_case(inputs={"scenario": "long"}, stream=self.slow("迟到的文字"),
                     cancelled=lambda: state["cancelled"], cancel_reason=lambda: "user_stop",
                     on_event=lambda kind, data, number: (events.append((kind, data, number)),
                                                          on_event(kind, data, number)))
        kinds = [kind for kind, _, _ in events]
        self.assertEqual(kinds[0], "request")
        self.assertEqual(kinds[-1], "response")
        self.assertNotIn("lesson.report", kinds)
        self.assertNotIn("迟到的文字", json.dumps(events, ensure_ascii=False))
        stream_facts = events[-1][1]["stream"]
        self.assertEqual((stream_facts["status"], stream_facts["cancel_reason"]), ("cancelled", "user_stop"))
        self.assertEqual(stream_facts["chunk_count"], 4)
        self.assertIsInstance(stream_facts["discarded_after_cancel"], int)
        self.assertEqual(events[-1][1]["body"]["choices"][0]["message"]["content"], "1. 一。\n2. 二。\n3. 三")
        self.assertIsNone(events[-1][1]["body"]["choices"][0]["finish_reason"])

    def test_a_stop_while_the_first_chunk_is_still_on_its_way_records_an_empty_stream(self):
        state, release = {"cancelled": False}, threading.Event()

        def stream(body, key):
            state["cancelled"] = True
            release.wait(2)
            yield chunk("太晚")

        events = []
        with self.assertRaises(RunCancelled):
            run_case(inputs={"scenario": "long"}, stream=stream, cancelled=lambda: state["cancelled"],
                     on_event=lambda kind, data, number: events.append((kind, data, number)))
        release.set()
        self.assertEqual([kind for kind, _, _ in events], ["request", "response"])
        self.assertEqual(events[-1][1]["stream"]["chunk_count"], 0)
        self.assertEqual(events[-1][1]["stream"]["cancel_reason"], "api")
        self.assertIsNone(events[-1][1]["stream"]["first_token_ms"])

    def test_a_stop_after_the_stream_ended_issues_no_second_request(self):
        state = {"cancelled": False}
        events = []

        def on_event(kind, data, number):
            events.append(kind)
            if kind == "response":
                state["cancelled"] = True
        with self.assertRaises(RunCancelled):
            run_case("stream-vs-block", cancelled=lambda: state["cancelled"], on_event=on_event)
        self.assertEqual(events.count("request"), 1)
        self.assertNotIn("lesson.report", events)

    def test_a_program_stop_is_not_a_cancel(self):
        # stop_when ends the stream with status "stopped" and the run completes; no RunCancelled, no reason.
        answer, events = run_case("stop-after-n")
        stream_facts = of(events, "response")[0]["stream"]
        self.assertEqual(stream_facts["status"], "stopped")
        self.assertNotIn("cancel_reason", stream_facts)
        self.assertNotIn("discarded_after_cancel", stream_facts)
        self.assertTrue(answer)


class WebRunTests(unittest.TestCase):
    """The real run path (POST /api/runs, cancel, the event stream) with this lesson treated as available."""

    def setUp(self):
        import tempfile
        from pathlib import Path

        from server import catalog, offline
        from server.catalog import load_lessons
        from server.run_store import RunStore

        self.web = __import__("server.app", fromlist=["app"])
        stack = ExitStack()
        self.addCleanup(stack.close)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        previous, store = self.web.run_store, RunStore(Path(directory.name) / "runs.sqlite3")
        self.web.run_store = store

        def restore():
            self.web.run_store = previous
            store.close()
        self.addCleanup(restore)
        if not any(item["id"] == "streaming-cancel" for item in catalog.LESSONS):
            spec = next(item for item in load_lessons(include_planned=True) if item["id"] == "streaming-cancel")
            catalog.LESSONS.append(spec)
            self.addCleanup(catalog.LESSONS.remove, spec)
        self.spec = next(item for item in catalog.LESSONS if item["id"] == "streaming-cancel")
        self.gate, self.reached = threading.Event(), threading.Event()
        real = catalog.lesson_callable

        def gated_stream(exercise_id, inputs=None, locale="zh-CN"):
            def stream(body, api_key):
                yield chunk("", role="assistant")
                yield chunk("1. 先到的内容。")
                self.reached.set()
                self.gate.wait(5)
                yield chunk("\n2. 停止之后才到的内容。")
                yield chunk("", finish="stop")
            return stream

        stack.enter_context(patch.object(offline, "lesson_callable", lambda spec, reference: (
            gated_stream if reference == "fixtures:create_stream" else real(spec, reference))))
        self.client = TestClient(self.web.app, base_url="http://localhost")

    def body(self, exercise_id, locale="zh-CN"):
        from server.catalog import lesson_presets

        exercises, _ = lesson_presets(self.spec, locale)
        question = next(item for item in exercises if item["id"] == exercise_id)["question"]
        return {"lesson_id": "streaming-cancel", "mode": "offline", "question": question,
                "exercise_id": exercise_id, "locale": locale}

    def start(self, exercise_id, locale="zh-CN"):
        created = self.client.post("/api/runs", json=self.body(exercise_id, locale))
        self.assertEqual(created.status_code, 202, created.text)
        run_id = created.json()["run_id"]
        self.addCleanup(self.finish, run_id)
        return run_id

    def finish(self, run_id):
        self.gate.set()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and (self.web.active_run(run_id) or self.web.run_lock.locked()):
            time.sleep(0.02)

    def read(self, run_id):
        text = self.client.get(f"/api/runs/{run_id}/events").text
        return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]

    def test_every_exercise_completes_and_labels_its_stream_events(self):
        self.gate.set()
        for exercise_id in EXERCISE_INPUTS:
            for locale in ("zh-CN", "en"):
                with self.subTest(exercise=exercise_id, locale=locale):
                    events = self.read(self.start(exercise_id, locale))
                    self.assertEqual(events[-1]["type"], "done")
                    self.assertEqual(events[-1]["data"]["status"], "completed")
                    self.assertEqual(events[1]["type"], "request")
                    self.assertTrue(events[1]["data"]["stream"])
                    stream_events = [e for e in events if e["type"] in ("response_delta", "response")
                                     and (e["type"] == "response_delta" or e["data"].get("stream"))]
                    self.assertTrue(stream_events)
                    for event in stream_events:
                        self.assertEqual(event["span_id"], events[1]["span_id"])
                        self.assertEqual(event["representation"], "sdk_standardized")
                    self.assertNotIn("client_disconnects", events[-1]["data"])
                    self.assertNotIn("cancel_reason", events[-1]["data"])

    def test_stop_button_ends_in_cancelled_and_keeps_only_what_arrived(self):
        for reason in ("user_stop", "page_closed"):
            with self.subTest(reason=reason):
                self.gate.clear(), self.reached.clear()
                run_id = self.start("long-stream")
                self.assertTrue(self.reached.wait(5))
                # Both chunks are recorded once the idle flush has published the second one (the first is alone).
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and sum(
                        json.loads(text)["type"] == "response_delta"
                        for _, _, text in self.web.run_store.events(run_id)) < 2:
                    time.sleep(0.02)
                stopped = self.client.post(f"/api/runs/{run_id}/cancel", json={"reason": reason})
                self.assertEqual((stopped.status_code, stopped.json()["reason"]), (202, reason))
                events = self.read(run_id)
                self.gate.set()
                response = next(e for e in events if e["type"] == "response")
                self.assertEqual(response["data"]["stream"]["status"], "cancelled")
                self.assertEqual(response["data"]["stream"]["cancel_reason"], reason)
                self.assertIsInstance(response["data"]["stream"]["discarded_after_cancel"], int)
                content = response["data"]["body"]["choices"][0]["message"]["content"]
                self.assertEqual(content, "1. 先到的内容。")
                self.assertNotIn("停止之后才到", json.dumps(events, ensure_ascii=False))
                self.assertEqual((events[-1]["data"]["status"], events[-1]["data"]["cancel_reason"]),
                                 ("cancelled", reason))
                self.assertNotIn("answer", [e["type"] for e in events])
                self.assertNotIn("lesson.report", [e["type"] for e in events])
                self.assertEqual(self.client.get(f"/api/runs/{run_id}").json()["status"], "cancelled")

    def test_closing_the_event_stream_does_not_stop_the_run(self):
        self.gate.clear(), self.reached.clear()
        run_id = self.start("long-stream")
        self.assertTrue(self.reached.wait(5))
        checks_made = {"count": 0}

        class LeavingReader:
            async def is_disconnected(self):
                checks_made["count"] += 1
                return checks_made["count"] > 1

        async def read_until_gone():
            response = await self.web.run_events(run_id, LeavingReader(), from_seq=1, last_event_id=None)
            return [part async for part in response.body_iterator]
        received = asyncio.run(read_until_gone())
        self.assertTrue(received)
        active = self.web.active_run(run_id)
        self.assertIsNotNone(active, "the run is still going after the reader left")
        self.assertFalse(active.cancelled.is_set())
        self.gate.set()
        events = self.read(run_id)
        done = events[-1]["data"]
        # Only the connection closed: the backend finished the stream and wrote its own terminal state.
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["client_disconnects"], 1)
        self.assertNotIn("cancel_reason", done)
        response = next(e for e in events if e["type"] == "response")
        self.assertEqual(response["data"]["stream"]["status"], "completed")
        self.assertIn("lesson.report", [e["type"] for e in events])
        self.assertIn("停止之后才到的内容", response["data"]["body"]["choices"][0]["message"]["content"])
        self.assertEqual(self.client.get(f"/api/runs/{run_id}").json()["status"], "completed")


if __name__ == "__main__":
    unittest.main()
