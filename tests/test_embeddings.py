"""Embedding 请求：RunContext.embed 的事件、预算、取消与输入校验，服务商接入、离线夹具、录制与回放。

全部使用确定性向量或 mock 的传输层，从不请求真实模型。
"""
import importlib
import json
import os
import re
import time
import unittest
import uuid
from contextlib import ExitStack
from importlib import metadata
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from course.execution import EmbeddingNotConfigured, LessonInputs, RunContext
from course.runner import RunCancelled
from run_support import run_and_read, use_temporary_run_store
from scripts.run_live import summarize
from server.envelope import EnvelopeBuilder, SCHEMA_VERSION
from server.offline import embedding_for
from server.providers import EMBEDDING_MODEL_ENV, PROVIDERS, ProviderRegistry
from server.recordings import validate_document
from server.run_store import utc_now
from test_recordings import LABELS, SLUG, RecordingTestCase

web = importlib.import_module("server.app")
CJK = re.compile(r"[㐀-鿿＀-￯　-〿]")


def vectors(body, size=4):
    """确定性测试向量：第 i 条输入得到 [i+1, len(text), 0, ...]，只服务测试。"""
    return {"object": "list", "model": body["model"],
            "data": [{"object": "embedding", "index": index,
                      "embedding": [float(index + 1), float(len(text))] + [0.0] * (size - 2)}
                     for index, text in enumerate(body["input"])],
            "usage": {"prompt_tokens": len(body["input"]), "total_tokens": len(body["input"])}}


def make_context(events, **overrides):
    values = dict(lesson_id="embed-test", exercise_id="vec", question="q", mode="live",
                  model="chat-model", representation="http_body", inputs={}, api_key="fixture-secret",
                  completion=None, emit_event=lambda kind, data, number: events.append((kind, data, number)),
                  embedding=lambda body, key: vectors(body), embedding_model="embed-model",
                  embedding_batch_limit=3)
    return RunContext(**{**values, **overrides})


