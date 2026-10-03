"""课程扩展的注册、资源边界和同名测试样本隔离。测试课程只写入临时目录。"""
import copy
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lessons
from server.catalog import LessonValidationError, lesson_detail, load_lessons, public_lesson
from server.offline import completion_for


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-lesson-registry-")
        self.root = Path(self.temporary.name)
        self.catalog = {"lessons": []}

    def tearDown(self):
        for name in list(sys.modules):
            if name.startswith("lessons.lesson_registry_"):
                del sys.modules[name]
        self.temporary.cleanup()

    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def course(self, identifier="one", status="available", custom=False):
        module = "lesson_registry_" + identifier
        directory = self.root / "lessons" / module
        directory.mkdir(parents=True)
        (directory / "__init__.py").write_text("", encoding="utf-8")
        (directory / "main.py").write_text("SYSTEM_PROMPT = 'test'\nTOOLS = []\n", encoding="utf-8")
        (directory / "runtime.py").write_text("def run(context):\n    return None\n", encoding="utf-8")
        (directory / "fixtures.py").write_text(
            "from server.offline import CompletionScript\n"
            "def create_completion(exercise_id, inputs=None):\n"
            f"    return CompletionScript(lambda results: {{'content': '{identifier}:' + str(inputs.get('value', ''))}})\n",
            encoding="utf-8")
        learning = {
            "sections": [{"title": "讲解", "body": "原理说明"}], "observe": ["检查事件"],
            "quiz": [{"id": "q", "prompt": "问题", "explanation": "答案依据", "correct_option": "yes",
                      "options": [{"id": "yes", "text": "正确"}, {"id": "no", "text": "错误"}]}],
        }
        self.write_json(directory / "content.json", learning)
        manifest = {
            "schema_version": 1, "id": identifier, "subtitle": "教学副标题", "content": "content.json",
            "sources": [{"path": f"lessons/{module}/main.py", "language": "python"}],
            "exercises": [{"id": "shared", "title": "实验", "question": "执行实验"}],
            "runtime": {"kind": "custom" if custom else "native", "entrypoint": "runtime:run" if custom else "main",
                        "requires_model": not custom},
            "testing": {"completion_factory": "fixtures:create_completion"},
        }
        self.write_json(directory / "lesson.json", manifest)
        self.catalog["lessons"].append({"id": identifier, "title": "目录标题 " + identifier,
                                        "summary": "目录说明", "objectives": ["目录目标"], "status": status})
        return directory, manifest

    def load(self, **kwargs):
        return load_lessons(self.root, self.catalog, **kwargs)

    def test_registration_uses_catalog_order_and_metadata_without_importing_runtime(self):
        self.course("one")
        self.course("two")
        self.catalog["lessons"].reverse()
        with patch("server.catalog.import_module", side_effect=AssertionError("discovery must not execute code")):
            result = self.load()
        self.assertEqual([spec["id"] for spec in result], ["two", "one"])
        self.assertEqual(result[0]["title"], "目录标题 two")
        self.assertEqual(result[0]["description"], "目录说明")
        self.assertEqual(result[0]["objectives"], ["目录目标"])
        self.assertEqual(result[0]["runtime"]["max_rounds"], 3)
        public = public_lesson(result[0])
        self.assertFalse({"root", "package", "module", "runtime", "testing", "sources", "content_path"} & set(public))
        json.dumps(public)

    def test_planned_manifest_is_validated_but_not_unlocked(self):
        directory, manifest = self.course(status="planned")
        self.assertEqual(self.load(), [])
        draft = self.load(include_planned=True)[0]
        self.assertFalse(draft["available"])
        self.assertEqual(draft["status"], "planned")
        manifest["schema_version"] = 999
        self.write_json(directory / "lesson.json", manifest)
        with self.assertRaisesRegex(LessonValidationError, "schema_version"):
            self.load()

    def test_available_without_manifest_fails_with_course_id(self):
        directory, _ = self.course()
        (directory / "lesson.json").unlink()
        with self.assertRaisesRegex(LessonValidationError, "one.*available.*lesson.json"):
            self.load()

    def test_unknown_duplicate_manifest_and_duplicate_catalog_id_are_rejected(self):
        first, manifest = self.course()
        manifest["id"] = "unregistered"
        self.write_json(first / "lesson.json", manifest)
        with self.assertRaisesRegex(LessonValidationError, "未登记"):
            self.load()
        manifest["id"] = "one"
        self.write_json(first / "lesson.json", manifest)
        second, duplicate = self.course("two")
        duplicate["id"] = "one"
        self.write_json(second / "lesson.json", duplicate)
        with self.assertRaisesRegex(LessonValidationError, "实现 id 重复"):
            self.load()
        (second / "lesson.json").unlink()
        self.catalog["lessons"] = [self.catalog["lessons"][0]] * 2
        with self.assertRaisesRegex(LessonValidationError, "课程 id 不能重复"):
            self.load()

    def test_manifest_must_use_slug_and_spec_carries_number_and_aliases(self):
        first, manifest = self.course("one")
        self.course("two")
        self.catalog["lessons"][0]["aliases"] = ["one-old"]
        self.catalog["lessons"][1]["aliases"] = ["two-old", "old-two"]
        one, two = self.load()
        self.assertEqual((one["id"], one["number"], one["aliases"]), ("one", 1, ["one-old"]))
        self.assertEqual((two["number"], two["aliases"]), (2, ["two-old", "old-two"]))
        self.assertEqual({key: public_lesson(two)[key] for key in ("id", "number", "aliases")},
                         {"id": "two", "number": 2, "aliases": ["two-old", "old-two"]})
        manifest["id"] = "one-old"
        self.write_json(first / "lesson.json", manifest)
        with self.assertRaisesRegex(LessonValidationError, "slug「one」"):
            self.load()

    def test_invalid_manifest_schema_and_metadata_drift_are_rejected(self):
        directory, baseline = self.course()
        cases = [
            {"schema_version": True}, {"title": "重复的课程标题"}, {"exercises": []},
            {"exercises": baseline["exercises"] * 2}, {"sources": baseline["sources"] * 2},
            {"runtime": {"kind": "native", "entrypoint": "main", "max_rounds": True}},
            {"runtime": {"kind": "native", "entrypoint": "main", "requires_model": False}},
            {"testing": {}}, {"ui": {"unknown": "custom"}}, {"input_defaults": []},
            # 只有 custom 运行器能让单个练习不调用模型；值必须是布尔。
            {"exercises": [{**baseline["exercises"][0], "requires_model": False}]},
            {"exercises": [{**baseline["exercises"][0], "requires_model": "no"}]},
        ]
        for override in cases:
            with self.subTest(override=override):
                self.write_json(directory / "lesson.json", {**baseline, **override})
                with self.assertRaises(LessonValidationError):
                    self.load()

    def test_content_must_belong_to_own_course_and_quiz_answers_must_exist(self):
        directory, manifest = self.course()
        other, _ = self.course("two")
        for path in ("../" + other.name + "/content.json", "C:/private/content.json", "missing.json"):
            with self.subTest(path=path):
                self.write_json(directory / "lesson.json", {**manifest, "content": path})
                with self.assertRaises(LessonValidationError):
                    self.load()
        self.write_json(directory / "lesson.json", manifest)
        learning = json.loads((directory / "content.json").read_text(encoding="utf-8"))
        learning["quiz"][0]["correct_option"] = "missing"
        self.write_json(directory / "content.json", learning)
        with self.assertRaisesRegex(LessonValidationError, "content.json.*correct"):
            self.load()

    def test_source_paths_reject_private_files_and_escaping_paths(self):
        directory, manifest = self.course()
        for name in ("local_config.py", "secrets.json", ".env", ".venv/value.py"):
            file = directory / name
            file.parent.mkdir(exist_ok=True)
            file.write_text("private", encoding="utf-8")
        paths = ["local_config.py", "../outside.py", "C:/private.py", "course\\runner.py",
                 f"lessons/{directory.name}/missing.py"]
        paths.extend(f"lessons/{directory.name}/{name}" for name in ("local_config.py", "secrets.json", ".env", ".venv/value.py"))
        for path in paths:
            with self.subTest(path=path):
                self.write_json(directory / "lesson.json", {**manifest, "sources": [{"path": path, "language": "python"}]})
                with self.assertRaises(LessonValidationError):
                    self.load()

    def test_symlinks_cannot_escape_source_boundary(self):
        directory, manifest = self.course()
        outside = self.root / "private.py"
        outside.write_text("private", encoding="utf-8")
        linked = directory / "linked.py"
        try:
            linked.symlink_to(outside)
        except OSError as error:
            self.skipTest("当前 Windows 账户无法创建测试符号链接: " + str(error))
        manifest["sources"] = [{"path": f"lessons/{directory.name}/linked.py", "language": "python"}]
        self.write_json(directory / "lesson.json", manifest)
        with self.assertRaisesRegex(LessonValidationError, "超出允许目录"):
            self.load()

    def test_entrypoints_and_factories_are_restricted_to_course_modules(self):
        directory, baseline = self.course()
        for reference in ("os:system", "../fixtures:create_completion", "fixtures:create_completion:extra", "fixtures:bad-name"):
            with self.subTest(reference=reference):
                manifest = copy.deepcopy(baseline)
                manifest["testing"]["completion_factory"] = reference
                self.write_json(directory / "lesson.json", manifest)
                with self.assertRaises(LessonValidationError):
                    self.load()
        manifest = copy.deepcopy(baseline)
        manifest["runtime"]["entrypoint"] = "main:run"
        self.write_json(directory / "lesson.json", manifest)
        with self.assertRaisesRegex(LessonValidationError, "本课模块"):
            self.load()

    def test_custom_detail_has_optional_native_tools_and_local_runtime_needs_no_fixture(self):
        directory, manifest = self.course(custom=True)
        del manifest["testing"]
        manifest["input_defaults"] = {"value": "default"}
        manifest["exercises"][0]["inputs"] = {"value": "preset"}
        manifest["ui"] = {"lab": "structured-inputs"}
        (directory / "runtime.py").write_text(
            "from course.execution import LessonInputs\n"
            "class Inputs(LessonInputs):\n    value: str = 'model-default'\n    count: int = 2\n"
            "INPUT_MODEL = Inputs\n"
            "def run(context):\n    return 'done'\n", encoding="utf-8")
        self.write_json(directory / "lesson.json", manifest)
        spec = self.load()[0]
        with patch.object(lessons, "__path__", [str(self.root / "lessons")]):
            importlib.invalidate_caches()
            detail = lesson_detail(spec)
        self.assertEqual(detail["tools"], [])
        self.assertEqual(detail["system_prompt"], "")
        self.assertTrue(detail["capabilities"]["custom_runtime"])
        self.assertTrue(detail["capabilities"]["supports_inputs"])
        self.assertFalse(detail["capabilities"]["requires_model"])
        self.assertEqual(detail["input_defaults"], {"value": "default"})
        self.assertEqual(detail["exercises"][0]["inputs"], {"value": "preset", "count": 2})
        self.assertEqual(spec["exercises"][0]["inputs"], {"value": "preset"})

    def test_identical_exercise_ids_resolve_their_own_course_factory(self):
        self.course("one")
        self.course("two")
        first, second = self.load()
        with patch.object(lessons, "__path__", [str(self.root / "lessons")]):
            importlib.invalidate_caches()
            one = completion_for(first, "shared", {"value": "alpha"})
            two = completion_for(second, "shared", {"value": "beta"})
        self.assertEqual(one({"messages": []}, "")["choices"][0]["message"]["content"], "one:alpha")
        self.assertEqual(two({"messages": []}, "")["choices"][0]["message"]["content"], "two:beta")
        self.assertEqual(one.calls, 1)
        self.assertEqual(two.calls, 1)
        with self.assertRaisesRegex(ValueError, "未声明"):
            completion_for(first, "another-course-only")


if __name__ == "__main__":
    unittest.main()
