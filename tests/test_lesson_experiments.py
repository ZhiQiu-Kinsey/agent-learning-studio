"""实验、导览、预测与理解自测的内容校验：用确定性测试适配器真实运行每个实验组。

每课每个实验的每个 arm 都以 mode=offline 跑一次（模型响应来自课程 fixture，工具执行真实 Python；
不需要模型的课程或练习直接运行本地程序；offline_only 的练习本来就只在离线模式运行）。
断言观察点选择器至少在一个 arm 的事件中命中、导览目标存在、舞台聚焦的节点在运行中出现、
predict 引用的实验存在且规则可从真实事件计算。
"""
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from run_support import run_and_read, web
from server.catalog import CATALOG_INDEX, LESSONS, ROOT
from server.content import lesson_content_model
from server.content_schema import MicroQuiz, Predict, Prose
from server.envelope import INSTANT_PREFIXES, SPAN_EVENTS
from server.run_store import RunStore
from server.selectors import count_events, select_events

STAGE_ROLES = {"user", "runtime", "model", "tool", "memory"}
# “先跑一次”：predict 放在第一道微测之前。2026-10-03 起所有课都已改好，这个过渡清单保持为空，不再往里加。
PREDICT_AT_END: set[str] = set()


def stage_roles(events):
    """与 frontend/src/stage/derive.ts 的拓扑规则一致：节点由事件决定。"""
    roles = {"user", "runtime"} if events else set()
    for event in events:
        if event["type"] == "request":
            roles.add("model")
        elif event["type"] == "tool_call":
            roles.add("tool")
        elif event["type"] in ("lesson.memory", "lesson.state"):
            roles.add("memory")
    return roles


