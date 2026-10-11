"""课程正文的用词：术语只在引入课写中英并列，先讲后用，正文不留裸英文词，代码说明有出处。

规则与作者流程见 docs/architecture/terminology.md；逐课明细用 scripts/term_report.py 查看。
"""
import json
import unittest

from server.catalog import CATALOG_INDEX, LESSONS, ROOT, lesson_code_names
from server.code_names import code_names, names_in_source
from server.content import lesson_content_model
from server.glossary import load_glossary
from server.vocabulary import UNREPORTED, TermMatcher, bare_words, lesson_problems, marked_texts, name_used


class CodeNameTests(unittest.TestCase):
    def test_names_come_from_tokens_not_comments_or_docstrings(self):
        source = '"""Docstring words stay out."""\n# comment words stay out\n' \
                 'TASK = {"evidence": 1, "stop": "Final Answer:", "note": "a long sentence here is not a name"}\n' \
                 'def verify(claim):\n    return "lesson.plan"\n'
        names = names_in_source(source)
        self.assertTrue({"TASK", "evidence", "stop", "Final Answer", "verify", "claim", "lesson.plan"} <= names)
        self.assertFalse({"Docstring", "comment", "words", "a long sentence here is not a name"} & names)

    def test_glossary_names_win_over_code_names(self):
        names = code_names(['token = 1\nusage = 2\n'], glossary_forms=["Token"])
        self.assertIn("usage", names)
        self.assertNotIn("token", names)
        # 平台名字（角色、事件、终态）每课都可用。
        self.assertTrue({"assistant", "tool_result", "completed", "true"} <= set(names))

    def test_lesson_detail_publishes_code_names(self):
        spec = next(spec for spec in LESSONS if spec["id"] == "task-contract")
        names = lesson_code_names(spec)
        self.assertTrue({"evidence", "failure", "evidence_ref"} <= set(names))


class UnreportedWordingTests(unittest.TestCase):
    def test_usage_the_provider_did_not_report_is_not_called_unknown(self):
        # 统一用词：服务商没有报告的数写“未报告”；“未知”只留给确实无法知道的值。
        for text in ("命中数未知，不是 0", "用量未知", "提示 Token 未知", "未知的用量"):
            with self.subTest(text=text):
                self.assertTrue(UNREPORTED.search(text))
        for text in ("命中数未报告，不是 0", "路由遇到未知标签直接报错", "未知的消息角色"):
            with self.subTest(text=text):
                self.assertIsNone(UNREPORTED.search(text))


class MatcherTests(unittest.TestCase):
    TERMS = [
        {"id": "validator", "zh": "验证器", "en": "Validator", "aliases": ["验收器"]},
        {"id": "acceptance", "zh": "验收标准", "en": "Acceptance Criteria"},
        {"id": "evaluation", "zh": "评估", "en": "Evaluation", "not_in": ["评估者"]},
        {"id": "token", "zh": "Token", "en": "Token"},
    ]

    def test_longest_form_and_not_in_phrases(self):
        matcher = TermMatcher(self.TERMS)
        ids = [term["id"] for _, _, term in matcher.find("验收器对照验收标准；评估者给出评估。tokens 不是 Token")]
        self.assertEqual(ids, ["validator", "acceptance", "evaluation", "token"])

    def test_bare_words_skip_terms_code_tokens_and_code_names(self):
        matcher = TermMatcher(self.TERMS)
        text = "evidence 指向 tool_result，Token 数要看 tokenizer，lesson.report 汇总"
        self.assertEqual([word for word, _ in bare_words(text, {"evidence"}, matcher)], ["tokenizer"])
        self.assertTrue(name_used("stop", "请求里的 stop 参数"))
        self.assertFalse(name_used("stop", "stop_reason 与 lesson.stop"))


class LessonVocabularyTests(unittest.TestCase):
    """每课的用词问题必须为零；scripts/term_report.py 给出同样的清单和修改建议。"""

    @classmethod
    def setUpClass(cls):
        cls.terms = load_glossary(ROOT, CATALOG_INDEX)["terms"]
        cls.available = {spec["id"] for spec in LESSONS}

    def test_every_lesson_has_no_vocabulary_problems(self):
        for spec in LESSONS:
            with self.subTest(lesson=spec["id"]):
                model = lesson_content_model(spec["content_path"], spec)
                problems = lesson_problems(spec["id"], model, self.terms, CATALOG_INDEX.numbers,
                                           lesson_code_names(spec), self.available)
                self.assertEqual(problems, [], "\n".join(f"[{kind}] {message}" for kind, message in problems))

    def test_every_concept_introduced_by_an_available_lesson_is_marked_there(self):
        # first_lesson 指向可运行课时，那一课加下划线的正文里必须真的出现这个术语。
        matcher = TermMatcher(self.terms)
        specs = {spec["id"]: spec for spec in LESSONS}
        for term in self.terms:
            lesson = term.get("first_lesson")
            if lesson not in specs:
                continue
            with self.subTest(term=term["id"]):
                model = lesson_content_model(specs[lesson]["content_path"], specs[lesson])
                self.assertIn(term["id"], matcher.first_hits("\n".join(marked_texts(model))))

    def test_background_terms_have_no_first_lesson(self):
        for term in self.terms:
            if term.get("kind") == "background":
                self.assertNotIn("first_lesson", term, term["id"])


class GlossaryFileTests(unittest.TestCase):
    def test_dropped_everyday_words_stay_out(self):
        # 程序员都懂的常用词不收录：标出来只会打断阅读。
        data = json.loads((ROOT / "curriculum" / "glossary.json").read_text(encoding="utf-8"))
        names = {term["zh"] for term in data["terms"]}
        self.assertFalse({"重试", "修订", "提示词"} & names)


if __name__ == "__main__":
    unittest.main()
