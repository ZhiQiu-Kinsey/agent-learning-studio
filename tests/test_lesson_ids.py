"""课程 slug 主 ID、数字别名、显示课号与目录引用校验。"""
import copy
import json
import re
import unittest

from fastapi.testclient import TestClient

import server.app as web
from server.catalog import LESSONS, LessonValidationError, lesson_spec
from server.curriculum import index_catalog, load_curriculum
from tests.run_support import run_and_read, use_temporary_run_store


def catalog(*lessons, **extra):
    """最小目录：只含身份字段，便于单独检查 slug、别名与引用规则。"""
    return {"lessons": [dict(lesson) for lesson in lessons], **extra}


def lesson(slug, *aliases, prerequisites=(), **fields):
    return {"id": slug, "aliases": list(aliases), "status": "planned",
            "prerequisites": list(prerequisites), **fields}


class CatalogIndexTests(unittest.TestCase):
    def test_numbers_follow_catalog_order_and_survive_insertions(self):
        base = catalog(lesson("alpha", "1"), lesson("beta", "2"), lesson("gamma", "3"))
        index = index_catalog(base)
        self.assertEqual(index.numbers, {"alpha": 1, "beta": 2, "gamma": 3})
        inserted = copy.deepcopy(base)
        inserted["lessons"].insert(1, lesson("new-topic"))
        moved = index_catalog(inserted)
        # 插入新课只改变显示课号，slug 与别名解析保持不变。
        self.assertEqual(moved.numbers, {"alpha": 1, "new-topic": 2, "beta": 3, "gamma": 4})
        self.assertEqual(moved.resolve("2"), "beta")
        self.assertEqual(moved.resolve("beta"), "beta")
        self.assertIsNone(moved.resolve("4"))
        self.assertIsNone(moved.resolve(4))

    def test_slug_format_is_enforced(self):
        for bad in ("1", "Tool-selection", "tool_selection", "-tool", "tool-", "tool--selection",
                    "工具", "", " tool", "a" * 49):
            with self.subTest(slug=bad), self.assertRaisesRegex(LessonValidationError, "slug|非空"):
                index_catalog(catalog(lesson(bad)))
        index_catalog(catalog(lesson("a" * 48), lesson("rag2-basics")))

    def test_alias_conflicts_are_rejected(self):
        cases = {
            "重复 slug": catalog(lesson("alpha"), lesson("alpha")),
            "别名与其他 slug 相同": catalog(lesson("alpha", "beta"), lesson("beta")),
            "slug 与先出现的别名相同": catalog(lesson("alpha", "beta-old"), lesson("beta-old")),
            "两个课程共用别名": catalog(lesson("alpha", "1"), lesson("beta", "1")),
            "同课重复别名": catalog(lesson("alpha", "1", "1")),
            "别名等于本课 slug": catalog(lesson("alpha", "alpha")),
            "别名格式非法": catalog(lesson("alpha", "01")),
            "别名不是字符串": catalog(lesson("alpha", 1)),
        }
        for name, value in cases.items():
            with self.subTest(name), self.assertRaises(LessonValidationError):
                index_catalog(value)

    def test_prerequisites_must_reference_earlier_existing_slugs(self):
        with self.assertRaisesRegex(LessonValidationError, "不存在"):
            index_catalog(catalog(lesson("alpha", prerequisites=["missing"])))
        with self.assertRaisesRegex(LessonValidationError, "slug「alpha」"):
            index_catalog(catalog(lesson("alpha", "1"), lesson("beta", prerequisites=["1"])))
        with self.assertRaisesRegex(LessonValidationError, "之前"):
            index_catalog(catalog(lesson("alpha", prerequisites=["beta"]), lesson("beta")))
        with self.assertRaisesRegex(LessonValidationError, "之前"):
            index_catalog(catalog(lesson("alpha", prerequisites=["alpha"])))
        with self.assertRaisesRegex(LessonValidationError, "重复"):
            index_catalog(catalog(lesson("alpha"), lesson("beta", prerequisites=["alpha", "alpha"])))
        with self.assertRaisesRegex(LessonValidationError, "electives"):
            index_catalog(catalog(lesson("alpha"), electives=[{"id": "X1", "prerequisites": ["gone"]}]))

    def test_module_order_must_match_lesson_order(self):
        def categories(*ids):
            return [{"id": "A", "modules": [{"id": "A1", "lesson_ids": list(ids)}]}]

        lessons = [lesson("alpha", category_id="A", module_id="A1"), lesson("beta", category_id="A", module_id="A1")]
        index_catalog(catalog(*lessons, categories=categories("alpha", "beta")))
        for ids, message in ((["beta", "alpha"], "顺序"), (["alpha"], "只能登记"),
                             (["alpha", "beta", "beta"], "只能登记"), (["alpha", "2"], "不存在")):
            with self.subTest(ids=ids), self.assertRaisesRegex(LessonValidationError, message):
                index_catalog(catalog(*lessons, categories=categories(*ids)))


