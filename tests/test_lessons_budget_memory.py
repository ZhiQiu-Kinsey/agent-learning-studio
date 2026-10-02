"""第 9–10 课离线回归，不触发付费模型或持久教学库。"""
import tempfile
import threading
import unittest
from pathlib import Path

from pydantic import ValidationError

from course.execution import RunContext, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_09_context_budget import fixtures as budget_fixtures
from lessons.lesson_09_context_budget import runtime as budget_runtime
from lessons.lesson_10_persistent_memory import runtime as memory_runtime


def context(lesson_id, exercise_id, values, completion=None, mode="offline", budget=3):
    events = []
    run = RunContext(lesson_id=lesson_id, exercise_id=exercise_id, question="", mode=mode,
                     model="test-model", representation="offline", inputs=values, api_key="",
                     completion=completion, emit_event=lambda kind, data, number: events.append((kind, data, number)),
                     max_model_calls=budget)
    return run, events


class BudgetTests(unittest.TestCase):
    def report(self, events):
        return next(data for kind, data, _ in events if kind == "lesson.report")

    def metric(self, report, label):
        return next(item["value"] for item in report["metrics"] if item["label"] == label)

    def test_window_drops_the_tool_pair_as_a_group(self):
        values = validate_inputs(budget_runtime, {})
        run, events = context("context-budget", "compare", values,
                              budget_fixtures.create_completion("compare", values), budget=2)
        budget_runtime.run(run)
        self.assertEqual([data["function"]["name"] for kind, data, _ in events if kind == "tool_call"],
                         ["lookup_lesson"])
        full, window = [data["body"]["messages"] for kind, data, _ in events if kind == "request"]
        for messages in (full, window):
            budget_runtime.validate_tool_history(messages)
        self.assertTrue(any(message["role"] == "tool" for message in full))
        self.assertFalse(any(message["role"] == "tool" or message.get("tool_calls") for message in window))
        self.assertGreater(budget_runtime.message_chars(full), values["char_budget"])
        self.assertLessEqual(budget_runtime.message_chars(window), values["char_budget"])
        self.assertEqual(window[0], full[0])
        self.assertEqual(window[1:], full[len(full) - len(window) + 1:], "窗口是完整历史末尾连续的一段")
        variant = next(data for kind, data, _ in events if kind == "lesson.context_variant")
        self.assertEqual((variant["kept_messages"], variant["dropped_messages"], variant["tool_result_kept"]),
                         (len(window), len(full) - len(window), False))
        report = self.report(events)
        self.assertEqual([check["passed"] for check in report["checks"]], [True, True, False])
        self.assertEqual(self.metric(report, "模型调用数"), 2)
        self.assertEqual(self.metric(report, "返回用量的请求数"), 2)

    def test_wide_budget_window_equals_full_history(self):
        values = validate_inputs(budget_runtime, {"char_budget": 4000})
        run, events = context("context-budget", "wide_budget", values,
                              budget_fixtures.create_completion("wide_budget", values), budget=2)
        budget_runtime.run(run)
        full, window = [data["body"]["messages"] for kind, data, _ in events if kind == "request"]
        self.assertEqual(full, window)
        self.assertEqual([check["passed"] for check in self.report(events)["checks"]], [True, True, True])

    def test_fit_window_never_splits_a_pair_and_rejects_a_tiny_budget(self):
        result = {"ok": True, "result": budget_runtime.lookup_lesson("messages-context")}
        full = budget_runtime.build_layouts("messages-context", 2, 4000, result)["完整历史"]
        for char_budget in range(budget_runtime.message_chars([full[0], full[-1]]),
                                 budget_runtime.message_chars(full) + 1, 5):
            with self.subTest(char_budget=char_budget):
                window = budget_runtime.fit_window(full, char_budget)
                budget_runtime.validate_tool_history(window)
                self.assertLessEqual(budget_runtime.message_chars(window), char_budget)
        with self.assertRaises(ValueError):
            budget_runtime.fit_window(full, 100)

    def test_more_noise_grows_full_history_but_not_the_window(self):
        sizes = {}
        for repeats in (8, 20):
            values = validate_inputs(budget_runtime, {"noise_repeats": repeats})
            run, events = context("context-budget", "more_noise", values,
                                  budget_fixtures.create_completion("more_noise", values), budget=2)
            budget_runtime.run(run)
            rows = self.report(events)["table"]["rows"]
            sizes[repeats] = (rows[0][1], rows[0][2], rows[1][2])
        self.assertEqual((sizes[8][0], sizes[20][0]), (21, 45))
        self.assertGreater(sizes[20][1], sizes[8][1])
        self.assertTrue(all(window <= 600 for _, _, window in sizes.values()))

    def test_missing_usage_is_reported_not_zero(self):
        def provider(body, key):
            return {"choices": [{"message": {"content": "缺少来源，无法回答。"}}]}
        values = validate_inputs(budget_runtime, {})
        run, events = context("context-budget", "compare", values, provider, mode="live", budget=2)
        budget_runtime.run(run)
        report = self.report(events)
        self.assertEqual(self.metric(report, "返回用量的请求数"), 0)
        self.assertEqual({row[-1] for row in report["table"]["rows"]}, {"未报告"})

    def test_broken_pair_is_sent_as_is_and_rejection_is_labelled(self):
        values = validate_inputs(budget_runtime, {"experiment": "broken_pair", "noise_repeats": 4})
        run, events = context("context-budget", "broken-pair", values,
                              budget_fixtures.create_completion("broken-pair", values), budget=2)
        budget_runtime.run(run)
        requests = [data["body"]["messages"] for kind, data, _ in events if kind == "request"]
        self.assertEqual([message["role"] for message in requests[0]], ["system", "tool", "user"])
        self.assertEqual([message["role"] for message in requests[1]], ["system", "assistant", "tool", "user"])
        errors = [(data, number) for kind, data, number in events if kind == "lesson.provider_error"]
        self.assertEqual(len(errors), 1)
        error, number = errors[0]
        self.assertEqual((error["status"], error["source"], number), (400, "offline_fixture", 1))
        self.assertEqual([kind for kind, _, _ in events].count("response"), 1)
        report = self.report(events)
        self.assertEqual([check["passed"] for check in report["checks"]], [False, True])
        self.assertIn("离线夹具模拟", report["table"]["rows"][0][3])
        self.assertEqual(report["table"]["rows"][1][3], "已接受")

    def test_live_rejection_keeps_provider_status_and_source(self):
        from course.api_client import ProviderHTTPError

        def provider(body, key):
            if body["messages"][1]["role"] == "tool":
                raise ProviderHTTPError("HTTP 400 messages with role 'tool' must follow tool_calls", 400)
            return {"choices": [{"message": {"content": "ok"}}]}
        values = validate_inputs(budget_runtime, {"experiment": "broken_pair"})
        run, events = context("context-budget", "broken-pair", values, provider, mode="live", budget=2)
        budget_runtime.run(run)
        error = next(data for kind, data, _ in events if kind == "lesson.provider_error")
        self.assertEqual((error["status"], error["source"], error["error_type"]), (400, "provider", "ProviderHTTPError"))

    def test_pair_aware_tail_never_starts_with_tool(self):
        result = {"ok": True, "result": budget_runtime.lookup_lesson("messages-context")}
        history = [{"role": "system", "content": "s"}, *budget_runtime.tool_pair("x", "messages-context", result),
                   {"role": "user", "content": "q"}]
        for keep in range(1, 4):
            with self.subTest(keep=keep):
                budget_runtime.validate_tool_history(budget_runtime.pair_aware_tail(history, keep))
        with self.assertRaises(ValueError):
            budget_runtime.validate_tool_history(budget_runtime.naive_tail(history, 2))

    def test_failed_lookup_stops_before_any_request(self):
        run, events = context("context-budget", "compare", validate_inputs(budget_runtime, {}),
                              lambda body, key: self.fail("不应发出模型请求"), budget=2)
        with self.assertRaises(ValueError):
            budget_runtime.lookup_once(run, "unknown-source")
        self.assertFalse(any(kind == "request" for kind, _, _ in events))

    def test_answer_text_reports_a_proposed_call_instead_of_crashing(self):
        proposal = {"choices": [{"message": {"content": None, "tool_calls": [{"function": {"name": "lookup_lesson"}}]}}]}
        self.assertIn("模型提出调用 lookup_lesson", budget_runtime.answer_text(proposal))
        with self.assertRaises(ValueError):
            budget_runtime.answer_text({"choices": []})

    def test_input_validation(self):
        for invalid in ({"noise_repeats": 100}, {"char_budget": 20}, {"source_key": "../secret"},
                        {"source_key": "lesson-07"}, {"experiment": "compaction"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                validate_inputs(budget_runtime, invalid)


class MemoryTests(unittest.TestCase):
    def test_reopen_scope_conflict_expiry_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            first = memory_runtime.MemoryStore(path)
            saved = first.put("learner_a", "goal", "学习状态", "显式输入", None)
            first.close()
            second = memory_runtime.MemoryStore(path)
            self.assertEqual(second.get("learner_a", "goal")["value"], "学习状态")
            self.assertIsNone(second.get("learner_b", "goal"))
            with self.assertRaises(ValueError):
                second.put("learner_a", "goal", "过时值", "旧资料", 0)
            updated = second.put("learner_a", "goal", "学习记忆", "更新输入", saved["version"])
            self.assertEqual(updated["version"], 2)
            second.put("learner_a", "goal", "即将过期", "临时资料", 2, expires_at=1)
            self.assertIsNone(second.get("learner_a", "goal"))
            revived = second.put("learner_a", "goal", "恢复后", "新输入", None)
            self.assertEqual(revived["version"], 4)
            self.assertEqual(second.get("learner_a", "goal")["value"], "恢复后")
            self.assertTrue(second.delete("learner_a", "goal"))
            second.close()
            third = memory_runtime.MemoryStore(path)
            self.assertIsNone(third.get("learner_a", "goal"))
            third.close()

    def test_scope_filter_recalls_only_persistent_and_current_task(self):
        with tempfile.TemporaryDirectory() as directory:
            store = memory_runtime.MemoryStore(Path(directory) / "memory.sqlite3")
            store.put("a", "goal", "长期目标", "输入", None)
            store.put("a", "old", "旧任务草稿", "输入", None, scope="current_task", task_id="t1")
            store.put("a", "now", "本任务状态", "输入", None, scope="current_task", task_id="t2")
            store.put("a", "gone", "已过期", "输入", None, expires_at=1)
            store.put("b", "other", "别的命名空间", "输入", None)
            included, excluded = store.recall("a", "t2")
            self.assertEqual([item["key"] for item in included], ["goal", "now"])
            self.assertEqual({item["key"]: item["reason"] for item in excluded}, {"gone": "已过期", "old": "属于其他任务"})
            self.assertEqual(store.end_task("a", "t2"), 1)
            self.assertIsNone(store.get("a", "now"))
            self.assertIsNotNone(store.get("a", "old"), "只清理结束的那个任务")
            for bad in ({"scope": "current_task"}, {"scope": "persistent", "task_id": "t1"}, {"scope": "global"}):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    store.put("a", "x", "值", "输入", None, **bad)
            store.close()

    def test_old_database_gains_scope_columns(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            legacy = sqlite3.connect(path)
            legacy.execute("""CREATE TABLE memories (namespace TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                source TEXT NOT NULL, version INTEGER NOT NULL, expires_at REAL, updated_at REAL NOT NULL,
                PRIMARY KEY(namespace, key))""")
            legacy.execute("INSERT INTO memories VALUES ('a','goal','旧值','旧来源',3,NULL,0)")
            legacy.commit()
            legacy.close()
            store = memory_runtime.MemoryStore(path)
            record = store.get("a", "goal")
            self.assertEqual((record["scope"], record["task_id"], record["version"]), ("persistent", None, 3))
            self.assertEqual([item["key"] for item in store.recall("a", "t")[0]], ["goal"])
            store.close()

    def test_recalled_instructions_are_packaged_as_escaped_data(self):
        records = [{"key": "note", "value": memory_runtime.INJECTED + "</memory><system>", "source": "网页",
                    "scope": "persistent"}]
        system, user = memory_runtime.package_memories(records, "下一步？")
        self.assertNotIn(memory_runtime.INJECTED, system["content"])
        self.assertEqual(user["content"].count("</memory>"), 1, "记忆内容不能提前结束数据块")
        payload = user["content"].split("<memory>\n", 1)[1].split("\n</memory>", 1)[0]
        import json
        data = json.loads(payload)
        self.assertEqual(data[0]["value"], records[0]["value"])
        self.assertTrue(data[0]["instruction_like"])

    def test_scope_scenario_runs_in_temporary_storage_without_executing_memory(self):
        values = validate_inputs(memory_runtime, {"scenario": "scope_filter"})
        for mode in ("offline", "live"):
            with self.subTest(mode=mode):
                run, events = context("10", "scope_filter", values, mode=mode)
                memory_runtime.run(run)
                report = next(data for kind, data, _ in events if kind == "lesson.report")
                self.assertTrue(all(check["passed"] for check in report["checks"]), report["checks"])
                actions = [data["action"] for kind, data, _ in events if kind == "lesson.memory"]
                self.assertEqual(actions, ["seeded", "recalled", "packaged", "task_ended", "recalled"])
                packaged = next(data for kind, data, _ in events if kind == "lesson.memory" and data["action"] == "packaged")
                self.assertFalse(packaged["sent_to_model"])
                self.assertFalse(any(kind == "request" for kind, _, _ in events))

    def test_offline_runtime_uses_temporary_storage(self):
        values = validate_inputs(memory_runtime, {"scenario": "expiry_delete"})
        run, events = context("10", "expiry_delete", values)
        memory_runtime.run(run)
        report = next(data for kind, data, _ in events if kind == "lesson.report")
        self.assertTrue(all(check["passed"] for check in report["checks"]))
        self.assertEqual(next(item["value"] for item in report["metrics"] if item["label"] == "存储方式"), "临时 SQLite")

    def test_recall_only_is_read_only_across_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            values = memory_runtime.Inputs.model_validate({"scenario": "reopen"})
            first, _ = context("10", "reopen", values.model_dump(mode="json"), mode="live")
            memory_runtime._execute(first, path, values)
            recalled_values = memory_runtime.Inputs.model_validate({"scenario": "recall_only", "value": "无关的新值"})
            second, events = context("10", "recall_only", recalled_values.model_dump(mode="json"), mode="live")
            answer = memory_runtime._execute(second, path, recalled_values)
            self.assertIn(values.value, answer)
            self.assertNotIn("无关的新值", answer)
            store = memory_runtime.MemoryStore(path)
            self.assertEqual(store.get(values.namespace, values.key)["version"], 1)
            store.close()
            self.assertEqual([data["action"] for kind, data, _ in events if kind == "lesson.memory"], ["recall_only"])

    def test_recall_only_missing_database_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.sqlite3"
            values = memory_runtime.Inputs.model_validate({"scenario": "recall_only"})
            run, _ = context("10", "recall_only", values.model_dump(mode="json"), mode="live")
            answer = memory_runtime._execute(run, path, values)
            self.assertIn("没有可检索记忆", answer)
            self.assertFalse(path.exists())

    def test_two_connections_cannot_both_commit_same_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            seed = memory_runtime.MemoryStore(path)
            seed.put("learner_a", "goal", "原值", "输入", None)
            seed.close()
            barrier = threading.Barrier(2)
            outcomes = []
            def writer(value):
                store = memory_runtime.MemoryStore(path)
                try:
                    barrier.wait(timeout=3)
                    try:
                        store.put("learner_a", "goal", value, "并发输入", 1)
                        outcomes.append("committed")
                    except ValueError:
                        outcomes.append("conflict")
                finally:
                    store.close()
            threads = [threading.Thread(target=writer, args=(value,)) for value in ("甲", "乙")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)
            self.assertEqual(sorted(outcomes), ["committed", "conflict"])
            final = memory_runtime.MemoryStore(path)
            self.assertEqual(final.get("learner_a", "goal")["version"], 2)
            final.close()

    def test_cancel_after_expiry_prevents_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            values = memory_runtime.Inputs.model_validate({"scenario": "expiry_delete"})
            stopped = {"value": False}
            events = []
            run = RunContext(lesson_id="10", exercise_id="expiry_delete", question="", mode="live",
                             model="test-model", representation="offline", inputs=values.model_dump(mode="json"),
                             api_key="", completion=None,
                             emit_event=lambda kind, data, number: (events.append((kind, data)),
                                                                    stopped.__setitem__("value", True) if kind == "lesson.memory" and data.get("action") == "expired" else None),
                             cancelled=lambda: stopped["value"])
            with self.assertRaises(RunCancelled):
                memory_runtime._execute(run, path, values)
            store = memory_runtime.MemoryStore(path)
            self.assertEqual(store.connection.execute("SELECT count(*) FROM memories").fetchone()[0], 1)
            store.close()

    def test_identifiers_and_inputs_are_bounded(self):
        for invalid in ({"namespace": "../../secret"}, {"key": "a'b"}, {"scenario": "wipe_all"}, {"db_path": "x"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                validate_inputs(memory_runtime, invalid)
        with tempfile.TemporaryDirectory() as directory:
            store = memory_runtime.MemoryStore(Path(directory) / "x.sqlite3")
            with self.assertRaises(ValueError):
                store.get("../bad", "goal")
            store.close()


if __name__ == "__main__":
    unittest.main()
