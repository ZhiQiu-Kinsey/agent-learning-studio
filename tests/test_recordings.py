"""随课录制（recorded_run）的导出、校验与只读接口。

全部使用临时课程目录与临时运行存储；存储中的 mode=live 运行由 EnvelopeBuilder 按平台
信封规则构造，只用于检验录制格式，从不请求真实模型，也不向仓库写入任何录制文件。
"""
import importlib
import json
import os
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from run_support import use_temporary_run_store
from server.catalog import load_lessons
from server.envelope import SCHEMA_VERSION, EnvelopeBuilder
from server.recordings import (ExportRefused, RecordingInvalid, RecordingStale, export_run, find_sensitive,
                               integrity_hash, load_document, source_files, source_hash, valid_name,
                               validate_document, validate_lesson_recordings)
from server.run_store import RunStore, utc_now

web = importlib.import_module("server.app")

SLUG = "rec-demo"
MODULE = "lesson_rec_demo"
LITELLM = {"name": "litellm", "version": "1.103.0"}
LABELS = {"bailian": "百炼（原生 HTTP）", "openai": "OpenAI"}


class RecordingTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-recordings-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.write_lesson()
        self.spec = self.load_spec()
        self.store = RunStore(self.root / ".runtime" / "runs.sqlite3")
        self.addCleanup(lambda: self.store.close())

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_lesson(self):
        directory = f"lessons/{MODULE}"
        self.write(f"{directory}/__init__.py", "")
        self.write(f"{directory}/main.py", "SYSTEM_PROMPT = 'test'\nTOOLS = []\n")
        self.write(f"{directory}/tools.py", "def add(a, b):\n    return a + b\n")
        self.write(f"{directory}/fixtures.py", "def create_completion(exercise_id, inputs=None):\n    return None\n")
        self.write(f"{directory}/content.json", json.dumps({
            "sections": [{"title": "讲解", "body": "原理"}], "observe": ["观察"],
            "quiz": [{"id": "q", "prompt": "问题", "explanation": "依据", "correct_option": "a",
                      "options": [{"id": "a", "text": "对"}, {"id": "b", "text": "错"}]}]}, ensure_ascii=False))
        self.write(f"{directory}/lesson.json", json.dumps({
            "schema_version": 1, "id": SLUG, "content": "content.json",
            "sources": [{"path": f"{directory}/tools.py", "language": "python"},
                        {"path": f"{directory}/main.py", "language": "python"}],
            "exercises": [{"id": "sum", "title": "加法", "question": "19+23"}],
            "runtime": {"kind": "native", "entrypoint": "main", "requires_model": True},
            "testing": {"completion_factory": "fixtures:create_completion"}}, ensure_ascii=False))
        self.catalog = {"lessons": [{"id": SLUG, "aliases": ["r1"], "title": "录制演示", "summary": "说明",
                                     "objectives": ["目标"], "status": "available"}]}
        # 让源码修改时间明显早于运行创建时间。
        past = time.time() - 60
        for path in (self.root / directory).iterdir():
            os.utime(path, (past, past))

    def load_spec(self):
        return load_lessons(self.root, self.catalog, include_planned=True)[0]

    def make_run(self, *, mode="live", status="completed", provider="bailian", extra=None, finish=True,
                 locale="zh-CN"):
        """按平台信封规则写入一次运行；只用于测试录制格式。"""
        representation = "http_body" if provider == "bailian" else "sdk_standardized"
        sdk = None if provider == "bailian" else dict(LITELLM)
        if mode == "offline":
            provider, sdk = "testing", {"name": "deterministic-test-adapter", "version": None}
            representation = "sdk_standardized"
        run_id = uuid.uuid4().hex
        builder = EnvelopeBuilder(run_id, provenance="real_run", representation=representation, sdk=sdk)
        self.store.create_run(run_id=run_id, lesson_id=SLUG, exercise_id="sum", mode=mode, model="demo-model",
                              provider_id=provider, representation=representation, provenance="real_run",
                              schema_version=SCHEMA_VERSION, created_at=utc_now(), locale=locale)
        body = {"model": "demo-model", "messages": [{"role": "user", "content": "19+23"}]}
        call = {"id": "call-1", "type": "function", "function": {"name": "add", "arguments": "{\"a\":19,\"b\":23}"}}
        events = [
            ("run_start", {"lesson_id": SLUG, "mode": mode, "model": "demo-model", "question": "19+23",
                           "inputs": {}, "runtime_kind": "native", "provider_id": provider,
                           "provider_label": LABELS.get(provider, "确定性测试"),
                           "trace_representation": representation, "locale": locale}, None),
            ("request", {"body": body, "representation": representation}, 1),
            ("response", {"body": {"choices": [{"message": {"role": "assistant", "tool_calls": [call]}}]},
                          "representation": representation}, 1),
            ("tool_call", {"id": "call-1", "name": "add", "arguments": {"a": 19, "b": 23}}, 1),
            ("tool_result", {"tool_call_id": "call-1", "name": "add", "result": 42, **(extra or {})}, 1),
            ("answer", {"content": "42"}, 2),
        ]
        for kind, data, number in events:
            event = builder.build(kind, data, number, utc_now())
            self.store.append(run_id, event["seq"], kind, json.dumps(event, ensure_ascii=False))
        if finish:
            done = builder.build("done", {"status": status, "duration_ms": 12}, None, utc_now())
            self.store.finish(run_id, done["seq"], "done", json.dumps(done, ensure_ascii=False), status, utc_now())
        return run_id

    def export(self, run_id, name="demo-run", **kwargs):
        return export_run(self.store.path, run_id, name, root=self.root, specs=[self.spec], **kwargs)

    def stored_events(self, run_id):
        return [json.loads(text) for _, _, text in self.store.events(run_id)]

    def rewrite(self, path, mutate, rehash=True):
        document = load_document(path)
        mutate(document)
        if rehash:
            document["metadata"]["integrity_hash"] = integrity_hash(document["events"])
            document["metadata"]["event_count"] = len(document["events"])
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return document

    def assert_invalid(self, document, location=None, **kwargs):
        with self.assertRaises(RecordingInvalid) as caught:
            validate_document(document, self.spec, **kwargs)
        if location is not None:
            self.assertEqual(caught.exception.location, location)
        return caught.exception


