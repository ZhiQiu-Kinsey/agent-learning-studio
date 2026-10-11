"""运行语言：每课每个练习在它支持的每种运行语言下离线跑通，英文运行的事件里没有中文，消息目录逐字段对应。

离线测试模式：模型响应来自课程 fixture，工具照常真实执行。这是英文运行时的回归防线——
课程或平台在英文运行里漏出一句中文，这里就会指出是哪课、哪个练习、事件里的哪个位置。
"""
import importlib
import json
import pkgutil
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from course import i18n
from course.i18n import RUNTIME_LOCALES, SOURCE_LOCALE, cli_locale, parity_problems, resolve_locale
from run_support import run_and_read, web
from server.catalog import LESSONS, ROOT, lesson_presets, lesson_runtime
from server.run_store import RunStore

CJK = re.compile(r"[　-〿㐀-䶿一-鿿豈-﫿＀-￯]")


def cjk_paths(value, path="$"):
    """事件里含中文的位置（JSON 路径与前 40 个字），用于失败信息。"""
    if isinstance(value, str):
        return [f"{path}: {value[:40]}"] if CJK.search(value) else []
    if isinstance(value, dict):
        return [hit for key, item in value.items() for hit in cjk_paths(key, path + ".<key>") + cjk_paths(item, f"{path}.{key}")]
    if isinstance(value, list):
        return [hit for index, item in enumerate(value) for hit in cjk_paths(item, f"{path}[{index}]")]
    return []


def catalog_packages():
    """lessons/ 与 course/ 下所有运行时文本包（名为 locales 的包及其子包）。"""
    found = []
    for base in ("course", "lessons"):
        for module in pkgutil.walk_packages([str(ROOT / base)], base + "."):
            if module.ispkg and "locales" in module.name.split(".")[1:]:
                found.append(module.name)
    return sorted(found)


class ResolveLocaleTests(unittest.TestCase):
    def test_exact_then_same_language_then_source(self):
        both = ("zh-CN", "en")
        self.assertEqual(resolve_locale("en", both), "en")
        self.assertEqual(resolve_locale("en-US", both), "en")
        self.assertEqual(resolve_locale("zh", both), "zh-CN")
        self.assertEqual(resolve_locale("zh-TW", both), "zh-CN")
        self.assertEqual(resolve_locale("fr", both), SOURCE_LOCALE)
        self.assertEqual(resolve_locale(None, both), SOURCE_LOCALE)
        self.assertEqual(resolve_locale("en", ("zh-CN",)), SOURCE_LOCALE)
        with self.assertRaises(ValueError):
            resolve_locale("en", ("en",))

    def test_cli_flag(self):
        self.assertEqual(cli_locale([]), SOURCE_LOCALE)
        self.assertEqual(cli_locale(["--locale", "en"]), "en")
        self.assertEqual(cli_locale(["--locale=en"]), "en")
        with self.assertRaises(SystemExit):
            cli_locale(["--locale", "fr"])


class CatalogTests(unittest.TestCase):
    def test_every_catalog_has_the_source_locale_and_matching_fields(self):
        packages = catalog_packages()
        self.assertIn("course.locales", packages)
        for name in packages:
            package = importlib.import_module(name)
            with self.subTest(package=name):
                texts_for = package.texts_for
                locales = i18n.available_locales(name)
                self.assertIn(SOURCE_LOCALE, locales, "源语言的消息目录必须存在")
                source = texts_for(SOURCE_LOCALE)
                for locale in locales:
                    texts = texts_for(locale)
                    self.assertIsInstance(texts, package.Texts)
                    self.assertEqual(parity_problems(source, texts), [], f"{name} {locale}")
                    if locale == "en":
                        leaks = [path for path, value in i18n.leaves(texts) if isinstance(value, str) and CJK.search(value)]
                        self.assertEqual(leaks, [], f"{name}.en 里有中文")

    def test_missing_locale_falls_back_to_the_source_catalog(self):
        texts_for = i18n.catalog("course.locales", importlib.import_module("course.locales").Texts)
        self.assertIs(texts_for("en"), importlib.import_module("course.locales.en").TEXTS)
        dependent = i18n.catalog("lessons.lesson_chat_request.locales",
                                 importlib.import_module("lessons.lesson_chat_request.locales").Texts)
        self.assertIsNotNone(dependent("zh-CN"))
        with self.assertRaises(ValueError):
            texts_for("fr")

    def test_placeholders_must_match(self):
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class Texts:
            message: str
            items: tuple

        self.assertEqual(parity_problems(Texts("第 {round} 轮", ("a",)), Texts("Round {round}", ("b",))), [])
        problems = parity_problems(Texts("第 {round} 轮", ("a",)), Texts("Round {number}", ("b", "c")))
        self.assertTrue(any("placeholders" in item for item in problems))
        self.assertTrue(any("unexpected" in item for item in problems))