class EmbedContextTests(unittest.TestCase):
    def test_request_and_response_are_recorded_with_endpoint_and_exact_body(self):
        events, received = [], []
        def provider(body, key):
            self.assertEqual(key, "fixture-secret")
            received.append(json.loads(json.dumps(body)))
            return vectors(body)
        context = make_context(events, embedding=provider)
        texts = ["借阅规则", "开放时间"]
        response = context.embed(texts, 2, branch="docs", dimensions=64)
        texts.append("later")
        kinds = [kind for kind, _, _ in events]
        self.assertEqual(kinds, ["request", "response"])
        request, reply = events[0][1], events[1][1]
        self.assertEqual(request["endpoint"], "embeddings")
        self.assertEqual(request["body"], {"model": "embed-model", "input": ["借阅规则", "开放时间"], "dimensions": 64})
        self.assertEqual(request["body"], received[0])
        self.assertEqual((request["representation"], request["branch"]), ("http_body", "docs"))
        self.assertEqual(reply["endpoint"], "embeddings")
        self.assertEqual(reply["body"], response)
        self.assertEqual(len(reply["body"]["data"][0]["embedding"]), 4)
        self.assertIsInstance(reply["duration_ms"], int)
        self.assertEqual({number for _, _, number in events}, {2})
        # 不传 dimensions 时请求体里就没有这个字段，不替服务商填默认值。
        context.embed(["一条"])
        self.assertNotIn("dimensions", events[2][1]["body"])
        self.assertNotIn("branch", events[2][1])

    def test_embeddings_share_the_model_call_budget_with_chat(self):
        events = []
        chat = lambda body, key: {"choices": [{"message": {"content": "ok"}}]}
        context = make_context(events, completion=chat, max_model_calls=2)
        context.complete({"messages": []})
        context.embed(["a"])
        with self.assertRaises(RuntimeError):
            context.embed(["b"])
        self.assertEqual([kind for kind, _, _ in events], ["request", "response", "request", "response"])

    def test_cancellation_stops_before_sending_and_after_the_response(self):
        events, sent = [], []
        context = make_context(events, cancelled=lambda: True,
                               embedding=lambda body, key: sent.append(body) or vectors(body))
        with self.assertRaises(RunCancelled):
            context.embed(["a"])
        self.assertEqual((events, sent), ([], []))
        cancelled = False
        def provider(body, key):
            nonlocal cancelled
            cancelled = True
            return vectors(body)
        context = make_context(events, cancelled=lambda: cancelled, embedding=provider)
        with self.assertRaises(RunCancelled):
            context.embed(["a"])
        # 请求已经发出：请求事件如实留下，响应到达时已取消，不再继续。
        self.assertEqual([kind for kind, _, _ in events], ["request"])

    def test_inputs_are_validated_before_any_event_or_call(self):
        events, sent = [], []
        context = make_context(events, embedding=lambda body, key: sent.append(body) or vectors(body))
        cases = [([], {}), ("text", {}), (("a",), {}), ([""], {}), (["  "], {}), ([1], {}),
                 (["a", "b", "c", "d"], {}), (["a"], {"dimensions": 0}), (["a"], {"dimensions": True}),
                 (["a"], {"dimensions": "64"}), (["a"], {"branch": 3})]
        for texts, options in cases:
            with self.subTest(texts=texts, options=options):
                with self.assertRaises(ValueError) as caught:
                    context.embed(texts, **options)
                self.assertNotIsInstance(caught.exception, EmbeddingNotConfigured)
        with self.assertRaisesRegex(ValueError, "split them into batches"):
            context.embed(["a", "b", "c", "d"])
        self.assertEqual((events, sent), ([], []))
        self.assertEqual(context._model_count, 0)

    def test_missing_embedding_model_is_a_coded_error_in_live_runs(self):
        for locale in ("zh-CN", "en"):
            events = []
            context = make_context(events, embedding=None, embedding_model=None, locale=locale)
            with self.assertRaises(EmbeddingNotConfigured) as caught:
                context.embed(["a"])
            self.assertEqual(caught.exception.code, "embedding_model_missing")
            self.assertEqual(events, [])
            if locale == "en":
                self.assertIsNone(CJK.search(str(caught.exception)))
        # 离线课程没有声明夹具是作者的编程错误，不是学生要去配置的东西。
        context = make_context([], mode="offline", embedding=None, embedding_model=None)
        with self.assertRaises(ValueError) as caught:
            context.embed(["a"])
        self.assertNotIsInstance(caught.exception, EmbeddingNotConfigured)
        self.assertIn("embedding_factory", str(caught.exception))

    def test_response_with_the_wrong_number_of_vectors_is_recorded_then_rejected(self):
        events = []
        context = make_context(events, locale="en",
                               embedding=lambda body, key: {"data": [{"index": 0, "embedding": [1.0]}]})
        with self.assertRaises(RuntimeError) as caught:
            context.embed(["a", "b"])
        self.assertEqual([kind for kind, _, _ in events], ["request", "response"])
        self.assertIsNone(CJK.search(str(caught.exception)))


EMBED_SPEC = {
    "id": "embed-test", "title": "Embedding test", "input_defaults": {},
    "runtime": {"kind": "custom", "entrypoint": "runtime:run", "requires_model": True, "max_rounds": 3,
                "locales": ["zh-CN", "en"]},
    "testing": {"embedding_factory": "fixtures:create_embedding"},
    "exercises": [{"id": "vec", "title": "Vectors", "question": "q"},
                  {"id": "local", "title": "Local", "question": "q", "requires_model": False}],
}


def batched_runner(context):
    """课程运行器示例：按 embedding_batch_limit 分批，发 lesson.report 后回答。"""
    texts = [f"chunk {index}" for index in range(12)]
    count = 0
    for start in range(0, len(texts), context.embedding_batch_limit):
        response = context.embed(texts[start:start + context.embedding_batch_limit], 1)
        count += len(response["data"])
    return f"{count} vectors"


class EmbeddingRunTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web.app, base_url="http://localhost")
        use_temporary_run_store(self)
        stack = ExitStack()
        self.addCleanup(stack.close)
        previous_registry, previous_key = web.provider_registry, web.session_key
        web.provider_registry, web.session_key = ProviderRegistry(), ""
        self.addCleanup(setattr, web, "provider_registry", previous_registry)
        self.addCleanup(setattr, web, "session_key", previous_key)
        environment = {name: "" for fields in PROVIDERS.values() for name in fields[1:] if name}
        environment.update({name: "" for name in EMBEDDING_MODEL_ENV.values()})
        environment["DASHSCOPE_API_KEY"] = "bailian-env-secret"
        stack.enter_context(patch.dict(os.environ, environment))
        self.local_config = SimpleNamespace(API_URL="https://native.example.invalid/compatible-mode/v1/chat/completions",
                                            MODEL="native-model")
        stack.enter_context(patch.dict("sys.modules", {"local_config": self.local_config}))
        self.spec = json.loads(json.dumps(EMBED_SPEC))
        self.factory_calls = []

    def create_embedding(self, exercise_id, inputs=None, locale="zh-CN"):
        self.factory_calls.append((exercise_id, inputs, locale))
        return lambda body, api_key: vectors(body)

    def start(self, runner=batched_runner, *, mode="offline", exercise="vec", locale=None, expect=202):
        module = SimpleNamespace(INPUT_MODEL=LessonInputs, run=runner)
        body = {"lesson_id": "embed-test", "exercise_id": exercise, "question": "q", "mode": mode}
        if locale:
            body["locale"] = locale
        with patch.object(web, "lesson_spec", return_value=self.spec), \
                patch.object(web, "lesson_runtime", return_value=module), \
                patch("server.offline.lesson_callable", return_value=self.create_embedding):
            result = run_and_read(self.client, body)
        self.assertEqual(result.status_code, expect, result.text)
        return result

    def test_offline_runs_use_the_lesson_embedding_fixture_in_batches(self):
        events = self.start().events
        kinds = [event["type"] for event in events]
        self.assertEqual(kinds, ["run_start", "request", "response", "request", "response", "answer", "done"])
        self.assertEqual(events[0]["data"]["embedding_model"], "offline-embedding")
        requests = [event for event in events if event["type"] == "request"]
        self.assertEqual([len(event["data"]["body"]["input"]) for event in requests], [10, 2])
        for event in events[1:5]:
            self.assertEqual(event["data"]["endpoint"], "embeddings")
            self.assertEqual(event["representation"], "sdk_standardized")
            self.assertEqual(event["sdk"], {"name": "deterministic-test-adapter", "version": None})
            self.assertEqual(event["span_kind"], "llm")
        self.assertEqual(events[1]["span_id"], events[2]["span_id"])
        self.assertEqual(events[-2]["data"]["content"], "12 vectors")
        self.assertEqual(self.factory_calls, [("vec", {}, "zh-CN")])

    def test_embeddings_count_against_max_rounds(self):
        self.spec["runtime"]["max_rounds"] = 1
        events = self.start().events
        self.assertEqual([event["type"] for event in events], ["run_start", "request", "response", "error", "done"])
        self.assertEqual(events[-1]["data"]["status"], "error")

    def test_english_offline_run_has_no_chinese(self):
        events = self.start(locale="en").events
        self.assertEqual(self.factory_calls[-1][2], "en")
        self.assertIsNone(CJK.search(json.dumps(events, ensure_ascii=False)))

    def test_exercise_without_model_gets_no_embedding_connection(self):
        def runner(context):
            self.assertIsNone(context.embedding)
            return "local"
        events = self.start(runner, exercise="local").events
        self.assertNotIn("embedding_model", events[0]["data"])
        self.assertEqual(self.factory_calls, [])

    def test_live_run_is_refused_when_the_provider_has_no_embedding_model(self):
        self.client.post("/api/settings", json={"provider_id": "anthropic", "model": "claude-test",
                                                "api_key": "anthropic-secret"})
        never = lambda context: self.fail("must not start")
        result = self.start(never, mode="live", expect=400)
        detail = json.loads(result.text)
        self.assertEqual(detail["code"], "embedding_model_missing")
        self.assertEqual(detail["params"], {"setting": "ANTHROPIC_EMBEDDING_MODEL"})
        self.assertNotIn("anthropic-secret", result.text)
        self.assertFalse(web.run_lock.locked())

    def test_undeclared_embed_call_without_model_reports_the_code_in_the_error_event(self):
        self.spec["testing"] = {"completion_factory": "fixtures:create_completion"}
        self.client.post("/api/settings", json={"provider_id": "deepseek", "model": "deepseek-chat",
                                                "api_key": "deepseek-secret"})
        events = self.start(lambda context: context.embed(["a"]) and "never", mode="live", locale="en").events
        error = next(event for event in events if event["type"] == "error")
        self.assertEqual(error["data"]["code"], "embedding_model_missing")
        self.assertEqual(error["data"]["params"], {"setting": "DEEPSEEK_EMBEDDING_MODEL"})
        self.assertIsNone(CJK.search(error["data"]["message"]))
        self.assertNotIn("request", [event["type"] for event in events])

    def test_litellm_path_uses_the_default_openai_embedding_model_and_is_labeled(self):
        self.client.post("/api/settings", json={"provider_id": "openai", "model": "gpt-test",
                                                "api_key": "openai-secret"})
        received = []
        def fake_sdk(**kwargs):
            received.append(kwargs)
            reply = vectors({"model": kwargs["model"], "input": kwargs["input"]})
            reply["echo"] = "openai-secret"
            return SimpleNamespace(model_dump=lambda **_: reply)
        with patch("course.providers.sdk_embedding", fake_sdk):
            events = self.start(lambda context: str(len(context.embed(["a", "b"], dimensions=8)["data"])),
                              mode="live").events
        self.assertEqual(events[0]["data"]["embedding_model"], "text-embedding-3-small")
        request = next(event for event in events if event["type"] == "request")
        self.assertEqual(request["data"]["body"], {"model": "text-embedding-3-small", "input": ["a", "b"],
                                                   "dimensions": 8})
        self.assertEqual(request["representation"], "sdk_standardized")
        self.assertEqual(request["sdk"], {"name": "litellm", "version": metadata.version("litellm")})
        self.assertEqual(received[0]["model"], "openai/text-embedding-3-small")
        self.assertEqual(received[0]["api_key"], "openai-secret")
        self.assertEqual((received[0]["num_retries"], received[0]["drop_params"]), (0, False))
        self.assertEqual(received[0]["allowed_openai_params"], ["dimensions"])
        response = next(event for event in events if event["type"] == "response")
        self.assertEqual(response["data"]["body"]["echo"], "[REDACTED]")
        self.assertEqual(events[-1]["data"]["status"], "completed")

    def test_embedding_model_comes_from_environment_or_settings(self):
        with patch.dict(os.environ, {"GEMINI_EMBEDDING_MODEL": "text-embedding-004"}):
            self.assertEqual(web.provider_registry.resolve("gemini").embedding_model, "text-embedding-004")
        self.assertEqual(web.provider_registry.resolve("gemini").embedding_model, "")
        self.client.post("/api/settings", json={"provider_id": "ollama", "model": "qwen3",
                                                "embedding_model": "nomic-embed-text"})
        profile = web.provider_registry.resolve("ollama")
        self.assertEqual((profile.embedding_model, profile.embedding_batch_limit), ("nomic-embed-text", 10))
        public = {item["id"]: item for item in self.client.get("/api/providers").json()["providers"]}
        self.assertEqual(public["ollama"]["embedding_model"], "nomic-embed-text")
        self.assertEqual(public["openai"]["embedding_model"], "text-embedding-3-small")
        self.assertEqual(self.client.post("/api/settings", json={"embedding_model": ["x"]}).status_code, 400)

    def test_bailian_native_path_posts_to_the_derived_embeddings_url(self):
        sent = []

        class Response:
            def __init__(self, body): self.body = body
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return json.dumps(vectors(self.body)).encode("utf-8")

        def urlopen(request, timeout):
            sent.append(request)
            return Response(json.loads(request.data))
        self.assertEqual(web.provider_registry.resolve("bailian").embedding_model, "text-embedding-v4")
        with patch("urllib.request.urlopen", urlopen):
            events = self.start(lambda context: str(len(context.embed(["a"])["data"])), mode="live").events
        self.assertEqual(sent[0].full_url, "https://native.example.invalid/compatible-mode/v1/embeddings")
        self.assertEqual(sent[0].get_header("Authorization"), "Bearer bailian-env-secret")
        request = next(event for event in events if event["type"] == "request")
        self.assertEqual(json.loads(sent[0].data), request["data"]["body"])
        self.assertEqual(request["data"]["body"]["model"], "text-embedding-v4")
        self.assertEqual((request["representation"], request["sdk"]), ("http_body", None))
        self.assertNotIn("bailian-env-secret", json.dumps(events))
        # 显式配置的模型与地址优先。
        self.local_config.EMBEDDING_MODEL = "text-embedding-v3"
        self.local_config.EMBEDDING_API_URL = "https://other.example.invalid/v1/embeddings"
        with patch("urllib.request.urlopen", urlopen):
            events = self.start(lambda context: "ok", mode="live").events
        self.assertEqual(events[0]["data"]["embedding_model"], "text-embedding-v3")
        with patch("urllib.request.urlopen", urlopen):
            self.start(lambda context: str(len(context.embed(["a"])["data"])), mode="live")
        self.assertEqual(sent[-1].full_url, "https://other.example.invalid/v1/embeddings")

    def test_bailian_without_a_derivable_embeddings_url_is_not_configured(self):
        self.local_config.API_URL = "https://native.example.invalid/custom/endpoint"
        result = self.start(lambda context: "never", mode="live", expect=400)
        self.assertEqual(json.loads(result.text)["code"], "embedding_model_missing")

    def test_offline_loader_passes_locale_and_rejects_non_callables(self):
        spec = {**self.spec, "id": "embed-test"}
        with patch("server.offline.lesson_callable", return_value=self.create_embedding):
            self.assertTrue(callable(embedding_for(spec, "vec", {}, "en")))
        self.assertEqual(self.factory_calls[-1], ("vec", {}, "en"))
        with patch("server.offline.lesson_callable", return_value=lambda exercise_id, inputs=None, locale="zh-CN": None):
            with self.assertRaisesRegex(ValueError, "embedding_factory"):
                embedding_for(spec, "vec", {}, "zh-CN")
        with self.assertRaises(ValueError):
            embedding_for(spec, "unknown", {}, "zh-CN")


