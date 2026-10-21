"""流式请求：RunContext.complete_stream 的分块事件、节流、拼合、取消与错误，百炼 SSE 与 LiteLLM 传输，接口端到端。

全部使用确定性分块或 mock 的传输层，从不请求真实模型。
"""
import asyncio
import importlib
import json
import re
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from course.api_client import ProviderHTTPError, stream_bailian
from course.execution import RunContext, StreamAssembler
from course.providers import ModelProfile, SDKCompletion
from course.runner import RunCancelled
from hitl_support import LessonHarness, chunk, spec_for
from server.envelope import EnvelopeBuilder

web = importlib.import_module("server.app")
CJK = re.compile(r"[㐀-鿿＀-￯　-〿]")


def make_context(events, stream, **overrides):
    values = dict(lesson_id="stream-test", exercise_id="main", question="q", mode="live", model="chat-model",
                  representation="http_body", inputs={}, api_key="fixture-secret", completion=None,
                  emit_event=lambda kind, data, number: events.append((kind, data, number)),
                  stream_completion=stream)
    return RunContext(**{**values, **overrides})


def answer_chunks(text="你好，世界", usage=True):
    chunks = [chunk(role="assistant", text="")]
    chunks += [chunk(piece) for piece in text]
    chunks.append(chunk("", finish="stop"))
    if usage:
        chunks.append(chunk(choices=False, usage={"prompt_tokens": 5, "completion_tokens": len(text),
                                                  "total_tokens": 5 + len(text)}))
    return chunks


def recorded_chunks(events):
    return [item for kind, data, _ in events if kind == "response_delta" for item in data["chunks"]]


class AssemblerTests(unittest.TestCase):
    def test_text_reasoning_usage_and_finish_reason_are_merged_without_additions(self):
        assembler = StreamAssembler()
        for number, item in enumerate([chunk(role="assistant", reasoning="想"), chunk(reasoning="一想"),
                                       chunk("答"), chunk("案", finish="stop"),
                                       chunk(choices=False, usage={"total_tokens": 9})], 1):
            assembler.add(item, number * 10)
        body = assembler.body()
        self.assertEqual(body["choices"], [{"index": 0, "finish_reason": "stop", "message": {
            "role": "assistant", "content": "答案", "reasoning_content": "想一想"}}])
        self.assertEqual(body["usage"], {"total_tokens": 9})
        self.assertEqual((body["id"], body["model"]), ("chatcmpl-test", "offline-script"))
        self.assertNotIn("object", body)
        self.assertEqual((assembler.first_chunk_ms, assembler.first_token_ms, assembler.chunk_count), (10, 10, 5))

    def test_tool_call_fragments_join_by_index_and_none_counts_as_empty(self):
        assembler = StreamAssembler()
        fragments = [
            [{"index": 0, "id": "call_a", "type": "function", "function": {"name": "save", "arguments": '{"pa'}}],
            [{"index": 1, "id": "call_b", "type": "function", "function": {"name": "read", "arguments": None}}],
            [{"index": 0, "id": "", "function": {"arguments": 'th": "a.txt"}'}}],
            [{"index": 1, "function": {"name": None, "arguments": "{}"}}],
        ]
        for number, calls in enumerate(fragments):
            assembler.add(chunk(tool_calls=calls), number)
        assembler.add(chunk(finish="tool_calls"), 9)
        message = assembler.body()["choices"][0]["message"]
        self.assertIsNone(message["content"])
        self.assertEqual(message["tool_calls"], [
            {"id": "call_a", "type": "function", "function": {"name": "save", "arguments": '{"path": "a.txt"}'}},
            {"id": "call_b", "type": "function", "function": {"name": "read", "arguments": "{}"}}])

    def test_no_usage_chunk_means_no_usage_field(self):
        assembler = StreamAssembler()
        assembler.add(chunk("a", finish="stop"), 1)
        self.assertNotIn("usage", assembler.body())