class LocalizedLessonTests(unittest.TestCase):
    """每课 × 每个练习 × 本课的每种运行语言，经 runs 接口离线跑通。"""

    @classmethod
    def setUpClass(cls):
        cls._directory = tempfile.TemporaryDirectory()
        cls._previous = web.run_store
        cls._store = RunStore(Path(cls._directory.name) / "runs.sqlite3")
        web.run_store = cls._store
        cls.client = TestClient(web.app, base_url="http://localhost")
        cls.runs = {}
        for spec in LESSONS:
            for locale in spec["runtime"]["locales"]:
                exercises, _ = lesson_presets(spec, locale)
                for exercise in exercises:
                    body = {"lesson_id": spec["id"], "mode": "offline", "question": exercise["question"],
                            "exercise_id": exercise["id"], "locale": locale}
                    cls.runs[(spec["id"], exercise["id"], locale)] = run_and_read(cls.client, body)

    @classmethod
    def tearDownClass(cls):
        web.run_store = cls._previous
        cls._store.close()
        cls._directory.cleanup()

    def test_every_exercise_runs_in_every_runtime_locale(self):
        for (lesson, exercise, locale), result in self.runs.items():
            with self.subTest(lesson=lesson, exercise=exercise, locale=locale):
                self.assertEqual(result.status_code, 202, result.text)
                self.assertEqual(result.events[-1]["type"], "done")
                self.assertEqual(result.events[-1]["data"]["status"], "completed", json.dumps(
                    [event["data"] for event in result.events if event["type"] == "error"], ensure_ascii=False))
                start = result.events[0]
                self.assertEqual((start["type"], start["data"]["locale"]), ("run_start", locale))
                self.assertNotIn("requested_locale", start["data"])
                self.assertEqual(self._store.get_run(result.run_id)["locale"], locale)

    def test_english_runs_contain_no_chinese(self):
        english = [(key, result) for key, result in self.runs.items() if key[2] == "en"]
        self.assertTrue(english, "至少要有一课支持英文运行")
        for (lesson, exercise, _), result in english:
            with self.subTest(lesson=lesson, exercise=exercise):
                self.assertEqual(cjk_paths(result.events), [])

    def test_chinese_runs_stay_chinese(self):
        for (lesson, exercise, locale), result in self.runs.items():
            if locale == "zh-CN" and lesson in ("chat-request", "tool-selection"):
                with self.subTest(lesson=lesson, exercise=exercise):
                    request = next(event for event in result.events if event["type"] == "request")
                    self.assertTrue(CJK.search(json.dumps(request["data"]["body"]["messages"], ensure_ascii=False)))

    def test_input_schemas_of_english_lessons_have_no_chinese_defaults(self):
        # 自然语言输入不设中文默认值：预设按语言写在 lesson.json 里，英文界面的参数控件也不会露出中文。
        for spec in LESSONS:
            if "en" not in spec["runtime"]["locales"]:
                continue
            model = getattr(lesson_runtime(spec), "INPUT_MODEL", None)
            if model is not None:
                with self.subTest(lesson=spec["id"]):
                    self.assertEqual(cjk_paths(model.model_json_schema()), [])


