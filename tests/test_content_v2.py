"""content v2：schema 约束、迁移阶梯与无损迁移。"""
import copy
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from server.content_migrations import (LESSON_STEPS, ONBOARDING_STEPS, ContentVersionError,
                                       lesson_v1_to_v2, migrate, onboarding_v1_to_v2)
from server.content_schema import LessonContent, Onboarding, json_schemas

ROOT = Path(__file__).resolve().parents[1]
V1_LESSON = {
    "sections": [{"title": "标题", "body": "正文"}],
    "observe": ["看第一轮请求"],
    "quiz": [{"id": "q1", "prompt": "问题", "options": [{"id": "a", "text": "甲"}, {"id": "b", "text": "乙"}],
              "correct_option": "b", "explanation": "解析"}],
    "presentation": {
        "eyebrow": "E", "headline": "H", "highlight": "HL", "takeaway": "T",
        "concepts": [{"label": "01 / INTERFACE", "title": "概念", "description": "描述", "token": "tools"}],
        "flow": {"title": "流程", "description": "说明", "steps": [
            {"label": "1", "actor": "用户 → 模型", "title": "步骤", "body": "内容", "code": "{}",
             "language": "json", "evidence": "证据"}]},
    },
}
CONTEXT = {"lesson": "tool-selection", "subtitle": "让模型决定何时调用 Python",
           "exercises": [{"id": "sum", "title": "计算加法", "question": "19+23"}]}


def strings(value, skip_keys=()):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings(item, skip_keys)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in skip_keys:
                yield from strings(item, skip_keys)


class SchemaTests(unittest.TestCase):
    def valid(self):
        return migrate(copy.deepcopy(V1_LESSON), LESSON_STEPS, CONTEXT)

    def test_migrated_minimal_lesson_is_valid(self):
        content = LessonContent.model_validate(self.valid())
        self.assertEqual(content.lesson, "tool-selection")
        self.assertEqual([type(block).__name__ for block in content.scenes.understand.blocks],
                         ["Hero", "Concepts", "Prose", "Walkthrough"])
        self.assertEqual(content.scenes.understand.blocks[3].provenance, "illustration")

    def test_rejects_duplicate_ids_unknown_fields_and_bad_references(self):
        cases = {
            "duplicate block id": lambda d: d["scenes"]["understand"]["blocks"][2].update(id="hero"),
            "unknown field": lambda d: d["scenes"]["understand"]["blocks"][0].update(color="red"),
            "wrong answer": lambda d: d["scenes"]["check"]["blocks"][0]["questions"][0].update(correct="z"),
            "flow without illustration": lambda d: d["scenes"]["understand"]["blocks"].append(
                {"type": "flow", "id": "flow", "illustration": "missing"}),
            "predict without experiment": lambda d: d["scenes"]["understand"]["blocks"].append(
                {"type": "predict", "id": "guess", "prompt": "几次？", "experiment": "nope",
                 "rule": {"kind": "count_events", "event": "tool_call"}}),
            "guide to missing observe": lambda d: d["scenes"]["lab"]["experiments"][0].update(
                guide=[{"action": "seek", "observe": "observe-99"}]),
            "empty selector": lambda d: d["scenes"]["lab"]["experiments"][0]["observe"][0].update(selector={}),
            "ragged table": lambda d: d["scenes"]["understand"]["blocks"].append(
                {"type": "compare", "id": "table", "columns": ["a", "b"], "rows": [["1"]]}),
            "bad id": lambda d: d["scenes"]["understand"]["blocks"][0].update(id="Hero Block"),
        }
        for name, mutate in cases.items():
            with self.subTest(name):
                data = self.valid()
                mutate(data)
                with self.assertRaises(ValidationError):
                    LessonContent.model_validate(data)

    def test_onboarding_chapters_only_use_understand_and_check(self):
        data = migrate(json.loads((ROOT / "curriculum" / "onboarding.json").read_text(encoding="utf-8")),
                       ONBOARDING_STEPS)
        data["chapters"][0]["scenes"]["lab"] = self.valid()["scenes"]["lab"]
        with self.assertRaises(ValidationError):
            Onboarding.model_validate(data)


class MigrationLadderTests(unittest.TestCase):
    def test_missing_step_and_newer_content_fail_loudly(self):
        with self.assertRaisesRegex(ContentVersionError, "没有从版本 1"):
            migrate(copy.deepcopy(V1_LESSON), {}, CONTEXT)
        with self.assertRaisesRegex(ContentVersionError, "比平台支持的 2 新"):
            migrate({"schema_version": 3}, LESSON_STEPS, CONTEXT)

    def test_current_content_is_returned_unchanged(self):
        data = migrate(copy.deepcopy(V1_LESSON), LESSON_STEPS, CONTEXT)
        self.assertIs(migrate(data, LESSON_STEPS, CONTEXT), data)

    def test_migration_keeps_every_text_of_every_shipped_v1_file(self):
        # 只对仍是 v1 的文件验证；迁移落盘后由 test_catalog 层面校验 v2 文件。
        for path in sorted((ROOT / "lessons").glob("*/content.json")):
            source = json.loads(path.read_text(encoding="utf-8"))
            if "schema_version" in source:
                continue
            with self.subTest(path.parent.name):
                lesson = json.loads((path.parent / "lesson.json").read_text(encoding="utf-8"))
                context = {"lesson": lesson["id"], "subtitle": lesson["subtitle"],
                           "exercises": lesson["exercises"]}
                migrated = lesson_v1_to_v2(source, context)
                LessonContent.model_validate(migrated)
                self.assertLessEqual(set(strings(source)), set(strings(migrated)) | {"correct_option"})
        onboarding = json.loads((ROOT / "curriculum" / "onboarding.json").read_text(encoding="utf-8"))
        if onboarding.get("version") == 1:
            migrated = onboarding_v1_to_v2(onboarding, {})
            Onboarding.model_validate(migrated)
            kinds = {"explanation", "steps", "comparison", "warning"}
            self.assertLessEqual(set(strings(onboarding)) - kinds, set(strings(migrated)))


class LockstepTests(unittest.TestCase):
    def test_committed_json_schemas_match_the_models(self):
        for name, schema in json_schemas().items():
            with self.subTest(name):
                committed = json.loads((ROOT / "curriculum" / "schema" / name).read_text(encoding="utf-8"))
                self.assertEqual(committed, schema, "运行 scripts/export_content_schema.py 后再提交")

    def test_content_files_are_current_and_canonical(self):
        import subprocess
        import sys
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "migrate_content.py"), "--check"],
                                capture_output=True, text=True, encoding="utf-8",
                                env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
