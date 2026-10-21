"""检查点与恢复：RunContext.checkpoint 的事件，/resume 接口的新运行、thread_id、错误路径，以及服务重启后恢复。

恢复不重放来源运行的模型请求：测试数清楚确定性模型适配器被调用的次数。
"""
import importlib
import json
import unittest

from course.execution import RunContext, approval_digest
from course.runner import RunCancelled
from hitl_support import LessonHarness, spec_for
from server.run_store import RunStore

web = importlib.import_module("server.app")


def make_context(events, **overrides):
    values = dict(lesson_id="cp-test", exercise_id="main", question="q", mode="offline", model="m",
                  representation="sdk_standardized", inputs={}, api_key="", completion=None,
                  emit_event=lambda kind, data, number: events.append((kind, data, number)))
    return RunContext(**{**values, **overrides})


class CheckpointContextTests(unittest.TestCase):
    def test_checkpoint_records_a_snapshot_with_digest_thread_and_source(self):
        events = []
        context = make_context(events, thread_id="t" * 32, source_hash="sha256:" + "b" * 64)
        state = {"step": "generated", "draft": {"title": "练习一"}, "saved": []}
        first = context.checkpoint("before-save", state, round_number=2)
        state["saved"].append("later")
        second = context.checkpoint("after-save", {"step": "saved"})
        self.assertEqual((first, second), ("cp-1", "cp-2"))
        kind, data, number = events[0]
        self.assertEqual((kind, number), ("checkpoint", 2))
        self.assertEqual(data["state"], {"step": "generated", "draft": {"title": "练习一"}, "saved": []})
        self.assertEqual(data["state_digest"], approval_digest(data["state"]))
        self.assertEqual((data["checkpoint_id"], data["name"], data["thread_id"], data["source_hash"]),
                         ("cp-1", "before-save", "t" * 32, "sha256:" + "b" * 64))

    def test_a_resumed_run_numbers_its_checkpoints_after_the_source_run(self):
        events = []
        context = make_context(events, thread_id="t" * 32, checkpoint_offset=3)
        self.assertEqual(context.checkpoint("again", {"step": 1}), "cp-4")
        self.assertEqual(events[0][1]["checkpoint_id"], "cp-4")

    def test_invalid_checkpoints_fail_before_any_event(self):
        events = []
        context = make_context(events)
        for name, state in (("has space", {}), ("", {}), ("x" * 65, {}), ("ok", []), ("ok", {"x": float("inf")}),
                            ("ok", {"blob": "x" * 70000})):
            with self.subTest(name=name), self.assertRaises(ValueError):
                context.checkpoint(name, state)
        self.assertEqual(events, [])
        with self.assertRaises(RunCancelled):
            make_context(events, cancelled=lambda: True).checkpoint("ok", {})

    def test_fresh_runs_have_no_resume_state(self):
        context = make_context([])
        self.assertIsNone(context.resume_state)
        self.assertIsNone(context.resumed_from)


def checkpointing_runner(saved):
    """课程运行器示例：生成后存检查点；恢复时从检查点继续，按操作标识只保存一次。"""
    def runner(context):
        if context.resume_state is None:
            reply = context.complete({"messages": [{"role": "user", "content": context.question}]}, 1)
            draft = reply["choices"][0]["message"]["content"]
            context.checkpoint("before-save", {"draft": draft, "operation_id": "save-1", "done": []})
            raise RuntimeError("simulated crash before saving")
        state = context.resume_state
        if state["operation_id"] not in saved:
            saved.append(state["operation_id"])
        reply = context.complete({"messages": [{"role": "user", "content": "confirm " + state["draft"]}]}, 2)
        context.checkpoint("after-save", {**state, "done": [state["operation_id"]]})
        return "saved once: " + reply["choices"][0]["message"]["content"]
    return runner