class LocaleApiTests(unittest.TestCase):
    def setUp(self):
        from run_support import use_temporary_run_store

        self.store = use_temporary_run_store(self)
        self.client = TestClient(web.app, base_url="http://localhost")

    def test_detail_and_code_follow_the_runtime_locale(self):
        english = self.client.get("/api/lessons/chat-request?lang=en").json()
        self.assertEqual((english["runtime_locale"], english["runtime_locales"]), ("en", ["zh-CN", "en"]))
        self.assertEqual(english["exercises"][0]["question"], "Explain in one sentence what an agent is.")
        self.assertFalse(CJK.search(english["exercises"][0]["inputs"]["system_prompt"]))
        paths = [source["path"] for source in english["sources"]]
        self.assertIn("lessons/lesson_chat_request/locales/en.py", paths)
        self.assertNotIn("lessons/lesson_chat_request/locales/zh_CN.py", paths)
        chinese = self.client.get("/api/lessons/chat-request").json()
        self.assertEqual(chinese["runtime_locale"], "zh-CN")
        self.assertEqual(chinese["exercises"][0]["question"], "用一句话解释什么是 Agent。")
        tools = self.client.get("/api/lessons/tool-selection?lang=en").json()
        self.assertEqual(cjk_paths([tools["system_prompt"], tools["tools"]]), [])
        code = self.client.get("/api/lessons/tool-selection/code?lang=en").json()
        self.assertEqual(code["runtime_locale"], "en")
        self.assertIn("lessons/lesson_01_tool_selection/locales/tools/en.py", [f["path"] for f in code["files"]])
        # 本课还没有英文运行时：英文界面拿到的问题、源码和运行都是中文，并写明运行语言。
        pending = self.client.get("/api/lessons/dependent-calls?lang=en").json()
        self.assertEqual(pending["runtime_locale"], "zh-CN")
        self.assertTrue(CJK.search(pending["exercises"][0]["question"]))

    def test_unsupported_locale_falls_back_and_records_the_request(self):
        detail = self.client.get("/api/lessons/dependent-calls?lang=en").json()
        exercise = detail["exercises"][0]
        result = run_and_read(self.client, {"lesson_id": "dependent-calls", "mode": "offline",
                                            "question": exercise["question"], "exercise_id": exercise["id"],
                                            "locale": "en"})
        start = result.events[0]["data"]
        self.assertEqual((start["locale"], start["requested_locale"]), ("zh-CN", "en"))
        listed = self.client.get("/api/runs").json()["runs"][0]
        self.assertEqual((listed["run_id"], listed["locale"]), (result.run_id, "zh-CN"))
        # 地区变体按同一语言处理。
        result = run_and_read(self.client, {"lesson_id": "chat-request", "mode": "offline",
                                            "question": "Explain in one sentence what an agent is.",
                                            "exercise_id": "basic", "locale": "en-US"})
        self.assertEqual((result.events[0]["data"]["locale"], result.events[0]["data"]["requested_locale"]),
                         ("en", "en-US"))

    def test_offline_preset_must_match_the_run_locale_and_locale_must_be_well_formed(self):
        mismatch = self.client.post("/api/runs", json={"lesson_id": "chat-request", "mode": "offline",
                                                       "question": "用一句话解释什么是 Agent。",
                                                       "exercise_id": "basic", "locale": "en"})
        self.assertEqual(mismatch.json()["code"], "offline_requires_preset")
        for bad in ("english", "EN", "en_US", "x" * 40):
            response = self.client.post("/api/runs", json={"lesson_id": "chat-request", "mode": "offline",
                                                           "question": "q", "exercise_id": "basic", "locale": bad})
            self.assertEqual((response.status_code, response.json()["code"]), (422, "invalid_request"), bad)

    def test_old_run_store_gets_a_locale_column(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.sqlite3"
            connection = sqlite3.connect(path)
            connection.executescript("""
                CREATE TABLE runs (run_id TEXT PRIMARY KEY, lesson_id TEXT NOT NULL, exercise_id TEXT NOT NULL,
                    mode TEXT NOT NULL, model TEXT NOT NULL, provider_id TEXT NOT NULL, representation TEXT,
                    provenance TEXT NOT NULL, schema_version INTEGER NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, finished_at TEXT);
                INSERT INTO runs VALUES ('a', 'chat-request', 'basic', 'live', 'm', 'bailian', 'http_body',
                    'real_run', 2, 'completed', '2026-10-01T00:00:00+00:00', NULL);""")
            connection.commit()
            connection.close()
            store = RunStore(path)
            try:
                self.assertEqual(store.get_run("a")["locale"], "zh-CN")
            finally:
                store.close()


class FixtureContractTests(unittest.TestCase):
    def test_lessons_with_more_than_one_locale_accept_locale_in_their_fixture(self):
        import inspect

        from server.catalog import lesson_callable

        for spec in LESSONS:
            if len(spec["runtime"]["locales"]) > 1 and spec["testing"].get("completion_factory"):
                with self.subTest(lesson=spec["id"]):
                    factory = lesson_callable(spec, spec["testing"]["completion_factory"])
                    self.assertIn("locale", inspect.signature(factory).parameters)

    def test_runtime_locales_are_known(self):
        for spec in LESSONS:
            self.assertEqual(spec["runtime"]["locales"][0], SOURCE_LOCALE)
            self.assertTrue(set(spec["runtime"]["locales"]) <= set(RUNTIME_LOCALES))


if __name__ == "__main__":
    unittest.main()