class LessonExperimentTests(unittest.TestCase):
    runs: dict = {}

    @classmethod
    def setUpClass(cls):
        cls._directory = tempfile.TemporaryDirectory()
        cls._previous_store = web.run_store
        cls._store = RunStore(Path(cls._directory.name) / "runs.sqlite3")
        web.run_store = cls._store
        cls.client = TestClient(web.app, base_url="http://localhost")
        cls.models = {spec["id"]: (spec, lesson_content_model(spec["content_path"], spec)) for spec in LESSONS}

    @classmethod
    def tearDownClass(cls):
        web.run_store = cls._previous_store
        cls._store.close()
        cls._directory.cleanup()

    def run_arm(self, spec, arm):
        key = (spec["id"], arm.exercise, json.dumps(arm.inputs, sort_keys=True))
        if key not in self.runs:
            exercise = next(item for item in spec["exercises"] if item["id"] == arm.exercise)
            body = {"lesson_id": spec["id"], "mode": "offline", "question": exercise["question"],
                    "exercise_id": arm.exercise}
            if arm.inputs is not None:
                body["inputs"] = arm.inputs
            result = run_and_read(self.client, body)
            self.assertEqual(result.status_code, 202, f"{key} 无法离线运行：{result.text}")
            self.assertEqual(result.events[-1]["type"], "done", key)
            self.assertEqual(result.events[-1]["data"]["status"], "completed", key)
            self.runs[key] = result.events
        return self.runs[key]

    def experiments(self):
        for lesson_id, (spec, model) in self.models.items():
            for experiment in model.scenes.lab.experiments:
                yield spec, model, experiment

    def test_every_observe_selector_hits_in_some_arm(self):
        for spec, _, experiment in self.experiments():
            arm_events = [self.run_arm(spec, arm) for arm in experiment.arms]
            for point in experiment.observe:
                with self.subTest(lesson=spec["id"], experiment=experiment.id, observe=point.id):
                    self.assertIsNotNone(point.selector, "每个观察点都要有选择器")
                    hits = [select_events(point.selector, events) for events in arm_events]
                    self.assertTrue(any(hits), "选择器在所有 arm 的确定性运行中都没有命中")

    def test_guides_target_real_evidence_and_stage_nodes(self):
        for spec, _, experiment in self.experiments():
            with self.subTest(lesson=spec["id"], experiment=experiment.id):
                roles = set().union(*(stage_roles(self.run_arm(spec, arm)) for arm in experiment.arms))
                observe_ids = {point.id for point in experiment.observe}
                self.assertTrue(experiment.guide, "每个实验都要有导览")
                for step in experiment.guide:
                    if step.observe is not None:
                        self.assertIn(step.observe, observe_ids)
                    if step.stage is not None:
                        self.assertIn(step.stage, STAGE_ROLES)
                        self.assertIn(step.stage, roles, f"舞台上没有 {step.stage} 节点")
                targeted = {step.observe for step in experiment.guide if step.observe}
                self.assertEqual(targeted, observe_ids, "导览应逐一讲到每个观察点")
                texts = [step.text for step in experiment.guide]
                self.assertEqual(len(texts), len(set(texts)), "导览每一步说一句不同的话")

    def test_experiments_state_hypothesis_and_honest_conclusion(self):
        for spec, _, experiment in self.experiments():
            with self.subTest(lesson=spec["id"], experiment=experiment.id):
                self.assertTrue(experiment.hypothesis)
                self.assertIsNotNone(experiment.conclusion)
                self.assertTrue(experiment.conclusion.proves)
                self.assertTrue(experiment.conclusion.does_not_prove)
                self.assertTrue(all(arm.label for arm in experiment.arms))

    def test_experiments_cover_every_exercise(self):
        for lesson_id, (spec, model) in self.models.items():
            with self.subTest(lesson=lesson_id):
                used = {arm.exercise for experiment in model.scenes.lab.experiments for arm in experiment.arms}
                self.assertEqual(used, {exercise["id"] for exercise in spec["exercises"]})
                self.assertTrue(model.capabilities)

    def test_predict_closes_understand_and_counts_real_events(self):
        for lesson_id, (spec, model) in self.models.items():
            with self.subTest(lesson=lesson_id):
                blocks = model.scenes.understand.blocks
                predicts = [block for block in blocks if isinstance(block, Predict)]
                self.assertEqual(len(predicts), 1)
                if lesson_id in PREDICT_AT_END:
                    self.assertIs(blocks[-1], predicts[0], "已改到第一道微测之前，请从 PREDICT_AT_END 删除")
                else:
                    first_quiz = next(index for index, item in enumerate(blocks) if isinstance(item, MicroQuiz))
                    self.assertLess(blocks.index(predicts[0]), first_quiz, "predict 放在第一道微测之前（先跑一次）")
                block = predicts[0]
                experiment = next(item for item in model.scenes.lab.experiments if item.id == block.experiment)
                self.assertEqual(experiment.predict, block.id)
                labels = [experiment.title] + [arm.label for arm in experiment.arms]
                self.assertTrue(any(f"“{label}”" in block.prompt for label in labels),
                                "预测题要写明在哪个实验或哪一组上核对")
                rule = block.rule
                self.assertTrue(rule.event in SPAN_EVENTS or rule.event.startswith(INSTANT_PREFIXES))
                if rule.name:
                    self.assertIn(rule.event, ("tool_call", "tool_result"))
                for arm in experiment.arms:
                    self.assertIsInstance(count_events(rule, self.run_arm(spec, arm)), int)

    def test_micro_quizzes_every_two_or_three_sections(self):
        for lesson_id, (_, model) in self.models.items():
            with self.subTest(lesson=lesson_id):
                since, quizzes = 0, 0
                for block in model.scenes.understand.blocks:
                    if isinstance(block, Prose):
                        since += 1
                        self.assertLessEqual(since, 3, f"{block.id} 前已连续 3 节没有微型自测")
                    elif isinstance(block, MicroQuiz):
                        self.assertGreaterEqual(since, 1, f"{block.id} 前没有讲解")
                        quizzes += 1
                        since = 0
                        self.assertTrue(all(option.feedback for option in block.question.options))
                self.assertGreaterEqual(quizzes, 1)


# 术语与代码名的用词检查见 tests/test_lesson_vocabulary.py。


if __name__ == "__main__":
    unittest.main()
