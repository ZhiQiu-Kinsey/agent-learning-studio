"""上下文压缩一课的行为测试：确定性模型数据，lookup_lesson 在 Python 中真实执行。"""
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_07_messages_context.runtime import validate_tool_history
from lessons.lesson_09_context_budget.runtime import FACTS, has_text, lookup_lesson
from lessons.lesson_context_compaction import runtime
from lessons.lesson_context_compaction.fixtures import create_completion


def run_case(exercise_id, inputs, completion=None, budget=5, cancelled=lambda: False, mode="offline"):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="context-compaction", exercise_id=exercise_id, question="", mode=mode,
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def rounds(events, kind):
    return [number for event, _, number in events if event == kind]


def metric(report, label):
    return next(item["value"] for item in report["metrics"] if item["label"] == label)


class CompactionRunTests(unittest.TestCase):
    def test_four_layouts_share_the_recent_part_and_one_probe(self):
        _, events = run_case("compare", {})
        self.assertEqual([call["id"] for call in of(events, "tool_call")], ["compaction_lookup_1", "compaction_lookup_2"])
        self.assertEqual(rounds(events, "request"), [1, 2, 3, 4, 5])
        full, rule, cleared, summary_request, summarized = [data["body"]["messages"] for data in of(events, "request")]
        for messages in (full, rule, cleared, summary_request, summarized):
            validate_tool_history(messages)
        self.assertEqual(summary_request[-1]["content"], runtime.SUMMARY_INSTRUCTIONS["keep_sources"])
        for messages in (full, rule, cleared, summarized):
            self.assertEqual(messages[-1]["content"], runtime.PROBE)
            self.assertEqual(messages[-5:], full[-5:], "最近部分在每一组里都原样保留")
        self.assertEqual(len(cleared), len(full), "清理只换内容，不删消息")
        self.assertLess(len(rule), len(full))
        self.assertLess(len(summarized), len(full))
        self.assertIn(FACTS["application-state"], str(cleared), "最近一次工具结果保留")
        layouts = [data for data in of(events, "lesson.compaction") if data["kind"] == "layout"]
        self.assertEqual([data["name"] for data in layouts], ["不压缩", "规则压缩", "清理旧工具结果", "摘要压缩"])
        self.assertEqual([data["phrase_in_context"] for data in layouts], [True, True, False, True])

    def test_report_keeps_string_check_and_screening_apart(self):
        _, events = run_case("compare", {})
        report = of(events, "lesson.report")[0]
        self.assertEqual([check["passed"] for check in report["checks"]], [True, True, True, True, False, True])
        self.assertEqual(metric(report, "模型调用数"), 5, "摘要的额外请求也计入")
        rows = report["table"]["rows"]
        self.assertEqual([row[3] for row in rows], [True, True, False, True])
        self.assertEqual([row[5] for row in rows], ["命中", "命中", "未命中", "命中"])

    def test_tight_budget_refuses_the_rule_record_without_a_request(self):
        _, events = run_case("tight-budget", {"char_budget": 100})
        self.assertEqual(rounds(events, "request"), [1, 3, 4, 5])
        refused = [(data, number) for data, number in zip(of(events, "lesson.compaction"), rounds(events, "lesson.compaction"))
                   if data["kind"] == "refused"]
        self.assertEqual(len(refused), 1)
        self.assertEqual(refused[0][1], 2)
        self.assertIn("100", refused[0][0]["reason"])
        report = of(events, "lesson.report")[0]
        self.assertFalse(report["checks"][1]["passed"])
        self.assertEqual(metric(report, "模型调用数"), 4)
        self.assertNotIn("规则压缩", [row[0] for row in report["table"]["rows"]])

    def test_brief_instruction_reaches_the_summary_request(self):
        _, events = run_case("brief-summary", {"summary_style": "brief"})
        summary_request = of(events, "request")[3]["body"]["messages"]
        self.assertEqual(summary_request[-1]["content"], runtime.SUMMARY_INSTRUCTIONS["brief"])
        summarized = next(data for data in of(events, "lesson.compaction") if data.get("name") == "摘要压缩")
        self.assertFalse(summarized["phrase_in_context"], "离线夹具的简短摘要不含原话")

    def test_summary_instruction_is_recorded_whatever_the_history_length(self):
        # 观察点读 lesson.compaction 的 instruction 字段；摘要请求的消息条数随 noise_repeats 变（2n+5）。
        for repeats, style in ((2, "keep_sources"), (8, "brief"), (25, "brief")):
            with self.subTest(noise_repeats=repeats, summary_style=style):
                _, events = run_case("compare", {"noise_repeats": repeats, "summary_style": style})
                tagged = [(data, number) for data, number in zip(of(events, "lesson.compaction"),
                                                                 rounds(events, "lesson.compaction"))
                          if data["kind"] == "summary_request"]
                self.assertEqual(len(tagged), 1)
                data, number = tagged[0]
                summary_request = of(events, "request")[3]["body"]["messages"]
                self.assertEqual(number, 4)
                self.assertEqual(len(summary_request), 2 * repeats + 5)
                self.assertEqual((data["instruction"], data["style"], data["messages"]),
                                 (summary_request[-1]["content"], style, len(summary_request)))
                self.assertEqual(data["instruction"], runtime.SUMMARY_INSTRUCTIONS[style])

    def test_missing_usage_is_reported_not_zero(self):
        def provider(body, key):
            return {"choices": [{"message": {"content": "无法回答。"}}]}
        _, events = run_case("compare", {}, provider, mode="live")
        report = of(events, "lesson.report")[0]
        self.assertEqual(metric(report, "摘要请求的用量"), "未报告")
        self.assertEqual({row[-1] for row in report["table"]["rows"]}, {"未报告"})

    def test_cancel_stops_before_any_request(self):
        with self.assertRaises(RunCancelled):
            run_case("compare", {}, cancelled=lambda: True)

    def test_model_budget_stops_the_run(self):
        with self.assertRaises(RuntimeError):
            run_case("compare", {}, budget=3)


