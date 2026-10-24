"""scripts/run_live.py：不连服务、不调模型，只检查它怎么挑练习、怎么处理被拒绝的运行。"""
import io
import json
import sys
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_live  # noqa: E402

DETAIL = {"id": "fail-safely", "exercises": [
    {"id": "divide", "question": "q1"},
    {"id": "unknown", "question": "q2", "offline_only": True},
]}
DONE = 'data: {"type": "done", "data": {"status": "completed"}}\n\n'


class RunLiveTests(unittest.TestCase):
    def run_main(self, fake_call, argv):
        out = io.StringIO()
        with patch.object(run_live, "call", side_effect=fake_call), redirect_stdout(out):
            code = run_live.main(argv)
        return code, out.getvalue()

    def test_live_mode_skips_offline_only_exercises_instead_of_crashing(self):
        posted = []

        def fake_call(base, path, payload=None, timeout=300):
            if path.startswith("/api/lessons/"):
                return json.dumps(DETAIL)
            if path == "/api/runs":
                posted.append(payload)
                return json.dumps({"run_id": "r1"})
            return DONE

        code, out = self.run_main(fake_call, ["fail-safely"])
        self.assertEqual(code, 0)
        self.assertEqual([payload["exercise_id"] for payload in posted], ["divide"])
        self.assertEqual(posted[0]["mode"], "live")
        self.assertIn('"status": "skipped"', out)

    def test_a_rejected_run_is_reported_and_the_rest_still_run(self):
        posted = []

        def fake_call(base, path, payload=None, timeout=300):
            if path.startswith("/api/lessons/"):
                return json.dumps(DETAIL)
            if path == "/api/runs":
                posted.append(payload)
                if payload["exercise_id"] == "divide":
                    raise urllib.error.HTTPError(path, 400, "bad", {}, io.BytesIO(b'{"code": "x"}'))
                return json.dumps({"run_id": "r2"})
            return DONE

        code, out = self.run_main(fake_call, ["fail-safely", "--offline"])
        self.assertEqual(code, 1)
        self.assertEqual([payload["exercise_id"] for payload in posted], ["divide", "unknown"])
        self.assertIn('"status": "rejected"', out)

    def test_locale_picks_presets_and_is_sent_with_the_run(self):
        # --locale 让课程详情按该语言返回问题与预设，创建运行时带上 locale；摘要写出实际运行语言。
        paths, posted = [], []

        def fake_call(base, path, payload=None, timeout=300):
            paths.append(path)
            if path.startswith("/api/lessons/"):
                return json.dumps({"id": "chat-request", "exercises": [{"id": "basic", "question": "Explain."}]})
            if path == "/api/runs":
                posted.append(payload)
                return json.dumps({"run_id": "r3"})
            return 'data: {"type": "run_start", "data": {"locale": "en"}}\n\n' + DONE

        code, out = self.run_main(fake_call, ["chat-request", "--offline", "--locale", "en"])
        self.assertEqual(code, 0)
        self.assertEqual(paths[0], "/api/lessons/chat-request?lang=en")
        self.assertEqual((posted[0]["locale"], posted[0]["question"]), ("en", "Explain."))
        self.assertIn('"locale": "en"', out)

    def test_approvals_are_answered_in_the_terminal_and_summarized(self):
        # --ask-approvals：终端输入经接口提交，和网页一样只针对这条审批与这份参数摘要。
        posted = []
        event = {"type": "approval_requested", "data": {
            "approval_id": "approval-1", "kind": "file.write", "summary": "write a.txt",
            "payload": {"path": "a.txt"}, "payload_digest": "sha256:" + "a" * 64}}
        answers = iter(["y", "path checked"])
        with patch.object(run_live, "call", side_effect=lambda base, path, payload=None: posted.append(
                (path, payload))), redirect_stdout(io.StringIO()):
            run_live.ask_approval("http://x", "r1", event, read=lambda prompt: next(answers))
        self.assertEqual(posted, [("/api/runs/r1/approvals", {
            "approval_id": "approval-1", "decision": "approve", "payload_digest": "sha256:" + "a" * 64,
            "note": "path checked"})])
        summary = run_live.summarize([
            {"type": "response", "data": {"body": {}, "stream": {"status": "cancelled", "chunk_count": 3,
                                                                 "first_chunk_ms": 210, "cancel_reason": "user_stop"}}},
            {"type": "approval_resolved", "data": {"approval_id": "approval-1", "outcome": "approved",
                                                   "decided_by": "learner"}},
            {"type": "checkpoint", "data": {"checkpoint_id": "cp-1", "name": "before-save"}},
        ])
        self.assertEqual(summary["streams"], [{"status": "cancelled", "chunks": 3, "first_chunk_ms": 210,
                                               "cancel_reason": "user_stop"}])
        self.assertEqual(summary["approvals"], [("approval-1", "approved", "learner")])
        self.assertEqual(summary["checkpoints"], [("cp-1", "before-save")])


if __name__ == "__main__":
    unittest.main()
