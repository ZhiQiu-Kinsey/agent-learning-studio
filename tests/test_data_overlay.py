"""课程目录、术语表与实现清单的译文层：路径、事实保护、过期回落、?lang= 接口与译文工具目标。"""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import server.app as web
from scripts import translation_kit
from server import catalog as catalog_module
from server.catalog import CATALOG_INDEX, ROOT, lesson_spec, localized_manifest
from server.content_overlay import OverlayError, digest, slot_coverage
from server.curriculum import public_curriculum
from server.data_overlay import catalog_slots, glossary_slots, manifest_slots
from server.glossary import public_glossary
from server.lesson_refs import resolve_refs


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def overlay(texts, locale="en"):
    return {"schema_version": 1, "locale": locale, "texts": texts}


def write(path, payload):
    Path(path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class CatalogOverlayTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "catalog.json"
        shutil.copy(ROOT / "curriculum" / "catalog.json", self.path)
        patcher = patch("server.curriculum.CATALOG_PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        catalog_module._catalog_cache.clear()
        self.addCleanup(catalog_module._catalog_cache.clear)
        self.source = read(self.path)
        self.slots = catalog_slots(copy.deepcopy(self.source))
        self.first = self.source["lessons"][0]
        self.planned = next(lesson for lesson in self.source["lessons"] if lesson["status"] == "planned")

    def entry(self, path, text):
        return {"text": text, "source": digest(self.slots[path].value)}

    def test_paths_are_keyed_by_ids_and_exclude_facts(self):
        category, module = self.source["categories"][0], self.source["categories"][0]["modules"][0]
        lesson, elective = self.first["id"], self.source["electives"][0]["id"]
        for path in ("title", "principles.0", f"category.{category['id']}.title", f"module.{module['id']}.description",
                     f"lesson.{lesson}.title", f"lesson.{lesson}.summary", f"lesson.{lesson}.objectives.0",
                     f"lesson.{lesson}.topics.0", f"lesson.{lesson}.acceptance.0",
                     f"lesson.{lesson}.experiments.0.title", f"lesson.{lesson}.experiments.0.steps.0",
                     f"lesson.{lesson}.experiments.0.deliverable", f"lesson.{self.planned['id']}.sections.0.gist",
                     f"elective.{elective}.title", f"elective.{elective}.topics.0",
                     f"source.{self.source['sources'][0]['id']}.role"):
            self.assertIn(path, self.slots)
        for fact in (f"lesson.{lesson}.id", f"lesson.{lesson}.status", f"lesson.{lesson}.prerequisites.0",
                     f"lesson.{lesson}.level", f"lesson.{lesson}.difficulty", f"lesson.{lesson}.estimated_minutes",
                     f"lesson.{lesson}.references.0.locator", f"source.{self.source['sources'][0]['id']}.url",
                     "version", f"category.{category['id']}.id"):
            self.assertNotIn(fact, self.slots)

    def test_merge_falls_back_per_entry_and_renders_refs_in_the_target_language(self):
        lesson = self.first["id"]
        stale = self.entry(f"lesson.{lesson}.summary", "Old summary")
        stale["source"] = "000000000000"
        title = f"lesson.{self.planned['id']}.title"
        texts = {f"lesson.{lesson}.title": self.entry(f"lesson.{lesson}.title", "One model request"),
                 f"lesson.{lesson}.summary": stale,
                 title: self.entry(title, "Loading, see {{lesson:%s}}" % lesson)}
        write(self.path.with_name("catalog.en.json"), overlay(texts))
        data = public_curriculum("en")
        by_id = {item["id"]: item for item in data["lessons"]}
        self.assertEqual(by_id[lesson]["title"], "One model request")
        self.assertEqual(by_id[lesson]["summary"], resolve_refs(self.first["summary"], CATALOG_INDEX.numbers))
        self.assertEqual(by_id[self.planned["id"]]["title"], "Loading, see Lesson 1")
        self.assertEqual(by_id[lesson]["status"], self.first["status"])
        self.assertEqual((data["i18n"]["locale"], data["i18n"]["translated"], data["i18n"]["stale"]),
                         ("en", 2, [f"lesson.{lesson}.summary"]))
        self.assertEqual(by_id[lesson]["difficulty_code"], "beginner")
        self.assertEqual(public_curriculum()["i18n"]["locale"], "zh-CN")

    def test_facts_and_broken_files_fall_back_to_the_source(self):
        write(self.path.with_name("catalog.en.json"),
              overlay({f"lesson.{self.first['id']}.status": {"text": "available", "source": "0"}}))
        with self.assertRaisesRegex(OverlayError, "不是可翻译的文本路径"):
            slot_coverage(read(self.path.with_name("catalog.en.json")), self.slots, "en")
        data = public_curriculum("en")
        self.assertEqual(data["i18n"]["locale"], "zh-CN")
        self.assertIn("error", data["i18n"])
        self.assertEqual(data["lessons"][0]["title"], self.first["title"])

    def test_api_serves_the_catalog_overlay_to_lessons_and_curriculum(self):
        lesson = self.first["id"]
        write(self.path.with_name("catalog.en.json"), overlay({
            f"lesson.{lesson}.title": self.entry(f"lesson.{lesson}.title", "One model request"),
            f"category.{self.first['category_id']}.title": self.entry(
                f"category.{self.first['category_id']}.title", "Native foundations")}))
        client = TestClient(web.app, base_url="http://localhost")
        listed = client.get("/api/lessons?lang=en").json()
        self.assertEqual(next(item for item in listed["lessons"] if item["id"] == lesson)["title"], "One model request")
        outline = client.get("/api/curriculum?lang=en").json()
        self.assertEqual(outline["categories"][0]["title"], "Native foundations")
        self.assertEqual(client.get("/api/curriculum").json()["lessons"][0]["title"], self.first["title"])
        self.assertEqual(client.get(f"/api/lessons/{lesson}?lang=en").json()["title"], "One model request")
        self.assertEqual(client.get("/api/curriculum?lang=en_US").status_code, 400)


class GlossaryOverlayTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "curriculum").mkdir()
        shutil.copy(ROOT / "curriculum" / "glossary.json", self.root / "curriculum" / "glossary.json")
        self.terms = read(self.root / "curriculum" / "glossary.json")["terms"]
        self.term = next(term for term in self.terms if term["zh"] != term["en"])

    def write_overlay(self, texts):
        write(self.root / "curriculum" / "glossary.en.json", overlay(texts))

    def test_english_names_definitions_and_aliases_merge_by_id(self):
        tid, en = self.term["id"], self.term["en"]
        self.write_overlay({f"{tid}.term": {"text": en.lower(), "source": digest(en)},
                            f"{tid}.definition": {"text": "An English definition.",
                                                  "source": digest(self.term["definition"])},
                            f"{tid}.aliases": {"text": ["alt name"], "source": digest(en)}})
        data = public_glossary(self.root, CATALOG_INDEX, "en")
        item = next(term for term in data["terms"] if term["id"] == tid)
        self.assertEqual((item["term"], item["display"], item["definition"], item["local_aliases"]),
                         (en.lower(), en.lower(), "An English definition.", ["alt name"]))
        self.assertEqual(item["definition_locale"], "en")
        # 映射字段与中文别名不变：回落成中文的正文仍能匹配。
        self.assertEqual((item["zh"], item["en"], item["aliases"]),
                         (self.term["zh"], en, self.term.get("aliases", [])))
        other = next(term for term in data["terms"] if term["id"] != tid)
        self.assertEqual((other["display"], other["definition_locale"]), (other["en"], "zh-CN"))
        self.assertEqual(data["i18n"]["translated"], 3)

    def test_source_language_keeps_bilingual_display_and_rejects_bad_entries(self):
        data = public_glossary(self.root, CATALOG_INDEX)
        item = next(term for term in data["terms"] if term["id"] == self.term["id"])
        self.assertEqual(item["display"], f"{self.term['zh']}（{self.term['en']}）")
        self.assertNotIn("term", item)
        tid = self.term["id"]
        for texts in ({f"{tid}.zh": {"text": "x", "source": "0"}},
                      {f"{tid}.aliases": {"text": "not a list", "source": digest(self.term["en"])}},
                      {f"{tid}.first_lesson": {"text": "x", "source": "0"}}):
            with self.subTest(texts=texts):
                self.write_overlay(texts)
                data = public_glossary(self.root, CATALOG_INDEX, "en")
                self.assertIn("error", data["i18n"])
                self.assertTrue(all(term["definition_locale"] == "zh-CN" for term in data["terms"]))

    def test_api_takes_lang(self):
        client = TestClient(web.app, base_url="http://localhost")
        data = client.get("/api/glossary?lang=en").json()
        self.assertEqual(data["i18n"]["requested"], "en")
        self.assertTrue(all(term["display"] == term["term"] for term in data["terms"]))
        self.assertTrue(all("（" not in term["display"] for term in data["terms"]))
        self.assertEqual(client.get("/api/glossary?lang=../x").status_code, 400)


class ManifestOverlayTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        source = lesson_spec("chat-request")
        self.spec = {**source, "root": Path(temp.name)}
        folder = Path(temp.name) / "lessons" / source["module"]
        folder.mkdir(parents=True)
        self.path = folder / "lesson.json"
        shutil.copy(source["root"] / "lessons" / source["module"] / "lesson.json", self.path)
        self.raw = read(self.path)
        self.slots = manifest_slots(copy.deepcopy(self.raw))

    def test_only_titles_and_labels_are_translatable(self):
        exercise = self.raw["exercises"][0]["id"]
        for path in ("subtitle", f"exercises.{exercise}.title", "ui.question_label", "ui.question_help"):
            self.assertIn(path, self.slots)
        for fact in (f"exercises.{exercise}.question", f"exercises.{exercise}.id", "ui.lab", "runtime.kind",
                     "input_defaults.system_prompt", "id"):
            self.assertNotIn(fact, self.slots)

    def test_merge_keeps_questions_and_inputs_in_the_source_language(self):
        exercise = self.raw["exercises"][0]
        key = f"exercises.{exercise['id']}.title"
        stale = {"text": "Old", "source": "000000000000"}
        write(self.path.with_name("lesson.en.json"), overlay({
            key: {"text": "With a system prompt", "source": digest(exercise["title"])},
            "ui.question_label": {"text": "User message", "source": digest(self.raw["ui"]["question_label"])},
            "subtitle": stale}))
        subtitle, exercises, ui, info = localized_manifest(self.spec, "en")
        self.assertEqual(exercises[0]["title"], "With a system prompt")
        self.assertEqual(exercises[0]["question"], exercise["question"])
        self.assertEqual(exercises[0].get("inputs"), exercise.get("inputs"))
        self.assertEqual((ui["question_label"], ui["lab"]), ("User message", self.raw["ui"]["lab"]))
        self.assertEqual(subtitle, self.raw["subtitle"])
        self.assertEqual((info["locale"], info["stale"]), ("en", ["subtitle"]))
        write(self.path.with_name("lesson.en.json"), overlay({f"exercises.{exercise['id']}.question":
                                                              {"text": "x", "source": "0"}}))
        _, exercises, _, info = localized_manifest(self.spec, "en")
        self.assertEqual((exercises[0]["title"], info["locale"]), (exercise["title"], "zh-CN"))
        self.assertIn("error", info)


class TranslationKitTargetTests(unittest.TestCase):
    def test_targets_cover_catalog_glossary_and_manifests(self):
        targets = translation_kit._documents()
        self.assertIn("catalog", targets)
        self.assertIn("glossary", targets)
        self.assertIn("manifest:chat-request", targets)
        exported = translation_kit.export("manifest:chat-request", "xx", include_all=True)
        self.assertIn("exercises.basic.title", exported)
        self.assertNotIn("exercises.basic.question", exported)
        glossary = translation_kit.export("glossary", "xx", include_all=True)
        term = next(path for path in glossary if path.endswith(".aliases"))
        self.assertEqual(glossary[term], glossary[term.replace(".aliases", ".term")])

    def test_apply_checks_shape_placeholders_and_facts(self):
        catalog = translation_kit.export("catalog", "xx", include_all=True)
        with_ref = next(path for path, text in catalog.items() if "{{lesson:" in text)
        with self.assertRaisesRegex(SystemExit, "占位符"):
            translation_kit.apply("catalog", "xx", {with_ref: "no reference"}, dry_run=True)
        with self.assertRaisesRegex(SystemExit, "不是可翻译路径"):
            translation_kit.apply("catalog", "xx", {"lesson.chat-request.status": "x"}, dry_run=True)
        glossary = translation_kit.export("glossary", "xx", include_all=True)
        aliases = next(path for path in glossary if path.endswith(".aliases"))
        with self.assertRaisesRegex(SystemExit, "字符串数组"):
            translation_kit.apply("glossary", "xx", {aliases: "one"}, dry_run=True)
        file = translation_kit.apply("glossary", "xx", {aliases: [], aliases.replace(".aliases", ".term"): "x"},
                                     dry_run=True)
        self.assertEqual(file.name, "glossary.xx.json")
        self.assertFalse(file.exists())


if __name__ == "__main__":
    unittest.main()
