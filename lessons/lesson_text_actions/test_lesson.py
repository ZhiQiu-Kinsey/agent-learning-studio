"""Behavior tests for text-actions: deterministic model data; the tool really runs in Python."""
import json
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_text_actions import runtime
from lessons.lesson_text_actions.fixtures import create_completion
from lessons.lesson_text_actions.locales import texts_for

ZH = texts_for("zh-CN")


def run_case(exercise_id, inputs, completion=None, budget=4, cancelled=lambda: False, locale="zh-CN"):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="text-actions", exercise_id=exercise_id, question="", mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def reply(content, finish_reason="stop"):
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish_reason}]}


class ParseStepTests(unittest.TestCase):
    def test_action_final_and_invalid(self):
        step = runtime.parse_step('Thought: 查\nAction: lookup_quiz_score\nAction Input: {"student_id": "s-1042"}\n', ZH)
        self.assertEqual((step["kind"], step["action"], step["arguments"]), ("action", "lookup_quiz_score", {"student_id": "s-1042"}))
        self.assertIsNone(step["fabricated"])
        self.assertEqual(runtime.parse_step("Thought: 好\nFinal Answer: 73 分", ZH)["answer"], "73 分")
        for text, error in (("我觉得是 73 分。", "既没有 Action"),
                            ("Action: lookup_quiz_score\nAction Input: {student_id: s-1042}", "不是合法 JSON"),
                            ('Action: lookup_quiz_score\nAction Input: ["s-1042"]', "必须是 JSON 对象")):
            with self.subTest(text=text):
                step = runtime.parse_step(text, ZH)
                self.assertEqual(step["kind"], "invalid")
                self.assertIn(error, step["error"])

    def test_parser_errors_follow_the_run_language(self):
        en = texts_for("en")
        self.assertEqual(runtime.parse_step("I think it is 73.", en)["error"], en.no_action)
        step = runtime.parse_step("Action: lookup_quiz_score\nAction Input: {student_id: s-1042}", en)
        self.assertTrue(step["error"].startswith("Action Input is not valid JSON: "))
        self.assertEqual(runtime.parse_step('Action: lookup_quiz_score\nAction Input: ["s-1042"]', en)["error"],
                         en.not_an_object)

    def test_multiline_json_and_trailing_text_are_read_without_guessing(self):
        step = runtime.parse_step('Action: lookup_quiz_score\nAction Input: {\n  "student_id": "s-2077"\n}\n多余的话', ZH)
        self.assertEqual(step["arguments"], {"student_id": "s-2077"})

    def test_model_written_observation_is_split_off(self):
        text = ('Action: lookup_quiz_score\nAction Input: {"student_id": "s-1042"}\n'
                'Observation: {"score": 88}\nThought: 及格\nFinal Answer: 88 分，及格。')
        step = runtime.parse_step(text, ZH)
        self.assertEqual(step["kind"], "action")
        self.assertEqual(step["fabricated"], '{"score": 88}')
        self.assertEqual(step["naive_final"], "88 分，及格。")
        self.assertNotIn("Observation", step["kept"])