class CompleteStreamTests(unittest.TestCase):
    def test_events_request_deltas_and_assembled_response(self):
        events, sent = [], []
        chunks = answer_chunks()

        def stream(body, key):
            self.assertEqual(key, "fixture-secret")
            sent.append(json.loads(json.dumps(body)))
            return iter(json.loads(json.dumps(chunks)))
        context = make_context(events, stream)
        result = context.complete_stream({"messages": [{"role": "user", "content": "hi"}]}, 2, branch="a")
        kinds = [kind for kind, _, _ in events]
        self.assertEqual(kinds[0], "request")
        self.assertEqual(kinds[-1], "response")
        self.assertTrue(all(kind == "response_delta" for kind in kinds[1:-1]))
        request = events[0][1]
        self.assertEqual(request["body"], {"model": "chat-model", "messages": [{"role": "user", "content": "hi"}],
                                           "stream": True, "stream_options": {"include_usage": True}})
        self.assertEqual(request["body"], sent[0])
        self.assertEqual((request["stream"], request["branch"]), (True, "a"))
        # 每个分块原样记录一次，顺序不变；第一块单独成一条事件，首块到达时刻可见。
        self.assertEqual(recorded_chunks(events), chunks)
        first = events[1][1]
        self.assertEqual((first["chunk_range"], first["delta_index"], first["branch"]), ([1, 1], 1, "a"))
        ranges = [data["chunk_range"] for kind, data, _ in events if kind == "response_delta"]
        self.assertEqual([low for low, _ in ranges[1:]], [high + 1 for _, high in ranges[:-1]])
        response = events[-1][1]
        self.assertEqual(response["body"]["choices"][0]["message"], {"role": "assistant", "content": "你好，世界"})
        self.assertEqual(response["body"]["usage"]["completion_tokens"], 5)
        facts = response["stream"]
        self.assertEqual((facts["assembled_from_chunks"], facts["status"], facts["chunk_count"]),
                         (True, "completed", len(chunks)))
        self.assertIsInstance(facts["first_chunk_ms"], int)
        self.assertGreaterEqual(facts["first_token_ms"], facts["first_chunk_ms"])
        self.assertIsNone(facts["done_marker"])
        self.assertEqual({number for _, _, number in events}, {2})
        self.assertEqual((result.status, result.text, result.chunk_count), ("completed", "你好，世界", len(chunks)))
        self.assertEqual(result.response, response["body"])

    def test_include_usage_can_be_turned_off_and_body_cannot_set_stream(self):
        events = []
        context = make_context(events, lambda body, key: iter([chunk("a", finish="stop")]))
        context.complete_stream({"messages": []}, include_usage=False)
        self.assertNotIn("stream_options", events[0][1]["body"])
        for body in ({"messages": [], "stream": False}, {"messages": [], "stream_options": {}},
                     {"model": "other", "messages": []}):
            with self.subTest(body=body), self.assertRaises(ValueError):
                context.complete_stream(body)
        with self.assertRaises(ValueError):
            make_context([], None).complete_stream({"messages": []})

    def test_bursts_are_grouped_but_never_dropped(self):
        events = []
        chunks = [chunk(str(index % 10)) for index in range(300)] + [chunk("", finish="stop")]
        context = make_context(events, lambda body, key: iter(chunks))
        context.complete_stream({"messages": []}, flush_max_chunks=50, flush_interval_s=5)
        deltas = [data for kind, data, _ in events if kind == "response_delta"]
        self.assertLessEqual(len(deltas), 1 + 301 // 50 + 1)
        self.assertEqual(recorded_chunks(events), chunks)
        self.assertEqual("".join(data["text"] for data in deltas), "".join(str(i % 10) for i in range(300)))

    def test_stream_counts_as_one_model_call(self):
        events = []
        context = make_context(events, lambda body, key: iter([chunk("a", finish="stop")]), max_model_calls=1)
        context.complete_stream({"messages": []})
        with self.assertRaises(RuntimeError):
            context.complete_stream({"messages": []})
        self.assertEqual([kind for kind, _, _ in events].count("request"), 1)

    def test_cancel_records_what_arrived_and_never_records_later_chunks(self):
        events, state = [], {"cancelled": False}
        late = chunk("迟到")

        def on_event(kind, data, number):
            events.append((kind, data, number))
            if kind == "response_delta" and data["chunk_range"][1] == 3:
                state["cancelled"] = True

        def stream(body, key):
            yield chunk("一")
            yield chunk("二")
            yield chunk("三")
            time.sleep(0.3)
            yield late

        context = make_context([], stream, emit_event=on_event, cancelled=lambda: state["cancelled"],
                               cancel_reason=lambda: "user_stop")
        with self.assertRaises(RunCancelled):
            context.complete_stream({"messages": []}, flush_max_chunks=1)
        self.assertEqual([item["choices"][0]["delta"]["content"] for item in recorded_chunks(events)],
                         ["一", "二", "三"])
        self.assertNotIn("迟到", json.dumps([data for _, data, _ in events], ensure_ascii=False))
        response = events[-1][1]
        self.assertEqual(events[-1][0], "response")
        self.assertEqual(response["stream"]["status"], "cancelled")
        self.assertEqual(response["stream"]["cancel_reason"], "user_stop")
        self.assertEqual(response["body"]["choices"][0]["message"]["content"], "一二三")
        self.assertIsNone(response["body"]["choices"][0]["finish_reason"])

    def test_cancel_before_any_chunk_still_closes_the_request_with_a_cancelled_response(self):
        events, state = [], {"cancelled": False}
        release = threading.Event()

        def stream(body, key):
            state["cancelled"] = True
            release.wait(1)
            yield chunk("太晚")

        context = make_context(events, stream, cancelled=lambda: state["cancelled"])
        with self.assertRaises(RunCancelled):
            context.complete_stream({"messages": []})
        release.set()
        self.assertEqual([kind for kind, _, _ in events], ["request", "response"])
        self.assertEqual(events[-1][1]["stream"]["chunk_count"], 0)
        self.assertEqual(events[-1][1]["stream"]["cancel_reason"], "api")

    def test_broken_stream_and_provider_error_chunk_are_recorded_then_raised(self):
        def broken(body, key):
            yield chunk("半")
            raise RuntimeError("connection reset")
        events = []
        with self.assertRaisesRegex(RuntimeError, "connection reset"):
            make_context(events, broken).complete_stream({"messages": []})
        self.assertEqual(events[-1][1]["stream"]["status"], "error")
        self.assertEqual(len(recorded_chunks(events)), 1)

        events = []
        error_chunk = {"error": {"code": "DataInspectionFailed", "message": "blocked"}}
        context = make_context(events, lambda body, key: iter([chunk("a"), error_chunk, chunk("b")]), locale="en")
        with self.assertRaises(RuntimeError) as caught:
            context.complete_stream({"messages": []})
        self.assertIn("DataInspectionFailed", str(caught.exception))
        self.assertIsNone(CJK.search(str(caught.exception)))
        self.assertEqual(recorded_chunks(events), [chunk("a"), error_chunk])
        self.assertEqual(events[-1][1]["stream"]["status"], "error")

    def test_stop_when_ends_the_stream_early_and_returns(self):
        events = []
        chunks = [chunk(str(index)) for index in range(10)]
        context = make_context(events, lambda body, key: iter(chunks))
        result = context.complete_stream({"messages": []}, stop_when=lambda view: len(view["text"]) >= 3)
        self.assertEqual((result.status, result.text), ("stopped", "012"))
        self.assertEqual(recorded_chunks(events), chunks[:3])
        self.assertEqual(events[-1][1]["stream"]["stop_reason"], "lesson")


class SSEResponse:
    """模拟 urlopen 返回的流式响应：按行迭代字节。"""

    def __init__(self, text):
        self.lines = [line.encode("utf-8") for line in text.splitlines(keepends=True)]
        self.closed = False

    def __iter__(self):
        return iter(self.lines)

    def close(self):
        self.closed = True


class TransportTests(unittest.TestCase):
    def setUp(self):
        local_config = SimpleNamespace(API_URL="https://native.example.invalid/compatible-mode/v1/chat/completions")
        patcher = patch.dict("sys.modules", {"local_config": local_config})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_bailian_stream_parses_sse_data_lines_and_the_done_marker(self):
        first, last = chunk("你"), chunk(choices=False, usage={"total_tokens": 3})
        text = (f"data: {json.dumps(first, ensure_ascii=False)}\n\n: keep-alive\n\n"
                f"data:{json.dumps(last)}\n\ndata: [DONE]\n\n")
        captured = {}

        def urlopen(request, timeout):
            captured.update(url=request.full_url, body=json.loads(request.data),
                            auth=request.get_header("Authorization"), timeout=timeout)
            captured["response"] = SSEResponse(text)
            return captured["response"]

        with patch("urllib.request.urlopen", urlopen):
            stream = stream_bailian({"model": "m", "stream": True}, "secret-key")
            items = list(stream)
        self.assertEqual(items, [first, last])
        self.assertTrue(stream.done_marker)
        self.assertTrue(captured["response"].closed)
        self.assertEqual(captured["auth"], "Bearer secret-key")
        self.assertEqual(captured["body"], {"model": "m", "stream": True})

    def test_bailian_stream_without_done_marker_and_with_bad_json(self):
        with patch("urllib.request.urlopen", lambda request, timeout: SSEResponse('data: {"a": 1}\n\n')):
            stream = stream_bailian({}, "k")
            self.assertEqual(list(stream), [{"a": 1}])
            self.assertFalse(stream.done_marker)
        with patch("urllib.request.urlopen", lambda request, timeout: SSEResponse("data: {oops\n\n")):
            with self.assertRaises(RuntimeError):
                list(stream_bailian({}, "k", locale="en"))

    def test_bailian_http_error_before_the_stream_keeps_the_status(self):
        import io
        import urllib.error

        def urlopen(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"bad key"))
        with patch("urllib.request.urlopen", urlopen), self.assertRaises(ProviderHTTPError) as caught:
            stream_bailian({}, "k")
        self.assertEqual(caught.exception.status_code, 401)

    def test_litellm_stream_passes_stream_options_and_yields_plain_dicts(self):
        calls = {}

        class Chunk:
            def __init__(self, data):
                self.data = data

            def model_dump(self, exclude_none=False):
                return self.data

        class Wrapper:
            closed = False

            def __iter__(self):
                return iter([Chunk(chunk("a")), Chunk(chunk(choices=False, usage={"total_tokens": 1}))])

            def close(self):
                Wrapper.closed = True

        def fake_sdk(**kwargs):
            calls.update(kwargs)
            return Wrapper()
        profile = ModelProfile(id="openai", label="OpenAI", model="gpt-test", api_key="sk-test",
                               api_base=None, config_ready=True)
        with patch("course.providers.sdk_completion", fake_sdk):
            stream = SDKCompletion(profile).stream({"model": "gpt-test", "messages": [], "stream": True,
                                                    "stream_options": {"include_usage": True}}, "sk-test")
            items = list(stream)
        self.assertEqual(items, [chunk("a"), chunk(choices=False, usage={"total_tokens": 1})])
        self.assertEqual((calls["model"], calls["stream"], calls["stream_options"]),
                         ("openai/gpt-test", True, {"include_usage": True}))
        self.assertEqual((calls["num_retries"], calls["max_retries"]), (0, 0))
        self.assertTrue(Wrapper.closed)
        self.assertIsNone(stream.done_marker)