class ExportTests(RecordingTestCase):
    def test_export_refuses_offline_cancelled_interrupted_and_running_runs(self):
        refused = {"offline": self.make_run(mode="offline"), "cancelled": self.make_run(status="cancelled")}
        running = self.make_run(finish=False)
        for label, run_id in refused.items():
            with self.subTest(label), self.assertRaises(ExportRefused):
                self.export(run_id, name=label)
        with self.assertRaisesRegex(ExportRefused, "running"):
            self.export(running, name="running")
        self.store.close()
        self.store = RunStore(self.store.path)  # 重新打开时遗留的 running 被标为 interrupted。
        self.assertEqual(self.store.get_run(running)["status"], "interrupted")
        with self.assertRaisesRegex(ExportRefused, "interrupted"):
            self.export(running, name="interrupted")
        self.assertFalse((self.root / "lessons" / MODULE / "recordings").exists())
        # 失败（error）的真实运行可以导出，如实保留状态。
        failed = self.export(self.make_run(status="error"), name="failed-run")
        self.assertEqual(load_document(failed)["metadata"]["status"], "error")

    def test_recording_carries_the_run_locale_and_it_must_be_supported(self):
        # 录制元数据记下运行语言，与 run_start 一致；本课只支持 zh-CN 时，英文运行的录制不能通过校验。
        run_id = self.make_run(locale="en")
        with self.assertRaisesRegex(ExportRefused, "metadata.locale"):
            self.export(run_id)

    def test_export_changes_only_provenance_and_records_metadata(self):
        run_id = self.make_run()
        target = self.export(run_id)
        self.assertEqual(target, self.root / "lessons" / MODULE / "recordings" / "demo-run.json")
        document = load_document(target)
        stored = self.stored_events(run_id)
        self.assertEqual(len(document["events"]), len(stored))
        for original, recorded in zip(stored, document["events"]):
            self.assertEqual(original["provenance"], "real_run")
            self.assertEqual(recorded["provenance"], "recorded_run")
            self.assertEqual(list(recorded), list(original), "字段与顺序不变")
            self.assertEqual({**recorded, "provenance": "real_run"}, original)
        metadata = document["metadata"]
        self.assertEqual({key: metadata[key] for key in ("schema_version", "lesson", "exercise_id", "run_id", "status",
                                                         "model", "provider_id", "provider_label", "representation",
                                                         "sdk", "event_count", "locale")},
                         {"schema_version": 2, "lesson": SLUG, "exercise_id": "sum", "run_id": run_id,
                          "status": "completed", "model": "demo-model", "provider_id": "bailian",
                          "provider_label": LABELS["bailian"], "representation": "http_body", "sdk": None,
                          "event_count": len(stored), "locale": "zh-CN"})
        self.assertEqual(metadata["recorded_at"], self.store.get_run(run_id)["created_at"])
        self.assertEqual(metadata["source_hash"], source_hash(self.spec))
        self.assertEqual(metadata["integrity_hash"], integrity_hash(document["events"]))
        self.assertTrue(metadata["platform_version"])
        self.assertEqual(validate_document(document, self.spec), metadata)
        self.assertEqual(validate_lesson_recordings(self.root, [self.spec]), (1, []))
        with self.assertRaisesRegex(ExportRefused, "--replace"):
            self.export(run_id)
        self.export(run_id, replace=True)
        for name in ("Demo", "demo_run", "-demo", "../demo", "a" * 65):
            self.assertFalse(valid_name(name), name)
            with self.assertRaises(ExportRefused):
                self.export(run_id, name=name)

    def test_sdk_run_exports_with_sdk_name_and_version(self):
        document = load_document(self.export(self.make_run(provider="openai"), name="sdk-run"))
        self.assertEqual((document["metadata"]["representation"], document["metadata"]["sdk"]),
                         ("sdk_standardized", LITELLM))
        models = [e for e in document["events"] if e["type"] in ("request", "response")]
        self.assertTrue(models)
        self.assertTrue(all(e["representation"] == "sdk_standardized" and e["sdk"] == LITELLM for e in models))

    def test_source_hash_rule_and_source_modified_after_run(self):
        self.assertEqual(source_files(self.spec), [f"lessons/{MODULE}/lesson.json", f"lessons/{MODULE}/main.py",
                                                   f"lessons/{MODULE}/tools.py"])
        before = source_hash(self.spec)
        path = self.root / "lessons" / MODULE / "tools.py"
        lf = path.read_bytes().replace(b"\r\n", b"\n")
        path.write_bytes(lf)
        self.assertEqual(source_hash(self.spec), before)
        path.write_bytes(lf.replace(b"\n", b"\r\n"))
        self.assertEqual(source_hash(self.spec), before, "换行符差异不影响源码哈希")
        run_id = self.make_run()
        future = time.time() + 60
        os.utime(path, (future, future))
        with self.assertRaisesRegex(ExportRefused, "之后被修改"):
            self.export(run_id)

    def test_export_refuses_secrets_and_private_paths_without_echoing_them(self):
        cases = {
            "sk-prefix": ({"note": "sk-abcdefghijklmnopqrstuvwx"}, (), "sk-abcdefghijklmnopqrstuvwx"),
            "configured": ({"note": "echo configured-secret-123456"}, ("configured-secret-123456",),
                           "configured-secret-123456"),
            "windows-home": ({"note": r"C:\Users\alice\project\notes.txt"}, (), "alice"),
            "posix-home": ({"note": "/home/alice/project"}, (), "alice"),
            "auth-field": ({"headers": {"Authorization": "Bearer abc"}}, (), "Bearer abc"),
            "api-key-field": ({"api_key": "short"}, (), "short"),
        }
        for label, (extra, keys, secret) in cases.items():
            with self.subTest(label):
                run_id = self.make_run(extra=extra)
                with self.assertRaises(ExportRefused) as caught:
                    self.export(run_id, name=label, keys=keys)
                message = str(caught.exception)
                self.assertIn("events[4].data.", message)
                self.assertNotIn(secret, message)
        self.assertFalse((self.root / "lessons" / MODULE / "recordings").exists())
        self.assertEqual(find_sensitive({"text": "[REDACTED] 与 task-list、/api/home/x"}, ()), [])


