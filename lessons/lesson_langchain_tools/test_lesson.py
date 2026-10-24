"""Behavior tests for langchain-tools: deterministic model data; the lookup tool, LangChain parsing and the business check really run."""
import json
import re
import unittest
from pathlib import Path

from langchain_core.tools import ToolException
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.frameworks import FRAMEWORK_INPUT_EVENT, FRAMEWORK_OUTPUT_EVENT, tools_as_callables
from course.locales import texts_for as platform_texts
from course.runner import RunCancelled, execute_tool
from lessons.lesson_05_structured_output.locales import texts_for as structured_texts
from lessons.lesson_05_structured_output.runtime import TaskCard, trusted_facts
from lessons.lesson_langchain_tools import components, runtime
from lessons.lesson_langchain_tools.fixtures import create_completion
from lessons.lesson_langchain_tools.locales import texts_for
from server.selectors import count_events, select_events

LOCALES = ("zh-CN", "en")
CJK = re.compile(r"[　-〿㐀-䶿一-鿿豈-﫿＀-￯]")
EXERCISES = {"normal": "normal", "missing-field": "missing_field", "wrong-fact": "wrong_fact",
             "tool-error": "tool_error"}


def run_case(exercise_id, inputs=None, completion=None, budget=4, cancelled=lambda: False, locale="zh-CN",
             question=""):
    events = []
    values = validate_inputs(runtime, inputs if inputs is not None else {"scenario": EXERCISES[exercise_id]})
    context = RunContext(
        lesson_id="langchain-tools", exercise_id=exercise_id, question=question, mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def report(events, title_field, locale="zh-CN", **fmt):
    title = getattr(texts_for(locale), title_field).format(**fmt)
    return next(data for data in of(events, "lesson.report") if data["title"] == title)


def metric(data, metric_id):
    return next(item["value"] for item in data["metrics"] if item.get("id") == metric_id)


def check(data, check_id):
    return next(item for item in data["checks"] if item.get("id") == check_id)


def reply(*calls, content=None):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = list(calls)
    return {"model": "fixture-model", "choices": [{"finish_reason": "tool_calls" if calls else "stop",
                                                   "message": message}]}


def call(call_id, name, arguments):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


def good_card(locale="zh-CN"):
    return json.dumps({**trusted_facts(structured_texts(locale)), "exercise": "write one task card"},
                      ensure_ascii=False)


def scripted(*replies):
    queue = list(replies)
    return lambda body, api_key: queue.pop(0)


LOOKUP_OK = reply(call("l1", "lookup_lesson", '{"lesson_id": "task-contract"}'))


class InputTests(unittest.TestCase):
    def test_inputs_are_validated(self):
        self.assertEqual(validate_inputs(runtime, {}), {"scenario": "normal", "repair": True})
        for bad in ({"scenario": "other"}, {"repair": "maybe"}, {"label": "x"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)


class ComponentTests(unittest.TestCase):
    def test_business_table_reuses_the_structured_output_facts(self):
        for locale in LOCALES:
            facts = components.lesson_facts(locale)
            self.assertEqual(facts[components.TARGET_LESSON], trusted_facts(structured_texts(locale)))
            self.assertEqual(facts["structured-output"]["prerequisite"], "task-contract")

    def test_lookup_tool_really_runs_and_raises_tool_exception(self):
        for locale in LOCALES:
            lookup = components.make_lookup_tool(locale)
            self.assertEqual(lookup.invoke({"lesson_id": "task-contract"})["prerequisite"], "fail-safely")
            with self.assertRaises(ToolException):
                lookup.invoke({"lesson_id": "task_contract"})
            allowed = tools_as_callables([lookup])
            # Through the platform executor the ToolException becomes a structured error, not a crash.
            result = execute_tool(call("c", "lookup_lesson", '{"lesson_id": "nope"}'), allowed, locale)
            self.assertEqual(result["ok"], False)
            self.assertEqual(result["error_type"], "ValueError")
            self.assertEqual(result["error"], texts_for(locale).lookup_unknown.format(
                lesson_id="nope", known="fail-safely, structured-output, task-contract"))
            # The framework's own argument schema rejects an empty slug before the function runs.
            empty = execute_tool(call("c", "lookup_lesson", '{"lesson_id": ""}'), allowed, locale)
            self.assertEqual((empty["ok"], empty["error_type"]), (False, "ValidationError"))

    def test_generated_definition_matches_the_handwritten_one(self):
        for locale in LOCALES:
            generated = convert_to_openai_tool(components.make_lookup_tool(locale))
            self.assertEqual(components.differing_paths(generated, components.handwritten_definition(locale)), [])
        self.assertEqual(components.differing_paths({"a": {"b": 1, "c": 2}}, {"a": {"b": 1}, "d": 3}),
                         ["a.c", "d"])

    def test_card_schema_only_adds_a_description(self):
        self.assertEqual(convert_to_openai_tool(TaskCard)["function"]["description"], "")
        for locale in LOCALES:
            schema = components.card_schema(locale)
            definition = convert_to_openai_tool(schema)["function"]
            self.assertEqual(definition["name"], "TaskCard")
            self.assertEqual(definition["description"], texts_for(locale).card_description)
            self.assertEqual(definition["parameters"], convert_to_openai_tool(TaskCard)["function"]["parameters"])
            self.assertTrue(issubclass(schema, TaskCard))
            with self.assertRaises(ValidationError):
                schema.model_validate({**trusted_facts(structured_texts(locale)), "exercise": "long enough",
                                       "extra": 1})

    def test_business_check_runs_only_on_a_parsed_card(self):
        skipped = components.business_checks(None, "en")[0]
        self.assertNotIn("passed", skipped)
        card = TaskCard.model_validate_json(good_card("en"))
        self.assertTrue(components.business_checks(card, "en")[0]["passed"])
        wrong = card.model_copy(update={"prerequisite": "dependent-calls"})
        self.assertFalse(components.business_checks(wrong, "en")[0]["passed"])


class ExerciseTests(unittest.TestCase):
    def test_every_exercise_passes_in_both_languages(self):
        for exercise_id in EXERCISES:
            for locale in LOCALES:
                with self.subTest(exercise=exercise_id, locale=locale):
                    answer, events = run_case(exercise_id, locale=locale)
                    self.assertTrue(answer.startswith(texts_for(locale).answer_passed.split("{")[0]))
                    final = report(events, "final_title", locale)
                    self.assertEqual(metric(final, "stop_reason"), "accepted")
                    # Every framework call is a recorded request between the two framework events.
                    self.assertEqual(len(of(events, "request")), len(of(events, FRAMEWORK_INPUT_EVENT)))
                    self.assertEqual(len(of(events, "request")), metric(final, "model_calls"))
                    if locale == "en":
                        self.assertIsNone(CJK.search(json.dumps([data for _, data, _ in events], ensure_ascii=False)))

    def test_normal_run_keeps_raw_and_framework_layers_apart(self):
        _, events = run_case("normal")
        kinds = [kind for kind, _, _ in events]
        self.assertEqual(kinds[:7], ["lesson.report", FRAMEWORK_INPUT_EVENT, "request", "response",
                                     FRAMEWORK_OUTPUT_EVENT, "tool_call", "tool_result"])
        lookup_request, card_request = of(events, "request")
        self.assertEqual(lookup_request["body"]["tool_choice"], "auto")
        self.assertEqual(lookup_request["body"]["tools"][0], components.handwritten_definition("zh-CN"))
        self.assertEqual(card_request["body"]["tool_choice"], "required")
        self.assertEqual(card_request["body"]["tools"][0]["function"]["name"], "TaskCard")
        # The provider sent a JSON string; the framework holds a parsed dict.
        raw_arguments = of(events, "response")[1]["body"]["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
        framework_args = of(events, FRAMEWORK_OUTPUT_EVENT)[1]["message"]["tool_calls"][0]["args"]
        self.assertIsInstance(raw_arguments, str)
        self.assertEqual(json.loads(raw_arguments), framework_args)
        self.assertEqual(of(events, FRAMEWORK_OUTPUT_EVENT)[1]["usage_reported"], False)
        definitions = report(events, "definitions_title")
        self.assertTrue(check(definitions, "definition_match")["passed"])
        self.assertEqual(metric(definitions, "business_description"), texts_for("zh-CN").value_empty)

    def test_missing_field_is_a_schema_error_answered_by_the_runner(self):
        _, events = run_case("missing-field")
        first = report(events, "attempt_title", attempt=1)
        self.assertEqual(metric(first, "outcome_1"), "schema_error")
        self.assertFalse(check(first, "framework_parse")["passed"])
        self.assertIn("prerequisite: missing", check(first, "framework_parse")["detail"])
        self.assertNotIn("passed", check(first, "business_facts"))
        # The feedback answers the failed TaskCard call; no tool ran, so there is only the lookup's tool_call.
        repair_messages = of(events, "request")[2]["body"]["messages"]
        feedback = repair_messages[-1]
        self.assertEqual((feedback["role"], feedback["tool_call_id"]), ("tool", "offline_card_1"))
        self.assertEqual(json.loads(feedback["content"])["error_type"], "schema_validation")
        self.assertEqual(len(of(events, "tool_call")), 1)
        self.assertEqual(metric(report(events, "final_title"), "structured_attempts"), 2)

    def test_schema_valid_card_still_fails_the_business_check(self):
        _, events = run_case("wrong-fact", locale="en")
        first = report(events, "attempt_title", "en", attempt=1)
        self.assertEqual(metric(first, "outcome_1"), "parsed")
        self.assertTrue(check(first, "framework_parse")["passed"])
        self.assertFalse(check(first, "business_facts")["passed"])
        feedback = json.loads(of(events, "request")[2]["body"]["messages"][-1]["content"])
        self.assertEqual(feedback["error_type"], "business_rule")
        self.assertIn("prerequisite", feedback["error"])

    def test_tool_exception_reaches_the_model_as_a_structured_error(self):
        _, events = run_case("tool-error")
        failed, succeeded = of(events, "tool_result")
        self.assertEqual((failed["result"]["ok"], failed["result"]["error_type"]), (False, "ValueError"))
        self.assertTrue(succeeded["result"]["ok"])
        second_request = of(events, "request")[1]["body"]["messages"]
        tool_message = next(item for item in second_request if item["role"] == "tool")
        self.assertEqual(json.loads(tool_message["content"]), failed["result"])
        self.assertEqual(metric(report(events, "final_title"), "tool_failures"), 1)

    def test_repair_off_stops_after_the_first_failure(self):
        answer, events = run_case("missing-field", {"scenario": "missing_field", "repair": False})
        self.assertEqual(answer, texts_for("zh-CN").answer_failed)
        self.assertEqual(len(of(events, "request")), 2)
        final = report(events, "final_title")
        self.assertEqual(metric(final, "stop_reason"), "repair_off")
        self.assertFalse(check(final, "framework_parse")["passed"])

    def test_learner_note_goes_into_the_final_report_only(self):
        _, events = run_case("normal", question="my note")
        self.assertIn("my note", json.dumps(report(events, "final_title")))
        self.assertNotIn("my note", json.dumps(of(events, "request")))


class SilentFailureTests(unittest.TestCase):
    def test_invalid_arguments_return_none_without_an_exception(self):
        answer, events = run_case("normal", completion=scripted(
            LOOKUP_OK, reply(call("c1", "TaskCard", "{broken")), reply(call("c2", "TaskCard", good_card()))))
        first = report(events, "attempt_title", attempt=1)
        self.assertEqual(metric(first, "outcome_1"), "invalid_arguments")
        # The raw broken string goes back in history and is answered by the runner's feedback.
        repair = of(events, "request")[2]["body"]["messages"]
        self.assertEqual(repair[-2]["tool_calls"][0]["function"]["arguments"], "{broken")
        self.assertEqual(repair[-1]["tool_call_id"], "c1")
        self.assertEqual(metric(report(events, "final_title"), "stop_reason"), "accepted")

    def test_text_instead_of_forced_call_uses_the_labelled_fallback(self):
        answer, events = run_case("normal", completion=scripted(LOOKUP_OK, reply(content="Card: " + good_card())))
        self.assertEqual(metric(report(events, "attempt_title", attempt=1), "outcome_1"), "text_fallback")
        rows = report(events, "capabilities_title")["table"]["rows"]
        t = texts_for("zh-CN")
        self.assertEqual(rows[1][2], t.status_fallback)
        self.assertEqual(metric(report(events, "final_title"), "stop_reason"), "accepted")

    def test_failed_fallback_and_empty_reply_are_failures(self):
        _, events = run_case("normal", {"scenario": "normal", "repair": False},
                             completion=scripted(LOOKUP_OK, reply(content='{"lesson_id": "x"}')))
        self.assertEqual(metric(report(events, "attempt_title", attempt=1), "outcome_1"), "text_fallback_failed")
        _, events = run_case("normal", completion=scripted(LOOKUP_OK, reply(content=""), reply(content="")))
        self.assertEqual(metric(report(events, "attempt_title", attempt=2), "outcome_2"), "no_structured_call")
        # A message without tool calls is answered with a user message, not a dangling tool message.
        self.assertEqual(of(events, "request")[2]["body"]["messages"][-1]["role"], "user")
        self.assertEqual(metric(report(events, "final_title"), "stop_reason"), "repair_used_up")

    def test_synthesized_ids_are_reported_as_adapter_fallback(self):
        no_id = {"type": "function", "function": {"name": "lookup_lesson", "arguments": '{"lesson_id": "task-contract"}'}}
        _, events = run_case("normal", completion=scripted(reply(no_id), reply(call("c", "TaskCard", good_card()))))
        rows = report(events, "capabilities_title")["table"]["rows"]
        self.assertEqual(rows[2][2], texts_for("zh-CN").status_fallback)
        self.assertEqual(of(events, "tool_call")[0]["id"], "framework_call_1_1")


class ContentEvidenceTests(unittest.TestCase):
    """The lesson is planned, so the shared experiment test skips it; check its selectors here."""

    def test_observe_points_hit_and_predict_counts_real_events(self):
        folder = Path(__file__).parent
        content = json.loads((folder / "content.json").read_text(encoding="utf-8"))
        presets = {item["id"]: item["inputs"]
                   for item in json.loads((folder / "lesson.json").read_text(encoding="utf-8"))["exercises"]}

        def events_of(exercise_id, locale):
            _, raw = run_case(exercise_id, presets[exercise_id], locale=locale)
            return [{"type": kind, "round": number, "data": data} for kind, data, number in raw]

        for locale in LOCALES:
            for experiment in content["scenes"]["lab"]["experiments"]:
                runs = [events_of(arm["exercise"], locale) for arm in experiment["arms"]]
                for point in experiment["observe"]:
                    with self.subTest(locale=locale, experiment=experiment["id"], observe=point["id"]):
                        self.assertTrue(any(select_events(point["selector"], events) for events in runs))
                self.assertEqual({step["observe"] for step in experiment["guide"] if step.get("observe")},
                                 {point["id"] for point in experiment["observe"]})
            predict = next(block for block in content["scenes"]["understand"]["blocks"] if block["type"] == "predict")
            self.assertEqual(count_events(predict["rule"], events_of(predict["arm"], locale)), 3)
            hunt = next(block for block in content["scenes"]["check"]["blocks"] if block["type"] == "trace-hunt")
            target = select_events(hunt["target"], events_of("missing-field", locale))
            self.assertTrue(target)
        used = {arm["exercise"] for experiment in content["scenes"]["lab"]["experiments"] for arm in experiment["arms"]}
        self.assertEqual(used, set(presets))


class StopTests(unittest.TestCase):
    def test_no_facts_means_no_card(self):
        answer, events = run_case("normal", completion=scripted(reply(content="I remember the facts.")))
        self.assertEqual(answer, texts_for("zh-CN").answer_no_facts)
        self.assertEqual(len(of(events, "request")), 1)
        final = report(events, "final_title")
        self.assertEqual(metric(final, "stop_reason"), "no_facts")
        self.assertFalse(check(final, "facts_found")["passed"])

    def test_lookup_is_limited_to_two_calls(self):
        bad = reply(call("b", "lookup_lesson", '{"lesson_id": "task_contract"}'))
        answer, events = run_case("tool-error", completion=scripted(bad, bad))
        self.assertEqual(answer, texts_for("zh-CN").answer_no_facts)
        self.assertEqual(len(of(events, "request")), runtime.LOOKUP_LIMIT)
        self.assertEqual(metric(report(events, "final_title"), "tool_failures"), 2)

    def test_platform_budget_still_applies(self):
        with self.assertRaises(RuntimeError) as caught:
            run_case("missing-field", budget=2)
        self.assertEqual(str(caught.exception), platform_texts("zh-CN").model_budget_exceeded.format(limit=2))

    def test_cancel_after_first_response_runs_no_tool(self):
        flag = {"stop": False}
        inner = create_completion("normal", {"scenario": "normal"}, "zh-CN")

        def completion(body, api_key):
            flag["stop"] = True
            return inner(body, api_key)

        events = []
        with self.assertRaises(RunCancelled):
            values = validate_inputs(runtime, {"scenario": "normal"})
            context = RunContext(
                lesson_id="langchain-tools", exercise_id="normal", question="", mode="offline", model="m",
                representation="sdk_standardized", inputs=values, api_key="", completion=completion,
                emit_event=lambda kind, data, number: events.append(kind), cancelled=lambda: flag["stop"],
                max_model_calls=4, locale="zh-CN")
            runtime.run(context)
        self.assertNotIn("tool_call", events)


if __name__ == "__main__":
    unittest.main()
