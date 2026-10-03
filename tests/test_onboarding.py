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
                         ["intro", "agent-origins", "how-llm-works", "llm-limits", "what-is-agent",
                          "workflow-or-agent", "learning-path-lab"])
        source_projects = set()
        for chapter in data["chapters"]:
            with self.subTest(chapter=chapter["id"]):
                self.assertIsNone(chapter["scenes"].get("code"))
                self.assertIsNone(chapter["scenes"].get("lab"))
                blocks = {block["type"]: block for block in chapter["scenes"]["understand"]["blocks"]}
                self.assertTrue(blocks["objectives"]["items"])
                exercise = chapter["scenes"]["check"]["blocks"][0]
                self.assertEqual(exercise["type"], "checkpoint")
                self.assertTrue(exercise["items"])
                sections = [block for block in chapter["scenes"]["understand"]["blocks"]
                            if block["type"] in {"prose", "compare", "steps", "callout"}]
                self.assertGreaterEqual(len(sections), 4)
                for section in sections:
                    self.assertTrue(section["paragraphs"])
                    for row in section.get("rows", []):
                        self.assertEqual(len(row), len(section["columns"]))
                # 讲解深度规范（docs/architecture/content-depth.md）：导学每章至少 1 道微测、1 个误区、1–2 个深入块。
                understand = chapter["scenes"]["understand"]["blocks"]
                quizzes = [block for block in understand if block["type"] == "micro-quiz"]
                self.assertTrue(quizzes)
                for quiz in quizzes:
                    self.assertTrue(all(option["feedback"] for option in quiz["question"]["options"]))
                self.assertTrue(any(block["type"] == "misconception" for block in understand))
                self.assertIn(sum(block["type"] == "deep-dive" for block in understand), (1, 2))
                for reference in blocks["references"]["items"]:
                    parsed = urlparse(reference["url"])
                    self.assertEqual(parsed.scheme, "https")
                    self.assertEqual(parsed.hostname, "github.com")
                    self.assertEqual(parsed.path.split("/")[3], "blob")  # 固定到 commit 的文件链接
                    source_projects.add(parsed.path.split("/")[2])
        self.assertEqual(source_projects,
                         {"ai-agents-for-beginners", "agents-course", "ai-agent-book", "claude-cookbooks",
                          "learn-claude-code", "hello-agents"})
        self.assertNotIn("local_path", response.text)
        self.assertNotIn(str(web.ROOT), response.text)

    def test_reading_chapters_do_not_gain_execution_permissions(self):
        chapters = self.client.get("/api/onboarding").json()["chapters"]
        with patch.object(web, "execute_lesson", side_effect=AssertionError("前置内容不可执行")):
            for chapter in chapters:
                with self.subTest(chapter=chapter["id"]):
                    self.assertEqual(self.client.get("/api/lessons/" + chapter["id"]).status_code, 404)
                    response = self.client.post("/api/runs", json={
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
