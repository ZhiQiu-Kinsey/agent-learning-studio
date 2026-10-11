"""真实工具、模拟模型与本地 Web API 的回归检查；从不请求百炼。"""
import importlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from course.api_client import send_bailian
from course.execution import RunContext, execute_lesson
from course.runner import AgentSetup, RunCancelled
from server.catalog import lesson_runtime, lesson_spec
from server.offline import completion_for
from run_support import run_and_read, use_temporary_run_store

web = importlib.import_module("server.app")


def native_context(events, completion, *, cancelled=lambda: False, model="offline-script", budget=3,
                   representation="local", emit=None):
    """原生课程在网页里的运行方式：RunContext 提供 complete 与 execute_proposal，循环本身来自 course.runner。"""
    return RunContext(lesson_id="native", exercise_id="test", question="练习", mode="offline", model=model,
                      representation=representation, inputs={}, api_key="test-secret", completion=completion,
                      emit_event=emit or (lambda kind, data, number: events.append({"type": kind, "data": data})),
                      cancelled=cancelled, max_model_calls=budget)


def execute(lesson_id, exercise_id):
    spec = lesson_spec(lesson_id)
    module = lesson_runtime(spec)
    events = []
    context = native_context(events, completion_for(spec, exercise_id), budget=spec["runtime"]["max_rounds"])
    context.run_native(module, spec["runtime"]["max_rounds"], publish_answer=True)
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

    def test_independent_calls_from_one_response_run_one_after_another(self):
        events = execute("dependent-calls", "both")
        responses = [e["data"]["body"] for e in events if e["type"] == "response"]
        ids = [call["id"] for call in responses[0]["choices"][0]["message"]["tool_calls"]]
        self.assertEqual(len(ids), 2)
        # 同一轮的两个调用逐个执行：前一个的结果记下之后，后一个才开始。
        steps = [(e["type"], e["data"].get("id") or e["data"].get("tool_call_id"))
                 for e in events if e["type"] in ("tool_call", "tool_result")]
        self.assertEqual(steps, [("tool_call", ids[0]), ("tool_result", ids[0]),
                                 ("tool_call", ids[1]), ("tool_result", ids[1])])
        results = [e["data"]["result"] for e in events if e["type"] == "tool_result"]
        self.assertEqual(results[0], {"ok": True, "result": 42})
        self.assertTrue(results[1]["ok"])
        requests = [e["data"]["body"] for e in events if e["type"] == "request"]
        self.assertEqual(len(requests), 2)
        self.assertEqual([m["tool_call_id"] for m in requests[1]["messages"] if m["role"] == "tool"], ids)
        self.assertEqual(events[-1]["type"], "answer")

    def test_zero_failure_is_returned_not_retried(self):
        events = execute("fail-safely", "zero")
        results = [e for e in events if e["type"] == "tool_result"]
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["data"]["result"]["ok"])
        self.assertIn("请修正", events[-1]["data"]["content"])

    def test_injected_faults_run_without_a_model_and_stop_before_any_function(self):
        """故障注入不调用模型：运行器构造的调用走同一个 execute_tool，事件标为运行器发起（origin: course_program）。"""
        spec = lesson_spec("fail-safely")
        module = lesson_runtime(spec)
        tools = importlib.import_module("lessons.lesson_03_fail_safely.tools")
        for case, error_type in (("unknown", "ValueError"), ("malformed", "JSONDecodeError")):
            with self.subTest(case=case):
                events = []
                context = RunContext(
                    lesson_id="fail-safely", exercise_id=case, question="q", mode="live", model="local-python",
                    representation="local", inputs={}, api_key="", completion=None,
                    emit_event=lambda kind, data, number: events.append({"type": kind, "data": data}))
                with patch.object(tools, "divide_numbers", lambda *_, **__: self.fail("函数被执行了")):
                    execute_lesson(spec, module, context)
                self.assertEqual([e["type"] for e in events], ["tool_call", "tool_result", "answer"])
                call, outcome, answer = (e["data"] for e in events)
                self.assertEqual(call["origin"], "course_program")
                self.assertEqual((outcome["result"]["ok"], outcome["result"]["error_type"]), (False, error_type))
                self.assertEqual(outcome["tool_call_id"], call["id"])
                self.assertIn(error_type, answer["content"])

    def test_exercise_without_model_needs_no_connection(self):
        plan = web.prepare_run(web.RunInput(lesson_id="fail-safely", exercise_id="unknown", mode="live",
                                            question="q"))
        self.assertIsNone(plan.completion)
        self.assertEqual((plan.provider_id, plan.model, plan.representation), ("local", "local-python", "local"))
        # 同一课需要模型的练习照旧要求连接配置。
        self.assertEqual(lesson_spec("fail-safely")["runtime"]["requires_model"], True)

    def test_submit_call_passes_raw_arguments_to_the_same_checks(self):
        events = []
        context = native_context(events, None)
        result = context.submit_call("divide_numbers", "{bad json", {"divide_numbers": lambda **_: self.fail("ran")})
        self.assertEqual(result["error_type"], "JSONDecodeError")
        self.assertEqual(events[0]["data"]["function"]["arguments"], "{bad json")
        self.assertEqual(events[0]["data"]["origin"], "course_program")

    def test_call_without_id_gets_a_marked_synthesized_id_that_pairs_and_reaches_the_history(self):
        """服务商漏发或发空调用 id 时，平台补一个确定的 id，并在 tool_call 事件里标明是补的；记录的响应保持原样。"""
        replies = iter([
            {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
                {"type": "function", "function": {"name": "add", "arguments": '{"a": 1, "b": 2}'}},
                {"id": "", "type": "function", "function": {"name": "add", "arguments": '{"a": 3, "b": 4}'}},
                {"id": "call_kept", "type": "function", "function": {"name": "add", "arguments": '{"a": 5, "b": 6}'}},
            ]}}]},
            {"choices": [{"message": {"role": "assistant", "content": "done"}}]},
        ])
        events = []
        module = SimpleNamespace(setup=lambda locale: AgentSetup("system", [], {"add": lambda a, b: a + b}))
        answer = native_context(events, lambda body, key: next(replies)).run_native(module, 3, publish_answer=True)
        self.assertEqual(answer, "done")
        calls = [e["data"] for e in events if e["type"] == "tool_call"]
        results = [e["data"] for e in events if e["type"] == "tool_result"]
        self.assertEqual([c["id"] for c in calls], ["synthesized_call_1_1", "synthesized_call_1_2", "call_kept"])
        self.assertEqual([c.get("id_synthesized") for c in calls], [True, True, None])
        self.assertEqual([r["tool_call_id"] for r in results], [c["id"] for c in calls])
        self.assertEqual([r["result"] for r in results], [{"ok": True, "result": n} for n in (3, 7, 11)])
        # 响应证据是服务商发来的原样：第一个调用没有 id，第二个是空字符串。
        response_calls = [e for e in events if e["type"] == "response"][0]["data"]["body"]["choices"][0]["message"]["tool_calls"]
        self.assertNotIn("id", response_calls[0])
        self.assertEqual(response_calls[1]["id"], "")
        # 下一轮请求里，助手消息的调用与工具消息用同一个补上的 id，请求格式正确。
        history = [e for e in events if e["type"] == "request"][1]["data"]["body"]["messages"]
        self.assertEqual([c["id"] for c in history[2]["tool_calls"]], [c["id"] for c in calls])
        self.assertEqual([m["tool_call_id"] for m in history if m["role"] == "tool"], [c["id"] for c in calls])
        self.assertNotIn("id_synthesized", json.dumps(history))

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
        def setup(locale):
            agent = module.setup(locale)
            return AgentSetup(agent.system_prompt, agent.tools,
                              {**agent.available_tools, "add_numbers": lambda **_: self.fail("cancelled tool ran")})
        with self.assertRaises(RunCancelled):
            native_context([], complete, cancelled=lambda: should_stop).run_native(SimpleNamespace(setup=setup), 3)

    def test_exact_transport_request_matches_trace(self):
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
        module = SimpleNamespace(setup=lambda locale: AgentSetup("system", [], {}))
        with patch.dict("sys.modules", {"local_config": SimpleNamespace(API_URL="https://example.invalid/chat", MODEL="test")}):
            with patch("urllib.request.urlopen", open_request):
                native_context(events, send_bailian, model="test", budget=1,
                               representation="http_body").run_native(module, 1)
        self.assertEqual(bodies[0], events[0]["data"]["body"])
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
            native_context([], completion_for(lesson_spec("tool-selection"), "sum"), cancelled=lambda: stopped,
                           emit=emit).run_native(module, 3)
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

