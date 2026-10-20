"""Behavior tests for observability-cost: deterministic model data; the tools, the ledger and the analysis really run in Python."""
import json
import re
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_observability_cost import runtime
from lessons.lesson_observability_cost.fixtures import create_completion
from lessons.lesson_observability_cost.locales import texts_for
from server.envelope import SpanTracker

LOCALES = ("zh-CN", "en")
EXERCISES = {"baseline": {"strategy": "baseline"}, "tool-cache": {"strategy": "tool_cache"},
             "batched-compare": {"strategy": "batched", "compare_with_baseline": True}}
CJK = re.compile(r"[　-〿一-鿿＀-￯]")


def run_case(exercise_id, inputs=None, *, locale="zh-CN", completion=None, budget=8, mode="offline",
             cancelled=lambda: False, **fixture):
    events = []
    # A short simulated latency keeps the tests fast; the slow tool is still clearly the slowest step offline.
    values = validate_inputs(runtime, {"rate_latency_ms": 15, **EXERCISES.get(exercise_id, {}), **(inputs or {})})
    context = RunContext(
        lesson_id="observability-cost", exercise_id=exercise_id, question="", mode=mode, model="fixture-model",
        representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale, **fixture), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)), locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def report(events, title_field, strategy, locale="zh-CN"):
    t = texts_for(locale)
    title = getattr(t, title_field).format(strategy=t.strategy_names[strategy])
    return next(data for data in of(events, "lesson.report") if data["title"] == title)


def by_id(items, item_id):
    return next(item for item in items if item.get("id") == item_id)


