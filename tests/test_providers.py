"""多厂商配置、密钥隔离和标准化轨迹；全部通过mock，不调用付费API。"""
import copy
import importlib
import json
import os
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from course.providers import ModelProfile, SDKCompletion, load_sdk
from course.runner import run_agent
from server.providers import PROVIDERS, ProviderRegistry, normalize_api_base
from run_support import run_and_read, use_temporary_run_store

web = importlib.import_module("server.app")


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.previous_registry, self.previous_key = web.provider_registry, web.session_key
        web.provider_registry, web.session_key = ProviderRegistry(), ""
        self.client = TestClient(web.app, base_url="http://localhost")
        use_temporary_run_store(self)
        environment = {name: "" for fields in PROVIDERS.values() for name in fields[1:] if name}
        environment["DASHSCOPE_API_KEY"] = "bailian-env-secret"
        self.stack.enter_context(patch.dict(os.environ, environment))
        self.stack.enter_context(patch.dict("sys.modules", {"local_config": SimpleNamespace(
            API_URL="https://native.example.invalid/compatible-mode/v1/chat/completions", MODEL="native-model")}))

    def tearDown(self):
        self.stack.close()
        web.provider_registry, web.session_key = self.previous_registry, self.previous_key

    def exercise(self):
        return {"lesson_id": "tool-selection", "mode": "live", "question": "19+23", "exercise_id": "sum"}

    def events(self, response):
        return response.events

    def test_public_profiles_and_default_native_configuration(self):
        response = self.client.get("/api/providers")
        data = response.json()
        self.assertEqual(data["active_provider"], "bailian")
        self.assertEqual({p["id"] for p in data["providers"]}, set(PROVIDERS))
        for profile in data["providers"]:
            self.assertEqual(set(profile), {"id", "label", "model", "api_key_configured",
                                           "config_ready", "base_url_configured", "supports_custom_base_url",
                                           "requires_api_key"})
            self.assertIsInstance(profile["requires_api_key"], bool)
        self.assertNotIn("bailian-env-secret", response.text)
        self.assertNotIn("native.example.invalid", response.text)
        status = self.client.get("/api/status").json()
        self.assertEqual(status["model"], "native-model")
        self.assertEqual(status["trace_representation"], "http_body")
        self.assertTrue(status["config_ready"])

    def test_no_cross_provider_key_fallback_and_no_model_no_run(self):
        self.client.post("/api/settings", json={"provider_id": "openai"})
        status = self.client.get("/api/status").json()
        self.assertFalse(status["api_key_configured"])
        self.assertFalse(status["config_ready"])
        with patch("course.providers.sdk_completion") as sdk:
            self.assertEqual(self.client.post("/api/runs", json=self.exercise()).status_code, 400)
            sdk.assert_not_called()
        self.client.post("/api/settings", json={"model": "gpt-test"})
        self.assertTrue(self.client.get("/api/status").json()["config_ready"])
        self.assertFalse(self.client.get("/api/status").json()["api_key_configured"])

    def test_session_keys_are_per_provider_blank_clears_to_own_env(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "openai-own-env"}):
            self.client.post("/api/settings", json={"provider_id": "openai", "model": "test", "api_key": "openai-session"})
            self.assertEqual(web.current_key(), "openai-session")
            self.client.post("/api/settings", json={"provider_id": "anthropic", "model": "claude-test", "api_key": "anthropic-session"})
            self.assertEqual(web.current_key(), "anthropic-session")
            self.client.post("/api/settings", json={"provider_id": "openai"})
            self.assertEqual(web.current_key(), "openai-session")
            self.client.post("/api/settings", json={"api_key": ""})
            self.assertEqual(web.current_key(), "openai-own-env")
            self.client.post("/api/settings", json={"provider_id": "bailian", "api_key": "legacy-session"})
            self.assertEqual(web.session_key, "legacy-session")
            self.client.post("/api/settings", json={"api_key": ""})
            self.assertEqual(web.current_key(), "bailian-env-secret")

    def test_custom_base_normalization_retention_and_invalid_updates_are_atomic(self):
        response = self.client.post("/api/settings", json={"provider_id": "custom", "model": "hosted/model",
                                   "api_key": "custom-secret", "api_base": "https://custom.example.invalid/api/v1/chat/completions/"})
        self.assertEqual(response.status_code, 200)
        profile = web.provider_registry.resolve()
        self.assertEqual(profile.api_base, "https://custom.example.invalid/api/v1")
        self.assertNotIn("custom.example.invalid", response.text)
        self.client.post("/api/settings", json={"api_base": " ", "model": "other-model"})
        self.assertEqual(web.provider_registry.resolve().api_base, profile.api_base)
        self.assertEqual(web.current_key(), "custom-secret")
        invalid = self.client.post("/api/settings", json={"provider_id": "openai", "api_key": "must-not-save",
                                   "api_base": "file:///C:/private/key"})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(web.provider_registry.active, "custom")
        self.assertNotIn("must-not-save", invalid.text)

    def test_url_validation_and_settings_validation_do_not_echo_secrets(self):
        for url in ("C:/private", "file:///private", "http://remote.example/v1", "https://x/v1?key=secret",
                    "https://secret@x/v1", "https://x/v1#secret", "https://x/../v1", "https://x:bad/v1"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    normalize_api_base(url)
        self.assertEqual(normalize_api_base("http://[::1]:11434/"), "http://[::1]:11434")
        secret = "secret-invalid-input"
        for payload in ({"api_key": [secret]}, {"provider_id": secret}, {"api_key": secret, "extra": secret}):
            response = self.client.post("/api/settings", json=payload)
            self.assertEqual(response.status_code, 400)
            self.assertNotIn(secret, response.text)
        response = self.client.post("/api/runs", json={"mode": secret})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(secret, response.text)

    def test_sdk_trace_tool_loop_is_labeled_and_secret_echo_is_scrubbed(self):
        secret = "selected-sdk-secret"
        self.client.post("/api/settings", json={"provider_id": "custom", "model": "hosted/model",
                         "api_key": secret, "api_base": "https://sdk.example.invalid/v1"})
        received = []
        def fake_sdk(**kwargs):
            received.append(copy.deepcopy(kwargs))
            if len(received) == 1:
                message = {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "call-sdk-1", "type": "function", "function": {
                        "name": "add_numbers", "arguments": '{"a":19,"b":23}'}}]}
            else:
                message = {"role": "assistant", "content": "42 " + secret + " bailian-env-secret"}
            return SimpleNamespace(model_dump=lambda **_: {"choices": [{"message": message}]})
        payload = self.exercise()
        del payload["mode"]  # 未指定时默认真实模型。
        with patch("course.providers.sdk_completion", fake_sdk):
            response = run_and_read(self.client, payload)
        events = self.events(response)
        self.assertEqual(events[0]["data"]["provider_id"], "custom")
        self.assertEqual(events[0]["data"]["trace_representation"], "sdk_standardized")
        self.assertEqual(events[-1]["data"]["status"], "completed")
        for event in events:
            if event["type"] in ("request", "response"):
                self.assertEqual(event["data"]["representation"], "sdk_standardized")
        self.assertNotIn(secret, response.text)
        self.assertNotIn("bailian-env-secret", response.text)
        self.assertEqual([len(r["messages"]) for r in received], [2, 4])
        self.assertEqual(received[0]["api_key"], secret)
        self.assertEqual(received[0]["model"], "openai/hosted/model")
        self.assertEqual(received[0]["max_retries"], 0)
        self.assertEqual(received[0]["num_retries"], 0)
        self.assertEqual(received[1]["messages"][-1]["tool_call_id"], "call-sdk-1")
        self.assertEqual(json.loads(received[1]["messages"][-1]["content"])["result"], 42)

    def test_native_path_retains_original_full_endpoint_and_http_trace(self):
        sent = []
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"choices":[{"message":{"role":"assistant","content":"ok"}}]}'
        def urlopen(request, timeout):
            sent.append((request.full_url, json.loads(request.data), timeout))
            return Response()
        with patch("urllib.request.urlopen", urlopen), patch("course.providers.sdk_completion") as sdk:
            response = run_and_read(self.client, self.exercise())
            sdk.assert_not_called()
        events = self.events(response)
        request = next(e for e in events if e["type"] == "request")
        self.assertEqual(request["data"]["representation"], "http_body")
        self.assertEqual(sent[0][1], request["data"]["body"])
        self.assertEqual(sent[0][0], "https://native.example.invalid/compatible-mode/v1/chat/completions")
        self.assertEqual(sent[0][2], 60)

    def test_ollama_does_not_require_cloud_key(self):
        self.client.post("/api/settings", json={"provider_id": "ollama", "model": "local-test"})
        status = self.client.get("/api/status").json()
        self.assertTrue(status["config_ready"])
        self.assertFalse(status["api_key_configured"])
        with patch("course.providers.sdk_completion", return_value={"choices": [{"message": {"role": "assistant", "content": "local"}}]}) as sdk:
            response = run_and_read(self.client, self.exercise())
        self.assertEqual(self.events(response)[-1]["data"]["status"], "completed")
        self.assertEqual(sdk.call_args.kwargs["api_key"], "ollama-local")
        self.assertEqual(sdk.call_args.kwargs["model"], "ollama_chat/local-test")


