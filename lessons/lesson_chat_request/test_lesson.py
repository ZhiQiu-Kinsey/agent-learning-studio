"""“一次模型请求”的行为测试：确定性模型数据，只检查请求体、响应读取与报告。"""
import json
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_chat_request import runtime
from lessons.lesson_chat_request.fixtures import create_completion


def run_case(exercise_id, inputs, completion=None, question="用一句话解释什么是 Agent。", cancelled=lambda: False):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="chat-request", exercise_id=exercise_id, question=question, mode="offline",
        model="fixture-model", representation="http_body", inputs=values, api_key="secret-key-for-test",
        completion=completion or create_completion(exercise_id, values), max_model_calls=1,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def metrics(events):
    return {item["label"]: item["value"] for item in of(events, "lesson.report")[-1]["metrics"]}


class RequestBodyTests(unittest.TestCase):
    def test_basic_sends_system_then_user_and_no_key(self):
        answer, events = run_case("basic", {})
        requests = of(events, "request")
        self.assertEqual(len(requests), 1)
        body = requests[0]["body"]
        self.assertEqual(body["model"], "fixture-model")
        self.assertEqual([message["role"] for message in body["messages"]], ["system", "user"])
        self.assertEqual(body["messages"][1]["content"], "用一句话解释什么是 Agent。")
        self.assertNotIn("max_tokens", body)
        # 密钥只交给传输层，记录下来的请求体里没有它。
        self.assertNotIn("secret-key-for-test", json.dumps(events, ensure_ascii=False))
        self.assertEqual(answer, of(events, "response")[0]["body"]["choices"][0]["message"]["content"])
        self.assertEqual(of(events, "answer")[0]["content"], answer)

    def test_empty_system_prompt_sends_only_the_user_message(self):
        _, events = run_case("no-system", {"system_prompt": ""})
        body = of(events, "request")[0]["body"]
        self.assertEqual([message["role"] for message in body["messages"]], ["user"])
        self.assertEqual(metrics(events)["system 消息"], "无")
        self.assertEqual(of(events, "lesson.report")[-1]["table"]["rows"], [[0, "user", "用一句话解释什么是 Agent。"]])

    def test_blank_question_falls_back_to_the_preset(self):
        _, events = run_case("basic", {}, question="   ")
        self.assertEqual(of(events, "request")[0]["body"]["messages"][-1]["content"], runtime.DEFAULT_QUESTION)


class ResponseReadingTests(unittest.TestCase):
    def test_short_limit_is_sent_and_reported_as_length(self):
        answer, events = run_case("short-limit", {"max_tokens": 16})
        self.assertEqual(of(events, "request")[0]["body"]["max_tokens"], 16)
        values = metrics(events)
        self.assertEqual(values["finish_reason"], "length")
        self.assertEqual(values["结束原因的含义"], "写到输出上限被截断")
        self.assertEqual(values["max_tokens"], 16)
        self.assertEqual(values["回答长度（字符）"], len(answer))

    def test_usage_comes_from_the_response(self):
        _, events = run_case("basic", {})
        usage = of(events, "response")[0]["body"]["usage"]
        values = metrics(events)
        self.assertEqual(values["提示 Token"], usage["prompt_tokens"])
        self.assertEqual(values["总 Token"], usage["total_tokens"])
        self.assertNotIn("其中推理 Token", values)

    def test_missing_usage_is_unreported_not_zero(self):
        def provider(body, key):
            return {"choices": [{"message": {"role": "assistant", "content": "好的。"}, "finish_reason": "stop"}]}
        _, events = run_case("basic", {}, provider)
        values = metrics(events)
        for label in ("提示 Token", "完成 Token", "总 Token"):
            self.assertEqual(values[label], "未报告")

    def test_reasoning_tokens_are_listed_when_reported(self):
        def provider(body, key):
            return {"choices": [{"message": {"role": "assistant", "content": "回答", "reasoning_content": "先想想"},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 30, "completion_tokens": 50, "total_tokens": 80,
                              "completion_tokens_details": {"reasoning_tokens": 40}}}
        answer, events = run_case("basic", {}, provider)
        values = metrics(events)
        self.assertEqual(values["其中推理 Token"], 40)
        self.assertEqual(values["推理内容（字符）"], 3)
        # 推理内容不是回答。
        self.assertEqual(answer, "回答")

    def test_empty_content_is_reported_honestly(self):
        # 先推理的模型在上限很小时，可能推理还没写完就被截断，content 为空。
        def provider(body, key):
            return {"choices": [{"message": {"role": "assistant", "content": "", "reasoning_content": "我们需要"},
                                 "finish_reason": "length"}],
                    "usage": {"prompt_tokens": 51, "completion_tokens": 16, "total_tokens": 67,
                              "completion_tokens_details": {"reasoning_tokens": 16}}}
        answer, events = run_case("short-limit", {"max_tokens": 16}, provider)
        self.assertIn("content 为空", answer)
        values = metrics(events)
        self.assertEqual(values["回答长度（字符）"], 0)
        self.assertEqual(values["finish_reason"], "length")
        self.assertEqual(values["其中推理 Token"], 16)

    def test_malformed_response_raises(self):
        with self.assertRaisesRegex(ValueError, "choices"):
            run_case("basic", {}, lambda body, key: {"error": "x"})


class BoundaryTests(unittest.TestCase):
    def test_inputs_are_bounded(self):
        for bad in ({"max_tokens": -1}, {"max_tokens": 5000}, {"system_prompt": "长" * 401}, {"extra": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)

    def test_cancel_stops_before_the_request(self):
        with self.assertRaises(RunCancelled):
            run_case("basic", {}, cancelled=lambda: True)


if __name__ == "__main__":
    unittest.main()