class RealCatalogTests(unittest.TestCase):
    def test_every_lesson_has_slug_and_legacy_numeric_alias(self):
        data = load_curriculum()
        index = index_catalog(data)
        aliases = [alias for item in data["lessons"] for alias in item["aliases"]]
        self.assertEqual(len(aliases), len(set(aliases)))
        for item in data["lessons"]:
            with self.subTest(lesson=item["id"]):
                self.assertRegex(item["id"], r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
                self.assertTrue(any(alias.isdigit() for alias in item["aliases"]), "保留旧数字 ID 作为别名")
        # 已实现的第 1–10 课显示课号不变，与旧数字 ID 一致。
        for spec in LESSONS:
            self.assertEqual(str(spec["number"]), spec["aliases"][0])
        self.assertEqual(index.numbers["tool-selection"], 1)
        self.assertEqual(index.resolve("10"), "persistent-memory")

    def test_manifest_directories_follow_slug_naming_convention(self):
        # 映射约定：lesson.json 的 id 决定课程身份；旧目录为 lesson_NN_<slug 下划线形式>，新目录为 lesson_<slug 下划线形式>。
        for spec in LESSONS:
            with self.subTest(lesson=spec["id"]):
                suffix = re.sub(r"^lesson_(?:\d+_)?", "", spec["module"])
                self.assertEqual(suffix.replace("_", "-"), spec["id"])


class LessonIdApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web.app, base_url="http://localhost")
        self.store = use_temporary_run_store(self)

    def test_lists_and_curriculum_publish_slug_number_and_aliases(self):
        lessons = self.client.get("/api/lessons").json()["lessons"]
        self.assertEqual([item["id"] for item in lessons], [spec["id"] for spec in LESSONS])
        first = lessons[0]
        self.assertEqual((first["id"], first["number"], first["aliases"]), ("tool-selection", 1, ["1"]))
        curriculum = self.client.get("/api/curriculum").json()
        self.assertEqual([item["number"] for item in curriculum["lessons"]],
                         list(range(1, len(curriculum["lessons"]) + 1)))
        modules = [lesson_id for category in curriculum["categories"]
                   for module in category["modules"] for lesson_id in module["lesson_ids"]]
        self.assertEqual(modules, [item["id"] for item in curriculum["lessons"]])

    def test_detail_by_slug_or_alias_returns_the_same_lesson(self):
        by_slug = self.client.get("/api/lessons/tool-selection")
        by_alias = self.client.get("/api/lessons/1")
        self.assertEqual(by_slug.status_code, 200)
        self.assertEqual(by_slug.json(), by_alias.json())
        self.assertEqual(by_alias.json()["id"], "tool-selection")
        self.assertEqual(by_alias.json()["number"], 1)
        self.assertIs(lesson_spec("1"), lesson_spec("tool-selection"))

    def run_events(self, lesson_id):
        spec = lesson_spec(lesson_id)
        exercise = spec["exercises"][0]
        result = run_and_read(self.client, {"lesson_id": lesson_id, "mode": "offline",
                                            "question": exercise["question"], "exercise_id": exercise["id"]})
        self.assertTrue(result.events, result)
        return result.events

    def test_run_by_slug_or_alias_records_the_canonical_slug(self):
        for requested in ("tool-selection", "1"):
            with self.subTest(requested=requested):
                events = self.run_events(requested)
                self.assertEqual(events[0]["type"], "run_start")
                self.assertEqual(events[0]["data"]["lesson_id"], "tool-selection")
                self.assertEqual(events[-1]["data"]["status"], "completed")

    def test_unknown_and_planned_ids_return_404_with_codes(self):
        cases = {"no-such-lesson": "lesson_not_found", "999": "lesson_not_found", "01": "lesson_not_found",
                 "document-loading": "lesson_not_available", "11": "lesson_not_available"}
        for requested, code in cases.items():
            with self.subTest(requested=requested):
                detail = self.client.get("/api/lessons/" + requested)
                self.assertEqual(detail.status_code, 404)
                self.assertEqual(detail.json()["code"], code)
                self.assertIsInstance(detail.json()["detail"], str)
                run = self.client.post("/api/runs", json={"lesson_id": requested, "mode": "offline",
                                                         "question": "test", "exercise_id": "test"})
                self.assertEqual((run.status_code, run.json()["code"]), (404, code))
                self.assertNotIn("data:", run.text)
        planned = self.client.get("/api/lessons/11").json()["detail"]
        self.assertIn("第 11 课", planned)
        self.assertNotIn("no-such-lesson", self.client.get("/api/lessons/no-such-lesson").text)


if __name__ == "__main__":
    unittest.main()
