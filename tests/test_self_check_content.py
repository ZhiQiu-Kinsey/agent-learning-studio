"""自检内容：每课的选项都有解释，轨迹找错的目标能在确定性运行中命中。

确定性运行走真实的 runs 接口（mode=offline 测试适配器 + 真实 Python 工具），
判定用与前端 selector.ts 语义一致的 server.selectors。
"""
import unittest

from fastapi.testclient import TestClient

from server.catalog import LESSONS, lesson_detail
from server.selectors import select_events
from tests.run_support import run_and_read, use_temporary_run_store, web


def check_blocks(spec):
    return lesson_detail(spec)["learning"]["scenes"]["check"]["blocks"]


class CheckContentTests(unittest.TestCase):
    def test_every_lesson_has_quiz_trace_hunt_and_checkpoint(self):
        for spec in LESSONS:
            with self.subTest(spec["id"]):
                kinds = [block["type"] for block in check_blocks(spec)]
                for kind in ("quiz", "trace-hunt", "checkpoint"):
                    self.assertIn(kind, kinds)

    def test_every_option_explains_why_it_is_right_or_wrong(self):
        for spec in LESSONS:
            for block in check_blocks(spec):
                if block["type"] != "quiz":
                    continue
                for question in block["questions"]:
                    for option in question["options"]:
                        with self.subTest(spec["id"], question=question["id"], option=option["id"]):
                            self.assertTrue((option.get("feedback") or "").strip(), "选项缺少 feedback")
                    texts = [option["text"] for option in question["options"]]
                    self.assertEqual(len(texts), len(set(texts)), f"{question['id']} 的选项文字重复")


class TraceHuntTargetTests(unittest.TestCase):
    """每个 trace-hunt 目标都至少能在一个学习者可运行的练习里命中，且不会命中整次运行。"""

    def setUp(self):
        use_temporary_run_store(self)
        self.client = TestClient(web.app, base_url="http://localhost")

    def run_exercise(self, spec, detail, exercise):
        inputs = {**(detail.get("input_defaults") or {}), **(exercise.get("inputs") or {})}
        result = run_and_read(self.client, {
            "lesson_id": spec["id"], "mode": "offline", "question": exercise["question"],
            "exercise_id": exercise["id"], "inputs": inputs,
        })
        self.assertEqual(result.status_code, 202, result.text)
        self.assertEqual(result.events[-1]["type"], "done", result.text[-500:])
        self.assertEqual(result.events[-1]["data"]["status"], "completed")
        return result.events

    def test_targets_hit_in_deterministic_runs(self):
        for spec in LESSONS:
            detail = self.client.get(f"/api/lessons/{spec['id']}").json()
            hunts = [block for block in detail["learning"]["scenes"]["check"]["blocks"]
                     if block["type"] == "trace-hunt"]
            # 学生界面只能运行非离线注入的练习，命中必须发生在这些练习里。
            exercises = [item for item in detail["exercises"] if not item.get("offline_only")]
            runs = {exercise["id"]: self.run_exercise(spec, detail, exercise) for exercise in exercises}
            for hunt in hunts:
                with self.subTest(spec["id"], hunt=hunt["id"]):
                    hits = {exercise_id: select_events(hunt["target"], events)
                            for exercise_id, events in runs.items()}
                    self.assertTrue(any(hits.values()), f"{hunt['target']} 在任何练习中都没有命中")
                    for exercise_id, indices in hits.items():
                        self.assertLess(len(indices), len(runs[exercise_id]),
                                        f"{exercise_id}：目标命中了每一步，起不到找证据的作用")
                    # 运行中真实存在的事件才能被选中；命中的都是 real_run。
                    for exercise_id, indices in hits.items():
                        for index in indices:
                            self.assertEqual(runs[exercise_id][index]["provenance"], "real_run")


if __name__ == "__main__":
    unittest.main()
