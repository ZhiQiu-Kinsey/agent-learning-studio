"""“采样与不确定性”的行为测试：确定性模型数据，检查请求体不变、统计与报告。"""
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_sampling_variance import runtime
from lessons.lesson_sampling_variance.fixtures import create_completion


def run_case(exercise_id, inputs, completion=None, budget=5, question="", cancelled=lambda: False):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="sampling-variance", exercise_id=exercise_id, question=question, mode="offline",
        model="fixture-model", representation="http_body", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def metrics(events):
    return {item["label"]: item["value"] for item in of(events, "lesson.report")[-1]["metrics"]}


class SamplingTests(unittest.TestCase):
    def test_every_request_body_is_identical(self):
        _, events = run_case("high-temp", {"temperature": 1.3, "repeats": 5})
        bodies = [data["body"] for data in of(events, "request")]
        self.assertEqual(len(bodies), 5)
        self.assertTrue(all(body == bodies[0] for body in bodies))
        self.assertEqual(bodies[0]["temperature"], 1.3)
        self.assertEqual([number for kind, _, number in events if kind == "request"], [1, 2, 3, 4, 5])

    def test_distinct_answers_are_counted_from_responses(self):
        answer, events = run_case("high-temp", {"temperature": 1.3, "repeats": 5})
        contents = [data["body"]["choices"][0]["message"]["content"] for data in of(events, "response")]
        self.assertEqual(metrics(events)["不同回答数"], len(set(contents)))
        self.assertEqual(metrics(events)["不同回答数"], 4)
        self.assertEqual([row[1] for row in of(events, "lesson.report")[-1]["table"]["rows"]], contents)
        self.assertIn("4 种", answer)

    def test_low_temperature_fixture_repeats_one_answer(self):
        _, events = run_case("low-temp", {"temperature": 0, "repeats": 5})
        self.assertEqual(metrics(events)["不同回答数"], 1)
        self.assertEqual(metrics(events)["出现最多的回答"], "5 次")
        self.assertEqual(metrics(events)["提示 Token 合计"], 200)

    def test_count_strips_whitespace_but_not_punctuation(self):
        self.assertEqual(runtime.count_distinct(["喵星小铺", " 喵星小铺\n", "喵星小铺。"]), 2)

    def test_partial_usage_makes_the_total_unreported(self):
        calls = []

        def provider(body, key):
            calls.append(1)
            usage = {"usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}} if len(calls) == 1 else {}
            return {"choices": [{"message": {"role": "assistant", "content": "店名"}, "finish_reason": "stop"}], **usage}
        _, events = run_case("low-temp", {"temperature": 0, "repeats": 2}, provider)
        values = metrics(events)
        self.assertEqual(values["提示 Token 合计"], "未报告")
        self.assertEqual(of(events, "lesson.report")[-1]["table"]["rows"][1][2], "未报告")

    def test_question_box_is_the_user_message(self):
        _, events = run_case("low-temp", {"temperature": 0, "repeats": 2}, question="给咖啡店起名。")
        self.assertEqual(of(events, "request")[0]["body"]["messages"][1]["content"], "给咖啡店起名。")


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