class SDKHttpTests(unittest.TestCase):
    def test_actual_litellm_openai_adapter_with_mock_http(self):
        import httpx
        litellm = load_sdk()
        self.assertFalse(litellm.telemetry)
        self.assertEqual(litellm.callbacks, [])
        self.assertEqual(os.environ["LITELLM_LOCAL_MODEL_COST_MAP"], "True")
        self.assertEqual(os.environ["LITELLM_MODE"], "PRODUCTION")
        requests = []
        def receive(request):
            requests.append(request)
            return httpx.Response(200, json={"id": "mock-response", "object": "chat.completion",
                "model": "mock-model", "choices": [{"index": 0, "message": {"role": "assistant", "content": "mock-ok"},
                "finish_reason": "stop"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
        profile = ModelProfile("custom", "Compatible", "mock-model", "mock-key", "https://mock-provider.invalid/v1", True)
        with httpx.Client(transport=httpx.MockTransport(receive)) as client:
            with patch.object(litellm, "client_session", client):
                result = SDKCompletion(profile)({"model": "mock-model", "messages": [{"role": "user", "content": "hi"}],
                                               "tools": [], "tool_choice": "auto"}, "mock-key")
        self.assertEqual(result["choices"][0]["message"]["content"], "mock-ok")
        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url), "https://mock-provider.invalid/v1/chat/completions")
        self.assertEqual(requests[0].headers["authorization"], "Bearer mock-key")
        self.assertEqual(json.loads(requests[0].content)["model"], "mock-model")


if __name__ == "__main__":
    unittest.main()