class ValidationTests(RecordingTestCase):
    def setUp(self):
        super().setUp()
        self.path = self.export(self.make_run())

    def test_tampered_events_are_detected(self):
        document = load_document(self.path)
        document["events"][4]["data"]["result"] = 43
        self.assert_invalid(document, "metadata.integrity_hash")
        document = load_document(self.path)
        document["events"].pop(3)
        document["metadata"]["event_count"] -= 1
        self.assert_invalid(document, "metadata.integrity_hash")
        # 即使重算了完整性哈希，seq、span 与来源仍按信封 v2 规则重放检查。
        mutations = {
            "events[2]": lambda d: d["events"][2].update(seq=9),
            "events[3]": lambda d: d["events"][3].update(span_id="tool-9"),
            "events[1].provenance": lambda d: d["events"][1].update(provenance="real_run"),
            "events[5]": lambda d: d["events"].insert(5, dict(d["events"][4])),
        }
        original = self.path.read_text(encoding="utf-8")
        for location, mutate in mutations.items():
            with self.subTest(location):
                document = self.rewrite(self.path, mutate)
                self.assertIn(location, self.assert_invalid(document).location)
                self.path.write_text(original, encoding="utf-8")
        self.path.write_text("{not json", encoding="utf-8")
        passed, failures = validate_lesson_recordings(self.root, [self.spec])
        self.assertEqual(passed, 0)
        self.assertIn("无法读取有效 JSON", failures[0][1])

    def test_source_change_is_reported_as_stale(self):
        path = self.root / "lessons" / MODULE / "tools.py"
        path.write_text(path.read_text(encoding="utf-8") + "# 改动\n", encoding="utf-8")
        with self.assertRaises(RecordingStale) as caught:
            validate_document(load_document(self.path), self.spec)
        self.assertIn("源码已变化，请重新录制", str(caught.exception))
        passed, failures = validate_lesson_recordings(self.root, [self.spec])
        self.assertEqual((passed, len(failures)), (0, 1))
        self.assertIn("源码已变化，请重新录制", failures[0][1])
        # lesson.json 本身也参与源码哈希。
        path.write_text(path.read_text(encoding="utf-8").replace("# 改动\n", ""), encoding="utf-8")
        self.assertEqual(validate_lesson_recordings(self.root, [self.spec]), (1, []))
        manifest = self.root / "lessons" / MODULE / "lesson.json"
        manifest.write_text(manifest.read_text(encoding="utf-8").replace("加法", "加法练习"), encoding="utf-8")
        with self.assertRaises(RecordingStale):
            validate_document(load_document(self.path), self.load_spec())

    def test_secrets_and_private_paths_are_rejected_by_validation(self):
        secret = "configured-secret-123456"
        for label, value in {"key": "echo " + secret, "sk": "sk-proj-abcdefghijklmnopqrst",
                             "path": "/Users/alice/notes.txt"}.items():
            with self.subTest(label):
                document = self.rewrite(self.path, lambda d: d["events"][5]["data"].update(content=value))
                error = self.assert_invalid(document, "events[5].data.content", keys=(secret,))
                self.assertNotIn(value, str(error))
        project = str(self.root / "lessons")
        self.assert_invalid({"metadata": {}, "events": [project]}, "events[0]", private_paths=[str(self.root)])

    def test_sdk_labels_must_match_provider_and_events(self):
        sdk_path = self.export(self.make_run(provider="openai"), name="sdk-run")

        def relabel(document, representation, sdk):
            document["metadata"].update(representation=representation, sdk=sdk)
            document["events"][0]["data"]["trace_representation"] = representation
            for event in document["events"]:
                if event["type"] in ("request", "response"):
                    event.update(representation=representation, sdk=sdk)
                    event["data"]["representation"] = representation

        cases = {
            # SDK 数据整体改标为 http_body：事件自洽也不行，服务商经 SDK 调用。
            "sdk-as-http": (sdk_path, lambda d: relabel(d, "http_body", None), "metadata.representation"),
            "http-with-sdk": (sdk_path, lambda d: relabel(d, "http_body", LITELLM), "metadata.sdk"),
            "sdk-without-version": (sdk_path, lambda d: relabel(d, "sdk_standardized", {"name": "litellm"}),
                                    "metadata.sdk"),
            "test-adapter": (sdk_path, lambda d: relabel(d, "sdk_standardized",
                                                         {"name": "deterministic-test-adapter", "version": "1"}),
                             "metadata.sdk"),
            "bailian-as-sdk": (self.path, lambda d: relabel(d, "sdk_standardized", LITELLM),
                               "metadata.representation"),
            "metadata-only": (sdk_path, lambda d: d["metadata"].update(representation="http_body", sdk=None),
                              "metadata.representation"),
            "event-only": (sdk_path, lambda d: d["events"][1].update(representation="http_body", sdk=None),
                           "events[1]"),
            "v1-field": (sdk_path, lambda d: d["events"][2]["data"].update(representation="http_body"),
                         "events[2].data.representation"),
            "testing-provider": (sdk_path, lambda d: d["metadata"].update(provider_id="testing"),
                                 "metadata.provider_id"),
        }
        for label, (path, mutate, location) in cases.items():
            with self.subTest(label):
                original = path.read_text(encoding="utf-8")
                self.assertIn(location, self.assert_invalid(self.rewrite(path, mutate)).location)
                path.write_text(original, encoding="utf-8")

    def test_files_with_invalid_names_or_without_lesson_are_reported(self):
        self.write(f"lessons/{MODULE}/recordings/Bad_Name.json", "{}")
        self.write("lessons/lesson_orphan/recordings/demo.json", "{}")
        passed, failures = validate_lesson_recordings(self.root, [self.spec])
        self.assertEqual(passed, 1)
        self.assertEqual(sorted(path for path, _ in failures),
                         ["lessons/lesson_orphan/recordings/demo.json", f"lessons/{MODULE}/recordings/Bad_Name.json"])


