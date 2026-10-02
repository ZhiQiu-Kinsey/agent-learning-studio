"""术语表：单一来源的结构校验、课程引用与只读接口。"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import server.app as web
from server.catalog import CATALOG_INDEX, ROOT, LESSONS
from server.curriculum import LessonValidationError
from server.glossary import TRANSLATABLE_FIELDS, display_label, load_glossary, validate_glossary


def source():
    return json.loads((ROOT / "curriculum" / "glossary.json").read_text(encoding="utf-8"))


class GlossaryValidationTests(unittest.TestCase):
    def test_source_file_is_valid_and_references_real_lessons(self):
        data = load_glossary(ROOT, CATALOG_INDEX)
        ids = [term["id"] for term in data["terms"]]
        self.assertEqual(len(ids), len(set(ids)))
        # 第 7 节术语约定与现有课程核心术语必须收录。
        self.assertTrue({"harness", "tool-calling", "function-calling", "evaluation", "human-in-the-loop",
                         "progressive-disclosure", "prompt-caching", "trace", "span", "sandbox",
                         "context-window", "memory", "rag"}.issubset(ids))

    def test_first_lesson_actually_mentions_the_term(self):
        # 防止编造：first_lesson 指向的课程目录条目或教学内容中必须出现中文名、英文名或别名。
        specs = {spec["id"]: spec for spec in LESSONS}
        for term in source()["terms"]:
            if "first_lesson" not in term:
                continue
            with self.subTest(term=term["id"]):
                text = json.dumps(CATALOG_INDEX.entries[term["first_lesson"]], ensure_ascii=False)
                if term["first_lesson"] in specs:
                    text += specs[term["first_lesson"]]["content_path"].read_text(encoding="utf-8")
                names = [term["zh"], term["en"], *term.get("aliases", [])]
                self.assertTrue(any(name.casefold() in text.casefold() for name in names))

    def test_rejects_structural_errors(self):
        base = source()

        def mutate(change):
            data = copy.deepcopy(base)
            change(data)
            return data

        cases = {
            "重复 id": lambda d: d["terms"].append(copy.deepcopy(d["terms"][0])),
            "id 非 kebab-case": lambda d: d["terms"][0].update(id="Tool_Calling"),
            "缺少 zh": lambda d: d["terms"][0].pop("zh"),
            "缺少 en": lambda d: d["terms"][0].pop("en"),
            "缺少释义": lambda d: d["terms"][0].pop("definition"),
            "空释义": lambda d: d["terms"][0].update(definition="  "),
            "释义过长": lambda d: d["terms"][0].update(definition="长" * 161),
            "未知字段": lambda d: d["terms"][0].update(note="x"),
            "别名不是数组": lambda d: d["terms"][0].update(aliases="RAG"),
            "别名与中文名相同": lambda d: d["terms"][0].update(aliases=[d["terms"][0]["zh"]]),
            "名称跨条目冲突": lambda d: d["terms"][1].update(aliases=[d["terms"][0]["zh"]]),
            "首课不存在": lambda d: d["terms"][0].update(first_lesson="no-such-lesson"),
            "首课写成数字": lambda d: d["terms"][0].update(first_lesson="1"),
            "未知类别": lambda d: d["terms"][0].update(kind="other"),
            "背景词设首课": lambda d: d["terms"][2].update(kind="background"),
            "not_in 不含术语名": lambda d: d["terms"][0].update(not_in=["无关词组"]),
            "not_in 不是数组": lambda d: d["terms"][0].update(not_in="词组"),
            "版本错误": lambda d: d.update(schema_version=2),
            "源语言错误": lambda d: d.update(locale="en"),
            "空术语表": lambda d: d.update(terms=[]),
        }
        for name, change in cases.items():
            with self.subTest(name), self.assertRaises(LessonValidationError):
                validate_glossary(mutate(change), CATALOG_INDEX)
        # 真实目录已没有别名；用带旧 slug 别名的最小目录检查“首课不能写别名”。
        from server.curriculum import index_catalog
        renamed = index_catalog({"lessons": [{"id": "tool-selection", "aliases": ["tool-old"], "status": "available"}]})
        with self.assertRaisesRegex(LessonValidationError, "slug「tool-selection」"):
            validate_glossary(mutate(lambda d: d["terms"][0].update(first_lesson="tool-old")), renamed)

    def test_display_format_and_translatable_fields(self):
        self.assertEqual(display_label({"zh": "运行层", "en": "Harness"}), "运行层（Harness）")
        self.assertEqual(display_label({"zh": "JSON Schema", "en": "JSON Schema"}), "JSON Schema")
        # 译文层只能覆盖文本，不改术语映射。
        self.assertFalse({"id", "zh", "en", "first_lesson"} & set(TRANSLATABLE_FIELDS))


class GlossaryApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web.app, base_url="http://localhost")

    def test_api_returns_terms_with_display_and_lesson_number(self):
        response = self.client.get("/api/glossary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["locale"], "zh-CN")
        terms = {term["id"]: term for term in data["terms"]}
        self.assertEqual(len(terms), len(source()["terms"]))
        self.assertEqual(terms["tool-calling"]["display"], "工具调用（Tool Calling）")
        self.assertEqual(terms["tool-calling"]["first_lesson"], "tool-selection")
        self.assertEqual(terms["tool-calling"]["first_lesson_number"], CATALOG_INDEX.numbers["tool-selection"])
        self.assertNotIn("first_lesson", terms["sandbox"])
        self.assertEqual(terms["harness"]["kind"], "concept")
        self.assertEqual(terms["tokenizer"]["kind"], "background")
        self.assertEqual(terms["rag"]["aliases"], ["RAG"])

    def test_broken_glossary_returns_safe_503(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture_root = Path(temporary)
            with patch.object(web, "ROOT", fixture_root):
                missing = self.client.get("/api/glossary")
                (fixture_root / "curriculum").mkdir()
                (fixture_root / "curriculum" / "glossary.json").write_text("{malformed", encoding="utf-8")
                malformed = self.client.get("/api/glossary")
                invalid_data = source()
                invalid_data["terms"][0]["first_lesson"] = "no-such-lesson"
                (fixture_root / "curriculum" / "glossary.json").write_text(json.dumps(invalid_data), encoding="utf-8")
                invalid = self.client.get("/api/glossary")
            for response in (missing, malformed, invalid):
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["code"], "glossary_unavailable")
                self.assertNotIn(temporary, response.text)


if __name__ == "__main__":
    unittest.main()
