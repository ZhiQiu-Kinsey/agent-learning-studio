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
from server.code_reading import (classify, extract_symbols, extract_texts, line_count, localize_texts_block,
                                 source_role, split_lines, texts_layout)

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


ZH_TEXTS = textwrap.dedent('''    """zh."""
    from x import Texts

    TEXTS = Texts(
        system_prompt=(
            "第一句。"
            "第二句。"
        ),
        title="标题",
    )
    ''')
EN_TEXTS = textwrap.dedent('''    """en."""
    from x import Texts

    # A comment moves every line down by one.
    TEXTS = Texts(
        system_prompt=(
            "First sentence. "
            "Second sentence."
        ),
        title="Title",
    )
    ''')


class TextsTests(unittest.TestCase):
    def test_role_and_text_symbols(self):
        self.assertEqual(source_role("lessons/lesson_x/locales/zh_CN.py"), "texts")
        self.assertEqual(source_role("lessons/lesson_x/locales/tools/en.py"), "texts")
        self.assertEqual(source_role("course/locales/__init__.py"), "texts")
        self.assertEqual(source_role("course/runner.py"), "platform")
        symbols = {item["name"]: item for item in extract_texts(ZH_TEXTS)}
        self.assertEqual(set(symbols), {"t.system_prompt", "t.title"})
        self.assertEqual((symbols["t.system_prompt"]["start"], symbols["t.system_prompt"]["end"]), (5, 8))
        self.assertEqual(symbols["t.system_prompt"]["kind"], "text")
        # 改一个字就是变化。
        self.assertNotEqual(extract_texts(ZH_TEXTS)[0]["hash"],
                            extract_texts(ZH_TEXTS.replace("第二句", "第三句"))[0]["hash"])
        self.assertEqual(texts_layout(ZH_TEXTS)["TEXTS"], (4, 4))

    def test_blocks_on_source_texts_map_to_the_other_language_by_field(self):
        block = {"id": "b", "path": "lessons/x/locales/zh_CN.py", "start": 4, "end": 10,
                 "notes": [{"id": "n1", "line": 7, "anchor": "第二句", "text": "第二句的批注"},
                           {"id": "n2", "line": 9, "anchor": "title", "text": "标题"}],
                 "folds": []}
        moved = localize_texts_block(block, ZH_TEXTS, "lessons/x/locales/en.py", EN_TEXTS)
        self.assertEqual(moved["path"], "lessons/x/locales/en.py")
        self.assertEqual((moved["start"], moved["end"]), (5, 11))
        self.assertEqual([note["line"] for note in moved["notes"]], [8, 10])
        self.assertTrue(all("anchor" not in note for note in moved["notes"]))
        self.assertIn("Second sentence", EN_TEXTS.splitlines()[moved["notes"][0]["line"] - 1])


class TextsBlockValidationTests(unittest.TestCase):
    """写在运行时文本上的读码块：只写在源语言文件上，覆盖的字段各语言行数相同。"""

    SOURCES = [{"path": "lessons/x/locales/zh_CN.py", "language": "python", "locale": "zh-CN"},
               {"path": "lessons/x/locales/en.py", "language": "python", "locale": "en"}]

    def check(self, block, en_text=EN_TEXTS):
        from server.code_reading import _check_texts_block

        files = {"lessons/x/locales/zh_CN.py": ZH_TEXTS, "lessons/x/locales/en.py": en_text}
        _check_texts_block(block, self.SOURCES, files.__getitem__, "test")

    def block(self, **changes):
        from types import SimpleNamespace

        values = {"path": "lessons/x/locales/zh_CN.py", "start": 4, "end": 10, "folds": [],
                  "notes": [SimpleNamespace(id="n1", line=7)]}
        return SimpleNamespace(**{**values, **changes})

    def test_valid_block(self):
        self.check(self.block())

    def test_rejected_blocks(self):
        cases = {
            "源语言": self.block(path="lessons/x/locales/en.py"),
            "start 与 end": self.block(start=None),
            "不在 TEXTS": self.block(start=1),
        }
        for message, block in cases.items():
            with self.subTest(message=message), self.assertRaisesRegex(LessonValidationError, message):
                self.check(block)
        squeezed = EN_TEXTS.replace('"First sentence. "\n        "Second sentence."', '"First sentence. Second sentence."')
        self.assertNotEqual(squeezed, EN_TEXTS)
        with self.assertRaisesRegex(LessonValidationError, "行数"):
            self.check(self.block(), squeezed)


