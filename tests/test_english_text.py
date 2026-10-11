"""英文文本检查：不含中文（白名单除外）、没报告的用量写 not reported、不再写“中文原文加英文注释”。

覆盖英文译文层、英文运行时文本与英文界面文案；规则见 docs/architecture/terminology.md 第 5 节。
"""
import unittest

from scripts.validate_lessons import english_texts, validate_english
from server.catalog import LESSONS, ROOT
from server.vocabulary import ENGLISH_CJK_ALLOWED, english_problems


def kinds(text, file="lessons/lesson_x/content.en.json", path="section-1.paragraphs.0", **options):
    return [kind for kind, _ in english_problems(file, path, text, **options)]


class EnglishRuleTests(unittest.TestCase):
    def test_cjk_is_rejected(self):
        self.assertEqual(kinds("The report says 未报告 here."), ["英文文本含中文"])
        # 全角标点和全角数字也算。
        self.assertEqual(kinds("Done（finally）"), ["英文文本含中文"] * 2)
        self.assertEqual(kinds("Plain English, with “curly quotes” and — dashes."), [])

    def test_allowlist_is_exact_and_scoped(self):
        book = "*Understanding AI Agents in Depth* (深入理解 AI Agent) says so."
        self.assertEqual(kinds(book), [])
        # 书名必须带括号原样出现；单独的中文仍要报。
        self.assertEqual(kinds("The book 深入理解 AI Agent says so."), ["英文文本含中文"])
        # 分词示例只在 onboarding 的那一段里允许。
        example = 'the Chinese phrase "函数式编程" (functional programming)'
        self.assertEqual(kinds(example, file="curriculum/onboarding.en.json",
                               path="how-llm-works.tokens.paragraphs.1"), [])
        self.assertEqual(kinds(example, file="curriculum/onboarding.en.json", path="intro.paragraphs.0"),
                         ["英文文本含中文"])
        # 白名单子串之外的中文照样报。
        self.assertEqual(kinds(book + " 另外"), ["英文文本含中文"])

    def test_allowlist_entries_have_reasons(self):
        for file, path, substring, reason in ENGLISH_CJK_ALLOWED:
            with self.subTest(substring=substring):
                self.assertTrue(file and path and substring and reason.strip())

    def test_unreported_usage_must_not_be_unknown(self):
        for text in ("Usage unknown.", "the usage is unknown", "cache hits: unknown", "keep usage unknown",
                     "Unknown usage is not counted as zero.", "an unknown token count", "prompt tokens (unknown)",
                     "reasoning tokens were reported as \"unknown\""):
            with self.subTest(text=text):
                self.assertEqual(kinds(text), ["not reported 写成 unknown"])
        for text in ("usage the provider did not report is \"not reported\"", "usage of an unknown tool",
                     "An unknown tool name is refused.", "not reported means unknown",
                     "unknown tokens map to a fallback id", "usage, unknown elsewhere"):
            with self.subTest(text=text):
                self.assertEqual(kinds(text), [])
        self.assertEqual(kinds("Usage unknown.", unreported=False), [])

    def test_glossed_runtime_literal_is_rejected(self):
        self.assertEqual(kinds('the report shows "未报告" ("not reported")'), ["中文原文加英文注释"])
        self.assertEqual(kinds('the baseline “请给出答案”（“Give the answer”）'), ["中文原文加英文注释"])
        # 白名单救不了这种写法。
        self.assertEqual(kinds('see "(深入理解 AI Agent)" ("the book")'), ["中文原文加英文注释"])
        # 中文例子后面跟英文解释（不带引号）不是这种写法。
        self.assertEqual(kinds('the phrase "函数式编程" (functional programming)', file="curriculum/onboarding.en.json",
                               path="how-llm-works.tokens.paragraphs.1"), [])


class RepositoryTests(unittest.TestCase):
    def test_collects_every_kind_of_english_text(self):
        files = {file for file, *_ in english_texts(ROOT, LESSONS)}
        expected = {"curriculum/catalog.en.json", "curriculum/glossary.en.json", "curriculum/onboarding.en.json",
                    "course/locales/en.py", "frontend/src/i18n/locales/en/common.json",
                    "lessons/lesson_chat_request/content.en.json", "lessons/lesson_chat_request/lesson.en.json",
                    "lessons/lesson_chat_request/locales/en.py"}
        self.assertTrue(expected <= files, expected - files)
        self.assertTrue(any(file.endswith("/en.md") for file in files))

    def test_planned_catalog_entries_skip_only_the_unreported_rule(self):
        available = {spec["id"] for spec in LESSONS if spec.get("status") == "available"}
        for file, path, _, unreported in english_texts(ROOT, LESSONS):
            if file == "curriculum/catalog.en.json":
                parts = path.split(".")
                self.assertEqual(unreported, parts[0] == "lesson" and parts[1] in available, path)

    def test_repository_english_texts_pass(self):
        problems, unused = validate_english(ROOT, LESSONS)
        self.assertEqual(problems, [], "\n".join(f"{file} {path} [{kind}] {message}"
                                                 for file, path, kind, message in problems))
        self.assertEqual(unused, [], "白名单里有用不上的条目，请删掉")

    def test_every_allowlist_entry_is_used_in_this_repository(self):
        # validate_lessons 只对存在的具体文件查用不上的条目；通配条目在这里按整个仓库检查。
        from server.vocabulary import unused_allowances
        used = set()
        for file, path, text, unreported in english_texts(ROOT, LESSONS):
            english_problems(file, path, text, used, unreported=unreported)
        self.assertEqual(unused_allowances(used), [])


if __name__ == "__main__":
    unittest.main()
