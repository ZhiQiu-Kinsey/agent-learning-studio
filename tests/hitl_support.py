"""流式、审批与检查点测试的公用工具：临时课程声明、按事件轮询、等待运行结束。

课程声明与运行器都是测试里构造的，不读取 lessons/ 下的任何课程；运行存储换到临时目录。
"""
import importlib
import json
import time
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from course.execution import LessonInputs
from run_support import sse_events, use_temporary_run_store

web = importlib.import_module("server.app")


def chunk(text=None, *, index=0, finish=None, usage=None, role=None, reasoning=None, tool_calls=None,
          choices=True):
    """一个 chat.completion.chunk（确定性测试数据，形状与百炼兼容接口的流式分块相同）。"""
    delta = {}
    if role:
        delta["role"] = role
    if text is not None:
        delta["content"] = text
    if reasoning is not None:
        delta["reasoning_content"] = reasoning
    if tool_calls is not None:
        delta["tool_calls"] = tool_calls
    body = {"id": "chatcmpl-test", "object": "chat.completion.chunk", "created": 1, "model": "offline-script",
            "choices": [{"index": index, "delta": delta, "finish_reason": finish}] if choices else []}
    if usage is not None:
        body["usage"] = usage
    return body


def spec_for(lesson_id="hitl-test", *, testing=None, requires_model=True, exercises=None):
    return {"id": lesson_id, "title": "HITL test", "input_defaults": {},
            "runtime": {"kind": "custom", "entrypoint": "runtime:run", "requires_model": requires_model,
                        "max_rounds": 5, "locales": ["zh-CN", "en"]},
            "testing": dict(testing or {}),
            "exercises": exercises or [{"id": "main", "title": "Main", "question": "q"}]}


class LessonHarness(unittest.TestCase):
    """用测试里的课程声明发起运行；lesson_callable 按夹具名返回 self.fixtures 里的工厂。"""

    lesson_hash = "sha256:" + "a" * 64

    def setUp(self):
        self.client = TestClient(web.app, base_url="http://localhost")
        self.store = use_temporary_run_store(self)
        self.fixtures = {}
        self.spec = spec_for()
        self.runner = lambda context: "done"
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(web, "lesson_spec", side_effect=lambda lesson_id: self.spec))
        stack.enter_context(patch.object(web, "lesson_runtime", side_effect=lambda spec: SimpleNamespace(
            INPUT_MODEL=LessonInputs, run=lambda context: self.runner(context))))
        stack.enter_context(patch("server.offline.lesson_callable",
                                  side_effect=lambda spec, reference: self.fixtures[reference]))
        stack.enter_context(patch.object(web, "lesson_source_hash", side_effect=lambda spec: self.lesson_hash))

    def body(self, mode="offline", locale=None):
        body = {"lesson_id": self.spec["id"], "exercise_id": "main", "question": "q", "mode": mode}
        if locale:
            body["locale"] = locale
        return body

    def start(self, mode="offline", locale=None) -> str:
        created = self.client.post("/api/runs", json=self.body(mode, locale))
        self.assertEqual(created.status_code, 202, created.text)
        run_id = created.json()["run_id"]
        self.addCleanup(self.wait_finished, run_id)
        return run_id

    def read(self, run_id) -> list[dict]:
        """读完整个事件流（直到 done）；运行未结束时会一直等待，所以先确保运行能结束。"""
        return sse_events(self.client.get(f"/api/runs/{run_id}/events").text)

    def stored(self, run_id) -> list[dict]:
        """只读运行存储里已有的事件，不等待。"""
        return [json.loads(text) for _, _, text in self.store.events(run_id)]

    def wait_for(self, run_id, predicate, timeout=5.0) -> list[dict]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            events = self.stored(run_id)
            if predicate(events):
                return events
            time.sleep(0.02)
        self.fail(f"等待事件超时：{[event['type'] for event in self.stored(run_id)]}")

    def wait_finished(self, run_id, timeout=10.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if web.active_run(run_id) is None and not web.run_lock.locked():
                return
            time.sleep(0.02)
        # 用例失败时运行可能还停在审批点：先停止它并等它退出，免得互斥锁漏到下一个用例。
        active = web.active_run(run_id)
        if active is not None:
            active.request_cancel("api")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and (web.active_run(run_id) is not None or web.run_lock.locked()):
            time.sleep(0.02)
        raise AssertionError("运行没有在限定时间内结束")
