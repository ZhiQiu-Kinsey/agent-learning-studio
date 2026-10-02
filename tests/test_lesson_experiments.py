"""实验、导览、预测与理解自测的内容校验：用确定性测试适配器真实运行每个实验组。

每课每个实验的每个 arm 都以 mode=offline 跑一次（模型响应来自课程 fixture，工具执行真实 Python；
不需要模型的课程直接运行本地程序；offline_only 的故障注入练习本来就只在离线模式运行）。
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
from server.content_overlay import text_slots
from server.content_schema import Highlight, MicroQuiz, Narrate, Predict, Prose, Seek, Spotlight
from server.envelope import INSTANT_PREFIXES, SPAN_EVENTS
from server.run_store import RunStore
from server.selectors import count_events, select_events

STAGE_ROLES = {"user", "runtime", "model", "tool", "memory"}


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
                targeted = set()
                self.assertTrue(any(isinstance(action, Narrate) for action in experiment.guide))
                for action in experiment.guide:
                    if isinstance(action, (Highlight, Seek)):
                        self.assertIn(action.observe, observe_ids)
                        targeted.add(action.observe)
                    elif isinstance(action, Spotlight):
                        self.assertIn(action.target, STAGE_ROLES)
                        self.assertIn(action.target, roles, f"舞台上没有 {action.target} 节点")
                self.assertEqual(targeted, observe_ids, "导览应逐一讲到每个观察点")

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
                self.assertIs(blocks[-1], predicts[0], "predict 放在理解场景末尾")
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


class TerminologyTests(unittest.TestCase):
    """术语首次出现写成“中文（English）”，与 curriculum/glossary.json 一致。

    只检查到本课为止已引入的术语（first_lesson 的课号不大于本课）；hero 是展示标题，不计入；
    出现在更长术语内部的位置（如“持久记忆”中的“记忆”）不算该术语的出现。
    """

    def texts(self, model):
        parts = [block for block in model.scenes.understand.blocks if block.type != "hero"]
        parts.append(model.scenes.lab)
        values = []
        for part in parts:
            values += [slot.value for slot in text_slots(part, part.model_dump(mode="json")).values()]
        return "\n".join(values)

    def test_first_occurrence_is_bilingual(self):
        terms = json.loads((ROOT / "curriculum" / "glossary.json").read_text(encoding="utf-8"))["terms"]
        names = [term["zh"] for term in terms]
        numbers = CATALOG_INDEX.numbers
        for spec in LESSONS:
            text = self.texts(lesson_content_model(spec["content_path"], spec))
            for term in terms:
                first_lesson = term.get("first_lesson")
                if term["zh"] == term["en"] or first_lesson not in numbers or numbers[first_lesson] > numbers[spec["id"]]:
                    continue
                zh, pair = term["zh"], f"{term['zh']}（{term['en']}）"
                with self.subTest(lesson=spec["id"], term=term["id"]):
                    if first_lesson == spec["id"]:
                        self.assertIn(pair, text, "引入术语的课程要写出中英并列形式")
                    first = self.first_standalone(text, zh, [name for name in names if name != zh and zh in name])
                    if first is not None:
                        self.assertTrue(text.startswith(pair, first), f"首次出现应写作 {pair}：{text[first:first + 30]}")

    @staticmethod
    def first_standalone(text, zh, longer):
        start = 0
        while (index := text.find(zh, start)) >= 0:
            inside = any(index - name.find(zh) >= 0 and text.startswith(name, index - name.find(zh))
                         for name in longer)
            if not inside:
                return index
            start = index + 1
        return None


if __name__ == "__main__":
    unittest.main()
