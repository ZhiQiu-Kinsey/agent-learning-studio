"""读码场景：AST 符号提取、本课新增判定、批注校验与 /api/lessons/{id}/code 接口。"""
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import server.app as web
from server.catalog import LESSONS, LessonValidationError, lesson_code_view, load_lessons
from server.code_reading import classify, extract_symbols, line_count, split_lines

SAMPLE = textwrap.dedent('''\
    """模块说明。"""
    import json

    SYSTEM_PROMPT = "你好"
    TOOLS: list = []
    helper_value = 3


    @decorator
    def add(a, b):
        return a + b


    class Store:
        def get(self):
            return None
    ''')


class SymbolTests(unittest.TestCase):
    def test_extracts_top_level_functions_classes_and_constants_with_lines(self):
        symbols = {item["name"]: item for item in extract_symbols(SAMPLE)}
        self.assertEqual(set(symbols), {"SYSTEM_PROMPT", "TOOLS", "add", "Store"})  # 小写变量与方法不算
        self.assertEqual((symbols["SYSTEM_PROMPT"]["kind"], symbols["SYSTEM_PROMPT"]["start"]), ("constant", 4))
        self.assertEqual(symbols["TOOLS"]["kind"], "constant")
        self.assertEqual((symbols["add"]["kind"], symbols["add"]["start"], symbols["add"]["end"]), ("function", 9, 11))
        self.assertEqual((symbols["Store"]["kind"], symbols["Store"]["start"], symbols["Store"]["end"]), ("class", 14, 16))

    def test_hash_ignores_comments_whitespace_and_position_but_not_code(self):
        moved = "\n\n# 注释\n" + SAMPLE.replace("return a + b", "return a  +  b  # 求和")
        changed = SAMPLE.replace("return a + b", "return a - b")
        base = {item["name"]: item["hash"] for item in extract_symbols(SAMPLE)}
        self.assertEqual(base, {item["name"]: item["hash"] for item in extract_symbols(moved)})
        self.assertNotEqual(base["add"], {item["name"]: item["hash"] for item in extract_symbols(changed)}["add"])

    def test_syntax_errors_are_not_hidden(self):
        with self.assertRaises(SyntaxError):
            extract_symbols("def broken(:\n")

    def test_line_counting_matches_frontend_rules(self):
        self.assertEqual(line_count("a\nb\n"), 2)
        self.assertEqual(line_count("a\r\nb"), 2)
        self.assertEqual(split_lines("a\rb\n\n"), ["a", "b", ""])
        self.assertEqual(line_count(""), 0)

    def test_classify_added_changed_and_unchanged(self):
        current = [{"name": "run", "hash": "1"}, {"name": "TOOLS", "hash": "2"}, {"name": "new", "hash": "3"}]
        baseline = [{"name": "run", "hash": "9"}, {"name": "TOOLS", "hash": "2"}, {"name": "gone", "hash": "4"}]
        self.assertEqual(classify(current, baseline), {"run": "changed", "TOOLS": "unchanged", "new": "added"})
        self.assertEqual(classify(current, None), {"run": "added", "TOOLS": "added", "new": "added"})
        # 同一课内同名符号任一处与基准相同即视为沿用。
        twice = [{"name": "run", "hash": "1"}, {"name": "run", "hash": "9"}]
        self.assertEqual(classify(twice, baseline), {"run": "unchanged"})


