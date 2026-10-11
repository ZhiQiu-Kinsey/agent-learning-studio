"""Behavior tests for prompt-caching: cache-field normalization, prefix hashes, and the three arms on the deterministic fixture."""
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_prompt_caching import runtime
from lessons.lesson_prompt_caching.cache_usage import hit_ratio, normalize_cache_usage
from lessons.lesson_prompt_caching.fixtures import create_completion
from lessons.lesson_prompt_caching.locales import texts_for
from server.selectors import resolve_path

MANIFEST = json.loads(Path(runtime.__file__).with_name("lesson.json").read_text(encoding="utf-8"))
ZH = texts_for("zh-CN")
HANDBOOK = runtime.load_handbook("zh-CN")


def build(layout, session, question, dynamic, locale="zh-CN"):
    return runtime.build_messages(texts_for(locale), runtime.load_handbook(locale), layout, session, question, dynamic)


def run_case(exercise_id, inputs, completion=None, budget=6, cancelled=lambda: False, mode="offline", locale="zh-CN"):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="prompt-caching", exercise_id=exercise_id, question="", mode=mode,
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
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
        # Without prompt_tokens, hits plus misses are the whole input.
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
        first = build("dynamic_first", "s1", "问题一", "请求序号：1")
        second = build("dynamic_first", "s1", "问题二", "请求序号：2")
        self.assertNotEqual(runtime.prefix_hash(first), runtime.prefix_hash(second))
        self.assertLess(runtime.shared_prefix_chars(first, second), 40)
        stable_one = build("stable_prefix", "s1", "问题一", "请求序号：1")
        stable_two = build("stable_prefix", "s1", "问题二", "请求序号：2")
        self.assertEqual(runtime.prefix_hash(stable_one), runtime.prefix_hash(stable_two))
        self.assertGreater(runtime.shared_prefix_chars(stable_one, stable_two), len(HANDBOOK))
        self.assertIsNone(runtime.shared_prefix_chars(None, stable_one))

    def test_three_layouts_send_the_same_rules_handbook_and_question(self):
        for layout in ("dynamic_first", "stable_prefix", "warmup"):
            with self.subTest(layout=layout):
                messages = build(layout, "s1", "问题一", "请求序号：1")
                self.assertEqual([message["role"] for message in messages], ["system", "user"])
                self.assertIn(HANDBOOK, messages[0]["content"])
                self.assertIn("问题一", messages[1]["content"])
        self.assertTrue(build("dynamic_first", "s1", "问", "请求序号：1")[0]["content"]
                        .startswith("请求序号：1"))
        self.assertTrue(build("stable_prefix", "s1", "问", "请求序号：1")[1]["content"]
                        .endswith("（请求序号：1）"))

    def test_session_marker_changes_the_prefix(self):
        one = build("stable_prefix", "aaaa", "问", "请求序号：1")
        two = build("stable_prefix", "bbbb", "问", "请求序号：1")
        self.assertNotEqual(runtime.prefix_hash(one), runtime.prefix_hash(two))

    def test_handbook_is_long_enough_to_matter(self):
        self.assertGreater(len(HANDBOOK), 1500)


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
        # Only the first hit carries first_hit: the find-the-error check "first reported hit" counts only that one.
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
        # The dynamic line is in the last user message; the question changes to a different handbook question each time.
        bodies = [data["body"] for data in of(events, "request")]
        self.assertEqual([body["messages"][1]["content"].split("\n")[0] for body in bodies],
                         list(ZH.questions[:4]))

    def test_prefix_hash_check_is_found_by_id_in_both_languages(self):
        # The lab selects the prefix-hash check by id; the explained-hits check is only added when hits are reported.
        for locale in ("zh-CN", "en"):
            for exercise, layout, same in (("dynamic-first", "dynamic_first", False), ("stable-prefix", "stable_prefix", True)):
                with self.subTest(locale=locale, layout=layout):
                    _, events = run_case(exercise, {"layout": layout}, locale=locale)
                    check = resolve_path({"data": report(events)}, "data.checks[id=prefix_hash]")
                    self.assertEqual((check["label"], check["passed"]), (texts_for(locale).check_hash, same))

    def test_prefix_hash_detail_agrees_with_the_number_of_hashes(self):
        # One shared hash gets its own sentence ("a single prefix hash"), never "1 distinct prefix hashes".
        en = texts_for("en")
        _, events = run_case("stable-prefix", {"layout": "stable_prefix"}, locale="en")
        detail = resolve_path({"data": report(events)}, "data.checks[id=prefix_hash]")["detail"]
        self.assertEqual(detail, "4 requests produced a single prefix hash.")
        _, events = run_case("warmup", {"layout": "warmup", "repeats": 4}, locale="en")
        detail = resolve_path({"data": report(events)}, "data.checks[id=prefix_hash]")["detail"]
        self.assertEqual(detail, "5 requests produced a single prefix hash (the warmup request included).")
        _, events = run_case("dynamic-first", {"layout": "dynamic_first"}, locale="en")
        detail = resolve_path({"data": report(events)}, "data.checks[id=prefix_hash]")["detail"]
        self.assertEqual(detail, en.check_hash_detail.format(count=4, distinct=4, suffix=en.hash_suffix_plain))
        self.assertEqual(detail, "4 requests produced 4 distinct prefix hashes.")
        # Chinese also gives the single-hash case its own sentence.
        for layout, exercise, expected in (("stable_prefix", "stable-prefix", "4 次请求只出现了 1 个前缀哈希。"),
                                           ("dynamic_first", "dynamic-first", "4 次请求共出现 4 个不同的前缀哈希。")):
            _, events = run_case(exercise, {"layout": layout})
            detail = resolve_path({"data": report(events)}, "data.checks[id=prefix_hash]")["detail"]
            self.assertEqual(detail, expected)

    def test_warmup_sends_one_extra_request_and_unreported_is_never_zero(self):
        _, events = run_case("warmup", {"layout": "warmup", "repeats": 5})
        found = records(events)
        self.assertEqual([item["purpose"] for item in found], ["预热"] + ["测量"] * 5)
        self.assertIn(ZH.warmup_question, of(events, "request")[0]["body"]["messages"][1]["content"])
        # This arm's fixture deliberately returns no cache field: every record is "not reported", never 0.
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
                # The three providers count "all input" differently; after normalization they agree.
                usage = of(events, "response")[1]["body"]["usage"]
                total = usage.get("prompt_tokens") or (usage["input_tokens"] + usage["cache_read_input_tokens"])
                self.assertEqual(found[1]["input_tokens"], total)

    def test_each_run_gets_its_own_session_marker_unless_isolation_is_off(self):
        shared = create_completion("stable-prefix")
        _, first = run_case("stable-prefix", {"layout": "stable_prefix"}, shared)
        _, second = run_case("stable-prefix", {"layout": "stable_prefix"}, shared)
        self.assertNotEqual(records(first)[0]["prefix_hash"], records(second)[0]["prefix_hash"])
        self.assertEqual(records(second)[0]["cached_tokens"], 0)
        # Isolation off: the second run's first request reuses the prefix left by the first run, and the report
        # points out that the hit comes from before this run.
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


