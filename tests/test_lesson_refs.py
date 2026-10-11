"""正文里的课程引用 {{lesson:<slug>}}：校验、显示与“不写死课号”。"""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import server.app as web
from server.catalog import CATALOG_INDEX, LESSONS
from server.curriculum import LessonValidationError
from server.lesson_refs import check_refs, lesson_refs, resolve_refs

ROOT = Path(__file__).resolve().parents[1]
# 也拦“第 5、6 课”“第 1–10 课”这类并列和区间写法，以及英文眉题里的 “CHAPTER 03”。
HARDCODED = re.compile(r"第 ?\d+(?:\s*[、，,–—~-]\s*\d+)* ?课|CHAPTER\s*\d+")
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
        self.assertEqual(resolve_refs("{{lesson:beta}}", numbers, "en"), "Lesson 7")
        self.assertEqual(resolve_refs("{{lesson:beta}}", numbers, "fr"), "第 7 课")
        with self.assertRaisesRegex(LessonValidationError, "未登记"):
            check_refs({"x": "{{lesson:gamma}}"}, numbers, "where")
        with self.assertRaisesRegex(LessonValidationError, "未登记"):
            resolve_refs("{{lesson:gamma}}", numbers)

    def test_translated_text_says_lesson_n_and_fallback_text_keeps_the_source_form(self):
        from server.content import lesson_content_model, load_lesson_content
        from server.content_overlay import digest, text_slots

        spec = next(spec for spec in LESSONS
                    if len(lesson_refs(json.loads(spec["content_path"].read_text(encoding="utf-8")))) >= 2)
        numbers = CATALOG_INDEX.numbers
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "content.json"
            path.write_bytes(spec["content_path"].read_bytes())
            model = lesson_content_model(path, spec)
            texts = [(key, slot.value) for key, slot in text_slots(model, model.model_dump(mode="json")).items()
                     if "{{lesson:" in slot.value]
            (first, source), (_, untouched) = texts[0], texts[-1]
            refs = " ".join("{{lesson:%s}}" % slug for slug in lesson_refs(source))
            overlay = {"schema_version": 1, "locale": "en",
                       "texts": {first: {"text": "See " + refs, "source": digest(source)}}}
            path.with_name("content.en.json").write_text(json.dumps(overlay), encoding="utf-8")
            merged, info = load_lesson_content(path, spec, "en", lambda text: resolve_refs(text, numbers, "en"))
        rendered = json.dumps(resolve_refs(merged, numbers), ensure_ascii=False)
        self.assertEqual(info["translated"], 1)
        self.assertIn("See Lesson ", rendered)
        self.assertIn(json.dumps(resolve_refs(untouched, numbers), ensure_ascii=False)[1:-1], rendered)

    def test_malformed_refs_are_rejected_instead_of_shown(self):
        numbers = {"alpha": 1}
        for text in ("{{ lesson:alpha }}", "{{lesson:alpha}", "{lesson:alpha}}", "见{{lesson:alpha}}和{{lesson : alpha}}",
                     "{{lesson：alpha}}", "{{Lesson:alpha}}", "{{lesson:alpha}}}", "{{{lesson:alpha}}"):
            with self.subTest(text=text), self.assertRaisesRegex(LessonValidationError, "格式不对"):
                check_refs({"x": [text]}, numbers, "where")
        # 正文里的 JSON 示例有嵌套的 “}}”，不是引用。
        check_refs({"x": '见{{lesson:alpha}}，结果是 {"ok": true, "result": {"hour": 11}}'}, numbers, "where")

    def test_onboarding_and_manifests_are_checked_at_load(self):
        import tempfile
        from server.catalog import load_lessons
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "curriculum").mkdir()
            (root / "lessons").mkdir()
            catalog = json.loads((ROOT / "curriculum" / "catalog.json").read_text(encoding="utf-8"))
            for lesson in catalog["lessons"]:
                lesson["status"] = "planned"
            (root / "curriculum" / "onboarding.json").write_text(
                json.dumps({"x": "进入{{lesson:chat-requst}}"}, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(LessonValidationError, "onboarding.json.*未登记"):
                load_lessons(root, catalog)
            # 实现清单（lesson.json）里的引用同样在加载时检查。
            (root / "curriculum" / "onboarding.json").write_text("{}", encoding="utf-8")
            lesson_dir = root / "lessons" / "lesson_x"
            lesson_dir.mkdir()
            slug = catalog["lessons"][0]["id"]
            (lesson_dir / "lesson.json").write_text(
                json.dumps({"id": slug, "exercises": [{"title": "见{{lesson:nope}}"}]}, ensure_ascii=False),
                encoding="utf-8")
            (lesson_dir / "content.json").write_text("{}", encoding="utf-8")
            fake = {"content_path": lesson_dir / "content.json", "code_compare": None, "status": "planned"}
            with patch("server.catalog._manifest", return_value=fake),                     self.assertRaisesRegex(LessonValidationError, "lesson.json.*未登记"):
                load_lessons(root, catalog)

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

    def test_translation_overlays_are_checked_for_refs(self):
        import sys
        import tempfile
        sys.path.insert(0, str(ROOT / "scripts"))
        import validate_lessons
        spec = next(item for item in LESSONS if item["id"] == "chat-request")
        with tempfile.TemporaryDirectory() as temp:
            overlay = Path(temp) / "content.en-US.json"
            overlay.write_text(json.dumps({"x": "see {{lesson:nope}}"}), encoding="utf-8")
            with patch("server.content.overlay_locales", return_value=["en-US"]),                     patch("server.content.overlay_path", return_value=overlay),                     self.assertRaisesRegex(LessonValidationError, "未登记"):
                validate_lessons.validate_overlays(ROOT, [spec])

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
        # tool-selection 的读码批注引用了 fail-safely：要换成课号，而不是只看占位符不见了。
        code = json.dumps(client.get("/api/lessons/tool-selection/code").json(), ensure_ascii=False)
        self.assertNotIn("{{lesson:", code)
        self.assertIn(f"第 {CATALOG_INDEX.numbers['fail-safely']} 课", code)


if __name__ == "__main__":
    unittest.main()
