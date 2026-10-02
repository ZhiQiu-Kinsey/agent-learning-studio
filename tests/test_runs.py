"""事件信封 v2、运行存储与 runs 接口；使用确定性测试适配器与临时数据库，从不请求真实模型。"""
import asyncio
import importlib
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import ExitStack
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from course.execution import LessonInputs
from course.runner import RunCancelled
from run_support import run_and_read, sse_events, use_temporary_run_store
from scripts.export_trace_contract import TARGET, render
from server.envelope import SPAN_EVENTS, EnvelopeBuilder, SpanTracker, span_rule
from server.providers import PROVIDERS, ProviderRegistry
from server.run_store import RunStore

web = importlib.import_module("server.app")


def offline_body(lesson_id="tool-selection", exercise_id="sum"):
    spec = web.lesson_spec(lesson_id)
    exercise = next(e for e in spec["exercises"] if e["id"] == exercise_id)
    return {"lesson_id": lesson_id, "mode": "offline", "question": exercise["question"], "exercise_id": exercise_id}


class GatedRuntime:
    """自定义课程运行器：发出一条事件后等待放行，用于观察运行中的接口行为。"""

    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def __call__(self, context):
        context.emit("lesson.progress", {"step": 1}, 1)
        self.started.set()
        self.release.wait(10)
        context.check_cancelled()
        context.emit("lesson.progress", {"step": 2}, 2)
        return "gated"


class RunApiTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web.app, base_url="http://localhost")
        self.store = use_temporary_run_store(self)
        self.addCleanup(setattr, web, "session_key", web.session_key)

    def start_gated(self):
        gate = GatedRuntime()
        spec = {"id": "gated", "title": "Gated", "input_defaults": {},
                "runtime": {"kind": "custom", "entrypoint": "runtime:run", "requires_model": False},
                "exercises": [{"id": "gate", "title": "Gate", "question": "q"}]}
        module = SimpleNamespace(INPUT_MODEL=LessonInputs, run=gate)
        with patch.object(web, "lesson_spec", return_value=spec), \
                patch.object(web, "lesson_runtime", return_value=module):
            created = self.client.post("/api/runs", json={"lesson_id": "gated", "exercise_id": "gate",
                                                          "question": "q", "mode": "live"})
        self.assertEqual(created.status_code, 202)
        run_id = created.json()["run_id"]
        # 无论用例结果如何都放行并等待运行结束，避免锁泄漏到其他用例。
        self.addCleanup(self.wait_finished, run_id)
        self.addCleanup(gate.release.set)
        self.assertTrue(gate.started.wait(5))
        return run_id, gate

    def wait_finished(self, run_id, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if web.active_run(run_id) is None and not web.run_lock.locked():
                return
            time.sleep(0.01)
        self.fail("运行没有在预期时间内结束")


class EnvelopeAndSpanTests(RunApiTestCase):
    def test_seq_is_monotonic_and_every_event_carries_the_v2_envelope(self):
        result = run_and_read(self.client, offline_body("dependent-calls", "chain"))
        events = result.events
        self.assertEqual([e["seq"] for e in events], list(range(1, len(events) + 1)))
        for event in events:
            self.assertEqual(event["schema_version"], 2)
            self.assertEqual(event["run_id"], result.run_id)
            self.assertEqual(event["provenance"], "real_run")
            self.assertEqual(event["actor"], "agent")
            self.assertIsNone(event["role"])
            self.assertTrue({"type", "round", "timestamp", "data", "span_id", "parent_span_id",
                             "span_kind", "representation", "sdk"}.issubset(event))
        self.assertEqual(events[0]["type"], "run_start")
        self.assertEqual(events[-1]["type"], "done")
        stored = [json.loads(text) for _, _, text in self.store.events(result.run_id)]
        self.assertEqual(stored, events)

    def test_request_response_and_tool_call_result_form_paired_spans_under_round_steps(self):
        events = run_and_read(self.client, offline_body("dependent-calls", "chain")).events
        root = events[0]
        self.assertEqual((root["span_kind"], root["parent_span_id"]), ("run", None))
        self.assertEqual(events[-1]["span_id"], root["span_id"])
        steps = {}
        for event in events[1:-1]:
            if event["round"] is not None:
                step = steps.setdefault(event["round"], event["parent_span_id"] if event["span_kind"] != "step"
                                        else event["span_id"])
                if event["span_kind"] in ("llm", "tool"):
                    self.assertEqual(event["parent_span_id"], step)
        self.assertEqual(len(steps), 3)
        self.assertEqual(len(set(steps.values())), 3)
        requests = [e for e in events if e["type"] == "request"]
        responses = [e for e in events if e["type"] == "response"]
        self.assertEqual(len(requests), len(responses))
        for request, response in zip(requests, responses):
            self.assertEqual(request["span_kind"], "llm")
            self.assertEqual(request["span_id"], response["span_id"])
            self.assertLess(request["seq"], response["seq"])
        calls = {e["data"]["id"]: e for e in events if e["type"] == "tool_call"}
        results = [e for e in events if e["type"] == "tool_result"]
        self.assertEqual(len(calls), len(results))
        for result in results:
            call = calls[result["data"]["tool_call_id"]]
            self.assertEqual((call["span_kind"], call["span_id"]), ("tool", result["span_id"]))
        self.assertEqual(len({e["span_id"] for e in requests} | {e["span_id"] for e in results}),
                         len(requests) + len(results))
        answer = next(e for e in events if e["type"] == "answer")
        self.assertEqual(answer["span_kind"], "step")

    def test_tracker_handles_lesson_events_interleaved_rounds_and_unmatched_ends(self):
        tracker = SpanTracker()
        placed = [tracker.place(kind, data, number) for kind, data, number in [
            ("run_start", {}, None),
            ("lesson.note", {}, None),
            ("tool_call", {"id": "a"}, 1),
            ("tool_call", {"id": "b"}, 1),
            ("lesson.inside", {}, 1),
            ("tool_result", {"tool_call_id": "a"}, 1),
            ("tool_result", {"tool_call_id": "b"}, 1),
            ("response", {}, 1),
            ("request", {}, 2),
            ("lesson.report", {}, None),
            ("done", {}, None),
        ]]
        self.assertEqual(placed[0], ("run-1", None, "run"))
        self.assertEqual(placed[1], ("run-1", None, "run"))
        self.assertEqual(placed[2], ("tool-1", "step-1", "tool"))
        self.assertEqual(placed[3], ("tool-2", "step-1", "tool"))
        self.assertEqual(placed[4], ("tool-2", "step-1", "tool"))
        self.assertEqual(placed[5], ("tool-1", "step-1", "tool"))
        self.assertEqual(placed[6], ("tool-2", "step-1", "tool"))
        self.assertEqual(placed[7], ("step-1", "run-1", "step"), "没有打开的 llm span 时不凭空配对")
        self.assertEqual(placed[8], ("llm-1", "step-2", "llm"))
        self.assertEqual(placed[9], ("llm-1", "step-2", "llm"), "瞬时事件挂在当前未关闭的 span 下")
        self.assertEqual(placed[10], ("run-1", None, "run"))

    def test_parallel_branches_pair_responses_by_branch_not_by_order(self):
        tracker = SpanTracker()
        placed = [tracker.place(kind, data, number) for kind, data, number in [
            ("run_start", {}, None),
            ("request", {"branch": "a"}, 1),
            ("request", {"branch": "b"}, 1),
            ("response", {"branch": "a"}, 1),
            ("response", {"branch": "b"}, 1),
            ("request", {}, 2),
            ("response", {}, 2),
        ]]
        self.assertEqual(placed[1][0], "llm-1")
        self.assertEqual(placed[2][0], "llm-2")
        self.assertEqual(placed[3][0], "llm-1", "先返回的分支 a 关闭自己的 span，而不是最近打开的 b")
        self.assertEqual(placed[4][0], "llm-2")
        self.assertEqual((placed[5][0], placed[6][0]), ("llm-3", "llm-3"), "没有 branch 时行为不变")

    def test_span_table_declares_consistent_pairs_and_frontend_mirror_is_generated(self):
        for kind, rule in SPAN_EVENTS.items():
            if rule["phase"] == "start":
                closing = SPAN_EVENTS[rule["closed_by"]]
                self.assertEqual((closing["phase"], closing["opened_by"], closing["span_kind"]),
                                 ("end", kind, rule["span_kind"]))
        self.assertEqual(span_rule("lesson.anything"), {"phase": "instant"})
        self.assertTrue(TARGET.exists(), "缺少前端常量：python scripts/export_trace_contract.py")
        self.assertEqual(TARGET.read_text(encoding="utf-8"), render())

    def test_builder_refuses_unlabeled_sdk_data_and_unknown_labels(self):
        with self.assertRaises(ValueError):
            EnvelopeBuilder("x", representation="sdk_standardized")
        with self.assertRaises(ValueError):
            EnvelopeBuilder("x", representation="http_body", sdk={"name": "litellm", "version": "1"})
        with self.assertRaises(ValueError):
            EnvelopeBuilder("x", provenance="live")
        with self.assertRaises(ValueError):
            EnvelopeBuilder("x", representation="raw")


class RepresentationTests(RunApiTestCase):
    def setUp(self):
        super().setUp()
        stack = ExitStack()
        self.addCleanup(stack.close)
        previous = web.provider_registry
        web.provider_registry = ProviderRegistry()
        self.addCleanup(setattr, web, "provider_registry", previous)
        environment = {name: "" for fields in PROVIDERS.values() for name in fields[1:] if name}
        environment["DASHSCOPE_API_KEY"] = "bailian-env-secret"
        stack.enter_context(patch.dict(os.environ, environment))
        stack.enter_context(patch.dict("sys.modules", {"local_config": SimpleNamespace(
            API_URL="https://native.example.invalid/v1/chat/completions", MODEL="native-model")}))
        self.live = {"lesson_id": "tool-selection", "mode": "live", "question": "19+23", "exercise_id": "sum"}

    def model_events(self, events):
        return [e for e in events if e["type"] in ("request", "response")]

    def test_native_http_path_is_labeled_http_body_without_sdk(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{"choices":[{"message":{"role":"assistant","content":"ok"}}]}'
        with patch("urllib.request.urlopen", lambda request, timeout: Response()):
            result = run_and_read(self.client, self.live)
        model_events = self.model_events(result.events)
        self.assertEqual(len(model_events), 2)
        for event in model_events:
            self.assertEqual((event["representation"], event["sdk"]), ("http_body", None))
            self.assertEqual(event["data"]["representation"], "http_body")
        for event in result.events:
            if event["type"] not in ("request", "response"):
                self.assertIsNone(event["representation"])
        self.assertEqual(self.client.get(f"/api/runs/{result.run_id}").json()["representation"], "http_body")

    def test_sdk_path_is_labeled_sdk_standardized_with_name_and_version(self):
        self.client.post("/api/settings", json={"provider_id": "custom", "model": "hosted/model",
                                                "api_key": "sdk-secret", "api_base": "https://sdk.example.invalid/v1"})
        reply = {"choices": [{"message": {"role": "assistant", "content": "done"}}]}
        with patch("course.providers.sdk_completion", return_value=reply):
            result = run_and_read(self.client, self.live)
        model_events = self.model_events(result.events)
        self.assertEqual(len(model_events), 2)
        for event in model_events:
            self.assertEqual(event["representation"], "sdk_standardized")
            self.assertNotIn(event["representation"], ("http_body", "wire"))
            self.assertEqual(event["sdk"], {"name": "litellm", "version": metadata.version("litellm")})
        self.assertNotIn("sdk-secret", result.text)

    def test_deterministic_test_adapter_is_not_presented_as_an_sdk_or_http(self):
        events = run_and_read(self.client, offline_body()).events
        for event in self.model_events(events):
            self.assertEqual(event["representation"], "sdk_standardized")
            self.assertEqual(event["sdk"], {"name": "deterministic-test-adapter", "version": None})


class ResumeTests(RunApiTestCase):
    def collect(self, run_id, from_seq, limit=None):
        """直接驱动 SSE 生成器；limit 条后关闭，模拟浏览器断线。"""
        class ConnectedRequest:
            async def is_disconnected(self):
                return False

        async def read():
            response = await web.run_events(run_id, ConnectedRequest(), from_seq=from_seq, last_event_id=None)
            events = []
            iterator = response.body_iterator
            try:
                async for chunk in iterator:
                    events.extend(sse_events(chunk))
                    if limit is not None and len(events) >= limit:
                        break
            finally:
                await iterator.aclose()
            return events

        return asyncio.run(asyncio.wait_for(read(), 10))

    def test_reconnect_from_last_seq_continues_live_without_duplicates_or_gaps(self):
        run_id, gate = self.start_gated()
        first = self.collect(run_id, 1, limit=2)
        self.assertEqual([e["type"] for e in first], ["run_start", "lesson.progress"])
        self.assertIsNotNone(web.active_run(run_id), "断线不应取消服务端运行")
        timer = threading.Timer(0.2, gate.release.set)
        timer.start()
        self.addCleanup(timer.cancel)
        rest = self.collect(run_id, first[-1]["seq"] + 1)
        combined = first + rest
        self.assertEqual([e["seq"] for e in combined], list(range(1, len(combined) + 1)))
        self.assertEqual(combined[-1]["type"], "done")
        self.assertEqual(combined[-1]["data"]["status"], "completed")
        self.assertEqual(combined, [json.loads(text) for _, _, text in self.store.events(run_id)])

    def test_finished_runs_replay_from_any_seq_and_last_event_id(self):
        result = run_and_read(self.client, offline_body())
        full = result.events
        for start in (1, 3, len(full)):
            tail = sse_events(self.client.get(f"/api/runs/{result.run_id}/events?from_seq={start}").text)
            self.assertEqual(tail, full[start - 1:])
        header = sse_events(self.client.get(f"/api/runs/{result.run_id}/events",
                                            headers={"Last-Event-ID": "2"}).text)
        self.assertEqual(header, full[2:])
        self.assertEqual(self.client.get(f"/api/runs/{result.run_id}/events?from_seq={len(full) + 5}").text, "")
        self.assertEqual(self.client.get(f"/api/runs/{result.run_id}/events?from_seq=0").status_code, 422)
        self.assertEqual(self.client.get("/api/runs/" + "0" * 32 + "/events").status_code, 404)


class StorageTests(RunApiTestCase):
    def test_only_redacted_events_reach_the_database(self):
        secret = "stored-secret-key-4521"
        web.session_key = secret
        echoed = lambda body, key: {"choices": [{"message": {"role": "assistant", "content": "echo " + secret}}]}
        with patch.object(web, "completion_for", return_value=echoed):
            result = run_and_read(self.client, offline_body())
        self.assertIn("[REDACTED]", result.text)
        texts = [text for _, _, text in self.store.events(result.run_id)]
        self.assertTrue(texts)
        self.assertFalse(any(secret in text for text in texts))
        raw = b"".join(path.read_bytes() for path in self.store.path.parent.iterdir() if path.is_file())
        self.assertNotIn(secret.encode(), raw)

    def test_list_metadata_and_clear(self):
        first = run_and_read(self.client, offline_body())
        second = run_and_read(self.client, offline_body("fail-safely", "zero"))
        listed = self.client.get("/api/runs").json()["runs"]
        self.assertEqual([run["run_id"] for run in listed], [second.run_id, first.run_id])
        meta = self.client.get(f"/api/runs/{first.run_id}").json()
        self.assertEqual({key: meta[key] for key in ("lesson_id", "exercise_id", "mode", "status", "provenance",
                                                     "schema_version", "event_count", "last_seq")},
                         {"lesson_id": "tool-selection", "exercise_id": "sum", "mode": "offline", "status": "completed",
                          "provenance": "real_run", "schema_version": 2, "event_count": len(first.events),
                          "last_seq": len(first.events)})
        self.assertTrue(meta["finished_at"])
        with web.run_lock:
            busy = self.client.delete("/api/runs")
        self.assertEqual((busy.status_code, busy.json()["code"]), (409, "run_active"))
        self.assertEqual(len(self.client.get("/api/runs").json()["runs"]), 2)
        self.assertEqual(self.client.delete("/api/runs", headers={"Origin": "https://foreign.example"}).status_code, 403)
        cleared = self.client.delete("/api/runs")
        self.assertEqual(cleared.json(), {"deleted": 2})
        self.assertEqual(self.client.get("/api/runs").json(), {"runs": []})
        missing = self.client.get(f"/api/runs/{first.run_id}")
        self.assertEqual((missing.status_code, missing.json()["code"]), (404, "run_not_found"))
        self.assertEqual(self.client.get("/api/runs/not-a-run-id").status_code, 404)

    def test_store_is_append_only_unique_and_marks_abandoned_runs_interrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.sqlite3"
            store = RunStore(path)
            store.create_run(run_id="r", lesson_id="1", exercise_id="sum", mode="offline", model="m",
                             provider_id="testing", representation=None, provenance="real_run",
                             schema_version=2, created_at="2026-10-01T00:00:00+00:00")
            store.append("r", 1, "run_start", "{}")
            with self.assertRaises(sqlite3.IntegrityError):
                store.append("r", 1, "run_start", "{}")
            with self.assertRaises(sqlite3.DatabaseError):
                store._db.execute("UPDATE events SET event = 'changed'")
            self.assertEqual(store._db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            store.close()
            reopened = RunStore(path)
            self.assertEqual(reopened.get_run("r")["status"], "interrupted")
            self.assertEqual(reopened.events("r"), [(1, "run_start", "{}")])
            reopened.close()

    def test_tests_never_touch_the_real_runtime_directory(self):
        self.assertNotEqual(web.get_run_store().path.parent.resolve(), web.RUNTIME_DIR.resolve())


class LifecycleTests(RunApiTestCase):
    def test_mutex_cancel_by_run_id_and_approval_skeleton(self):
        run_id, gate = self.start_gated()
        busy = self.client.post("/api/runs", json=offline_body())
        self.assertEqual((busy.status_code, busy.json()["code"]), (409, "run_busy"))
        cleared = self.client.delete("/api/runs")
        self.assertEqual((cleared.status_code, cleared.json()["code"]), (409, "run_active"))
        approval = {"approval_id": "missing", "decision": "approve"}
        pending = self.client.post(f"/api/runs/{run_id}/approvals", json=approval)
        self.assertEqual((pending.status_code, pending.json()["code"]), (409, "no_pending_approval"))
        self.assertEqual(self.client.get(f"/api/runs/{run_id}").json()["status"], "running")
        stopped = self.client.post(f"/api/runs/{run_id}/cancel")
        self.assertEqual((stopped.status_code, stopped.json()["status"]), (202, "cancelling"))
        gate.release.set()
        events = sse_events(self.client.get(f"/api/runs/{run_id}/events").text)
        self.assertEqual(events[-1]["data"]["status"], "cancelled")
        self.assertNotIn("answer", [e["type"] for e in events])
        self.wait_finished(run_id)
        again = self.client.post(f"/api/runs/{run_id}/cancel")
        self.assertEqual((again.status_code, again.json()["code"]), (409, "run_not_active"))
        self.assertEqual(self.client.post(f"/api/runs/{'f' * 32}/cancel").status_code, 404)
        finished = self.client.post(f"/api/runs/{run_id}/approvals", json=approval)
        self.assertEqual((finished.status_code, finished.json()["code"]), (409, "no_pending_approval"))
        unknown = self.client.post(f"/api/runs/{'f' * 32}/approvals", json=approval)
        self.assertEqual((unknown.status_code, unknown.json()["code"]), (404, "run_not_found"))
        invalid = self.client.post(f"/api/runs/{run_id}/approvals", json={"approval_id": "x", "decision": "maybe"})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(self.client.get(f"/api/runs/{run_id}").json()["status"], "cancelled")
        # 运行结束后立即可以开始下一次运行。
        self.assertEqual(run_and_read(self.client, offline_body()).events[-1]["data"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
