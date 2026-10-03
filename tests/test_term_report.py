"""scripts/term_report.py：术语分组要按网页显示的文字匹配，课程引用先换成“第 N 课”。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import term_report  # noqa: E402

from server.catalog import CATALOG_INDEX, ROOT  # noqa: E402
from server.glossary import load_glossary  # noqa: E402


class TermGroupsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terms = load_glossary(ROOT, CATALOG_INDEX)["terms"]
        cls.numbers = CATALOG_INDEX.numbers

    def listed(self, text, lesson_id="chat-request"):
        groups = term_report.term_groups([text], self.terms, self.numbers, lesson_id)
        return {name for names in groups.values() for name in names}

    def test_lesson_ref_slug_words_are_not_reported_as_terms(self):
        # slug 里有 reflection、workflow、memory：不换成“第 N 课”就会被当成术语 Reflection 等。
        text = "这件事见{{lesson:reflection-revision}}，对比{{lesson:workflow-patterns}}和{{lesson:memory-lifecycle}}。"
        self.assertEqual(self.listed(text), set())

    def test_real_terms_next_to_a_ref_are_still_listed(self):
        text = "{{lesson:reflection-revision}}讲了反思，{{lesson:workflow-patterns}}讲了提示链。"
        self.assertEqual(self.listed(text), {"反思", "提示链"})


if __name__ == "__main__":
    unittest.main()
