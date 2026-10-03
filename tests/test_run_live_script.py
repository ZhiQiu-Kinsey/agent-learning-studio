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


if __name__ == "__main__":
    unittest.main()
