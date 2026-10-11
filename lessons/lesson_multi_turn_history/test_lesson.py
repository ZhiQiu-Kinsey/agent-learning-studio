"""Behavior tests for multi-turn-history: deterministic model data; they check the messages each turn really sent and the report."""
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_multi_turn_history import runtime
from lessons.lesson_multi_turn_history.fixtures import create_completion
from lessons.lesson_multi_turn_history.locales import texts_for


def run_case(exercise_id, inputs, completion=None, budget=3, cancelled=lambda: False, locale="zh-CN"):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="multi-turn-history", exercise_id=exercise_id, question="", mode="offline",
        model="fixture-model", representation="http_body", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def requests(events):
    return [(data["body"]["messages"], number) for kind, data, number in events if kind == "request"]


def report(events):
    return [data for kind, data, _ in events if kind == "lesson.report"][-1]


def by_field(items, locale="zh-CN"):
    """Report checks or metrics keyed by catalog field name, so one assertion covers both languages."""
    t = texts_for(locale)
    names = {getattr(t, field): field for field in vars(t) if field.startswith(("label_", "check_"))}
    return {names[item["label"]]: item.get("passed", item.get("value")) for item in items}


class HistoryTests(unittest.TestCase):
    def test_with_history_resends_the_first_turn(self):
        answer, events = run_case("with-history", {"history": "full", "turns": 2})
        sent = requests(events)
        self.assertEqual([number for _, number in sent], [1, 2])
        first, second = sent[0][0], sent[1][0]
        self.assertEqual([m["role"] for m in first], ["system", "user"])
        self.assertEqual([m["role"] for m in second], ["system", "user", "assistant", "user"])
        # Turn 1's answer goes back into the turn 2 request unchanged.
        first_reply = [d for k, d, _ in events if k == "response"][0]["body"]["choices"][0]["message"]["content"]
        self.assertEqual(second[2]["content"], first_reply)
        self.assertIn("团子", answer)
        checks = by_field(report(events)["checks"])
        self.assertTrue(checks["check_fact_sent"])
        self.assertTrue(checks["check_fact_answered"])

    def test_without_history_only_sends_the_latest_question(self):
        answer, events = run_case("without-history", {"history": "latest_only", "turns": 2})
        sent = requests(events)
        # Turn 1 is identical in both arms; they differ only in what turn 2 sends.
        self.assertEqual(sent[0][0], requests(run_case("with-history", {"history": "full", "turns": 2})[1])[0][0])
        self.assertEqual([m["role"] for m in sent[1][0]], ["system", "user"])
        self.assertEqual(sent[1][0][1]["content"], texts_for("zh-CN").turns[1])
        self.assertNotIn("团子", answer)
        self.assertFalse(by_field(report(events)["checks"])["check_fact_sent"])

    def test_three_turns_grow_and_report_each_prompt(self):
        answer, events = run_case("three-turns", {"history": "full", "turns": 3})
        sent = requests(events)
        self.assertEqual([len(messages) for messages, _ in sent], [2, 4, 6])
        rows = report(events)["table"]["rows"]
        prompts = [row[3] for row in rows]
        self.assertEqual(len(rows), 3)
        # The reported message count must equal what was really sent (the answer appended afterwards doesn't count).
        self.assertEqual([row[1] for row in rows], [2, 4, 6])
        self.assertEqual(by_field(report(events)["metrics"])["label_last_message_count"], 6)
        self.assertTrue(prompts[0] < prompts[1] < prompts[2])
        usage = [d["body"]["usage"]["prompt_tokens"] for k, d, _ in events if k == "response"]
        self.assertEqual(prompts, usage)
        self.assertIn("三岁", answer)

    def test_recorded_requests_are_snapshots(self):
        # Appending to history later does not change requests already recorded.
        _, events = run_case("three-turns", {"history": "full", "turns": 3})
        self.assertEqual(len(requests(events)[0][0]), 2)

    def test_missing_usage_is_unreported(self):
        def provider(body, key):
            return {"choices": [{"message": {"role": "assistant", "content": "好"}, "finish_reason": "stop"}]}
        _, events = run_case("with-history", {"history": "full", "turns": 2}, provider)
        data = report(events)
        self.assertEqual(data["table"]["rows"][0][3], "未报告")
        self.assertEqual(by_field(data["metrics"])["label_prompt_growth"], "未报告")


class EnglishRunTests(unittest.TestCase):
    def test_english_run_sends_and_reports_in_english(self):
        t = texts_for("en")
        answer, events = run_case("with-history", {"history": "full", "turns": 2}, locale="en")
        second = requests(events)[1][0]
        self.assertEqual(second[0]["content"], t.system_prompt)
        self.assertEqual([m["content"] for m in second if m["role"] == "user"], list(t.turns[:2]))
        self.assertIn(t.fact, answer)
        data = report(events)
        self.assertEqual((data["title"], data["summary"]), (t.report_title, t.summary_full))
        self.assertEqual(data["table"]["columns"], list(t.columns))
        self.assertEqual(data["table"]["rows"][1][2], t.value_yes)
        checks = by_field(data["checks"], "en")
        self.assertTrue(checks["check_fact_sent"] and checks["check_fact_answered"])
        metrics = by_field(data["metrics"], "en")
        self.assertEqual((metrics["label_mode"], metrics["label_note"]), (t.mode_values["full"], t.value_empty))

    def test_english_without_history_and_missing_usage(self):
        t = texts_for("en")
        answer, events = run_case("without-history", {"history": "latest_only", "turns": 2}, locale="en")
        self.assertNotIn(t.fact, answer)
        self.assertEqual(report(events)["summary"], t.summary_latest_only)
        self.assertFalse(by_field(report(events)["checks"], "en")["check_fact_sent"])

        def provider(body, key):
            return {"choices": [{"message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}]}
        _, events = run_case("with-history", {"history": "full", "turns": 2}, provider, locale="en")
        self.assertEqual(by_field(report(events)["metrics"], "en")["label_prompt_growth"], "not reported")
        with self.assertRaisesRegex(ValueError, "choices"):
            run_case("with-history", {}, lambda body, key: {}, locale="en")


class BoundaryTests(unittest.TestCase):
    def test_inputs_are_bounded(self):
        for bad in ({"turns": 1}, {"turns": 4}, {"history": "summary"}, {"extra": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)

    def test_budget_and_cancel(self):
        with self.assertRaisesRegex(RuntimeError, "超过 2 次"):
            run_case("three-turns", {"history": "full", "turns": 3}, budget=2)
        with self.assertRaises(RunCancelled):
            run_case("with-history", {}, cancelled=lambda: True)

    def test_malformed_response_raises(self):
        with self.assertRaisesRegex(ValueError, "choices"):
            run_case("with-history", {}, lambda body, key: {})


if __name__ == "__main__":
    unittest.main()
