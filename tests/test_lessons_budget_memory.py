"""“上下文预算与截取窗口”的离线回归，不触发付费模型。“持久记忆”的测试在 lessons/lesson_10_persistent_memory/test_lesson.py。"""
import threading
import unittest

from pydantic import ValidationError

from course.execution import RunContext, validate_inputs
from lessons.lesson_09_context_budget import fixtures as budget_fixtures
from lessons.lesson_09_context_budget import runtime as budget_runtime


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
            budget_runtime.validate_tool_history(messages, "zh-CN")
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
        t = budget_runtime.texts_for("zh-CN")
        result = {"ok": True, "result": budget_runtime.lookup_lesson(budget_runtime.helper_texts("zh-CN"), "messages-context")}
        full = budget_runtime.build_layouts(t, "zh-CN", "messages-context", 2, 4000, result)["full"]
        for char_budget in range(budget_runtime.message_chars([full[0], full[-1]]),
                                 budget_runtime.message_chars(full) + 1, 5):
            with self.subTest(char_budget=char_budget):
                window = budget_runtime.fit_window(full, char_budget, t)
                budget_runtime.validate_tool_history(window, "zh-CN")
                self.assertLessEqual(budget_runtime.message_chars(window), char_budget)
        with self.assertRaises(ValueError):
            budget_runtime.fit_window(full, 100, t)

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

    def test_timeout_rate_limit_and_connection_errors_are_raised_not_recorded(self):
        # LiteLLM 的超时（408）、连接失败（500）、限流（429）都带整数 status_code，
        # 但它们不是服务商对孤立 tool 消息的判断，不能记成“被拒绝”。
        from course.api_client import ProviderHTTPError
        from course.providers import load_sdk
        exceptions = load_sdk().exceptions
        failures = [
            exceptions.Timeout(message="请求超时", model="m", llm_provider="openai"),
            exceptions.APIConnectionError(message="连接失败", llm_provider="openai", model="m"),
            exceptions.RateLimitError(message="请求过多", llm_provider="openai", model="m"),
            ProviderHTTPError("HTTP 429", 429),
            RuntimeError("连接百炼失败"),
        ]
        for failure in failures:
            def provider(body, key, failure=failure):
                raise failure

            with self.subTest(error=type(failure).__name__):
                values = validate_inputs(budget_runtime, {"experiment": "broken_pair"})
                run, events = context("context-budget", "broken-pair", values, provider, mode="live", budget=2)
                with self.assertRaises(type(failure)):
                    budget_runtime.run(run)
                kinds = [kind for kind, _, _ in events]
                self.assertNotIn("lesson.provider_error", kinds)
                self.assertNotIn("lesson.report", kinds)

    def test_pair_aware_tail_never_starts_with_tool(self):
        result = {"ok": True, "result": budget_runtime.lookup_lesson(budget_runtime.helper_texts("zh-CN"), "messages-context")}
        history = [{"role": "system", "content": "s"}, *budget_runtime.tool_pair("x", "messages-context", result),
                   {"role": "user", "content": "q"}]
        for keep in range(1, 4):
            with self.subTest(keep=keep):
                budget_runtime.validate_tool_history(budget_runtime.pair_aware_tail(history, keep), "zh-CN")
        with self.assertRaises(ValueError):
            budget_runtime.validate_tool_history(budget_runtime.naive_tail(history, 2), "zh-CN")

    def test_failed_lookup_stops_before_any_request(self):
        run, events = context("context-budget", "compare", validate_inputs(budget_runtime, {}),
                              lambda body, key: self.fail("不应发出模型请求"), budget=2)
        with self.assertRaises(ValueError):
            budget_runtime.lookup_once(run, "unknown-source")
        self.assertFalse(any(kind == "request" for kind, _, _ in events))

    def test_answer_text_reports_a_proposed_call_instead_of_crashing(self):
        proposal = {"choices": [{"message": {"content": None, "tool_calls": [{"function": {"name": "lookup_lesson"}}]}}]}
        self.assertIn("模型提出调用 lookup_lesson", budget_runtime.answer_text(proposal, "zh-CN"))
        with self.assertRaises(ValueError):
            budget_runtime.answer_text({"choices": []}, "zh-CN")

    def test_input_validation(self):
        for invalid in ({"noise_repeats": 100}, {"char_budget": 20}, {"source_key": "../secret"},
                        {"source_key": "lesson-07"}, {"experiment": "compaction"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                validate_inputs(budget_runtime, invalid)


if __name__ == "__main__":
    unittest.main()
