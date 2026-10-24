"""审批闸门：RunContext.request_approval 的事件、决定来源、超时、取消与参数摘要，接口提交的校验与回放只读。

离线决定来自测试里注入的 approval_policy 或课程夹具；真实运行只接受接口提交的人的决定。
"""
import importlib
import json
import re
import threading
import unittest

from course.execution import RunContext, approval_digest
from course.runner import RunCancelled
from hitl_support import LessonHarness, spec_for

web = importlib.import_module("server.app")
CJK = re.compile(r"[㐀-鿿＀-￯　-〿]")
PAYLOAD = {"path": "notes/plan.md", "content": "# 计划\n第一步"}


def make_context(events, **overrides):
    values = dict(lesson_id="approval-test", exercise_id="main", question="q", mode="offline", model="m",
                  representation="sdk_standardized", inputs={}, api_key="", completion=None,
                  emit_event=lambda kind, data, number: events.append((kind, data, number)))
    return RunContext(**{**values, **overrides})


class RequestApprovalTests(unittest.TestCase):
    def test_policy_decision_is_recorded_with_the_exact_payload_and_digest(self):
        events, seen = [], []
        policy = lambda request: seen.append(request) or {"decision": "approve", "note": "看过了"}
        context = make_context(events, approval_policy=policy)
        payload = json.loads(json.dumps(PAYLOAD))
        decision = context.request_approval("file.write", "写入 notes/plan.md", payload, risk="high",
                                            timeout_s=30, round_number=2)
        payload["content"] = "changed later"
        self.assertEqual([kind for kind, _, _ in events], ["approval_requested", "approval_resolved"])
        requested, resolved = events[0][1], events[1][1]
        self.assertEqual(requested["payload"], PAYLOAD)
        self.assertEqual(requested["payload_digest"], approval_digest(PAYLOAD))
        self.assertEqual((requested["approval_id"], requested["kind"], requested["risk"], requested["editable"]),
                         ("approval-1", "file.write", "high", False))
        self.assertEqual(requested["timeout_s"], 30)
        self.assertIn("expires_at", requested)
        self.assertEqual(seen[0], requested)
        self.assertEqual((resolved["outcome"], resolved["decided_by"], resolved["note"], resolved["edited"]),
                         ("approved", "offline_fixture", "看过了", False))
        self.assertEqual(resolved["payload_digest"], requested["payload_digest"])
        self.assertNotIn("payload", resolved)
        self.assertEqual({number for _, _, number in events}, {2})
        self.assertTrue(decision.approved)
        self.assertEqual(decision.payload, PAYLOAD)
        self.assertTrue(decision.matches(PAYLOAD))
        self.assertFalse(decision.matches({**PAYLOAD, "path": "other.md"}))

    def test_digest_ignores_key_order_but_not_values(self):
        self.assertEqual(approval_digest({"a": 1, "b": [1, 2]}), approval_digest({"b": [1, 2], "a": 1}))
        self.assertNotEqual(approval_digest({"a": 1}), approval_digest({"a": "1"}))
        self.assertRegex(approval_digest({}), r"^sha256:[0-9a-f]{64}$")

    def test_rejection_and_timeout_are_returned_not_raised(self):
        for answer, outcome, by in (({"decision": "reject", "note": "路径不对"}, "rejected", "offline_fixture"),
                                    ({"decision": "timeout"}, "timeout", "timeout")):
            with self.subTest(outcome=outcome):
                events = []
                decision = make_context(events, approval_policy=lambda request: answer).request_approval(
                    "file.write", "s", PAYLOAD)
                self.assertFalse(decision.approved)
                self.assertEqual((decision.outcome, decision.decided_by), (outcome, by))
                self.assertEqual(events[-1][1]["outcome"], outcome)

    def test_tool_does_not_run_before_or_without_approval(self):
        writes = []

        def lesson(context):
            payload = {"path": "a.txt", "content": "x"}
            decision = context.request_approval("file.write", "write a.txt", payload)
            if decision.approved and decision.matches(payload):
                writes.append(payload["path"])
            return decision.outcome

        order = []
        context = make_context([], approval_policy=lambda request: order.append(len(writes)) or {"decision": "reject"})
        self.assertEqual(lesson(context), "rejected")
        self.assertEqual((order, writes), ([0], []))
        context = make_context([], approval_policy=lambda request: {"decision": "approve"})
        self.assertEqual(lesson(context), "approved")
        self.assertEqual(writes, ["a.txt"])

    def test_policy_none_leaves_the_decision_to_the_gate(self):
        events, gate_calls = [], []

        def gate(request, timeout_s):
            gate_calls.append((request["approval_id"], timeout_s))
            return {"decision": "approve", "note": None}
        context = make_context(events, approval_policy=lambda request: None, approval_gate=gate)
        decision = context.request_approval("file.write", "s", PAYLOAD, timeout_s=12)
        self.assertEqual(gate_calls, [("approval-1", 12)])
        self.assertEqual(decision.decided_by, "learner")
        self.assertNotIn("note", events[-1][1])

    def test_edited_payload_is_used_and_recorded_only_when_editable(self):
        events = []
        edited = {**PAYLOAD, "path": "notes/plan-v2.md"}
        context = make_context(events, approval_policy=lambda request: {"decision": "approve",
                                                                        "edited_payload": edited})
        decision = context.request_approval("file.write", "s", PAYLOAD, editable=True)
        resolved = events[-1][1]
        self.assertTrue(decision.edited)
        self.assertEqual(decision.payload, edited)
        self.assertEqual((resolved["edited"], resolved["payload"]), (True, edited))
        self.assertEqual(resolved["requested_digest"], approval_digest(PAYLOAD))
        self.assertEqual(resolved["payload_digest"], approval_digest(edited))
        with self.assertRaises(ValueError):
            make_context([], approval_policy=lambda request: {"decision": "approve", "edited_payload": edited}) \
                .request_approval("file.write", "s", PAYLOAD)

    def test_cancel_while_waiting_records_the_end_then_raises(self):
        events = []
        context = make_context(events, approval_gate=lambda request, timeout_s: {"decision": "cancelled"})
        with self.assertRaises(RunCancelled):
            context.request_approval("file.write", "s", PAYLOAD)
        self.assertEqual(events[-1][1]["outcome"], "cancelled")
        self.assertEqual(events[-1][1]["decided_by"], "run_cancelled")

    def test_invalid_requests_fail_before_any_event(self):
        events = []
        context = make_context(events, approval_policy=lambda request: {"decision": "approve"})
        cases = [("File Write", "s", PAYLOAD, {}), ("file.write", "", PAYLOAD, {}),
                 ("file.write", "s", ["not", "a", "dict"], {}), ("file.write", "s", {"x": float("nan")}, {}),
                 ("file.write", "s", PAYLOAD, {"timeout_s": 0}), ("file.write", "s", PAYLOAD, {"timeout_s": True}),
                 ("file.write", "s", PAYLOAD, {"risk": "extreme"}), ("file.write", "s", PAYLOAD, {"editable": 1}),
                 ("file.write", "s", {"blob": "x" * 20000}, {})]
        for kind, summary, payload, options in cases:
            with self.subTest(kind=kind, options=options), self.assertRaises(ValueError):
                context.request_approval(kind, summary, payload, **options)
        with self.assertRaises(ValueError):
            make_context(events).request_approval("file.write", "s", PAYLOAD)
        self.assertEqual(events, [])

    def test_malformed_policy_answers_are_programming_errors(self):
        for answer in ("approve", {"decision": "maybe"}, {"decision": "approve", "note": 3}):
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                make_context([], approval_policy=lambda request: answer).request_approval("file.write", "s", PAYLOAD)

    def test_lesson_code_cannot_fake_approval_events(self):
        context = make_context([], approval_policy=lambda request: {"decision": "approve"})
        for kind in ("approval_requested", "approval_resolved", "checkpoint", "response_delta"):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                context.emit(kind, {"approval_id": "approval-1"})