class EnglishRunTests(unittest.TestCase):
    """The same arms in English: the English handbook, rules and questions are sent, the report is English."""

    def metrics(self, events, locale="en"):
        """Report metrics keyed by catalog field name, so one assertion covers both languages."""
        t = texts_for(locale)
        names = {getattr(t, field): field for field in vars(t) if field.startswith("label_")}
        return {names[item["label"]]: item["value"] for item in report(events)["metrics"]}

    def test_english_handbook_and_rules_are_sent(self):
        t = texts_for("en")
        handbook = runtime.load_handbook("en")
        self.assertNotEqual(handbook, HANDBOOK)
        self.assertGreater(len(handbook), 1500)
        answer, events = run_case("stable-prefix", {"layout": "stable_prefix"}, locale="en")
        bodies = [data["body"] for data in of(events, "request")]
        system = bodies[0]["messages"][0]["content"]
        self.assertTrue(system.startswith("Session tag: "))
        self.assertIn(t.rules + "\n\n" + handbook, system)
        self.assertEqual([body["messages"][1]["content"].split("\n")[0] for body in bodies], list(t.questions[:4]))
        self.assertTrue(bodies[0]["messages"][1]["content"].endswith(")"))
        self.assertEqual([item["purpose"] for item in records(events)], [t.purpose_measure] * 4)
        self.assertEqual(answer, t.answer.format(count=4, layout="Stable prefix"))
        values = self.metrics(events)
        self.assertEqual(values["label_mode"], t.value_mode_offline)
        self.assertEqual(values["label_hits"], 3)

    def test_english_warmup_and_unreported(self):
        t = texts_for("en")
        _, events = run_case("warmup", {"layout": "warmup"}, locale="en")
        self.assertEqual(of(events, "request")[0]["body"]["messages"][1]["content"].split("\n")[0], t.warmup_question)
        self.assertEqual([item["purpose"] for item in records(events)], [t.purpose_warmup] + [t.purpose_measure] * 4)
        rows = report(events)["table"]["rows"]
        self.assertTrue(all(row[5] == "not reported" and row[6] == "not reported" for row in rows))
        self.assertEqual(self.metrics(events)["label_ratio"], "not reported")
        checks = {check["label"]: check for check in report(events)["checks"]}
        self.assertIn("instead of recording 0", checks[t.check_reported]["detail"])

    def test_english_dynamic_line_comes_first_and_session_tag_when_not_isolated(self):
        t = texts_for("en")
        _, events = run_case("dynamic-first", {"layout": "dynamic_first", "isolate_run": False}, locale="en")
        system = of(events, "request")[0]["body"]["messages"][0]["content"]
        self.assertTrue(system.startswith("Request number: 1; sent at: "))
        self.assertIn(t.session_tag.format(session=t.not_isolated), system)
        self.assertEqual(self.metrics(events)["label_session"], t.not_isolated)


if __name__ == "__main__":
    unittest.main()