class TextProtocolTests(unittest.TestCase):
    def test_stop_is_sent_and_real_observation_drives_the_answer(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                answer, events = run_case("text-stop", {"protocol": "text_stop"}, locale=locale)
                requests = [data["body"] for data in of(events, "request")]
                self.assertEqual(len(requests), 2)
                self.assertTrue(all(body["stop"] == ["Observation:"] for body in requests))
                self.assertEqual(requests[0]["messages"][0]["content"], texts_for(locale).text_system)
                self.assertEqual(of(events, "tool_result")[0]["result"]["result"]["score"], 73)
                self.assertTrue(requests[1]["messages"][-1]["content"].startswith("Observation: "))
                self.assertIn("73", answer)
                self.assertEqual([data["kind"] for data in of(events, "lesson.parse")], ["action", "final"])
                self.assertEqual(of(events, "lesson.fabricated_observation"), [])

    def test_the_question_is_in_the_run_language(self):
        _, events = run_case("text-stop", {"protocol": "text_stop"})
        self.assertEqual(of(events, "request")[0]["body"]["messages"][1]["content"],
                         "学号 s-1042 最近一次练习得了多少分？及格线是 60 分，他及格了吗？")
        _, events = run_case("text-stop", {"protocol": "text_stop"}, locale="en")
        self.assertEqual(of(events, "request")[0]["body"]["messages"][1]["content"],
                         "What did student s-1042 score on their latest quiz? The pass mark is 60. Did the student pass?")

    def test_runner_calls_are_marked_with_their_origin(self):
        _, events = run_case("text-stop", {"protocol": "text_stop"})
        self.assertEqual(of(events, "tool_call")[0]["origin"], "course_program")
        self.assertEqual(of(events, "tool_result")[0]["origin"], "course_program")

    def test_without_stop_fabrication_is_recorded_but_never_used(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                answer, events = run_case("text-no-stop", {"protocol": "text_no_stop"}, locale=locale)
                requests = [data["body"] for data in of(events, "request")]
                self.assertTrue(all("stop" not in body for body in requests))
                fabricated = of(events, "lesson.fabricated_observation")
                self.assertEqual(len(fabricated), 1)
                self.assertIn("88", fabricated[0]["model_wrote"])
                self.assertFalse(fabricated[0]["same_score"])
                self.assertEqual(fabricated[0]["real_result"]["result"]["score"], 73)
                self.assertIn("88", fabricated[0]["naive_final_answer"])
                self.assertNotIn("88", json.dumps(requests[1]["messages"], ensure_ascii=False))
                self.assertIn("73", answer)
                self.assertNotIn("88", answer)
                report = of(events, "lesson.report")[-1]
                self.assertEqual(report["checks"][0]["label"], texts_for(locale).check_not_leaked)
                self.assertTrue(report["checks"][0]["passed"])
        self.assertEqual(ZH.check_not_leaked, "模型自写的 Observation 没有进入后续上下文")

    def test_fabricated_pass_contradicts_a_failing_student(self):
        answer, events = run_case("text-no-stop-fail", {"protocol": "text_no_stop", "student_id": "s-2077"})
        fabricated = of(events, "lesson.fabricated_observation")[0]
        self.assertIn("及格", fabricated["naive_final_answer"])
        self.assertEqual(fabricated["real_result"]["result"]["score"], 58)
        self.assertIn("没有及格", answer)
        answer, events = run_case("text-no-stop-fail", {"protocol": "text_no_stop", "student_id": "s-2077"},
                                  locale="en")
        self.assertIn("passed", of(events, "lesson.fabricated_observation")[0]["naive_final_answer"])
        self.assertIn("did not pass", answer)

    def test_parse_failure_is_an_event_and_stops_without_repair(self):
        calls = []

        def provider(body, key):
            calls.append(body)
            return reply("我猜他得了 90 分。")
        answer, events = run_case("text-stop", {"protocol": "text_stop"}, provider)
        self.assertEqual(len(calls), 1)
        parse = of(events, "lesson.parse")[0]
        self.assertFalse(parse["ok"])
        self.assertEqual(parse["raw"], "我猜他得了 90 分。")
        self.assertEqual(of(events, "tool_call"), [])
        self.assertIn("解析失败", answer)
        answer, _ = run_case("text-stop", {"protocol": "text_stop"}, lambda body, key: reply("Maybe 90."), locale="en")
        self.assertEqual(answer, texts_for("en").text_parse_failed)

    def test_unknown_tool_name_returns_a_real_error_result(self):
        def provider(body, key):
            if len(body["messages"]) == 2:
                return reply('Action: get_grade\nAction Input: {"student_id": "s-1042"}')
            return reply("Final Answer: 查询失败，没有这个工具。")
        _, events = run_case("text-stop", {"protocol": "text_stop"}, provider)
        result = of(events, "tool_result")[0]["result"]
        self.assertFalse(result["ok"])
        self.assertIn("不认识这个工具", result["error"])

    def test_unknown_student_is_a_tool_error_in_the_run_language(self):
        def provider(body, key):
            if len(body["messages"]) == 2:
                return reply('Action: lookup_quiz_score\nAction Input: {"student_id": "s-0000"}')
            return reply("Final Answer: no record.")
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                _, events = run_case("text-stop", {"protocol": "text_stop"}, provider, locale=locale)
                result = of(events, "tool_result")[0]["result"]
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"], texts_for(locale).unknown_student.format(student_id="s-0000"))

    def test_step_limit_and_cancel(self):
        def loop(body, key):
            return reply('Action: lookup_quiz_score\nAction Input: {"student_id": "s-1042"}')
        answer, events = run_case("text-stop", {"protocol": "text_stop"}, loop, budget=3)
        self.assertEqual(len(of(events, "request")), 3)
        self.assertIn("3 步内没有 Final Answer", answer)
        answer, _ = run_case("text-stop", {"protocol": "text_stop"}, loop, budget=3, locale="en")
        self.assertIn("no Final Answer within 3 steps", answer)
        with self.assertRaises(RunCancelled):
            run_case("text-stop", {"protocol": "text_stop"}, cancelled=lambda: True)


class NativeTests(unittest.TestCase):
    def test_native_call_keeps_the_model_call_id(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                answer, events = run_case("native", {"protocol": "native"}, locale=locale)
                body = of(events, "request")[0]["body"]
                self.assertEqual(body["tools"], runtime.tool_definitions(locale))
                self.assertEqual(body["tools"][0]["function"]["name"], "lookup_quiz_score")
                self.assertEqual(body["messages"][0]["content"], texts_for(locale).native_system)
                self.assertNotIn("stop", body)
                call = of(events, "tool_call")[0]
                self.assertEqual(call["id"], "call_score_1")
                self.assertNotIn("origin", call)
                self.assertEqual(of(events, "tool_result")[0]["tool_call_id"], "call_score_1")
                follow_up = of(events, "request")[1]["body"]["messages"]
                self.assertEqual([m["role"] for m in follow_up[-2:]], ["assistant", "tool"])
                self.assertIn("73", answer)
                self.assertEqual(of(events, "lesson.parse"), [])
                self.assertEqual(of(events, "lesson.report")[-1]["title"], texts_for(locale).native_report_title)

    def test_tool_names_are_the_same_in_every_language(self):
        zh, en = runtime.tool_definitions("zh-CN"), runtime.tool_definitions("en")
        self.assertEqual(zh[0]["function"]["description"], "查询学生最近一次练习的得分、尝试次数和更新日期。")
        self.assertEqual([tool["function"]["name"] for tool in zh], [tool["function"]["name"] for tool in en])
        self.assertEqual(zh[0]["function"]["parameters"]["required"], en[0]["function"]["parameters"]["required"])

    def test_inputs_are_bounded(self):
        for bad in ({"protocol": "xml"}, {"student_id": "s-9999"}, {"extra": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)

    def test_the_catalog_cannot_be_replaced_by_model_arguments(self):
        tools = runtime.available_tools("en")
        with self.assertRaises(TypeError):
            tools["lookup_quiz_score"](t="x", student_id="s-1042")


if __name__ == "__main__":
    unittest.main()
