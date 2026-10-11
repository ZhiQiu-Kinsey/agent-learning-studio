"""课程作者工具不会覆盖已有工作，也不会意外开放规划课程。"""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.new_lesson import build_scaffold, main, write_scaffold


class LessonScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "curriculum").mkdir()
        self.catalog = {"lessons": [
            {"id": "tool-selection", "aliases": ["tool-old"], "title": "已有课程", "status": "available"},
            {"id": "task-contract", "aliases": ["task-card"], "title": "任务契约", "status": "planned"},
        ]}
        self.catalog_path = self.root / "curriculum" / "catalog.json"
        self.catalog_path.write_text(json.dumps(self.catalog, ensure_ascii=False), encoding="utf-8")

    def test_dry_run_lists_files_without_writing_or_unlocking(self):
        output = io.StringIO()
        before = self.catalog_path.read_bytes()
        with redirect_stdout(output):
            result = main(["--root", str(self.root), "--id", "task-card", "--slug", "task_contract", "--dry-run"])
        self.assertEqual(result, 0)
        self.assertIn("lesson_task_contract", output.getvalue())
        self.assertIn("lesson.json", output.getvalue())
        self.assertIn("planned", output.getvalue())
        self.assertFalse((self.root / "lessons").exists())
        self.assertEqual(self.catalog_path.read_bytes(), before)

    def generated(self, kind):
        """把生成的课程写进临时目录，并让 lessons 包能导入它（与 tests/test_lesson_registry.py 同样的做法）。"""
        import importlib
        import sys
        from unittest.mock import patch

        import lessons

        target, files = build_scaffold(self.root, "task-card", "task_contract", kind)
        write_scaffold(target, files)
        patcher = patch.object(lessons, "__path__", [str(self.root / "lessons"), *lessons.__path__])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lambda: [sys.modules.pop(name) for name in list(sys.modules)
                                 if name.startswith("lessons.lesson_task_contract")])
        importlib.invalidate_caches()
        return target, files, lambda name: importlib.import_module(f"lessons.lesson_task_contract.{name}")

    def test_native_scaffold_runs_real_tool_with_its_own_fixture_in_both_locales(self):
        from course.runner import execute_tool, run_agent

        target, files, load = self.generated("native")
        manifest = json.loads((target / "lesson.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["runtime"]["kind"], "native")
        self.assertEqual(manifest["runtime"]["locales"], ["zh-CN", "en"])
        self.assertEqual(manifest["testing"]["completion_factory"], "fixtures:create_completion")
        self.assertEqual(json.loads(self.catalog_path.read_text(encoding="utf-8")), self.catalog)
        main, fixtures = load("main"), load("fixtures")
        for locale, repeated in (("zh-CN", "课程脚手架"), ("en", "lesson scaffold")):
            with self.subTest(locale=locale):
                results = []
                completion = fixtures.create_completion("starter", locale=locale)
                agent = main.setup(locale)

                def execute(tool_call, available_tools):
                    results.append(execute_tool(tool_call, available_tools, locale))
                    return results[-1]

                answer = run_agent(manifest["exercises"][0]["question"][locale], agent.system_prompt, agent.tools,
                                   agent.available_tools, 3, complete=lambda body, number: completion(body, ""),
                                   execute=execute, locale=locale)
                self.assertEqual(results[0], {"ok": True, "result": {"text": repeated}})
                self.assertIn(repeated, answer)
        with self.assertRaises(ValueError):
            fixtures.create_completion("does-not-exist")

    def test_custom_scaffold_is_explicitly_local_and_validates_inputs(self):
        from types import SimpleNamespace
        from pydantic import ValidationError

        _, files, load = self.generated("custom")
        manifest = json.loads(files["lesson.json"])
        self.assertFalse(manifest["runtime"]["requires_model"])
        self.assertEqual(manifest["runtime"]["entrypoint"], "runtime:run")
        runtime = load("runtime")
        inputs = runtime.INPUT_MODEL(label="自定义输入").model_dump()
        events = []
        context = SimpleNamespace(inputs=inputs, check_cancelled=lambda: None, locale="zh-CN",
                                  emit=lambda kind, data: events.append((kind, data)))
        self.assertEqual(runtime.run(context), "本地脚手架已执行：自定义输入")
        self.assertEqual(events[0][0], "lesson.step")
        with self.assertRaises(ValidationError):
            runtime.INPUT_MODEL(label="")

    def test_existing_directory_and_duplicate_manifest_preserve_files(self):
        target, files = build_scaffold(self.root, "task-card", "task_contract")
        write_scaffold(target, files)
        original = (target / "main.py").read_bytes()
        for slug in ("task_contract", "different_name"):
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                build_scaffold(self.root, "task-card", slug)
        with self.assertRaises(FileExistsError):
            write_scaffold(target, {"main.py": "overwritten"})
        self.assertEqual((target / "main.py").read_bytes(), original)
        self.assertFalse((self.root / "lessons" / "lesson_different_name").exists())

    def test_rejects_invalid_targets_before_any_write(self):
        for lesson_id, slug in [("tool-old", "available"), ("999", "missing"), ("../task-card", "bad"),
                                ("task-card", "../escape"), ("task-card", "UpperCase"), ("task-card", "trailing_"),
                                ("task-card", "with/slash"), ("04", "leading_zero")]:
            with self.subTest(lesson_id=lesson_id, slug=slug), self.assertRaises(ValueError):
                build_scaffold(self.root, lesson_id, slug)
        self.assertFalse((self.root / "lessons").exists())

    def test_slug_or_alias_resolve_to_one_slug_directory_and_manifest(self):
        by_slug, files = build_scaffold(self.root, "task-contract")
        by_alias, _ = build_scaffold(self.root, "task-card", "task-contract")
        self.assertEqual(by_slug, by_alias)
        self.assertEqual(by_slug.name, "lesson_task_contract")
        self.assertEqual(json.loads(files["lesson.json"])["id"], "task-contract")
        # 课号随目录顺序变化，生成的文件里不写死（否则新课一生成，“不写死课号”的测试就失败）。
        for name, text in files.items():
            with self.subTest(file=name):
                self.assertNotRegex(text, r"第 ?\d+ ?课")
        self.assertIn("`task-contract`", files["README.md"])
        with self.assertRaisesRegex(ValueError, "task-contract"):
            build_scaffold(self.root, "task-contract", "other_name")
        target, files = build_scaffold(self.root, "task-contract")
        write_scaffold(target, files)
        # 已有清单无论用 slug 还是别名再次生成都会被拒绝。
        for identifier in ("task-contract", "task-card"):
            with self.subTest(identifier=identifier), self.assertRaisesRegex(ValueError, "已有实现清单"):
                build_scaffold(self.root, identifier)

    def test_broken_existing_manifest_blocks_creation(self):
        existing = self.root / "lessons" / "lesson_05_bad"
        existing.mkdir(parents=True)
        (existing / "lesson.json").write_text("{invalid", encoding="utf-8")
        with redirect_stderr(io.StringIO()):
            result = main(["--root", str(self.root), "--id", "task-card", "--slug", "task_contract"])
        self.assertEqual(result, 1)
        self.assertFalse((self.root / "lessons" / "lesson_task_contract").exists())

    def test_generated_drafts_pass_registry_validation_without_unlocking(self):
        from scripts.validate_lessons import main as validate_main
        from server.catalog import load_lessons

        self.catalog["lessons"] = [{"id": "task-contract", "aliases": ["task-card"], "title": "任务契约", "status": "planned",
                                    "summary": "测试课程", "objectives": ["核对实际结果"]}]
        self.catalog_path.write_text(json.dumps(self.catalog, ensure_ascii=False), encoding="utf-8")
        for kind in ("native", "custom"):
            with self.subTest(kind=kind):
                kind_root = self.root / kind
                (kind_root / "curriculum").mkdir(parents=True)
                (kind_root / "curriculum" / "catalog.json").write_bytes(self.catalog_path.read_bytes())
                target, files = build_scaffold(kind_root, "task-card", "task_contract", kind)
                write_scaffold(target, files)
                self.assertEqual(load_lessons(root=kind_root), [])
                specs = load_lessons(root=kind_root, include_planned=True)
                self.assertEqual([item["id"] for item in specs], ["task-contract"])
                output = io.StringIO()
                with redirect_stdout(output):
                    result = validate_main(["--root", str(kind_root)])
                self.assertEqual(result, 0)
                self.assertIn("0 可用", output.getvalue())

    def test_validator_rejects_broken_draft_content_with_local_diagnostic(self):
        from scripts.validate_lessons import main as validate_main

        self.catalog["lessons"] = [{"id": "task-contract", "aliases": ["task-card"], "title": "任务契约", "status": "planned",
                                    "summary": "测试课程", "objectives": ["核对实际结果"]}]
        self.catalog_path.write_text(json.dumps(self.catalog, ensure_ascii=False), encoding="utf-8")
        target, files = build_scaffold(self.root, "task-card", "task_contract")
        content = json.loads(files["content.json"])
        content["quiz"][0]["correct_option"] = "missing-option"
        files["content.json"] = json.dumps(content, ensure_ascii=False)
        write_scaffold(target, files)
        output = io.StringIO()
        with redirect_stderr(output):
            result = validate_main(["--root", str(self.root)])
        self.assertEqual(result, 1)
        self.assertIn("lesson_task_contract", output.getvalue())


if __name__ == "__main__":
    unittest.main()
