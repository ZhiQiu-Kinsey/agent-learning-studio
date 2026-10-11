"""Behavior tests for sampling-variance: deterministic model data; they check the unchanged request body, the count and the report."""
import json
import re
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_sampling_variance import runtime
from lessons.lesson_sampling_variance.fixtures import create_completion
from lessons.lesson_sampling_variance.locales import texts_for

CJK = re.compile(r"[　-〿一-鿿＀-￯]")


def run_case(exercise_id, inputs, completion=None, budget=5, question="", cancelled=lambda: False, locale="zh-CN"):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="sampling-variance", exercise_id=exercise_id, question=question, mode="offline",
        model="fixture-model", representation="http_body", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def metrics(events, locale="zh-CN"):
    """Report metrics keyed by catalog field name, so one assertion covers both languages."""
    t = texts_for(locale)
    names = {getattr(t, field): field for field in vars(t) if field.startswith("label_")}
    return {names[item["label"]]: item["value"] for item in of(events, "lesson.report")[-1]["metrics"]}


class SamplingTests(unittest.TestCase):
    def test_every_request_body_is_identical(self):
        _, events = run_case("high-temp", {"temperature": 1.3, "repeats": 5})
        bodies = [data["body"] for data in of(events, "request")]
        self.assertEqual(len(bodies), 5)
        self.assertTrue(all(body == bodies[0] for body in bodies))
        self.assertEqual(bodies[0]["temperature"], 1.3)
        self.assertEqual(bodies[0]["messages"][0]["content"], "你是起名助手。只输出一个店名，不加解释和标点。")
        self.assertEqual([number for kind, _, number in events if kind == "request"], [1, 2, 3, 4, 5])

    def test_distinct_answers_are_counted_from_responses(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                answer, events = run_case("high-temp", {"temperature": 1.3, "repeats": 5}, locale=locale)
                contents = [data["body"]["choices"][0]["message"]["content"] for data in of(events, "response")]
                values = metrics(events, locale)
                self.assertEqual(values["label_distinct"], len(set(contents)))
                self.assertEqual(values["label_distinct"], 4)
                self.assertEqual([row[1] for row in of(events, "lesson.report")[-1]["table"]["rows"]], contents)
                self.assertEqual(answer, texts_for(locale).answer.format(repeats=5, distinct=4))
        answer, _ = run_case("high-temp", {"temperature": 1.3, "repeats": 5})
        self.assertIn("4 种", answer)

    def test_low_temperature_fixture_repeats_one_answer(self):
        _, events = run_case("low-temp", {"temperature": 0, "repeats": 5})
        values = metrics(events)
        self.assertEqual(values["label_distinct"], 1)
        self.assertEqual(values["label_most_common"], "5 次")
        self.assertEqual(values["label_prompt_total"], 200)
        self.assertEqual(of(events, "lesson.report")[-1]["title"], "temperature=0：5 次回答")

    def test_count_strips_whitespace_but_not_punctuation(self):
        self.assertEqual(runtime.count_distinct(["喵星小铺", " 喵星小铺\n", "喵星小铺。"]), 2)

    def test_partial_usage_makes_the_total_unreported(self):
        for locale, expected in (("zh-CN", "未报告"), ("en", "not reported")):
            with self.subTest(locale=locale):
                calls = []

                def provider(body, key):
                    calls.append(1)
                    usage = ({"usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}}
                             if len(calls) == 1 else {})
                    return {"choices": [{"message": {"role": "assistant", "content": "name"},
                                         "finish_reason": "stop"}], **usage}
                _, events = run_case("low-temp", {"temperature": 0, "repeats": 2}, provider, locale=locale)
                self.assertEqual(metrics(events, locale)["label_prompt_total"], expected)
                self.assertEqual(of(events, "lesson.report")[-1]["table"]["rows"][1][2], expected)

    def test_question_box_is_the_user_message(self):
        _, events = run_case("low-temp", {"temperature": 0, "repeats": 2}, question="给咖啡店起名。")
        self.assertEqual(of(events, "request")[0]["body"]["messages"][1]["content"], "给咖啡店起名。")

    def test_blank_question_falls_back_to_the_preset(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                _, events = run_case("low-temp", {"temperature": 0, "repeats": 2}, question="  ", locale=locale)
                self.assertEqual(of(events, "request")[0]["body"]["messages"][1]["content"],
                                 texts_for(locale).default_question)


class EnglishRunTests(unittest.TestCase):
    def test_english_run_sends_and_reports_english(self):
        answer, events = run_case("low-temp", {"temperature": 0, "repeats": 5}, locale="en")
        body = of(events, "request")[0]["body"]
        self.assertEqual(body["messages"][0]["content"], texts_for("en").system_prompt)
        report = of(events, "lesson.report")[-1]
        self.assertEqual(report["title"], "temperature=0: 5 answers")
        self.assertEqual(metrics(events, "en")["label_most_common"], "5 times")
        self.assertEqual(report["table"]["columns"], ["#", "Answer", "Completion tokens"])
        self.assertTrue(answer.startswith("Sent the same request 5 times"))
        self.assertIsNone(CJK.search(json.dumps([data for _, data, _ in events], ensure_ascii=False)))

    def test_malformed_response_raises_in_the_run_language(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale), self.assertRaisesRegex(ValueError, r"choices\[0\]"):
                run_case("low-temp", {"temperature": 0, "repeats": 2}, lambda body, key: {"error": "x"},
                         locale=locale)


class BoundaryTests(unittest.TestCase):
    def test_inputs_are_bounded(self):
        for bad in ({"temperature": -0.1}, {"temperature": 2.5}, {"repeats": 1}, {"repeats": 6}, {"seed": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)

    def test_budget_and_cancel(self):
        with self.assertRaisesRegex(RuntimeError, "超过 3 次"):
            run_case("low-temp", {"temperature": 0, "repeats": 5}, budget=3)
        with self.assertRaises(RunCancelled):
            run_case("low-temp", {}, cancelled=lambda: True)


if __name__ == "__main__":
    unittest.main()
