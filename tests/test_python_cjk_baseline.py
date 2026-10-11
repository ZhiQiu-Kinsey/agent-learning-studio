"""课程与平台代码里的硬编码中文只许减少：运行时文本写进 locales/ 消息目录（规则见 scripts/cjk_baseline.py）。"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cjk_baseline  # noqa: E402


class PythonCjkBaselineTests(unittest.TestCase):
    def test_counts_string_literals_and_docstrings_but_not_comments(self):
        sample = '"""中文文档。"""\n# 注释不算\nA = "运行"\nB = f"第 {n} 轮"\nC = "English"\n'
        self.assertEqual(cjk_baseline.count(sample), 3)

    def test_source_catalogs_and_tests_are_exempt(self):
        self.assertTrue(cjk_baseline.exempt("lessons/lesson_x/locales/zh_CN.py"))
        self.assertTrue(cjk_baseline.exempt("lessons/lesson_x/locales/tools/zh_CN.py"))
        self.assertTrue(cjk_baseline.exempt("lessons/lesson_x/test_lesson.py"))
        self.assertFalse(cjk_baseline.exempt("lessons/lesson_x/locales/en.py"))
        self.assertFalse(cjk_baseline.exempt("lessons/lesson_x/zh_CN.py"))

    def test_matches_the_committed_baseline(self):
        baseline = json.loads(cjk_baseline.BASELINE.read_text(encoding="utf-8"))
        grew, shrank = cjk_baseline.compare(cjk_baseline.scan(), baseline)
        self.assertEqual(grew, [], "新增了硬编码中文：运行时文本移到 locales/ 消息目录，注释与文档字符串写英文")
        self.assertEqual(shrank, [], "硬编码中文减少了：运行 python scripts/cjk_baseline.py 收紧基线")


if __name__ == "__main__":
    unittest.main()
