"""译文层：可译路径、事实字段保护、过期检测、覆盖率与接口回落。"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import server.app as web
from server.catalog import lesson_spec
from server.content import lesson_content_model, load_lesson_content, load_onboarding, overlay_report
from server.content_overlay import OverlayError, digest, text_slots

ROOT = Path(__file__).resolve().parents[1]


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.spec = lesson_spec("tool-selection")
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "content.json"
        shutil.copy(self.spec["content_path"], self.path)
        self.model = lesson_content_model(self.path, self.spec)
        self.data = self.model.model_dump(mode="json")
        self.slots = text_slots(self.model, self.data)

    def write_overlay(self, texts, locale="en-US"):
        payload = {"schema_version": 1, "locale": locale, "texts": texts}
        self.path.with_name(f"content.{locale}.json").write_text(json.dumps(payload, ensure_ascii=False),
                                                                 encoding="utf-8")

    def entry(self, path, text):
        return {"text": text, "source": digest(self.slots[path].value)}

    def test_paths_use_stable_ids_and_exclude_facts(self):
        question = self.data["scenes"]["check"]["blocks"][0]["questions"][0]
        option = question["options"][0]["id"]
        for path in ("hero.headline", "concepts.01-interface.title", "section-1.paragraphs.0", "walkthrough.step-1.body",
                     "which-tool.title", "which-tool.tools-declared.text", "which-tool.sum.label",
                     f"quiz.{question['id']}.prompt", f"quiz.{question['id']}.{option}.text"):
            self.assertIn(path, self.slots)
        for fact in ("hero.id", "hero.type", "hero.reveal", "concepts.01-interface.token", "walkthrough.step-1.code",
                     "walkthrough.step-1.language", "which-tool.sum.exercise", f"quiz.{question['id']}.correct",
                     "lesson", "source_language"):
            self.assertNotIn(fact, self.slots)

    def test_merge_translates_current_entries_and_reports_missing_and_stale(self):
        stale = self.entry("hero.highlight", "old")
        stale["source"] = "000000000000"
        self.write_overlay({"hero.headline": self.entry("hero.headline", "From one question,"),
                            "hero.highlight": stale})
        data, info = load_lesson_content(self.path, self.spec, "en-US")
        hero = data["scenes"]["understand"]["blocks"][0]
        self.assertEqual(hero["headline"], "From one question,")
        self.assertEqual(hero["highlight"], self.slots["hero.highlight"].value)  # 过期译文回落源文本
        self.assertEqual((info["locale"], info["translated"], info["stale"]), ("en-US", 1, ["hero.highlight"]))
        self.assertEqual(len(info["missing"]), len(self.slots) - 2)
        self.assertEqual(hero["id"], "hero")

    def test_facts_and_unknown_paths_cannot_be_overridden(self):
        for path in ("walkthrough.step-1.code", "hero.id", "quiz.nope.prompt", "which-tool.sum.exercise"):
            with self.subTest(path=path):
                self.write_overlay({path: {"text": "x", "source": "0"}})
                with self.assertRaisesRegex(OverlayError, "不是可翻译的文本路径"):
                    overlay_report(self.path, self.model, "en-US")
                data, info = load_lesson_content(self.path, self.spec, "en-US")
                self.assertEqual(info["locale"], "zh-CN")
                self.assertIn("error", info)

    def test_rejects_wrong_locale_empty_text_and_bad_shape(self):
        cases = [({"hero.headline": {"text": " ", "source": "x"}}, "en-US", "text 非空"),
                 ({"hero.headline": "plain string"}, "en-US", "text, source"),
                 ({}, "fr-FR", "locale 必须为 en-US")]
        for texts, locale, message in cases:
            with self.subTest(message=message):
                payload = {"schema_version": 1, "locale": locale, "texts": texts}
                self.path.with_name("content.en-US.json").write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(OverlayError, message):
                    overlay_report(self.path, self.model, "en-US")

    def test_source_language_needs_no_overlay(self):
        _, info = load_lesson_content(self.path, self.spec, "zh-CN")
        self.assertEqual((info["locale"], info["missing"], info["translated"]), ("zh-CN", [], info["total"]))

    def test_onboarding_paths_are_scoped_by_chapter(self):
        data = load_onboarding(ROOT / "curriculum" / "onboarding.json", "en-US")
        self.assertEqual(data["i18n"]["locale"], "zh-CN")
        missing = set(data["i18n"]["missing"])
        self.assertIn("intro.title", missing)
        self.assertIn("intro.objectives.objective-1.text", missing)
        self.assertTrue(any(path.startswith("what-is-agent.boundaries.rows.0.") for path in missing))
        self.assertFalse(any(path.endswith(".url") for path in missing))


class OverlayApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web.app, base_url="http://localhost")

    def test_lang_parameter_falls_back_and_rejects_malformed_codes(self):
        detail = self.client.get("/api/lessons/tool-selection?lang=en-US").json()
        self.assertEqual(detail["learning_i18n"]["locale"], "zh-CN")
        self.assertEqual(detail["learning_i18n"]["requested"], "en-US")
        self.assertGreater(len(detail["learning_i18n"]["missing"]), 20)
        self.assertEqual(self.client.get("/api/lessons/tool-selection").json()["learning_i18n"]["missing"], [])
        for bad in ("english", "en_US", "../x"):
            response = self.client.get("/api/lessons/tool-selection", params={"lang": bad})
            self.assertEqual((response.status_code, response.json()["code"]), (400, "invalid_locale"))
        self.assertEqual(self.client.get("/api/onboarding?lang=en-US").json()["i18n"]["locale"], "zh-CN")


if __name__ == "__main__":
    unittest.main()