def approval_runner(release_note=None, **options):
    """课程运行器示例：先请求审批，批准才“写入”，拒绝或超时如实回答。"""
    def runner(context):
        payload = {"path": "notes/plan.md", "content": "draft"}
        decision = context.request_approval("file.write", "write notes/plan.md", payload, **options)
        if decision.approved and decision.matches(decision.payload):
            context.emit("lesson.report", {"title": "write", "written": decision.payload["path"]}, 1)
            return "written " + decision.payload["path"]
        return decision.outcome
    return runner


class ApprovalApiTests(LessonHarness):
    def setUp(self):
        super().setUp()
        self.spec = spec_for(requires_model=False)

    def pending(self, run_id):
        events = self.wait_for(run_id, lambda items: any(e["type"] == "approval_requested" for e in items))
        return next(e for e in events if e["type"] == "approval_requested")

    def submit(self, run_id, **body):
        return self.client.post(f"/api/runs/{run_id}/approvals", json=body)

    def test_learner_decision_resumes_the_run_and_replay_stays_read_only(self):
        self.runner = approval_runner(timeout_s=30)
        run_id = self.start(mode="live")
        requested = self.pending(run_id)
        self.assertEqual(requested["span_kind"], "approval")
        self.assertEqual(self.client.get(f"/api/runs/{run_id}").json()["status"], "paused")
        approval_id, digest = requested["data"]["approval_id"], requested["data"]["payload_digest"]
        wrong = self.submit(run_id, approval_id=approval_id, decision="approve", payload_digest="sha256:" + "0" * 64)
        self.assertEqual((wrong.status_code, wrong.json()["code"]), (409, "approval_digest_mismatch"))
        other = self.submit(run_id, approval_id="approval-9", decision="approve", payload_digest=digest)
        self.assertEqual((other.status_code, other.json()["code"]), (409, "no_pending_approval"))
        edit = self.submit(run_id, approval_id=approval_id, decision="approve", payload_digest=digest,
                           edited_payload={"path": "elsewhere"})
        self.assertEqual((edit.status_code, edit.json()["code"]), (422, "approval_edit_not_allowed"))
        malformed = self.submit(run_id, approval_id="approval-1; drop", decision="approve", payload_digest=digest)
        self.assertEqual(malformed.status_code, 422)
        accepted = self.submit(run_id, approval_id=approval_id, decision="approve", payload_digest=digest,
                               note="路径核对过")
        self.assertEqual((accepted.status_code, accepted.json()["status"]), (200, "accepted"))
        again = self.submit(run_id, approval_id=approval_id, decision="reject", payload_digest=digest)
        self.assertEqual(again.status_code, 409)
        events = self.read(run_id)
        resolved = next(e for e in events if e["type"] == "approval_resolved")
        self.assertEqual((resolved["data"]["outcome"], resolved["data"]["decided_by"], resolved["data"]["note"]),
                         ("approved", "learner", "路径核对过"))
        self.assertEqual(resolved["span_id"], requested["span_id"])
        kinds = [e["type"] for e in events]
        self.assertLess(kinds.index("approval_resolved"), kinds.index("lesson.report"))
        self.assertEqual(events[-2]["data"]["content"], "written notes/plan.md")
        self.wait_finished(run_id)
        self.assertEqual(self.client.get(f"/api/runs/{run_id}").json()["status"], "completed")
        # 回放只读：运行结束后不能再批准，事件也不会变。
        late = self.submit(run_id, approval_id=approval_id, decision="approve", payload_digest=digest)
        self.assertEqual((late.status_code, late.json()["code"]), (409, "approval_run_finished"))
        self.assertEqual(self.read(run_id), events)

    def test_rejection_ends_honestly_and_nothing_is_written(self):
        self.runner = approval_runner(timeout_s=30)
        run_id = self.start(mode="live")
        requested = self.pending(run_id)["data"]
        self.submit(run_id, approval_id=requested["approval_id"], decision="reject",
                    payload_digest=requested["payload_digest"], note="不要写这个文件")
        events = self.read(run_id)
        self.assertNotIn("lesson.report", [e["type"] for e in events])
        self.assertEqual(events[-2]["data"]["content"], "rejected")
        self.assertEqual(events[-1]["data"]["status"], "completed")

    def test_editable_request_accepts_an_edited_payload(self):
        self.runner = approval_runner(timeout_s=30, editable=True)
        run_id = self.start(mode="live")
        requested = self.pending(run_id)["data"]
        self.assertTrue(requested["editable"])
        response = self.submit(run_id, approval_id=requested["approval_id"], decision="approve",
                               payload_digest=requested["payload_digest"],
                               edited_payload={"path": "notes/plan-v2.md", "content": "draft"})
        self.assertEqual(response.status_code, 200)
        events = self.read(run_id)
        resolved = next(e for e in events if e["type"] == "approval_resolved")["data"]
        self.assertEqual((resolved["edited"], resolved["payload"]["path"]), (True, "notes/plan-v2.md"))
        self.assertEqual(events[-2]["data"]["content"], "written notes/plan-v2.md")

    def test_timeout_has_a_clear_outcome(self):
        self.runner = approval_runner(timeout_s=1)
        events = self.read(self.start(mode="live"))
        resolved = next(e for e in events if e["type"] == "approval_resolved")["data"]
        self.assertEqual((resolved["outcome"], resolved["decided_by"]), ("timeout", "timeout"))
        self.assertGreaterEqual(resolved["waited_ms"], 900)
        self.assertEqual(events[-2]["data"]["content"], "timeout")

    def test_stop_while_waiting_cancels_the_run(self):
        self.runner = approval_runner(timeout_s=30)
        run_id = self.start(mode="live")
        self.pending(run_id)
        self.client.post(f"/api/runs/{run_id}/cancel", json={"reason": "user_stop"})
        events = self.read(run_id)
        resolved = next(e for e in events if e["type"] == "approval_resolved")["data"]
        self.assertEqual(resolved["outcome"], "cancelled")
        self.assertEqual((events[-1]["data"]["status"], events[-1]["data"]["cancel_reason"]),
                         ("cancelled", "user_stop"))
        self.wait_finished(run_id)
        self.assertEqual(self.client.get(f"/api/runs/{run_id}").json()["status"], "cancelled")

    def test_offline_fixture_decides_only_in_offline_mode(self):
        calls = []

        def create_policy(exercise_id, inputs=None, locale="zh-CN"):
            calls.append((exercise_id, locale))
            return lambda request: {"decision": "approve", "note": "fixture"}
        self.fixtures["fixtures:create_approval_policy"] = create_policy
        self.spec = spec_for(requires_model=False, testing={"approval_factory": "fixtures:create_approval_policy"})
        self.runner = approval_runner(timeout_s=30)
        events = self.read(self.start(mode="offline", locale="en"))
        resolved = next(e for e in events if e["type"] == "approval_resolved")["data"]
        self.assertEqual((resolved["decided_by"], resolved["note"]), ("offline_fixture", "fixture"))
        self.assertEqual(calls, [("main", "en")])
        self.assertIsNone(CJK.search(json.dumps(events, ensure_ascii=False)))
        # 真实模式不加载审批夹具：决定只能来自页面提交。
        plan = web.prepare_run(web.RunInput(**self.body(mode="live")))
        self.assertIsNone(plan.approval_policy)
        self.assertEqual(len(calls), 1)

    def test_policy_returning_none_waits_for_the_api_like_a_live_run(self):
        self.fixtures["fixtures:create_approval_policy"] = lambda exercise_id, inputs=None, locale="zh-CN": (
            lambda request: None)
        self.spec = spec_for(requires_model=False, testing={"approval_factory": "fixtures:create_approval_policy"})
        self.runner = approval_runner(timeout_s=30)
        run_id = self.start(mode="offline")
        requested = self.pending(run_id)["data"]
        self.submit(run_id, approval_id=requested["approval_id"], decision="approve",
                    payload_digest=requested["payload_digest"])
        resolved = next(e for e in self.read(run_id) if e["type"] == "approval_resolved")["data"]
        self.assertEqual(resolved["decided_by"], "learner")


class RunStoreStatusTests(LessonHarness):
    def test_paused_runs_are_marked_interrupted_after_a_restart(self):
        from server.run_store import RunStore
        self.store.create_run(run_id="p" * 32, lesson_id="x", exercise_id="e", mode="live", model="m",
                              provider_id="local", representation=None, provenance="real_run", schema_version=2,
                              created_at="2026-10-20T00:00:00+00:00")
        self.store.set_live_status("p" * 32, "paused")
        self.assertEqual(self.store.get_run("p" * 32)["status"], "paused")
        with self.assertRaises(ValueError):
            self.store.set_live_status("p" * 32, "completed")
        reopened = RunStore(self.store.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get_run("p" * 32)["status"], "interrupted")
        # 已结束的运行不会被改回 running/paused。
        reopened.set_live_status("p" * 32, "running")
        self.assertEqual(reopened.get_run("p" * 32)["status"], "interrupted")


if __name__ == "__main__":
    unittest.main()