class CompactionFunctionTests(unittest.TestCase):
    def setUp(self):
        self.results = {key: {"ok": True, "result": lookup_lesson(key)} for key in runtime.SOURCES}

    def test_rule_record_keeps_every_field_and_the_order_or_raises(self):
        reads = [("messages-context", self.results["messages-context"])]
        record = runtime.rule_record(reads, 300)
        for field in ("目标：", "约束：", "来源：第 1 次读取 messages-context", "事实：" + FACTS["messages-context"], "待办："):
            self.assertIn(field, record["content"])
        both = runtime.rule_record([(key, self.results[key]) for key in runtime.SOURCES], 2000)["content"]
        self.assertIn("第 1 次读取 messages-context；第 2 次读取 application-state", both)
        with self.assertRaises(ValueError):
            runtime.rule_record(reads, 100)
        with self.assertRaises(ValueError):
            runtime.rule_record([("messages-context", {"ok": False, "error": "读取失败"})], 300)

    def test_a_proposed_tool_call_is_reported_not_executed(self):
        def provider(body, key):
            if body["messages"][-1]["content"] == runtime.PROBE and "cleared" in str(body["messages"]):
                return {"choices": [{"message": {"content": "", "tool_calls": [
                    {"id": "again", "type": "function", "function": {"name": "lookup_lesson", "arguments": "{}"}}]},
                    "finish_reason": "tool_calls"}]}
            return create_completion("compare")(body, key)
        _, events = run_case("compare", {}, provider)
        self.assertEqual(len(of(events, "tool_call")), 2, "运行器只执行自己发起的两次读取")
        row = next(row for row in of(events, "lesson.report")[0]["table"]["rows"] if row[0] == "清理旧工具结果")
        self.assertIn("模型提出调用 lookup_lesson", row[4])
        self.assertEqual(row[5], "未命中")

    def test_clearing_keeps_pairs_and_only_the_latest_result(self):
        older, recent = runtime.build_history(2, self.results)
        messages = runtime.clear_old_tool_results(older + recent)
        validate_tool_history(messages)
        tools = [message for message in messages if message["role"] == "tool"]
        self.assertIn("cleared", tools[0]["content"])
        self.assertIn(FACTS["application-state"], tools[1]["content"])
        none_kept = runtime.clear_old_tool_results(older + recent, keep_latest=0)
        self.assertFalse(any(has_text(none_kept, fact) for fact in FACTS.values()))

    def test_failed_lookup_is_not_compacted(self):
        broken = {**self.results, "messages-context": {"ok": False, "error_type": "ValueError", "error": "x"}}
        with self.assertRaises(ValueError):
            runtime.build_history(2, broken)

    def test_probe_hit_needs_both_source_and_phrase(self):
        self.assertTrue(runtime.probe_hit("来自 messages-context，原话：模型只看到本次请求里的消息；历史由应用程序重发。"))
        self.assertFalse(runtime.probe_hit("历史由应用程序重发"))
        self.assertFalse(runtime.probe_hit("来自 messages-context"))
        self.assertTrue(runtime.probe_hit("来自“上下文组成与消息协议”，原话：模型只看到本次请求里的消息，历史由应用程序重发"))

    def test_inputs_are_bounded(self):
        for bad in ({"char_budget": 50}, {"noise_repeats": 30}, {"summary_style": "long"}, {"extra": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)


if __name__ == "__main__":
    unittest.main()
