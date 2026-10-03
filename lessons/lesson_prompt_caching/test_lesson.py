"""提示缓存课的行为测试：缓存字段归一化、前缀哈希，以及用确定性夹具跑完三组请求。"""
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_prompt_caching import runtime
from lessons.lesson_prompt_caching.cache_usage import hit_ratio, normalize_cache_usage
from lessons.lesson_prompt_caching.fixtures import create_completion

MANIFEST = json.loads(Path(runtime.__file__).with_name("lesson.json").read_text(encoding="utf-8"))


def run_case(exercise_id, inputs, completion=None, budget=6, cancelled=lambda: False, mode="offline"):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="prompt-caching", exercise_id=exercise_id, question="", mode=mode,
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, *kinds):
    return [data for event, data, _ in events if event in kinds]


def records(events):
    return of(events, "lesson.cache_hit", "lesson.cache_miss", "lesson.cache_unreported")


def report(events):
    return of(events, "lesson.report")[-1]


class NormalizeTests(unittest.TestCase):
    def test_openai_compatible_cached_tokens_are_part_of_prompt_tokens(self):
        cache = normalize_cache_usage({"prompt_tokens": 547, "prompt_tokens_details": {"cached_tokens": 384}})
        self.assertEqual(cache, {"input_tokens": 547, "cached_tokens": 384, "cache_write_tokens": None,
                                 "field": "prompt_tokens_details.cached_tokens"})
        self.assertEqual(hit_ratio(cache), round(384 / 547, 4))

    def test_reported_zero_stays_zero(self):
        cache = normalize_cache_usage({"prompt_tokens": 460, "prompt_tokens_details": {"cached_tokens": 0}})
        self.assertEqual(cache["cached_tokens"], 0)
        self.assertEqual(hit_ratio(cache), 0.0)

    def test_deepseek_hit_and_miss(self):
        cache = normalize_cache_usage({"prompt_tokens": 1000, "prompt_cache_hit_tokens": 768,
                                       "prompt_cache_miss_tokens": 232})
        self.assertEqual((cache["input_tokens"], cache["cached_tokens"], cache["field"]),
                         (1000, 768, "prompt_cache_hit_tokens"))
        # 没有 prompt_tokens 时，命中与未命中合起来就是全部输入。
        self.assertEqual(normalize_cache_usage({"prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 900})
                         ["input_tokens"], 900)

    def test_anthropic_input_tokens_exclude_cache_reads_and_writes(self):
        cache = normalize_cache_usage({"input_tokens": 50, "cache_read_input_tokens": 1000,
                                       "cache_creation_input_tokens": 200, "output_tokens": 30})
        self.assertEqual(cache, {"input_tokens": 1250, "cached_tokens": 1000, "cache_write_tokens": 200,
                                 "field": "cache_read_input_tokens"})

    def test_missing_field_is_unreported_not_zero(self):
        for usage in ({"prompt_tokens": 460, "completion_tokens": 9},
                      {"prompt_tokens": 460, "prompt_tokens_details": {}},
                      {"prompt_tokens": 460, "prompt_tokens_details": None},
                      {"prompt_tokens": 460, "prompt_tokens_details": {"cached_tokens": None}},
                      {"prompt_tokens": 460, "prompt_tokens_details": {"audio_tokens": 0}}):
            with self.subTest(usage=usage):
                cache = normalize_cache_usage(usage)
                self.assertIsNone(cache["cached_tokens"])
                self.assertIsNone(cache["field"])
                self.assertEqual(cache["input_tokens"], 460)
                self.assertIsNone(hit_ratio(cache))

    def test_no_usage_at_all(self):
        for usage in (None, "460", [], 0):
            with self.subTest(usage=usage):
                self.assertEqual(normalize_cache_usage(usage), {"input_tokens": None, "cached_tokens": None,
                                                                "cache_write_tokens": None, "field": None})

    def test_values_that_are_not_counts_are_not_guessed(self):
        for value in (True, False, -1, 12.0, "384"):
            with self.subTest(value=value):
                cache = normalize_cache_usage({"prompt_tokens": 500, "prompt_tokens_details": {"cached_tokens": value}})
                self.assertIsNone(cache["cached_tokens"])
        self.assertIsNone(normalize_cache_usage({"prompt_tokens": True})["input_tokens"])

    def test_sdk_style_usage_with_both_shapes_uses_openai_field_and_keeps_writes(self):
        cache = normalize_cache_usage({"prompt_tokens": 1300, "prompt_tokens_details": {"cached_tokens": 1000},
                                       "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 200})
        self.assertEqual((cache["input_tokens"], cache["cached_tokens"], cache["cache_write_tokens"]),
                         (1300, 1000, 200))
        self.assertEqual(cache["field"], "prompt_tokens_details.cached_tokens")

    def test_ratio_needs_known_positive_input(self):
        self.assertIsNone(hit_ratio({"cached_tokens": 0, "input_tokens": 0}))
        self.assertIsNone(hit_ratio({"cached_tokens": 10, "input_tokens": None}))


class PrefixTests(unittest.TestCase):
    def test_dynamic_line_position_decides_whether_the_prefix_repeats(self):
        first = runtime.build_messages("dynamic_first", "s1", "问题一", "请求序号：1")
        second = runtime.build_messages("dynamic_first", "s1", "问题二", "请求序号：2")
        self.assertNotEqual(runtime.prefix_hash(first), runtime.prefix_hash(second))
        self.assertLess(runtime.shared_prefix_chars(first, second), 40)
        stable_one = runtime.build_messages("stable_prefix", "s1", "问题一", "请求序号：1")
        stable_two = runtime.build_messages("stable_prefix", "s1", "问题二", "请求序号：2")
        self.assertEqual(runtime.prefix_hash(stable_one), runtime.prefix_hash(stable_two))
        self.assertGreater(runtime.shared_prefix_chars(stable_one, stable_two), len(runtime.HANDBOOK))
        self.assertIsNone(runtime.shared_prefix_chars(None, stable_one))

    def test_three_layouts_send_the_same_rules_handbook_and_question(self):
        for layout in ("dynamic_first", "stable_prefix", "warmup"):
            with self.subTest(layout=layout):
                messages = runtime.build_messages(layout, "s1", "问题一", "请求序号：1")
                self.assertEqual([message["role"] for message in messages], ["system", "user"])
                self.assertIn(runtime.HANDBOOK, messages[0]["content"])
                self.assertIn("问题一", messages[1]["content"])
        self.assertTrue(runtime.build_messages("dynamic_first", "s1", "问", "请求序号：1")[0]["content"]
                        .startswith("请求序号：1"))
        self.assertTrue(runtime.build_messages("stable_prefix", "s1", "问", "请求序号：1")[1]["content"]
                        .endswith("（请求序号：1）"))

    def test_session_marker_changes_the_prefix(self):
        one = runtime.build_messages("stable_prefix", "aaaa", "问", "请求序号：1")
        two = runtime.build_messages("stable_prefix", "bbbb", "问", "请求序号：1")
        self.assertNotEqual(runtime.prefix_hash(one), runtime.prefix_hash(two))

    def test_handbook_is_long_enough_to_matter(self):
        self.assertGreater(len(runtime.HANDBOOK), 1500)


class RunTests(unittest.TestCase):
    def test_dynamic_first_reports_zero_on_every_request(self):
        answer, events = run_case("dynamic-first", {"layout": "dynamic_first"})
        bodies = [data["body"] for data in of(events, "request")]
        self.assertEqual(len(bodies), 4)
        self.assertTrue(all(body["messages"][0]["content"].startswith("请求序号：") for body in bodies))
        self.assertTrue(all(body["temperature"] == 0 and "tools" not in body for body in bodies))
        found = records(events)
        self.assertEqual(len(of(events, "lesson.cache_miss")), 4)
        self.assertEqual([item["cached_tokens"] for item in found], [0, 0, 0, 0])
        self.assertEqual(len({item["prefix_hash"] for item in found}), 4)
        self.assertTrue(all(item["shared_prefix_chars"] < 40 for item in found[1:]))
        checks = {check["label"]: check["passed"] for check in report(events)["checks"]}
        self.assertFalse(checks["各次请求的前缀哈希相同"])
        self.assertTrue(checks["每次响应都报告了缓存字段"])
        self.assertTrue(checks["报告命中的请求，前缀都在本次运行里发过"])
        self.assertIn("动态内容在前", answer)

    def test_stable_prefix_hits_from_the_second_request(self):
        _, events = run_case("stable-prefix", {"layout": "stable_prefix"})
        found = records(events)
        self.assertEqual([item["purpose"] for item in found], ["测量"] * 4)
        self.assertEqual(found[0]["cached_tokens"], 0)
        self.assertTrue(all(item["cached_tokens"] > 0 for item in found[1:]))
        self.assertEqual(len(of(events, "lesson.cache_hit")), 3)
        # 只有第一次命中带 first_hit：找错题“第一次报告命中”只认它。
        self.assertEqual([data.get("first_hit") for data in of(events, "lesson.cache_hit")], [True, None, None])
        self.assertEqual(len({item["prefix_hash"] for item in found}), 1)
        self.assertTrue(all(0 < item["ratio"] < 1 for item in found[1:]))
        data = report(events)
        self.assertTrue(all(check["passed"] for check in data["checks"]))
        metrics = {metric["label"]: metric["value"] for metric in data["metrics"]}
        self.assertEqual(metrics["测量请求中报告命中的次数"], 3)
        self.assertEqual(metrics["缓存字段"], "prompt_tokens_details.cached_tokens")
        self.assertEqual(metrics["运行模式"], "离线测试（数字来自夹具）")
        self.assertIn("夹具", data["summary"])
        # 动态行在最后一条 user 消息里，问题依次换成手册里的不同问题。
        bodies = [data["body"] for data in of(events, "request")]
        self.assertEqual([body["messages"][1]["content"].split("\n")[0] for body in bodies],
                         list(runtime.QUESTIONS[:4]))

    def test_warmup_sends_one_extra_request_and_unreported_is_never_zero(self):
        _, events = run_case("warmup", {"layout": "warmup", "repeats": 5})
        found = records(events)
        self.assertEqual([item["purpose"] for item in found], ["预热"] + ["测量"] * 5)
        self.assertIn(runtime.WARMUP_QUESTION, of(events, "request")[0]["body"]["messages"][1]["content"])
        # 这一组的夹具故意不返回缓存字段：每条都是“未报告”，不是 0。
        self.assertEqual(len(of(events, "lesson.cache_unreported")), 6)
        self.assertTrue(all(item["cached_tokens"] is None and item["ratio"] is None for item in found))
        data = report(events)
        rows = data["table"]["rows"]
        self.assertTrue(all(row[5] == "未报告" and row[6] == "未报告" for row in rows))
        self.assertNotIn(0, [row[5] for row in rows])
        checks = {check["label"]: check for check in data["checks"]}
        self.assertFalse(checks["每次响应都报告了缓存字段"]["passed"])
        self.assertIn("没有记成 0", checks["每次响应都报告了缓存字段"]["detail"])
        self.assertNotIn("报告命中的请求，前缀都在本次运行里发过", checks)
        metrics = {metric["label"]: metric["value"] for metric in data["metrics"]}
        self.assertEqual(metrics["测量请求中报告命中的次数"], "未报告")
        self.assertEqual(metrics["测量请求合计命中比例"], "未报告")
        self.assertEqual(metrics["缓存字段"], "未报告")

    def test_warmup_with_reported_fields_hits_on_every_measured_request(self):
        _, events = run_case("warmup", {"layout": "warmup"}, create_completion("warmup", style="openai"))
        found = records(events)
        self.assertEqual(found[0]["cached_tokens"], 0)
        self.assertTrue(all(item["cached_tokens"] > 0 for item in found[1:]))

    def test_other_providers_are_normalized_through_the_runner(self):
        for style, field in (("deepseek", "prompt_cache_hit_tokens"), ("anthropic", "cache_read_input_tokens")):
            with self.subTest(style=style):
                _, events = run_case("stable-prefix", {"layout": "stable_prefix"},
                                     create_completion("stable-prefix", style=style))
                found = records(events)
                self.assertEqual({item["field"] for item in found}, {field})
                self.assertEqual(found[0]["cached_tokens"], 0)
                self.assertTrue(all(item["cached_tokens"] > 0 for item in found[1:]))
                # 三家的“全部输入”口径不同，归一化后应一致。
                usage = of(events, "response")[1]["body"]["usage"]
                total = usage.get("prompt_tokens") or (usage["input_tokens"] + usage["cache_read_input_tokens"])
                self.assertEqual(found[1]["input_tokens"], total)

    def test_each_run_gets_its_own_session_marker_unless_isolation_is_off(self):
        shared = create_completion("stable-prefix")
        _, first = run_case("stable-prefix", {"layout": "stable_prefix"}, shared)
        _, second = run_case("stable-prefix", {"layout": "stable_prefix"}, shared)
        self.assertNotEqual(records(first)[0]["prefix_hash"], records(second)[0]["prefix_hash"])
        self.assertEqual(records(second)[0]["cached_tokens"], 0)
        # 关掉隔离：第二次运行的第一次请求就能复用上一次运行留下的前缀，报告会指出它来自本次运行之前。
        shared = create_completion("stable-prefix")
        _, first = run_case("stable-prefix", {"layout": "stable_prefix", "isolate_run": False}, shared)
        _, second = run_case("stable-prefix", {"layout": "stable_prefix", "isolate_run": False}, shared)
        self.assertEqual(records(first)[0]["prefix_hash"], records(second)[0]["prefix_hash"])
        self.assertGreater(records(second)[0]["cached_tokens"], 0)
        check = next(item for item in report(second)["checks"]
                     if item["label"] == "报告命中的请求，前缀都在本次运行里发过")
        self.assertFalse(check["passed"])
        self.assertIn("第 1 次", check["detail"])

    def test_live_mode_report_does_not_mention_the_fixture(self):
        _, events = run_case("stable-prefix", {"layout": "stable_prefix"}, mode="live")
        data = report(events)
        self.assertNotIn("夹具", data["summary"])
        self.assertEqual({metric["label"]: metric["value"] for metric in data["metrics"]}["运行模式"], "真实模型")

    def test_budget_cancel_and_inputs(self):
        self.assertGreaterEqual(MANIFEST["runtime"]["max_rounds"], 1 + 5)
        with self.assertRaisesRegex(RuntimeError, "超过 5 次"):
            run_case("warmup", {"layout": "warmup", "repeats": 5}, budget=5)
        with self.assertRaises(RunCancelled):
            run_case("stable-prefix", {"layout": "stable_prefix"}, cancelled=lambda: True)
        for bad in ({"layout": "random"}, {"repeats": 2}, {"repeats": 6}, {"extra": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)
        with self.assertRaises(ValueError):
            create_completion("unknown")


if __name__ == "__main__":
    unittest.main()
