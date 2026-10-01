"""前置阅读无需模型，内容与可执行课程的权限边界保持分离。"""
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

from fastapi.testclient import TestClient

web = importlib.import_module("server.app")


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web.app, base_url="http://localhost")

    def test_reading_is_complete_and_needs_no_model_configuration(self):
        with patch.object(web.provider_registry, "resolve", side_effect=AssertionError("不应读取模型配置")), \
                patch.object(web, "execute_lesson", side_effect=AssertionError("不应执行模型")):
            response = self.client.get("/api/onboarding")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual([chapter["id"] for chapter in data["chapters"]],
                         ["intro", "what-is-agent", "learning-path", "lab-evidence"])
        source_projects = set()
        for chapter in data["chapters"]:
            with self.subTest(chapter=chapter["id"]):
                self.assertTrue(chapter["learning_objectives"])
                self.assertTrue(chapter["exercise"]["checkpoints"])
                self.assertGreaterEqual(len(chapter["sections"]), 3)
                for section in chapter["sections"]:
                    self.assertIn(section["kind"], {"explanation", "comparison", "steps", "warning"})
                    self.assertTrue(section["paragraphs"])
                    if "table" in section:
                        for row in section["table"]["rows"]:
                            self.assertEqual(len(row), len(section["table"]["columns"]))
                for reference in chapter["references"]:
                    parsed = urlparse(reference["url"])
                    self.assertEqual(parsed.scheme, "https")
                    self.assertEqual(parsed.hostname, "github.com")
                    source_projects.add(parsed.path.split("/")[2])
        self.assertEqual(source_projects,
                         {"ai-agents-for-beginners", "agents-course", "ai-agent-book"})
        self.assertNotIn("local_path", response.text)
        self.assertNotIn(str(web.ROOT), response.text)

    def test_reading_chapters_do_not_gain_execution_permissions(self):
        chapters = self.client.get("/api/onboarding").json()["chapters"]
        with patch.object(web, "execute_lesson", side_effect=AssertionError("前置内容不可执行")):
            for chapter in chapters:
                with self.subTest(chapter=chapter["id"]):
                    self.assertEqual(self.client.get("/api/lessons/" + chapter["id"]).status_code, 404)
                    response = self.client.post("/api/run", json={
                        "lesson_id": chapter["id"], "mode": "offline",
                        "question": "test", "exercise_id": "test",
                    })
                    self.assertEqual(response.status_code, 404)
                    self.assertNotIn("data:", response.text)

    def test_missing_or_invalid_content_returns_a_safe_recoverable_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture_root = Path(temporary)
            with patch.object(web, "ROOT", fixture_root):
                missing = self.client.get("/api/onboarding")
                self.assertEqual(missing.status_code, 503)
                (fixture_root / "curriculum").mkdir()
                (fixture_root / "curriculum" / "onboarding.json").write_text("{malformed", encoding="utf-8")
                malformed = self.client.get("/api/onboarding")
                self.assertEqual(malformed.status_code, 503)
                self.assertEqual(missing.json(), malformed.json())
                self.assertNotIn(temporary, malformed.text)
                self.assertNotIn("malformed", malformed.text)


if __name__ == "__main__":
    unittest.main()
