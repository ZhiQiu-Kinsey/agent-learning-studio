"""“上下文组成与消息协议”“应用状态与运行生命周期”两课的离线行为回归。"""
import json
import unittest

from pydantic import ValidationError

from course.api_client import ProviderHTTPError
from course.execution import RunContext, execute_lesson, validate_inputs
from course.providers import load_sdk
from course.runner import RunCancelled
from lessons.lesson_07_messages_context import fixtures as context_fixtures
from lessons.lesson_07_messages_context import runtime as context_runtime
from lessons.lesson_08_application_state import runtime as state_runtime

CUSTOM = {"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}


def make_context(lesson_id, exercise_id, inputs, completion=None, cancelled=lambda: False, budget=4):
    events = []
    context = RunContext(
        lesson_id=lesson_id, exercise_id=exercise_id, question="", mode="offline",
        model="test-model", representation="offline", inputs=inputs,
        api_key="", completion=completion,
        emit_event=lambda kind, data, round_number: events.append((kind, data, round_number)),
        cancelled=cancelled, max_model_calls=budget,
    )
    return context, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def run_ablation(inputs=None, completion=None, budget=4):
    values = validate_inputs(context_runtime, inputs or {})
    completion = completion or context_fixtures.create_completion("ablate", values)
    context, events = make_context("messages-context", "ablate", values, completion, budget=budget)
    answer = execute_lesson(CUSTOM, context_runtime, context)
    return values, answer, events


class MessagesContextTests(unittest.TestCase):
    def test_five_variants_send_four_requests_and_block_the_orphan_call(self):
        values, answer, events = run_ablation()
        requests = [data["body"]["messages"] for data in of(events, "request")]
        self.assertEqual([len(messages) for messages in requests], [5, 4, 4, 3])
        self.assertEqual(len(of(events, "response")), 4)
        blocked = [data for data in of(events, "lesson.context") if "rejected" in data]
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]["variant"], "只去掉工具结果")
        self.assertEqual(blocked[0]["roles"], ["system", "user", "assistant", "user"])
        self.assertIn("4 组请求已发送，1 组", answer)

    def test_each_request_differs_from_full_context_only_by_the_removed_part(self):
        _, _, events = run_ablation()
        requests = [data["body"]["messages"] for data in of(events, "request")]
        full = requests[0]
        sent = [(name, removed) for name, removed in context_runtime.VARIANTS.items() if removed != ("tool_result",)]
        for (name, removed), messages in zip(sent, requests):
            with self.subTest(variant=name):
                expected = [message for key, message in zip(context_runtime.ORDER, full) if key not in removed]
                self.assertEqual(messages, expected)
                context_runtime.validate_tool_history(messages)

    def test_tool_result_is_really_executed_and_paired_by_the_same_call_id(self):
        values, _, events = run_ablation({"student_id": "s-2077"})
        call, result = of(events, "tool_call")[0], of(events, "tool_result")[0]
        self.assertEqual(call["origin"], "course_program")
        self.assertEqual(result["result"]["result"]["score"], 58)
        full = of(events, "request")[0]["body"]["messages"]
        self.assertEqual(full[2]["tool_calls"][0]["id"], call["id"])
        self.assertEqual(full[3]["tool_call_id"], call["id"])
        self.assertEqual(json.loads(full[3]["content"]), result["result"])
        self.assertIn("周四", full[1]["content"])
        self.assertNotIn("58", full[1]["content"] + full[4]["content"])

    def test_report_table_lists_screens_only_for_sent_variants(self):
        _, _, events = run_ablation({"free_day": "周六"})
        report = of(events, "lesson.report")[0]
        rows = {row[0]: row for row in report["table"]["rows"]}
        self.assertEqual(rows["完整上下文"][4:], [True, True, True])
        self.assertEqual(rows["去掉系统提示词"][6], False)
        self.assertEqual(rows["去掉之前的对话"][5], False)
        self.assertEqual(rows["去掉工具调用和结果"][4], False)
        self.assertEqual(rows["只去掉工具结果"][3:], ["未发送", "—", "—", "—"])
        self.assertTrue(all(check["passed"] for check in report["checks"]))
        metrics = {item["label"]: item["value"] for item in report["metrics"]}
        self.assertEqual((metrics["模型调用数"], metrics["被拦下的组"], metrics["能复习的日子"]), (4, 1, "周六"))

    def test_provider_rejection_is_recorded_and_other_variants_continue(self):
        values = validate_inputs(context_runtime, {})
        scripted = context_fixtures.create_completion("ablate", values)

        def completion(body, api_key):
            if body["messages"][0]["role"] != "system":
                raise ProviderHTTPError("HTTP 400", 400)
            return scripted(body, api_key)

        _, _, events = run_ablation(completion=completion)
        errors = of(events, "lesson.provider_error")
        self.assertEqual([error["status"] for error in errors], [400])
        rows = {row[0]: row for row in of(events, "lesson.report")[0]["table"]["rows"]}
        self.assertIn("服务商拒绝", rows["去掉系统提示词"][3])
        self.assertEqual(len(of(events, "request")), 4)

    def test_network_failure_budget_and_cancel_are_not_swallowed(self):
        def offline(body, api_key):
            raise RuntimeError("连接失败")

        with self.assertRaisesRegex(RuntimeError, "连接失败"):
            run_ablation(completion=offline)
        with self.assertRaisesRegex(RuntimeError, "超过 3 次"):
            run_ablation(budget=3)
        values = validate_inputs(context_runtime, {})
        context, _ = make_context("messages-context", "ablate", values,
                                  context_fixtures.create_completion("ablate", values), cancelled=lambda: True)
        with self.assertRaises(RunCancelled):
            context_runtime.run(context)

    def test_timeout_rate_limit_and_server_errors_are_not_recorded_as_rejections(self):
        # LiteLLM 的异常都带整数 status_code（超时 408、连接失败 500、限流 429）；它们不是服务商对消息的判断。
        exceptions = load_sdk().exceptions
        failures = [
            exceptions.Timeout(message="请求超时", model="m", llm_provider="openai"),
            exceptions.APIConnectionError(message="连接失败", llm_provider="openai", model="m"),
            exceptions.RateLimitError(message="请求过多", llm_provider="openai", model="m"),
            exceptions.ServiceUnavailableError(message="暂不可用", llm_provider="openai", model="m"),
            ProviderHTTPError("HTTP 429", 429),
            ProviderHTTPError("HTTP 502", 502),
            ProviderHTTPError("HTTP 401", 401),
        ]
        for failure in failures:
            def completion(body, api_key, failure=failure):
                raise failure

            with self.subTest(error=type(failure).__name__, status=failure.status_code):
                values = validate_inputs(context_runtime, {})
                context, events = make_context("messages-context", "ablate", values, completion)
                with self.assertRaises(type(failure)):
                    context_runtime.run(context)
                self.assertEqual(of(events, "lesson.provider_error"), [])
                self.assertEqual(of(events, "lesson.report"), [])

    def test_rejection_status_counts_only_request_level_4xx(self):
        for status, expected in ((400, 400), (413, 413), (422, 422), (401, None), (404, None),
                                 (408, None), (429, None), (500, None), (503, None)):
            with self.subTest(status=status):
                self.assertEqual(context_runtime.rejection_status(ProviderHTTPError("x", status)), expected)
        self.assertIsNone(context_runtime.rejection_status(RuntimeError("没有状态码")))

    def test_protocol_rejects_orphan_tool_result_and_unfinished_call(self):
        with self.assertRaises(ValueError):
            context_runtime.validate_tool_history([{"role": "tool", "tool_call_id": "x", "content": "3"}])
        with self.assertRaises(ValueError):
            context_runtime.validate_tool_history([{"role": "assistant", "tool_calls": [{"id": "x"}]}])
        with self.assertRaises(ValueError):
            context_runtime.validate_tool_history([{"role": "assistant", "tool_calls": [{"id": "x"}]},
                                                   {"role": "user", "content": "下一问"}])
        context_runtime.validate_tool_history([{"role": "assistant", "tool_calls": [{"id": "x"}]},
                                               {"role": "tool", "tool_call_id": "x", "content": "3"}])

    def test_input_contract(self):
        for invalid in ({"student_id": "s-9999"}, {"free_day": "明天"}, {"unexpected": "value"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                validate_inputs(context_runtime, invalid)
        with self.assertRaises(ValueError):
            context_runtime.lookup_score("s-9999")


class ApplicationStateTests(unittest.TestCase):
    def test_success_has_evidence_and_distinct_messages(self):
        values = validate_inputs(state_runtime, {})
        context, events = make_context("application-state", "success", values)
        answer = state_runtime.run(context)
        states = [data["state"] for data in of(events, "lesson.state")]
        self.assertEqual([state["status"] for state in states], ["ready", "running", "running", "completed"])
        self.assertEqual(len(states[-1]["evidence"]), 1)
        self.assertEqual(states[-1]["evidence"][0]["source"], "messages-context")
        metrics = of(events, "lesson.report")[0]["metrics"]
        self.assertEqual(next(item["value"] for item in metrics if item["label"] == "消息数"), 1)
        self.assertEqual(next(item["value"] for item in metrics if item["label"] == "已执行步骤"), 3)
        self.assertIn("messages-context", answer)

    def test_missing_and_budget_are_distinct_failures(self):
        # 结局只由资料来源和步骤预算决定，和 lesson.json 里两组练习的输入一致。
        presets = {"missing": {"source_key": "missing"},
                   "budget": {"source_key": "application-state", "step_budget": 2}}
        for scenario, inputs in presets.items():
            values = validate_inputs(state_runtime, inputs)
            context, events = make_context("application-state", scenario, values)
            state_runtime.run(context)
            states = [data["state"] for data in of(events, "lesson.state")]
            self.assertEqual(states[-1]["status"], "failed")
            self.assertTrue(states[-1]["terminal_reason"])
            self.assertEqual(len(states[-1]["evidence"]), 0 if scenario == "missing" else 1)
            self.assertEqual(states[-1]["used_steps"], 1 if scenario == "missing" else 2)
            self.assertEqual("waiting" in [s["status"] for s in states], scenario == "missing")
            # 没有进入 completed 时，“成功有证据和产物”没有可检查的对象，不标通过。
            success = of(events, "lesson.report")[0]["checks"][1]
            self.assertNotIn("passed", success)

    def test_budget_of_one_fails_before_checking_the_source(self):
        values = validate_inputs(state_runtime, {"source_key": "application-state", "step_budget": 1})
        context, events = make_context("application-state", "budget", values)
        self.assertIn("核对资料来源前耗尽", state_runtime.run(context))
        final = of(events, "lesson.state")[-1]["state"]
        self.assertEqual((final["status"], final["used_steps"], final["evidence"]), ("failed", 1, []))

    def test_invalid_transition_and_cancel(self):
        state = state_runtime.TaskState(run_id="one", goal="可检查的目标")
        with self.assertRaisesRegex(ValueError, "非法状态转换：ready → completed"):
            state.transition("completed", "未经执行")
        state.transition("running")
        with self.assertRaises(ValueError):
            state.transition("completed", "没有证据")
        state.evidence.append({"source": "x"})
        with self.assertRaises(ValueError):
            state.transition("completed", "没有产物")
        with self.assertRaises(ValueError):
            state.transition("failed")
        state.transition("cancelled", "用户停止")
        with self.assertRaises(ValueError):
            state.transition("running")
        values = validate_inputs(state_runtime, {})
        context, _ = make_context("application-state", "success", values, cancelled=lambda: True)
        with self.assertRaises(RunCancelled):
            state_runtime.run(context)

    def test_input_contract(self):
        # 没有 scenario 字段：结局不能靠预设标签指定，只能由资料和预算推出来。
        for invalid in ({"step_budget": 0}, {"source_key": "../../private"}, {"source_key": "lesson-07"},
                        {"scenario": "budget"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                validate_inputs(state_runtime, invalid)


if __name__ == "__main__":
    unittest.main()