class RealLessonTests(unittest.TestCase):
    def view(self, lesson_id):
        return lesson_code_view(next(spec for spec in LESSONS if spec["id"] == lesson_id))

    def test_first_lesson_has_no_baseline_and_lists_everything_as_added(self):
        data = self.view("tool-selection")
        self.assertIsNone(data["whats_new"]["compare_with"])
        self.assertEqual(data["whats_new"]["changed"], [])
        names = {item["name"] for item in data["whats_new"]["added"]}
        self.assertTrue({"TOOLS", "add_numbers", "get_current_time", "SYSTEM_PROMPT"} <= names)
        # 平台代码与测试夹具不算本课新增：run_agent 在 course/，create_completion 在 fixtures.py。
        self.assertFalse({"run_agent", "create_completion", "call_bailian"} & names)
        roles = {item["path"]: item["role"] for item in data["files"]}
        self.assertEqual(roles["course/runner.py"], "platform")
        self.assertEqual(roles["lessons/lesson_01_tool_selection/tools.py"], "lesson")
        self.assertEqual([item["path"] for item in data["files"]], [s["path"] for s in LESSONS[0]["sources"]])

    def test_second_lesson_compares_with_previous_and_keeps_shared_tools(self):
        data = self.view("dependent-calls")
        news = data["whats_new"]
        self.assertEqual(news["compare_with"]["id"], "tool-selection")
        self.assertEqual({item["name"] for item in news["changed"]}, {"SYSTEM_PROMPT", "main"})
        self.assertEqual(news["added"], [])
        unchanged = {item["name"] for item in news["unchanged"]}
        self.assertTrue({"TOOLS", "add_numbers"} <= unchanged)
        self.assertNotIn("run_agent", unchanged)
        prompt = next(item for item in news["changed"] if item["name"] == "SYSTEM_PROMPT")
        source = (Path(web.ROOT) / prompt["path"]).read_text(encoding="utf-8").splitlines()
        self.assertTrue(source[prompt["start"] - 1].startswith("SYSTEM_PROMPT"))

    def test_declared_compare_with_overrides_previous_lesson(self):
        spec = next(spec for spec in LESSONS if spec["id"] == "context-budget")
        self.assertEqual(spec["code_compare"], "messages-context")
        self.assertEqual(self.view("context-budget")["whats_new"]["compare_with"]["id"], "messages-context")

    def test_every_lesson_has_annotations_and_one_decision_on_real_lines(self):
        for spec in LESSONS:
            with self.subTest(lesson=spec["id"]):
                data = lesson_code_view(spec)
                self.assertTrue(1 <= len(data["annotations"]) <= 3)
                counts = {item["path"]: item["lines"] for item in data["files"]}
                for block in data["annotations"]:
                    self.assertIn(block["path"], counts)
                    self.assertTrue(block["notes"])
                    for note in block["notes"]:
                        self.assertLessEqual(note["line"], counts[block["path"]])
                content = json.loads(spec["content_path"].read_text(encoding="utf-8"))
                decisions = [b for b in content["scenes"]["code"]["blocks"] if b["type"] == "decision"]
                self.assertEqual(len(decisions), 1)
                self.assertTrue(decisions[0]["alternatives"])


