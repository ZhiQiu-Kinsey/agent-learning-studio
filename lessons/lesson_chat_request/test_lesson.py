"""Behavior tests for chat-request: deterministic model data; they check the request body, response reading and the report."""
import json
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_chat_request import runtime
from lessons.lesson_chat_request.fixtures import create_completion
from lessons.lesson_chat_request.locales import texts_for

QUESTIONS = {"zh-CN": "用一句话解释什么是 Agent。", "en": "Explain in one sentence what an agent is."}
SYSTEM = {"zh-CN": "你是编程课的助教。回答简短、具体，不超过两句话。",
          "en": "You are a teaching assistant for a programming course. "
                "Keep answers short and concrete, two sentences at most."}


def run_case(exercise_id, inputs=None, completion=None, question=None, cancelled=lambda: False, locale="zh-CN"):
    events = []
    values = validate_inputs(runtime, {"system_prompt": SYSTEM[locale], **(inputs or {})})
    context = RunContext(
        lesson_id="chat-request", exercise_id=exercise_id,
        question=QUESTIONS[locale] if question is None else question, mode="offline",
        model="fixture-model", representation="http_body", inputs=values, api_key="secret-key-for-test",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=1,
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


class RequestBodyTests(unittest.TestCase):
    def test_basic_sends_system_then_user_and_no_key(self):
        answer, events = run_case("basic")
        requests = of(events, "request")
        self.assertEqual(len(requests), 1)
        body = requests[0]["body"]
        self.assertEqual(body["model"], "fixture-model")
        self.assertEqual([message["role"] for message in body["messages"]], ["system", "user"])
        self.assertEqual(body["messages"][1]["content"], "用一句话解释什么是 Agent。")
        self.assertNotIn("max_tokens", body)
        # The key goes only to the transport; the recorded body never contains it.
        self.assertNotIn("secret-key-for-test", json.dumps(events, ensure_ascii=False))
        self.assertEqual(answer, of(events, "response")[0]["body"]["choices"][0]["message"]["content"])
        self.assertEqual(of(events, "answer")[0]["content"], answer)

    def test_empty_system_prompt_sends_only_the_user_message(self):
        _, events = run_case("no-system", {"system_prompt": ""})
        body = of(events, "request")[0]["body"]
        self.assertEqual([message["role"] for message in body["messages"]], ["user"])
        self.assertEqual(metrics(events)["label_system"], "无")
        self.assertEqual(of(events, "lesson.report")[-1]["table"]["rows"], [[0, "user", "用一句话解释什么是 Agent。"]])

    def test_blank_question_falls_back_to_the_preset(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                _, events = run_case("basic", question="   ", locale=locale)
                self.assertEqual(of(events, "request")[0]["body"]["messages"][-1]["content"],
                                 texts_for(locale).default_question)

    def test_system_prompt_has_no_hidden_default(self):
        # The preset in lesson.json supplies it in the run's language; an omitted field is an input error.
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {})


class ResponseReadingTests(unittest.TestCase):
    def test_short_limit_is_sent_and_reported_as_length(self):
        answer, events = run_case("short-limit", {"max_tokens": 16})
        self.assertEqual(of(events, "request")[0]["body"]["max_tokens"], 16)
        values = metrics(events)
        self.assertEqual(values["label_finish_reason"], "length")
        self.assertEqual(values["label_reason_meaning"], "写到输出上限被截断")
        self.assertEqual(values["label_max_tokens"], 16)
        self.assertEqual(values["label_answer_length"], len(answer))

    def test_usage_comes_from_the_response(self):
        _, events = run_case("basic")
        usage = of(events, "response")[0]["body"]["usage"]
        values = metrics(events)
        self.assertEqual(values["label_prompt_tokens"], usage["prompt_tokens"])
        self.assertEqual(values["label_total_tokens"], usage["total_tokens"])
        self.assertNotIn("label_reasoning_tokens", values)

    def test_missing_usage_is_not_reported_rather_than_zero(self):
        def provider(body, key):
            return {"choices": [{"message": {"role": "assistant", "content": "OK."}, "finish_reason": "stop"}]}
        for locale, expected in (("zh-CN", "未报告"), ("en", "not reported")):
            with self.subTest(locale=locale):
                _, events = run_case("basic", completion=provider, locale=locale)
                values = metrics(events, locale)
                for label in ("label_prompt_tokens", "label_completion_tokens", "label_total_tokens"):
                    self.assertEqual(values[label], expected)

    def test_reasoning_tokens_are_listed_when_reported(self):
        def provider(body, key):
            return {"choices": [{"message": {"role": "assistant", "content": "answer", "reasoning_content": "abc"},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 30, "completion_tokens": 50, "total_tokens": 80,
                              "completion_tokens_details": {"reasoning_tokens": 40}}}
        answer, events = run_case("basic", completion=provider)
        values = metrics(events)
        self.assertEqual(values["label_reasoning_tokens"], 40)
        self.assertEqual(values["label_reasoning_chars"], 3)
        # Reasoning is not the answer.
        self.assertEqual(answer, "answer")

    def test_empty_content_is_reported_honestly(self):
        # A reasoning model with a tiny limit may be cut off before it answers: content is empty.
        def provider(body, key):
            return {"choices": [{"message": {"role": "assistant", "content": "", "reasoning_content": "We need"},
                                 "finish_reason": "length"}],
                    "usage": {"prompt_tokens": 51, "completion_tokens": 16, "total_tokens": 67,
                              "completion_tokens_details": {"reasoning_tokens": 16}}}
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                answer, events = run_case("short-limit", {"max_tokens": 16}, provider, locale=locale)
                self.assertEqual(answer, texts_for(locale).empty_content)
                values = metrics(events, locale)
                self.assertEqual(values["label_answer_length"], 0)
                self.assertEqual(values["label_finish_reason"], "length")
                self.assertEqual(values["label_reasoning_tokens"], 16)

    def test_malformed_response_raises_in_the_run_language(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale), self.assertRaisesRegex(ValueError, r"choices\[0\]"):
                run_case("basic", completion=lambda body, key: {"error": "x"}, locale=locale)


class EnglishRunTests(unittest.TestCase):
    def test_english_run_sends_and_reports_english(self):
        answer, events = run_case("short-limit", {"max_tokens": 16}, locale="en")
        body = of(events, "request")[0]["body"]
        self.assertEqual(body["messages"][0]["content"], SYSTEM["en"])
        self.assertEqual(body["messages"][1]["content"], QUESTIONS["en"])
        report = of(events, "lesson.report")[-1]
        self.assertEqual(report["title"], "Key fields of one request")
        self.assertEqual(metrics(events, "en")["label_reason_meaning"], "cut off at the output limit")
        self.assertEqual(report["table"]["columns"], ["#", "role", "content"])
        self.assertTrue(answer.startswith("[Offline"))


class BoundaryTests(unittest.TestCase):
    def test_inputs_are_bounded(self):
        for bad in ({"max_tokens": -1}, {"max_tokens": 5000}, {"system_prompt": "x" * 401}, {"extra": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, {"system_prompt": "ok", **bad})

    def test_cancel_stops_before_the_request(self):
        with self.assertRaises(RunCancelled):
            run_case("basic", cancelled=lambda: True)


if __name__ == "__main__":
    unittest.main()