def reply(text, usage=None):
    response = {"choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]}
    if usage is not None:
        response["usage"] = usage
    return response


class UsageTests(unittest.TestCase):
    def test_openai_and_anthropic_names(self):
        self.assertEqual(runtime.read_usage({"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}),
                         {"input_tokens": 10, "output_tokens": 3, "total_tokens": 13})
        self.assertEqual(runtime.read_usage({"input_tokens": 7, "output_tokens": 2}),
                         {"input_tokens": 7, "output_tokens": 2, "total_tokens": 9})

    def test_missing_usage_is_none_not_zero(self):
        empty = {"input_tokens": None, "output_tokens": None, "total_tokens": None}
        self.assertEqual(runtime.read_usage(None), empty)
        self.assertEqual(runtime.read_usage({}), empty)
        self.assertEqual(runtime.read_usage({"prompt_tokens": 5}), {"input_tokens": 5, "output_tokens": None,
                                                                    "total_tokens": None})

    def test_reported_zero_stays_zero_and_odd_values_are_not_guessed(self):
        self.assertEqual(runtime.read_usage({"prompt_tokens": 0, "completion_tokens": 0})["total_tokens"], 0)
        odd = runtime.read_usage({"prompt_tokens": True, "completion_tokens": "3", "total_tokens": -1})
        self.assertEqual(odd, {"input_tokens": None, "output_tokens": None, "total_tokens": None})

    def test_fingerprint_ignores_key_order_but_not_values(self):
        self.assertEqual(runtime.fingerprint("lookup_rate", {"a": 1, "b": 2}),
                         runtime.fingerprint("lookup_rate", {"b": 2, "a": 1}))
        self.assertNotEqual(runtime.fingerprint("lookup_rate", {"currency": "USD"}),
                            runtime.fingerprint("lookup_rate", {"currency": "CNY"}))
        self.assertNotEqual(runtime.fingerprint("lookup_rate", {"x": 1}), runtime.fingerprint("category_limit", {"x": 1}))


class ToolTests(unittest.TestCase):
    def test_tools_return_values_and_raise_on_bad_input(self):
        t = texts_for("en")
        self.assertEqual(runtime.lookup_rate(t, 0, currency="USD"),
                         {"currency": "USD", "rate": 7.1, "simulated_latency_ms": 0})
        self.assertEqual(runtime.category_limit(t, category="meals"), {"category": "meals", "limit": 200.0})
        with self.assertRaisesRegex(ValueError, "JPY"):
            runtime.lookup_rate(t, 0, currency="JPY")
        with self.assertRaisesRegex(ValueError, "taxi"):
            runtime.category_limit(t, category="taxi")

    def test_grade_names_the_first_failure(self):
        receipt = runtime.RECEIPTS[1]
        rate = {"ok": True, "result": {"rate": 7.1}}
        limit = {"ok": True, "result": {"limit": 1200.0}}
        self.assertEqual(runtime.grade(receipt, "lodging", rate, limit)["reason"], "ok")
        self.assertEqual(runtime.grade(receipt, None, rate, None)["reason"], "unparsed")
        self.assertEqual(runtime.grade(receipt, "taxi", rate, {"ok": False})["reason"], "tool_error")
        self.assertEqual(runtime.grade(receipt, "meals", rate, {"ok": True, "result": {"limit": 200.0}})["reason"],
                         "wrong_category")
        self.assertEqual(runtime.grade(receipt, "lodging", {"ok": True, "result": {"rate": 1.0}}, limit)["reason"],
                         "wrong_amount")


class StrategyTests(unittest.TestCase):
    def test_baseline_repeats_tools_and_one_request(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_case("baseline", locale=locale)
                requests = of(events, "request")
                self.assertEqual(len(requests), 4)
                self.assertEqual(len(of(events, "tool_call")), 8)
                # r4 has r1's description: the request bodies are identical, the fingerprints too.
                self.assertEqual(requests[3]["body"], requests[0]["body"])
                rows = of(events, "lesson.ledger")[0]["rows"]
                groups = runtime.repeated_groups(rows)
                self.assertEqual(sorted((g["name"], len(g["steps"])) for g in groups),
                                 [("category_limit", 2), ("fixture-model", 2), ("lookup_rate", 3)])
                bottleneck = report(events, "bottleneck_title", "baseline", locale)
                self.assertFalse(by_id(bottleneck["checks"], "no_repeats")["passed"])
                self.assertIn("lookup_rate", by_id(bottleneck["metrics"], "slowest_step")["value"])
                self.assertIn("4/4", answer)

    def test_every_ledger_row_points_at_its_platform_events(self):
        _, events = run_case("baseline")
        rows = of(events, "lesson.ledger")[0]["rows"]
        tracker, spans = SpanTracker(), {}
        for kind, data, number in events:
            span_id, parent, _ = tracker.place(kind, data, number)
            if kind == "tool_call":
                spans[data["id"]] = (number, parent)
        request_rounds = [number for kind, _, number in events if kind == "request"]
        for row in rows:
            if row["kind"] == "tool":
                # The correlation ID is the tool_call id; its tool span hangs under the step of the same round.
                round_number, parent = spans[row["call_id"]]
                self.assertEqual(round_number, row["step"])
                self.assertTrue(parent.startswith("step-"))
            else:
                self.assertIn(row["step"], request_rounds)
        self.assertEqual(sorted(spans), sorted(row["call_id"] for row in rows if row["kind"] == "tool"))

    def test_tool_cache_changes_only_the_tool_calls(self):
        _, base = run_case("baseline")
        _, cached = run_case("tool-cache")
        self.assertEqual(len(of(cached, "tool_call")), 5)
        self.assertEqual(len(of(cached, "request")), len(of(base, "request")))
        rows = of(cached, "lesson.ledger")[0]["rows"]
        hits = [row for row in rows if row["kind"] == "cache"]
        self.assertEqual([(row["name"], row["step"]) for row in hits],
                         [("lookup_rate", 2), ("lookup_rate", 4), ("category_limit", 4)])
        self.assertTrue(all(row["call_id"] is None for row in hits))
        ledger = report(cached, "ledger_title", "tool_cache")
        self.assertEqual(by_id(ledger["metrics"], "cache_hits")["value"], 3)
        self.assertTrue(by_id(ledger["checks"], "quality")["passed"])
        # The identical model request is still there: the tool cache does not touch it.
        groups = runtime.repeated_groups(rows)
        self.assertEqual([(g["kind"], g["steps"]) for g in groups], [("llm", [1, 4])])

    def test_batched_compare_runs_both_passes_on_the_same_set(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("batched-compare", locale=locale)
                requests = of(events, "request")
                self.assertEqual(len(requests), 5)
                self.assertEqual(requests[4]["body"]["messages"][0]["content"], t.batch_system)
                self.assertEqual([n for k, _, n in events if k == "request"], [1, 2, 3, 4, 5])
                compare = of(events, "lesson.report")[-1]
                self.assertTrue(by_id(compare["checks"], "no_regression")["passed"])
                self.assertEqual(by_id(compare["metrics"], "regressions")["value"], t.value_none)
                calls = next(row for row in compare["table"]["rows"] if row[0] == t.row_model_calls)
                self.assertEqual(calls[1:], [4, 1, -3])
                self.assertIn(t.check_no_regression_ok, answer)

    def test_regression_is_reported_when_the_batched_request_mislabels(self):
        t = texts_for("zh-CN")
        answer, events = run_case("batched-compare", mislabel={"r2": "meals"})
        compare = of(events, "lesson.report")[-1]
        self.assertFalse(by_id(compare["checks"], "no_regression")["passed"])
        self.assertFalse(by_id(compare["checks"], "no_more_failures")["passed"])
        self.assertEqual(by_id(compare["metrics"], "regressions")["value"], "r2")
        cases = of(events, "lesson.ledger")[-1]["cases"]
        self.assertEqual(next(c for c in cases if c["receipt"] == "r2")["reason"], "wrong_category")
        self.assertIn("r2", answer)
        self.assertIn(t.reason_names["wrong_category"], json.dumps(of(events, "lesson.report")[2], ensure_ascii=False))


class HonestyTests(unittest.TestCase):
    def test_unreported_usage_is_never_zero(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                _, events = run_case("baseline", locale=locale, usage_style="none")
                ledger = report(events, "ledger_title", "baseline", locale)
                self.assertEqual(by_id(ledger["metrics"], "total_tokens")["value"], t.value_not_reported)
                self.assertEqual(by_id(ledger["metrics"], "unreported_calls")["value"], 4)
                self.assertFalse(by_id(ledger["checks"], "usage_reported")["passed"])
                llm_cells = [row[7] for row in ledger["table"]["rows"] if row[1] == t.kind_names["llm"]]
                self.assertEqual(llm_cells, [t.value_not_reported] * 4)
                tool_cells = {row[7] for row in ledger["table"]["rows"] if row[1] == t.kind_names["tool"]}
                self.assertEqual(tool_cells, {t.value_not_applicable})
                bottleneck = report(events, "bottleneck_title", "baseline", locale)
                self.assertEqual(by_id(bottleneck["metrics"], "repeat_tokens")["value"], t.value_not_reported)

    def test_partly_reported_total_says_how_many_are_missing(self):
        t = texts_for("zh-CN")
        _, events = run_case("baseline", usage_style="partial")
        rows = of(events, "lesson.ledger")[0]["rows"]
        known = sum(row["total_tokens"] for row in rows if row["kind"] == "llm" and row["total_tokens"] is not None)
        ledger = report(events, "ledger_title", "baseline")
        self.assertEqual(by_id(ledger["metrics"], "total_tokens")["value"],
                         t.tokens_partly_reported.format(total=known, missing=1))
        self.assertIn("2", by_id(ledger["checks"], "usage_reported")["detail"])

    def test_cost_needs_a_named_price_table(self):
        t = texts_for("en")
        _, events = run_case("baseline", locale="en")
        self.assertEqual(by_id(report(events, "ledger_title", "baseline", "en")["metrics"], "cost")["value"], t.cost_none)
        prices = {"price_input_per_m": 2.0, "price_output_per_m": 8.0, "price_currency": "USD",
                  "price_source": "provider price page", "price_date": "2026-10-01"}
        _, events = run_case("baseline", prices, locale="en")
        rows = of(events, "lesson.ledger")[0]["rows"]
        expected = round(sum(r["input_tokens"] * 2.0 + r["output_tokens"] * 8.0 for r in rows if r["kind"] == "llm")
                         / 1_000_000, 6)
        value = by_id(report(events, "ledger_title", "baseline", "en")["metrics"], "cost")["value"]
        for part in (str(expected), "USD", "fixture-model", "provider price page", "2026-10-01", "4/4"):
            self.assertIn(part, value)
        _, events = run_case("baseline", prices, locale="en", usage_style="none")
        self.assertEqual(by_id(report(events, "ledger_title", "baseline", "en")["metrics"], "cost")["value"],
                         t.cost_no_usage)

    def test_offline_note_only_in_offline_mode(self):
        t = texts_for("zh-CN")
        _, events = run_case("baseline")
        self.assertIn(t.offline_note, report(events, "ledger_title", "baseline")["summary"])
        _, events = run_case("baseline", mode="live")
        ledger = report(events, "ledger_title", "baseline")
        self.assertNotIn(t.offline_note, ledger["summary"])
        self.assertEqual(by_id(ledger["metrics"], "mode")["value"], t.mode_live)

    def test_english_events_have_no_chinese(self):
        for exercise in EXERCISES:
            with self.subTest(exercise=exercise):
                answer, events = run_case(exercise, locale="en")
                self.assertIsNone(CJK.search(json.dumps([answer, events], ensure_ascii=False)))


class FailureTests(unittest.TestCase):
    def test_unparsed_reply_skips_the_limit_tool(self):
        completion = lambda body, api_key: reply("I think it is travel.", {"total_tokens": 9})
        _, events = run_case("baseline", completion=completion)
        names = [data["function"]["name"] for data in of(events, "tool_call")]
        self.assertEqual(names, ["lookup_rate"] * 4)
        cases = of(events, "lesson.ledger")[0]["cases"]
        self.assertEqual({case["reason"] for case in cases}, {"unparsed"})
        self.assertFalse(by_id(report(events, "ledger_title", "baseline")["checks"], "quality")["passed"])

    def test_unknown_category_becomes_a_structured_tool_error(self):
        completion = lambda body, api_key: reply('{"category": "taxi"}', {"total_tokens": 9})
        _, events = run_case("baseline", completion=completion, locale="en")
        results = [data["result"] for data in of(events, "tool_result") if data["name"] == "category_limit"]
        self.assertEqual(len(results), 4)
        self.assertTrue(all(not r["ok"] and r["error_type"] == "ValueError" and "taxi" in r["error"] for r in results))
        rows = of(events, "lesson.ledger")[0]["rows"]
        self.assertEqual({row["status"] for row in rows if row["name"] == "category_limit"}, {"error"})
        self.assertEqual({case["reason"] for case in of(events, "lesson.ledger")[0]["cases"]}, {"tool_error"})

    def test_model_budget_and_cancel(self):
        with self.assertRaises(RuntimeError):
            run_case("baseline", budget=3)
        with self.assertRaises(RunCancelled):
            run_case("baseline", cancelled=lambda: True)

    def test_inputs_are_validated(self):
        for bad in ({"strategy": "baseline", "compare_with_baseline": True}, {"strategy": "cache"},
                    {"price_source": "page"}, {"price_date": "2026-10-01"},
                    {"price_source": "page", "price_date": "2026-13-01"},
                    {"price_source": "page", "price_date": "20261001"},
                    {"rate_latency_ms": 5000}, {"price_input_per_m": -1}, {"extra": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                runtime.Inputs.model_validate(bad)
        self.assertEqual(runtime.Inputs.model_validate({}).strategy, "baseline")


if __name__ == "__main__":
    unittest.main()
