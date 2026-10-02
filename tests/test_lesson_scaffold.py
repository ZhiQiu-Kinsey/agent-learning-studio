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

    def test_native_scaffold_runs_real_tool_with_its_own_fixture(self):
        from course.runner import run_agent

        target, files = build_scaffold(self.root, "task-card", "task_contract")
        write_scaffold(target, files)
        manifest = json.loads((target / "lesson.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["runtime"]["kind"], "native")
        self.assertEqual(manifest["testing"]["completion_factory"], "fixtures:create_completion")
        self.assertEqual(json.loads(self.catalog_path.read_text(encoding="utf-8")), self.catalog)
        tools = {}
        fixture = {}
        exec(compile(files["tools.py"], "tools.py", "exec"), tools)
        exec(compile(files["fixtures.py"], "fixtures.py", "exec"), fixture)
        events = []
        answer = run_agent(
            question="请复述：课程脚手架。", api_key="", model="offline-script",
            system_prompt="复述", tools=tools["TOOLS"], available_tools=tools["AVAILABLE_TOOLS"],
            max_tool_rounds=3, completion=fixture["create_completion"]("starter"),
            emit=lambda kind, data, number: events.append((kind, data)), quiet=True,
        )
        result = next(data for kind, data in events if kind == "tool_result")
        self.assertEqual(result["result"], {"ok": True, "result": {"text": "课程脚手架"}})
        self.assertIn("课程脚手架", answer)
        with self.assertRaises(ValueError):
            fixture["create_completion"]("does-not-exist")

    def test_custom_scaffold_is_explicitly_local_and_validates_inputs(self):
        from types import SimpleNamespace
        from pydantic import ValidationError

        _, files = build_scaffold(self.root, "task-card", "task_contract", "custom")
        manifest = json.loads(files["lesson.json"])
        self.assertFalse(manifest["runtime"]["requires_model"])
        self.assertEqual(manifest["runtime"]["entrypoint"], "runtime:run")
        namespace = {}
        exec(compile(files["runtime.py"], "runtime.py", "exec"), namespace)
        inputs = namespace["INPUT_MODEL"](label="自定义输入").model_dump()
        events = []
        context = SimpleNamespace(inputs=inputs, check_cancelled=lambda: None,
                                  emit=lambda kind, data: events.append((kind, data)))
        self.assertEqual(namespace["run"](context), "本地脚手架已执行：自定义输入")
        self.assertEqual(events[0][0], "lesson.step")
        with self.assertRaises(ValidationError):
            namespace["INPUT_MODEL"](label="")

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
        self.assertIn("第 2 课", files["README.md"])
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