class RunLiveSummaryTests(unittest.TestCase):
    def test_summary_separates_embedding_calls_from_chat_responses(self):
        events = [
            {"type": "run_start", "data": {"locale": "en"}},
            {"type": "request", "data": {"endpoint": "embeddings", "body": {"model": "m", "input": ["a", "b"]}}},
            {"type": "response", "data": {"endpoint": "embeddings", "body": vectors({"model": "m", "input": ["a", "b"]})}},
            {"type": "request", "data": {"body": {"messages": []}}},
            {"type": "response", "data": {"body": {"choices": [{"finish_reason": "stop"}], "usage": {"total_tokens": 3}}}},
            {"type": "done", "data": {"status": "completed"}},
        ]
        summary = summarize(events)
        self.assertEqual(summary["finish_reasons"], ["stop"])
        self.assertEqual(summary["usage"], [{"total_tokens": 3}])
        self.assertEqual(summary["embeddings"], [{"model": "m", "inputs": 2, "vectors": 2, "dimensions": 4,
                                                  "usage": {"prompt_tokens": 2, "total_tokens": 2}}])
        self.assertEqual(summary["events"]["request"], 2)


class EmbeddingRecordingTests(RecordingTestCase):
    def test_recorded_embedding_events_pass_validation_unchanged(self):
        run_id = uuid.uuid4().hex
        builder = EnvelopeBuilder(run_id, provenance="real_run", representation="http_body")
        self.store.create_run(run_id=run_id, lesson_id=SLUG, exercise_id="sum", mode="live", model="demo-model",
                              provider_id="bailian", representation="http_body", provenance="real_run",
                              schema_version=SCHEMA_VERSION, created_at=utc_now(), locale="zh-CN")
        body = {"model": "text-embedding-v4", "input": ["a", "b"]}
        events = [
            ("run_start", {"lesson_id": SLUG, "mode": "live", "model": "demo-model", "question": "19+23",
                           "inputs": {}, "runtime_kind": "native", "provider_id": "bailian",
                           "provider_label": LABELS["bailian"], "trace_representation": "http_body",
                           "locale": "zh-CN", "embedding_model": "text-embedding-v4"}, None),
            ("request", {"endpoint": "embeddings", "body": body, "representation": "http_body"}, 1),
            ("response", {"endpoint": "embeddings", "body": vectors(body, size=1024),
                          "representation": "http_body", "duration_ms": 30}, 1),
            ("answer", {"content": "2"}, 1),
        ]
        for kind, data, number in events:
            event = builder.build(kind, data, number, utc_now())
            self.store.append(run_id, event["seq"], kind, json.dumps(event, ensure_ascii=False))
        done = builder.build("done", {"status": "completed", "duration_ms": 40}, None, utc_now())
        self.store.finish(run_id, done["seq"], "done", json.dumps(done, ensure_ascii=False), "completed", utc_now())
        time.sleep(0.01)
        path = self.export(run_id, "embedding-run")
        document = json.loads(path.read_text(encoding="utf-8"))
        metadata_ = validate_document(document, self.spec)
        self.assertEqual(metadata_["event_count"], 5)
        response = document["events"][2]["data"]
        # 录制保存完整向量，不截断。
        self.assertEqual(len(response["body"]["data"][0]["embedding"]), 1024)
        self.assertEqual(response["endpoint"], "embeddings")


if __name__ == "__main__":
    unittest.main()
