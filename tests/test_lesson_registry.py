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

    def test_embedding_factory_is_validated_like_completion_factory(self):
        directory, baseline = self.course(custom=True)
        (directory / "fixtures.py").write_text(
            "def create_embedding(exercise_id, inputs=None, locale='zh-CN'):\n"
            "    return lambda body, api_key: {'data': []}\n", encoding="utf-8")
        # 只用 Embedding 的模型课可以只声明 embedding_factory。
        manifest = copy.deepcopy(baseline)
        manifest["runtime"]["requires_model"] = True
        manifest["testing"] = {"embedding_factory": "fixtures:create_embedding"}
        manifest["exercises"].append({"id": "local", "title": "本地", "question": "本地实验",
                                      "requires_model": False})
        self.write_json(directory / "lesson.json", manifest)
        spec = self.load()[0]
        self.assertEqual(spec["testing"], {"embedding_factory": "fixtures:create_embedding"})
        from server.catalog import exercise_requires_embedding
        shared, local = spec["exercises"]
        self.assertTrue(exercise_requires_embedding(spec, shared))
        self.assertFalse(exercise_requires_embedding(spec, local))
        for reference in ("os:system", "fixtures:bad-name", "../fixtures:create_embedding"):
            with self.subTest(reference=reference):
                broken = copy.deepcopy(manifest)
                broken["testing"]["embedding_factory"] = reference
                self.write_json(directory / "lesson.json", broken)
                with self.assertRaises(LessonValidationError):
                    self.load()
        for exercise_fields, testing in (({"requires_embedding": True}, {"completion_factory": "fixtures:create_completion"}),
                                         ({"requires_embedding": True, "requires_model": False}, manifest["testing"]),
                                         ({"requires_embedding": "yes"}, manifest["testing"])):
            with self.subTest(exercise=exercise_fields):
                broken = copy.deepcopy(manifest)
                broken["testing"] = testing
                broken["exercises"][0].update(exercise_fields)
                self.write_json(directory / "lesson.json", broken)
                with self.assertRaises(LessonValidationError):
                    self.load()
        broken = copy.deepcopy(manifest)
        broken["testing"] = {}
        self.write_json(directory / "lesson.json", broken)
        with self.assertRaisesRegex(LessonValidationError, "embedding_factory"):
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

    def test_runtime_locales_and_localized_presets(self):
        directory, manifest = self.course(custom=True)
        module = directory.name
        locales = directory / "locales"
        locales.mkdir()
        for name in ("__init__.py", "zh_CN.py", "en.py"):
            (locales / name).write_text("", encoding="utf-8")
        texts = [{"path": f"lessons/{module}/locales/zh_CN.py", "language": "python", "locale": "zh-CN"},
                 {"path": f"lessons/{module}/locales/en.py", "language": "python", "locale": "en"}]
        localized = {**manifest, "runtime": {**manifest["runtime"], "locales": ["en", "zh-CN"]},
                     "sources": manifest["sources"] + texts,
                     "exercises": [{**manifest["exercises"][0], "question": {"zh-CN": "执行实验", "en": "Run it"},
                                    "inputs": {"value": {"zh-CN": "预设", "en": "preset"}, "count": 3}}],
                     "input_defaults": {"label": {"zh-CN": "标签", "en": "label"}}}
        self.write_json(directory / "lesson.json", localized)
        spec = self.load()[0]
        # 平台顺序：源语言在前。spec 的练习与默认输入是源语言那份，每种语言另存一份。
        self.assertEqual(spec["runtime"]["locales"], ["zh-CN", "en"])
        self.assertEqual(spec["exercises"][0]["question"], "执行实验")
        self.assertEqual(spec["presets"]["en"]["exercises"][0]["inputs"], {"value": "preset", "count": 3})
        self.assertEqual(spec["presets"]["en"]["input_defaults"], {"label": "label"})
        bad = [
            # 缺源语言、未知语言、语言重复
            {"runtime": {**localized["runtime"], "locales": ["en"]}},
            {"runtime": {**localized["runtime"], "locales": ["zh-CN", "fr"]}},
            {"runtime": {**localized["runtime"], "locales": ["zh-CN", "zh-CN"]}},
            # 按语言填写时少一种语言；多语言课里含中文的预设没有分语言
            {"exercises": [{**localized["exercises"][0], "question": {"zh-CN": "执行实验"}}]},
            {"exercises": [{**localized["exercises"][0], "question": "执行实验"}]},
            {"input_defaults": {"label": "中文标签"}},
            {"input_defaults": {"label": {"zh-CN": {"nested": 1}, "en": "x"}}},
            # 语言文件不写 locale、写错 locale、只登记一种语言；普通文件不能写 locale
            {"sources": manifest["sources"] + [texts[0], {**texts[1], "locale": None}]},
            {"sources": manifest["sources"] + [texts[0], {**texts[1], "locale": "zh-CN"}]},
            {"sources": manifest["sources"] + texts[:1]},
            {"sources": [{**manifest["sources"][0], "locale": "en"}] + texts},
        ]
        for override in bad:
            with self.subTest(override=override):
                self.write_json(directory / "lesson.json", {**localized, **override})
                with self.assertRaises(LessonValidationError):
                    self.load()

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