class ResumeApiTests(LessonHarness):
    def setUp(self):
        super().setUp()
        self.spec = spec_for(testing={"completion_factory": "fixtures:create_completion"})
        self.model_calls = []
        self.fixtures["fixtures:create_completion"] = self.create_completion
        self.saved = []
        self.runner = checkpointing_runner(self.saved)

    def create_completion(self, exercise_id, inputs=None, locale="zh-CN"):
        def completion(body, api_key):
            self.model_calls.append(body["messages"][-1]["content"])
            return {"choices": [{"index": 0, "message": {"role": "assistant", "content": f"draft-{len(self.model_calls)}"},
                                 "finish_reason": "stop"}]}
        return completion

    def resume(self, run_id, checkpoint_id="cp-1"):
        return self.client.post(f"/api/runs/{run_id}/resume", json={"checkpoint_id": checkpoint_id})

    def test_resume_starts_a_new_run_from_the_saved_state_without_replaying_requests(self):
        source_id = self.start()
        source = self.read(source_id)
        self.assertEqual(source[-1]["data"]["status"], "error")
        checkpoint = next(e for e in source if e["type"] == "checkpoint")
        self.assertEqual(checkpoint["data"]["thread_id"], source_id)
        self.assertEqual(checkpoint["data"]["source_hash"], self.lesson_hash)
        self.assertEqual(self.model_calls, ["q"])
        self.wait_finished(source_id)

        created = self.resume(source_id)
        self.assertEqual(created.status_code, 202, created.text)
        new_id = created.json()["run_id"]
        self.assertNotEqual(new_id, source_id)
        self.assertEqual(created.json()["resumed_from"], {"run_id": source_id, "checkpoint_id": "cp-1"})
        events = self.read(new_id)
        start = events[0]["data"]
        self.assertEqual(start["resumed_from"]["run_id"], source_id)
        self.assertEqual(start["resumed_from"]["checkpoint_id"], "cp-1")
        self.assertEqual(start["resumed_from"]["seq"], checkpoint["seq"])
        self.assertEqual(start["resumed_from"]["state"], checkpoint["data"]["state"])
        self.assertEqual(start["thread_id"], source_id)
        # 新运行里只有一次真实的新请求，来源运行的请求没有被重放。
        self.assertEqual([e["type"] for e in events].count("request"), 1)
        self.assertEqual(self.model_calls, ["q", "confirm draft-1"])
        self.assertEqual(self.saved, ["save-1"])
        self.assertEqual(events[-1]["data"]["status"], "completed")
        self.wait_finished(new_id)
        record = self.client.get(f"/api/runs/{new_id}").json()
        self.assertEqual((record["thread_id"], record["resumed_from_run"], record["resumed_from_checkpoint"]),
                         (source_id, source_id, "cp-1"))
        self.assertEqual(self.client.get(f"/api/runs/{source_id}").json()["thread_id"], source_id)

        # 恢复出来的运行再存的检查点仍属于同一条线程，编号接在来源运行之后，同一线程里的 id 互不重复；
        # 从它恢复，thread_id 不变。
        new_checkpoints = [e["data"]["checkpoint_id"] for e in events if e["type"] == "checkpoint"]
        self.assertTrue(new_checkpoints and "cp-1" not in new_checkpoints, new_checkpoints)
        self.assertEqual(new_checkpoints[0], "cp-2")
        again = self.resume(new_id, new_checkpoints[0])
        self.assertEqual(again.status_code, 202, again.text)
        third = self.read(again.json()["run_id"])
        self.assertEqual(third[0]["data"]["thread_id"], source_id)
        # 已经保存过的操作标识不会再保存一次：这是课程代码的责任，检查点本身不保证。
        self.assertEqual(self.saved, ["save-1"])

    def test_resume_survives_a_server_restart(self):
        source_id = self.start()
        self.read(source_id)
        self.wait_finished(source_id)
        path = self.store.path
        # 模拟重启：关闭运行存储，再按同一路径打开一个新的（新进程只能读到磁盘上的记录）。
        self.store.close()
        restarted = RunStore(path)
        self.addCleanup(restarted.close)
        web.run_store = self.store = restarted
        created = self.resume(source_id)
        self.assertEqual(created.status_code, 202, created.text)
        events = self.read(created.json()["run_id"])
        self.assertEqual(events[0]["data"]["resumed_from"]["state"]["operation_id"], "save-1")
        self.assertEqual(events[-1]["data"]["status"], "completed")

    def test_interrupted_runs_can_resume_from_their_last_checkpoint(self):
        source_id = self.start()
        self.read(source_id)
        self.wait_finished(source_id)
        # 把运行改成“进程死在半路”：状态 running、没有 done，重新打开存储后标为 interrupted。
        self.store._db.execute("UPDATE runs SET status = 'running', finished_at = NULL WHERE run_id = ?",
                               (source_id,))
        self.store._db.execute("DROP TRIGGER events_append_only_update")
        self.store._db.execute("DELETE FROM events WHERE run_id = ? AND type IN ('error', 'done')", (source_id,))
        path = self.store.path
        self.store.close()
        restarted = RunStore(path)
        self.addCleanup(restarted.close)
        web.run_store = self.store = restarted
        self.assertEqual(restarted.get_run(source_id)["status"], "interrupted")
        created = self.resume(source_id)
        self.assertEqual(created.status_code, 202, created.text)
        self.assertEqual(self.read(created.json()["run_id"])[-1]["data"]["status"], "completed")

    def test_error_paths(self):
        source_id = self.start()
        self.read(source_id)
        self.wait_finished(source_id)
        missing = self.resume(source_id, "cp-9")
        self.assertEqual((missing.status_code, missing.json()["code"]), (404, "checkpoint_not_found"))
        self.assertEqual(self.resume("f" * 32).status_code, 404)
        self.assertEqual(self.client.post(f"/api/runs/{source_id}/resume", json={"checkpoint_id": "x"}).status_code,
                         422)
        self.assertEqual(self.client.post(f"/api/runs/{source_id}/resume",
                                          json={"checkpoint_id": "cp-1", "state": {}}).status_code, 422)
        # 课程源码变了：检查点里的执行位置可能已经不对应现在的代码，拒绝恢复。
        self.lesson_hash = "sha256:" + "c" * 64
        stale = self.resume(source_id)
        self.assertEqual((stale.status_code, stale.json()["code"]), (409, "checkpoint_stale"))

    def test_runs_still_active_and_busy_lock_are_refused(self):
        import threading
        release = threading.Event()

        def runner(context):
            context.checkpoint("waiting", {"n": 1})
            release.wait(5)
            return "done"
        self.runner = runner
        self.spec = spec_for(requires_model=False)
        run_id = self.start()
        self.wait_for(run_id, lambda events: any(e["type"] == "checkpoint" for e in events))
        active = self.resume(run_id)
        self.assertEqual((active.status_code, active.json()["code"]), (409, "run_still_active"))
        release.set()
        self.read(run_id)
        self.wait_finished(run_id)
        self.assertTrue(web.run_lock.acquire(blocking=False))
        try:
            busy = self.resume(run_id)
            self.assertEqual((busy.status_code, busy.json()["code"]), (409, "run_busy"))
        finally:
            web.run_lock.release()

    def test_english_resume_keeps_the_run_language(self):
        source_id = self.start(locale="en")
        self.read(source_id)
        self.wait_finished(source_id)
        events = self.read(self.resume(source_id).json()["run_id"])
        self.assertEqual(events[0]["data"]["locale"], "en")
        self.assertEqual(events[0]["data"]["mode"], "offline")


if __name__ == "__main__":
    unittest.main()