class RealLessonTests(unittest.TestCase):
    def view(self, lesson_id):
        return lesson_code_view(next(spec for spec in LESSONS if spec["id"] == lesson_id))

    def test_first_lesson_has_no_baseline_and_lists_everything_as_added(self):
        self.assertEqual(LESSONS[0]["id"], "chat-request")
        data = self.view("chat-request")
        self.assertIsNone(data["whats_new"]["compare_with"])
        self.assertEqual(data["whats_new"]["changed"], [])
        names = {item["name"] for item in data["whats_new"]["added"]}
        self.assertTrue({"build_request", "read_reply", "run", "INPUT_MODEL"} <= names)
        # 平台代码与测试夹具不算本课新增：send_bailian 在 course/，create_completion 在 fixtures.py。
        self.assertFalse({"send_bailian", "call_bailian", "create_completion"} & names)
        roles = {item["path"]: item["role"] for item in data["files"]}
        self.assertEqual(roles["course/api_client.py"], "platform")
        self.assertEqual(roles["lessons/lesson_chat_request/runtime.py"], "lesson")
        self.assertEqual(roles["lessons/lesson_chat_request/fixtures.py"], "fixture")
        # 运行时文本只给出运行语言那一份：中文界面看 zh_CN.py，英文界面看 en.py。
        self.assertEqual([item["path"] for item in data["files"]],
                         [s["path"] for s in LESSONS[0]["sources"] if s.get("locale") in (None, "zh-CN")])
        self.assertEqual(roles["lessons/lesson_chat_request/locales/zh_CN.py"], "texts")
        english = lesson_code_view(LESSONS[0], "en")
        self.assertEqual(english["runtime_locale"], "en")
        self.assertIn("lessons/lesson_chat_request/locales/en.py", [item["path"] for item in english["files"]])
        self.assertNotIn("lessons/lesson_chat_request/locales/zh_CN.py", [item["path"] for item in english["files"]])
        # 运行时文本的字段也算本课新增，名字写成代码里读取它的样子。
        self.assertIn("t.report_title", names)

    def test_tool_lessons_share_the_tool_definitions(self):
        # 执行课沿用提议课的 tools.py：工具定义显示为沿用，main.py 的系统提示词与入口才是新内容。
        data = self.view("tool-selection")
        news = data["whats_new"]
        self.assertEqual(news["compare_with"]["id"], "tool-proposals")
        unchanged = {item["name"] for item in news["unchanged"]}
        self.assertTrue({"tool_definitions", "available_tools", "add_numbers", "get_current_time"} <= unchanged)
        # 工具描述在共用的 locales/tools/ 里，提议课也登记了它：沿用；系统提示词在提议课的基础上改写过。
        self.assertIn("t.add_numbers", unchanged)
        self.assertIn("t.system_prompt", {item["name"] for item in news["changed"]})
        # 运行时文本按源语言比较，英文界面得出同样的结论。
        english = lesson_code_view(next(spec for spec in LESSONS if spec["id"] == "tool-selection"), "en")
        self.assertEqual({item["name"] for item in english["whats_new"]["unchanged"]}, unchanged)
        self.assertFalse({"run_agent", "execute_tool"} & {item["name"] for item in news["added"]})
        roles = {item["path"]: item["role"] for item in data["files"]}
        self.assertEqual(roles["course/runner.py"], "platform")
        self.assertEqual(roles["lessons/lesson_01_tool_selection/tools.py"], "lesson")

    def test_second_lesson_compares_with_previous_and_keeps_shared_tools(self):
        data = self.view("dependent-calls")
        news = data["whats_new"]
        self.assertEqual(news["compare_with"]["id"], "tool-selection")
        # 两课的 main.py 写法相同、只换了提示词：系统提示词显示为变化，setup 与 main 沿用。
        self.assertIn("t.system_prompt", {item["name"] for item in news["changed"]})
        self.assertEqual({item["name"] for item in news["added"]}, set())
        unchanged = {item["name"] for item in news["unchanged"]}
        self.assertTrue({"setup", "main", "tool_definitions", "add_numbers", "t.add_numbers"} <= unchanged)
        self.assertNotIn("run_agent", unchanged)
        prompt = next(item for item in news["changed"] if item["name"] == "t.system_prompt")
        source = (Path(web.ROOT) / prompt["path"]).read_text(encoding="utf-8").splitlines()
        self.assertTrue(source[prompt["start"] - 1].strip().startswith("system_prompt="))

    def test_compared_lesson_title_follows_the_requested_language(self):
        # 对照课标题来自实现清单的源语言；英文界面要换成目录译文里的标题，没有译文时保持源文本。
        from server.catalog import localized_entries

        spec = next(spec for spec in LESSONS if spec["id"] == "dependent-calls")
        source = lesson_code_view(spec)["whats_new"]["compare_with"]["title"]
        english = lesson_code_view(spec, "en")["whats_new"]["compare_with"]
        self.assertEqual(english["title"], localized_entries("en")[english["id"]]["title"])
        if (Path(web.ROOT) / "curriculum" / "catalog.en.json").is_file():
            self.assertNotEqual(english["title"], source)
        self.assertEqual(lesson_code_view(spec, "fr")["whats_new"]["compare_with"]["title"], source)

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
        self.assertEqual(set(data), {"lesson_id", "runtime_locale", "files", "whats_new", "annotations"})
        self.assertEqual(data["lesson_id"], "fail-safely")
        self.assertIn("divide_numbers", {item["name"] for item in data["whats_new"]["added"]})
        self.assertNotIn("content", data["files"][0])  # 源码正文仍由课程详情提供

    def test_unknown_planned_and_invalid_locale_use_error_codes(self):
        # 目录里已没有 planned 课：临时把 document-loading 从可执行课程里拿掉，它就只剩目录登记（未开放）。
        hidden = [item for item in LESSONS if item["id"] != "document-loading"]
        self.enterContext(patch.object(web, "LESSONS", hidden))
        self.enterContext(patch("server.catalog.LESSONS", hidden))
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
