"""正文里的课程引用 {{lesson:<slug>}}：校验、显示与“不写死课号”。"""
import json
import re
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import server.app as web
from server.catalog import CATALOG_INDEX, LESSONS
from server.curriculum import LessonValidationError
from server.lesson_refs import check_refs, lesson_refs, resolve_refs

ROOT = Path(__file__).resolve().parents[1]
HARDCODED = re.compile(r"第 ?\d+ ?课")
# 运行器、夹具、测试、README 与实现清单里的文档串和运行时字符串也不写死课号。
# 2026-10-03 起所有课都已改好，过渡清单保持为空，不再往里加。
SOURCE_LEGACY: set[str] = set()


class LessonRefTests(unittest.TestCase):
    def test_refs_resolve_to_display_numbers_and_unknown_slugs_are_rejected(self):
        numbers = {"alpha": 1, "beta": 7}
        value = {"a": ["见{{lesson:beta}}", {"b": "{{lesson:alpha}}与{{lesson:beta}}"}], "n": 3}
        self.assertEqual(lesson_refs(value), ["beta", "alpha", "beta"])
        self.assertEqual(resolve_refs(value, numbers),
                         {"a": ["见第 7 课", {"b": "第 1 课与第 7 课"}], "n": 3})
        self.assertEqual(resolve_refs("{{lesson:beta}}", numbers, "en-US"), "Lesson 7")
        with self.assertRaisesRegex(LessonValidationError, "未登记"):
            check_refs({"x": "{{lesson:gamma}}"}, numbers, "where")

    def test_course_text_never_hardcodes_lesson_numbers(self):
        # 显示课号随目录顺序变化；提到另一门课要写 {{lesson:<slug>}}。
        files = [spec["content_path"] for spec in LESSONS]
        files += [ROOT / "curriculum" / "catalog.json", ROOT / "curriculum" / "onboarding.json"]
        for path in files:
            with self.subTest(path=Path(path).name):
                self.assertEqual(HARDCODED.findall(Path(path).read_text(encoding="utf-8")), [])

    def test_lesson_sources_never_hardcode_lesson_numbers(self):
        # 源码和运行事件不做 {{lesson:<slug>}} 替换：提到别的课写课名或 slug。
        for directory in sorted((ROOT / "lessons").glob("lesson_*")):
            if directory.name in SOURCE_LEGACY:
                continue
            for path in sorted([*directory.glob("*.py"), *directory.glob("*.md"), *directory.glob("*.json")]):
                with self.subTest(path=f"{directory.name}/{path.name}"):
                    self.assertEqual(HARDCODED.findall(path.read_text(encoding="utf-8")), [])

    def test_api_serves_resolved_text(self):
        client = TestClient(web.app, base_url="http://localhost")
        detail = client.get("/api/lessons/structured-output").json()
        text = json.dumps(detail["learning"], ensure_ascii=False)
        self.assertNotIn("{{lesson:", text)
        self.assertIn(f"第 {CATALOG_INDEX.numbers['task-contract']} 课", text)
        curriculum = json.dumps(client.get("/api/curriculum").json(), ensure_ascii=False)
        self.assertNotIn("{{lesson:", curriculum)
        self.assertNotIn("{{lesson:", json.dumps(client.get("/api/lessons").json(), ensure_ascii=False))
        self.assertNotIn("{{lesson:", json.dumps(client.get("/api/onboarding").json(), ensure_ascii=False))
        code = json.dumps(client.get("/api/lessons/structured-output/code").json(), ensure_ascii=False)
        self.assertNotIn("{{lesson:", code)


if __name__ == "__main__":
    unittest.main()