class ValidationTests(unittest.TestCase):
    """在临时项目中构造一门课，验证批注越界、路径不在白名单与对比课引用都会让课程加载失败。"""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-code-reading-")
        self.root = Path(self.temporary.name)
        self.catalog = {"lessons": []}

    def tearDown(self):
        for name in list(sys.modules):
            if name.startswith("lessons.lesson_code_"):
                del sys.modules[name]
        self.temporary.cleanup()

    def course(self, identifier, blocks, extra_file=False):
        module = "lesson_code_" + identifier
        directory = self.root / "lessons" / module
        directory.mkdir(parents=True)
        (directory / "runtime.py").write_text("def run(context):\n    return 'ok'\n", encoding="utf-8")
        if extra_file:
            (directory / "other.py").write_text("X = 1\n", encoding="utf-8")
        content = {"schema_version": 2, "lesson": identifier, "source_language": "zh-CN",
                   "scenes": {"code": {"blocks": blocks}}}
        (directory / "content.json").write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
        manifest = {"schema_version": 1, "id": identifier, "subtitle": "副标题", "content": "content.json",
                    "sources": [{"path": f"lessons/{module}/runtime.py", "language": "python"}],
                    "exercises": [{"id": "e", "title": "实验", "question": "运行"}],
                    "runtime": {"kind": "custom", "entrypoint": "runtime:run", "requires_model": False}}
        (directory / "lesson.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        self.catalog["lessons"].append({"id": identifier, "title": "标题", "summary": "说明",
                                        "objectives": ["目标"], "status": "available"})
        return f"lessons/{module}/runtime.py"

    def note_block(self, path, line, anchor=None, **extra):
        # runtime.py 第 1 行是 def run(context):，第 2 行是 return 'ok'。
        anchor = anchor or {1: "def run", 2: "return"}.get(line, "x")
        return {"id": "src", "type": "annotated-source", "path": path, **extra,
                "notes": [{"id": "n", "line": line, "anchor": anchor, "text": "批注"}]}

    def load(self):
        return load_lessons(self.root, self.catalog)

    def test_valid_annotations_load(self):
        path = "lessons/lesson_code_one/runtime.py"
        self.course("one", [self.note_block(path, 2, start=1, end=2)])
        self.assertEqual(self.load()[0]["id"], "one")

    def test_line_beyond_file_length_is_rejected(self):
        path = "lessons/lesson_code_one/runtime.py"
        self.course("one", [self.note_block(path, 3)])
        with self.assertRaisesRegex(LessonValidationError, "超出文件行数"):
            self.load()

    def test_range_beyond_file_and_note_outside_range_are_rejected(self):
        path = "lessons/lesson_code_one/runtime.py"
        self.course("one", [self.note_block(path, 1, start=1, end=9)])
        with self.assertRaisesRegex(LessonValidationError, "end=9"):
            self.load()

    def test_note_outside_declared_range_is_rejected(self):
        path = "lessons/lesson_code_one/runtime.py"
        self.course("one", [self.note_block(path, 1, start=2, end=2)])
        with self.assertRaisesRegex(LessonValidationError, "不在 2–2 范围内"):
            self.load()

    def test_path_outside_lesson_sources_is_rejected_even_if_file_exists(self):
        self.course("one", [self.note_block("lessons/lesson_code_one/other.py", 1)], extra_file=True)
        with self.assertRaisesRegex(LessonValidationError, "不在本课 sources 中"):
            self.load()

    def test_anchor_must_appear_on_the_annotated_line(self):
        path = "lessons/lesson_code_one/runtime.py"
        self.course("one", [self.note_block(path, 2, anchor="def run")])
        with self.assertRaisesRegex(LessonValidationError, "锚点「def run」不在第 2 行"):
            self.load()

    def test_fold_must_stay_inside_block_range(self):
        path = "lessons/lesson_code_one/runtime.py"
        block = self.note_block(path, 1, start=1, end=1)
        block["folds"] = [{"id": "f", "start": 2, "end": 2, "label": "平台代码"}]
        self.course("one", [block])
        with self.assertRaisesRegex(LessonValidationError, "折叠 f 的 2–2 不在 1–1 范围内"):
            self.load()

    def test_note_inside_fold_is_rejected(self):
        path = "lessons/lesson_code_one/runtime.py"
        block = self.note_block(path, 2)
        block["folds"] = [{"id": "f", "start": 2, "end": 2, "label": "平台代码"}]
        self.course("one", [block])
        with self.assertRaisesRegex(LessonValidationError, "折叠 f 内不能有批注"):
            self.load()

    def test_compare_with_must_reference_another_implemented_lesson(self):
        self.course("one", [{"id": "news", "type": "whats-new", "compare_with": "one"}])
        with self.assertRaisesRegex(LessonValidationError, "compare_with"):
            self.load()

    def test_compare_with_accepts_alias_and_resolves_to_slug(self):
        self.course("one", [{"id": "news", "type": "whats-new"}])
        self.course("two", [{"id": "news", "type": "whats-new", "compare_with": "old-one"}])
        self.catalog["lessons"][0]["aliases"] = ["old-one"]
        specs = self.load()
        self.assertEqual([spec["code_compare"] for spec in specs], [None, "one"])


class CodeApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web.app, base_url="http://localhost")

    def test_slug_returns_the_code_payload_and_numbers_are_not_ids(self):
        by_slug = self.client.get("/api/lessons/fail-safely/code")
        self.assertEqual(by_slug.status_code, 200)
        # 显示课号不是 ID：插入新课会改变课号，接口只认 slug。
        self.assertEqual(self.client.get("/api/lessons/3/code").json()["code"], "lesson_not_found")
        data = by_slug.json()
        self.assertEqual(set(data), {"lesson_id", "files", "whats_new", "annotations"})
        self.assertEqual(data["lesson_id"], "fail-safely")
        self.assertIn("divide_numbers", {item["name"] for item in data["whats_new"]["added"]})
        self.assertNotIn("content", data["files"][0])  # 源码正文仍由课程详情提供

    def test_unknown_planned_and_invalid_locale_use_error_codes(self):
        cases = {"/api/lessons/no-such-lesson/code": (404, "lesson_not_found"),
                 "/api/lessons/document-loading/code": (404, "lesson_not_available"),
                 "/api/lessons/tool-selection/code?lang=bad%20code": (400, "invalid_locale")}
        for url, (status, code) in cases.items():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual((response.status_code, response.json()["code"]), (status, code))

    def test_unparsable_source_returns_code_unavailable(self):
        with patch("server.code_reading.extract_symbols", side_effect=SyntaxError("broken")), \
                patch("server.code_reading._cache", {}):
            response = self.client.get("/api/lessons/tool-selection/code")
        self.assertEqual((response.status_code, response.json()["code"]), (503, "code_unavailable"))
        self.assertNotIn("broken", response.text)


if __name__ == "__main__":
    unittest.main()