class RecordingApiTests(RecordingTestCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(web.app, base_url="http://localhost")
        use_temporary_run_store(self)
        original = web.lesson_spec
        spec = self.spec
        patcher = patch.object(web, "lesson_spec",
                               side_effect=lambda value: spec if value in (SLUG, "r1") else original(value))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.path = self.export(self.make_run())

    def test_list_and_read_by_slug_or_alias(self):
        for lesson_id in (SLUG, "r1"):
            listed = self.client.get(f"/api/lessons/{lesson_id}/recordings")
            self.assertEqual(listed.status_code, 200)
            body = listed.json()
            self.assertEqual(body["lesson_id"], SLUG)
            self.assertEqual([(r["name"], r["valid"], r["error_code"]) for r in body["recordings"]],
                             [("demo-run", True, None)])
            self.assertEqual(body["recordings"][0]["metadata"], load_document(self.path)["metadata"])
            self.assertNotIn("events", body["recordings"][0])
            detail = self.client.get(f"/api/lessons/{lesson_id}/recordings/demo-run").json()
            self.assertEqual(detail["events"], load_document(self.path)["events"])
            self.assertTrue(all(event["provenance"] == "recorded_run" for event in detail["events"]))
        real = self.client.get("/api/lessons/tool-selection/recordings").json()
        self.assertEqual(real, {"lesson_id": "tool-selection", "recordings": []})
        # 录制不进入运行存储，也不出现在“你的运行”列表中。
        self.assertEqual(self.client.get("/api/runs").json(), {"runs": []})

    def test_error_codes(self):
        def error(url):
            response = self.client.get(url)
            return response.status_code, response.json().get("code"), "events" in response.json()

        self.assertEqual(error(f"/api/lessons/{SLUG}/recordings/missing"), (404, "recording_not_found", False))
        # 名称必须是 kebab-case；大小写不敏感的文件系统上也不能借大写名读到文件。
        self.assertEqual(error(f"/api/lessons/{SLUG}/recordings/DEMO-RUN"), (404, "recording_not_found", False))
        self.assertEqual(error(f"/api/lessons/{SLUG}/recordings/demo-run.json"), (404, "recording_not_found", False))
        self.assertEqual(error("/api/lessons/no-such-lesson/recordings")[:2], (404, "lesson_not_found"))
        original = self.path.read_text(encoding="utf-8")
        self.rewrite(self.path, lambda d: d["events"][5]["data"].update(content="43"), rehash=False)
        self.assertEqual(error(f"/api/lessons/{SLUG}/recordings/demo-run"), (422, "recording_invalid", False))
        listed = self.client.get(f"/api/lessons/{SLUG}/recordings").json()["recordings"]
        self.assertEqual(listed, [{"name": "demo-run", "valid": False, "error_code": "recording_invalid",
                                   "metadata": None}])
        self.path.write_text(original, encoding="utf-8")
        tools = self.root / "lessons" / MODULE / "tools.py"
        tools.write_text(tools.read_text(encoding="utf-8") + "# 改动\n", encoding="utf-8")
        self.assertEqual(error(f"/api/lessons/{SLUG}/recordings/demo-run"), (409, "recording_stale", False))
        stale = self.client.get(f"/api/lessons/{SLUG}/recordings").json()["recordings"][0]
        self.assertEqual((stale["valid"], stale["error_code"]), (False, "recording_stale"))
        self.assertEqual(stale["metadata"]["run_id"], load_document(self.path)["metadata"]["run_id"])


if __name__ == "__main__":
    unittest.main()