class StreamRunTests(LessonHarness):
    def setUp(self):
        super().setUp()
        self.spec = spec_for(testing={"stream_factory": "fixtures:create_stream"})
        self.chunks = answer_chunks("Hello")
        self.factory_calls = []
        self.fixtures["fixtures:create_stream"] = self.create_stream

    def create_stream(self, exercise_id, inputs=None, locale="zh-CN"):
        self.factory_calls.append((exercise_id, locale))
        return lambda body, api_key: iter(json.loads(json.dumps(self.chunks)))

    def test_offline_stream_events_share_the_llm_span_and_are_labelled(self):
        def runner(context):
            return context.complete_stream({"messages": [{"role": "user", "content": context.question}]}).text
        self.runner = runner
        events = self.read(self.start(locale="en"))
        kinds = [event["type"] for event in events]
        self.assertEqual(kinds[:2], ["run_start", "request"])
        self.assertEqual(kinds[-3:], ["response", "answer", "done"])
        request = events[1]
        deltas = [event for event in events if event["type"] == "response_delta"]
        response = next(event for event in events if event["type"] == "response")
        self.assertTrue(deltas)
        for event in deltas + [response]:
            self.assertEqual(event["span_id"], request["span_id"])
            self.assertEqual(event["span_kind"], "llm")
            self.assertEqual(event["representation"], "sdk_standardized")
            self.assertEqual(event["sdk"], {"name": "deterministic-test-adapter", "version": None})
        self.assertEqual(response["data"]["stream"]["status"], "completed")
        self.assertEqual(events[-2]["data"]["content"], "Hello")
        self.assertEqual(self.factory_calls, [("main", "en")])
        self.assertIsNone(CJK.search(json.dumps(events, ensure_ascii=False)))
        # 录制校验用同一个 EnvelopeBuilder 重放：分块事件的 span 规则在重放里一致。
        builder = EnvelopeBuilder(request["run_id"], representation="sdk_standardized",
                                  sdk={"name": "deterministic-test-adapter", "version": None})
        for event in events:
            rebuilt = builder.build(event["type"], event["data"], event["round"], event["timestamp"])
            self.assertEqual(rebuilt, event)

    def test_stop_button_mid_stream_records_the_reason_and_the_partial_answer(self):
        arrived, release = threading.Event(), threading.Event()

        def create_stream(exercise_id, inputs=None, locale="zh-CN"):
            def stream(body, api_key):
                yield chunk("部分")
                arrived.set()
                release.wait(5)
                yield chunk("不该记录")
            return stream
        self.fixtures["fixtures:create_stream"] = create_stream
        self.runner = lambda context: context.complete_stream({"messages": []}).text
        run_id = self.start()
        self.assertTrue(arrived.wait(5))
        self.wait_for(run_id, lambda events: any(e["type"] == "response_delta" for e in events))
        stopped = self.client.post(f"/api/runs/{run_id}/cancel", json={"reason": "user_stop"})
        self.assertEqual((stopped.status_code, stopped.json()["reason"]), (202, "user_stop"))
        events = self.read(run_id)
        release.set()
        response = next(event for event in events if event["type"] == "response")
        self.assertEqual(response["data"]["stream"]["status"], "cancelled")
        self.assertEqual(response["data"]["stream"]["cancel_reason"], "user_stop")
        self.assertEqual(response["data"]["body"]["choices"][0]["message"]["content"], "部分")
        self.assertNotIn("不该记录", json.dumps(events, ensure_ascii=False))
        self.assertEqual((events[-1]["data"]["status"], events[-1]["data"]["cancel_reason"]),
                         ("cancelled", "user_stop"))
        self.assertNotIn("answer", [event["type"] for event in events])
        self.assertEqual(self.client.get(f"/api/runs/{run_id}").json()["status"], "cancelled")

    def test_unknown_cancel_reason_is_rejected(self):
        release = threading.Event()
        self.runner = lambda context: release.wait(5) and "done"
        self.spec = spec_for(requires_model=False)
        run_id = self.start()
        response = self.client.post(f"/api/runs/{run_id}/cancel", json={"reason": "because"})
        self.assertEqual(response.status_code, 422)
        release.set()
        self.assertEqual(self.read(run_id)[-1]["data"]["status"], "completed")

    def test_closing_the_event_stream_does_not_stop_the_run(self):
        release = threading.Event()

        def runner(context):
            context.emit("lesson.progress", {"step": 1}, 1)
            release.wait(5)
            context.emit("lesson.progress", {"step": 2}, 1)
            return "finished"
        self.runner = runner
        self.spec = spec_for(requires_model=False)
        run_id = self.start()
        self.wait_for(run_id, lambda events: any(e["type"] == "lesson.progress" for e in events))
        # 读者收到前两条事件后断开（is_disconnected 第二次起为真）：事件流结束，运行不停。
        checks = {"count": 0}

        class LeavingReader:
            async def is_disconnected(self):
                checks["count"] += 1
                return checks["count"] > 1

        async def read_until_gone():
            response = await web.run_events(run_id, LeavingReader(), from_seq=1, last_event_id=None)
            return [part async for part in response.body_iterator]
        received = asyncio.run(read_until_gone())
        self.assertTrue(any('"lesson.progress"' in part for part in received))
        self.assertIsNotNone(web.active_run(run_id))
        self.assertFalse(web.active_run(run_id).cancelled.is_set())
        release.set()
        events = self.read(run_id)
        self.assertEqual(events[-1]["data"]["status"], "completed")
        self.assertEqual(events[-2]["data"]["content"], "finished")
        self.assertNotIn("cancel_reason", events[-1]["data"])
        # 断开只作为计数写进 done，供“断开不等于停止”的实验核对。
        self.assertEqual(events[-1]["data"]["client_disconnects"], 1)

    def test_live_bailian_run_uses_the_native_stream_transport(self):
        local_config = SimpleNamespace(API_URL="https://native.example.invalid/compatible-mode/v1/chat/completions",
                                       MODEL="native-model")
        sent = []

        def urlopen(request, timeout):
            sent.append(json.loads(request.data))
            body = "".join(f"data: {json.dumps(item)}\n\n" for item in answer_chunks("ok")) + "data: [DONE]\n\n"
            return SSEResponse(body)
        self.runner = lambda context: context.complete_stream({"messages": []}).text
        with patch.dict("sys.modules", {"local_config": local_config}), \
                patch("urllib.request.urlopen", urlopen), \
                patch.object(web, "session_key", "bailian-secret"), \
                patch.object(web.provider_registry, "resolve", return_value=ModelProfile(
                    id="bailian", label="Bailian", model="native-model", api_key="bailian-secret",
                    api_base=None, config_ready=True)):
            events = self.read(self.start(mode="live"))
        self.assertEqual(sent[0]["stream"], True)
        response = next(event for event in events if event["type"] == "response")
        self.assertEqual(response["representation"], "http_body")
        self.assertTrue(response["data"]["stream"]["done_marker"])
        self.assertEqual(events[-1]["data"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
