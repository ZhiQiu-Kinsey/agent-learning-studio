"""课程目录与可执行课程保持一致，未来计划不获得执行权限。"""
import unittest

from fastapi.testclient import TestClient

from server.app import app
from server.catalog import LESSONS
from server.curriculum import load_curriculum
from scripts.export_curriculum import ROOT, document


class CurriculumTests(unittest.TestCase):
    def test_hierarchy_and_prerequisites_are_consistent(self):
        catalog = load_curriculum()
        lessons = {lesson["id"]: lesson for lesson in catalog["lessons"]}
        self.assertTrue(lessons)
        self.assertEqual(len(catalog["lessons"]), len(lessons))
        self.assertTrue(catalog["categories"])
        self.assertEqual(len({category["id"] for category in catalog["categories"]}), len(catalog["categories"]))
        positions = {identifier: index for index, identifier in enumerate(lessons)}
        occurrences = []
        module_ids = []
        for category in catalog["categories"]:
            self.assertTrue(category["modules"])
            for module in category["modules"]:
                module_ids.append(module["id"])
                for lesson_id in module["lesson_ids"]:
                    lesson = lessons[lesson_id]
                    self.assertEqual(lesson["category_id"], category["id"])
                    self.assertEqual(lesson["module_id"], module["id"])
                    occurrences.append(lesson_id)
        self.assertEqual(len(module_ids), len(set(module_ids)))
        self.assertCountEqual(occurrences, lessons.keys())
        source_ids = {source["id"] for source in catalog["sources"]}
        self.assertEqual(source_ids, {"microsoft", "huggingface", "book"})
        self.assertEqual(len(source_ids), len(catalog["sources"]))
        self.assertTrue(source_ids)
        for lesson in lessons.values():
            with self.subTest(lesson=lesson["id"]):
                self.assertGreaterEqual(len(lesson["objectives"]), 3)
                self.assertGreaterEqual(len(lesson["topics"]), 4)
                self.assertGreaterEqual(len(lesson["acceptance"]), 3)
                self.assertTrue(lesson["experiments"])
                self.assertTrue(lesson["references"])
                for reference in lesson["references"]:
                    self.assertIn(reference["source"], source_ids)
                for prerequisite in lesson["prerequisites"]:
                    self.assertIn(prerequisite, lessons)
                    self.assertLess(positions[prerequisite], positions[lesson["id"]], "先修必须位于前面，避免形成循环")

    def test_plans_do_not_become_executable_lessons(self):
        client = TestClient(app, base_url="http://localhost")
        catalog = client.get("/api/curriculum").json()
        available = [lesson for lesson in catalog["lessons"] if lesson["status"] == "available"]
        self.assertEqual({lesson["id"]: lesson["title"] for lesson in available},
                         {lesson["id"]: lesson["title"] for lesson in LESSONS})
        self.assertFalse(any("local_path" in source for source in catalog["sources"]))
        for lesson in catalog["lessons"]:
            if lesson["status"] == "planned":
                self.assertEqual(client.get("/api/lessons/" + lesson["id"]).status_code, 404)
        unavailable = next((lesson["id"] for lesson in catalog["lessons"] if lesson["status"] == "planned"), "unknown-course")
        response = client.post("/api/runs", json={"lesson_id": unavailable, "mode": "offline", "question": "test", "exercise_id": "test"})
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("data:", response.text)

    def test_readable_curriculum_matches_the_single_source(self):
        self.assertEqual((ROOT / "docs/course-plan.md").read_text(encoding="utf-8"), document(),
                         "课程表已过期：catalog.json、content.json 的小节、lesson.json 或术语表改过后，"
                         "运行 scripts/export_curriculum.py")

    def test_every_lesson_has_time_difficulty_and_an_outline(self):
        from server.catalog import curriculum_outline

        for lesson in curriculum_outline()["lessons"]:
            with self.subTest(lesson=lesson["id"]):
                self.assertIsInstance(lesson["estimated_minutes"], int)
                self.assertIn(lesson["difficulty"], ("入门", "进阶", "挑战"))
                if lesson["status"] == "available":
                    self.assertGreaterEqual(len(lesson["sections"]), 2, "可运行课的小节来自正文节标题")
                    self.assertIsInstance(lesson["calls_model"], bool)


if __name__ == "__main__":
    unittest.main()
