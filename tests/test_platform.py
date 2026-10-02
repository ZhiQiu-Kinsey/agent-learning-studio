"""真实工具、模拟模型与本地 Web API 的回归检查；从不请求百炼。"""
import importlib
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from course.api_client import send_bailian
from course.runner import RunCancelled, run_agent
from server.catalog import lesson_runtime, lesson_spec
from server.offline import completion_for
from run_support import run_and_read, use_temporary_run_store

web = importlib.import_module("server.app")


def execute(lesson_id, exercise_id, **kwargs):
    spec = lesson_spec(lesson_id)
    module = lesson_runtime(spec)
    events = []
    run_agent("练习", "", module.SYSTEM_PROMPT, module.TOOLS, module.AVAILABLE_TOOLS,
              spec["runtime"]["max_rounds"], model="offline-script", completion=completion_for(spec, exercise_id),
              emit=lambda kind, data, number: events.append({"type": kind, "data": data}), quiet=True, **kwargs)
    return events


class RunnerTests(unittest.TestCase):
    def test_chain_uses_actual_time_and_immutable_history(self):
        events = execute("dependent-calls", "chain")
        results = [e["data"]["result"] for e in events if e["type"] == "tool_result"]
        calls = [e["data"] for e in events if e["type"] == "tool_call"]
        actual = results[0]["result"]
        self.assertEqual(calls[0]["function"]["name"], "get_current_time")
        self.assertEqual(json.loads(calls[1]["function"]["arguments"]), {"a": actual["hour"], "b": actual["minute"]})
        self.assertEqual(results[1]["result"], actual["hour"] + actual["minute"])
        requests = [e["data"]["body"] for e in events if e["type"] == "request"]
        self.assertEqual([len(r["messages"]) for r in requests], [2, 4, 6])
        self.assertEqual(requests[1]["messages"][-1]["tool_call_id"], calls[0]["id"])

    def test_zero_and_injected_failures_are_returned_not_retried(self):
        for case in ("zero", "unknown", "malformed"):
            with self.subTest(case=case):
                events = execute("fail-safely", case)
                results = [e for e in events if e["type"] == "tool_result"]
                self.assertEqual(len(results), 1)
                self.assertFalse(results[0]["data"]["result"]["ok"])
                self.assertIn("请修正", events[-1]["data"]["content"])

    def test_offline_does_not_import_local_config(self):
        with patch.dict("sys.modules", {"local_config": None}):
            self.assertEqual(execute("tool-selection", "sum")[-1]["type"], "answer")

    def test_cancel_after_response_prevents_tool_execution(self):
        module = lesson_runtime(lesson_spec("tool-selection"))
        should_stop = False
        def complete(body, key):
            nonlocal should_stop
            should_stop = True
            return completion_for(lesson_spec("tool-selection"), "sum")(body, key)
        with patch.dict(module.AVAILABLE_TOOLS, {"add_numbers": lambda **_: self.fail("cancelled tool ran")}):
            with self.assertRaises(RunCancelled):
                run_agent("x", "", module.SYSTEM_PROMPT, module.TOOLS, module.AVAILABLE_TOOLS, 3,
                          model="offline", completion=complete, cancelled=lambda: should_stop, quiet=True)

    def test_exact_transport_request_matches_trace(self):
        from types import SimpleNamespace
        bodies = []
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"choices":[{"message":{"role":"assistant","content":"ok"}}]}'
        def open_request(request, timeout):
            bodies.append(json.loads(request.data))
            self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
            return Response()
        events = []
        with patch.dict("sys.modules", {"local_config": SimpleNamespace(API_URL="https://example.invalid/chat", MODEL="test")}):
            with patch("urllib.request.urlopen", open_request):
                run_agent("hello", "test-secret", "system", [], {}, 1, model="test", quiet=True,
                          emit=lambda k, d, r: events.append((k, d)))
        self.assertEqual(bodies[0], events[0][1]["body"])
        self.assertNotIn("test-secret", json.dumps(events))

    def test_cancel_after_tool_result_prevents_next_request(self):
        module = lesson_runtime(lesson_spec("tool-selection"))
        stopped = False
        requests = []
        def emit(kind, data, number):
            nonlocal stopped
            if kind == "request":
                requests.append(data)
            if kind == "tool_result":
                stopped = True
        with self.assertRaises(RunCancelled):
            run_agent("x", "", module.SYSTEM_PROMPT, module.TOOLS, module.AVAILABLE_TOOLS, 3,
                      model="offline", completion=completion_for(lesson_spec("tool-selection"), "sum"), cancelled=lambda: stopped,
                      emit=emit, quiet=True)
        self.assertEqual(len(requests), 1)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web.app, base_url="http://localhost")
        self.old_key = web.session_key
        use_temporary_run_store(self)

    def tearDown(self):
        web.session_key = self.old_key

    def body(self, lesson_id="tool-selection", case="sum"):
        spec = lesson_spec(lesson_id)
        exercise = next(e for e in spec["exercises"] if e["id"] == case)
        return {"lesson_id": lesson_id, "mode": "offline", "question": exercise["question"], "exercise_id": case}

    def test_sse_completes_all_offline_exercises(self):
        for spec in web.LESSONS:
            for exercise in spec["exercises"]:
                with self.subTest(lesson=spec["id"], exercise=exercise["id"]):
                    response = run_and_read(self.client, self.body(spec["id"], exercise["id"]))
                    self.assertEqual(response.status_code, 202)
                    events = response.events
                    self.assertEqual(events[0]["type"], "run_start")
                    self.assertEqual(events[-1]["data"]["status"], "completed")
                    self.assertTrue(any(e["type"] == "answer" for e in events))

    def test_input_guard_and_busy_lock(self):
        body = self.body()
        body["question"] = "free input"
        self.assertEqual(self.client.post("/api/runs", json=body).status_code, 400)
        body["mode"] = "invalid"
        self.assertEqual(self.client.post("/api/runs", json=body).status_code, 422)
        with web.run_lock:
            busy = self.client.post("/api/runs", json=self.body())
            self.assertEqual(busy.status_code, 409)
            self.assertEqual(busy.json()["code"], "run_busy")
        self.assertEqual(self.client.post("/api/runs", json=self.body(), headers={"Origin": "https://foreign.example"}).status_code, 403)
        self.assertEqual(self.client.get("/api/status", headers={"Host": "evil.example"}).status_code, 400)
        self.assertEqual(self.client.post("/api/settings", content="a" * 33000).status_code, 413)

    def test_secret_never_returned_or_echoed_by_validation(self):
        secret = "super-private-test-key"
        response = self.client.post("/api/settings", json={"api_key": secret})
        self.assertTrue(response.json()["api_key_configured"])
        self.assertNotIn(secret, self.client.get("/api/status").text)
        malformed = self.client.post("/api/settings", json={"api_key": [secret]})
        self.assertEqual(malformed.status_code, 400)
        self.assertNotIn(secret, malformed.text)
        self.assertEqual(web.scrub({secret: ["echo " + secret]}, [secret]), {"[REDACTED]": ["echo [REDACTED]"]})

    def test_sources_whitelist(self):
        response = self.client.get("/api/lessons/tool-selection").json()
        self.assertTrue(any(s["path"] == "course/runner.py" for s in response["sources"]))
        self.assertFalse(any(s["path"] == "local_config.py" for s in response["sources"]))
        self.assertEqual(self.client.get("/api/lessons/local_config.py").status_code, 404)

    def test_all_lessons_include_learning_content_and_input_schemas(self):
        for spec in web.LESSONS:
            with self.subTest(lesson=spec["id"]):
                response = self.client.get("/api/lessons/" + spec["id"])
                self.assertEqual(response.status_code, 200)
                detail = response.json()
                learning = detail["learning"]
                self.assertEqual((learning["schema_version"], learning["lesson"]), (2, spec["id"]))
                prose = [block for block in learning["scenes"]["understand"]["blocks"] if block["type"] == "prose"]
                self.assertGreaterEqual(len(prose), 2)
                for section in prose:
                    self.assertTrue(section["title"].strip())
                    self.assertTrue(all(paragraph.strip() for paragraph in section["paragraphs"]))
                experiments = learning["scenes"]["lab"]["experiments"]
                for experiment in experiments:
                    self.assertGreaterEqual(len(experiment["observe"]), 1)
                # 实验可以拆分得更有针对性，但每个练习都要出现在某个实验组里。
                self.assertEqual({arm["exercise"] for experiment in experiments for arm in experiment["arms"]},
                                 {exercise["id"] for exercise in detail["exercises"]})
                questions = learning["scenes"]["check"]["blocks"][0]["questions"]
                self.assertGreaterEqual(len(questions), 2)
                for question in questions:
                    self.assertTrue(question["prompt"].strip())
                    self.assertTrue(question["explanation"].strip())
                    option_ids = [option["id"] for option in question["options"]]
                    self.assertIn(question["correct"], option_ids)
                    self.assertTrue(all(option["text"].strip() for option in question["options"]))
                self.assertTrue(detail["sources"])
                if not spec["capabilities"]["custom_runtime"]:
                    self.assertTrue(detail["system_prompt"])
                for tool in detail["tools"]:
                    parameters = tool["function"]["parameters"]
                    self.assertEqual(parameters["type"], "object")
                    self.assertIsInstance(parameters["properties"], dict)
                    self.assertIsInstance(parameters["required"], list)
                    self.assertTrue(set(parameters["required"]).issubset(parameters["properties"]))
                    self.assertFalse(parameters["additionalProperties"])
        request_fields = web.RunInput.model_json_schema()["properties"]
        self.assertTrue({"lesson_id", "mode", "question", "exercise_id"}.issubset(request_fields))

    def test_stream_redacts_provider_echo_and_releases_lock_after_error(self):
        secret = "sensitive-test-token-987"
        web.session_key = secret
        def echoed_response(body, api_key):
            return {"choices": [{"message": {"role": "assistant", "content": "echo " + secret}}]}
        with patch.object(web, "completion_for", return_value=echoed_response):
            response = run_and_read(self.client, self.body())
        self.assertNotIn(secret, response.text)
        self.assertIn("[REDACTED]", response.text)
        def broken_response(body, api_key):
            raise RuntimeError("provider echoed " + secret)
        with patch.object(web, "completion_for", return_value=broken_response):
            response = run_and_read(self.client, self.body())
        self.assertNotIn(secret, response.text)
        self.assertIn('"status": "error"', response.text)
        self.assertFalse(web.run_lock.locked())


if __name__ == "__main__":
    unittest.main()

