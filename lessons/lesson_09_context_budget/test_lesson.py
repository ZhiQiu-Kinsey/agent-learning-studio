"""English-run tests for context-budget; the Chinese behaviour tests are in tests/test_lessons_budget_memory.py.

Deterministic model data; lookup_lesson really runs in Python.
"""
import json
import re
import unittest

from course.execution import RunContext, validate_inputs
from lessons.lesson_09_context_budget import fixtures, runtime
from lessons.lesson_09_context_budget.locales import texts_for
from lessons.lesson_09_context_budget.locales.helpers import texts_for as helper_texts

CJK = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")


def run_case(exercise_id, inputs=None, completion=None, locale="en", mode="offline"):
    events = []
    values = validate_inputs(runtime, inputs or {})
    context = RunContext(
        lesson_id="context-budget", exercise_id=exercise_id, question="", mode=mode,
        model="fixture-model", representation="offline", inputs=values, api_key="",
        completion=completion or fixtures.create_completion(exercise_id, values, locale), max_model_calls=2,
        emit_event=lambda kind, data, number: events.append((kind, data, number)), locale=locale,
    )
    answer = runtime.run(context)
    return values, answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


class EnglishRunTests(unittest.TestCase):
    def test_english_runs_have_no_chinese(self):
        for exercise, inputs in (("compare", {}), ("wide_budget", {"char_budget": 4000}),
                                 ("more_noise", {"noise_repeats": 20}),
                                 ("broken-pair", {"experiment": "broken_pair", "noise_repeats": 4})):
            with self.subTest(exercise=exercise):
                _, answer, events = run_case(exercise, inputs)
                self.assertIsNone(CJK.search(json.dumps([answer, events], ensure_ascii=False)))

    def test_english_window_has_the_same_outcome_as_the_chinese_one(self):
        # The English text is longer, but the default budget still drops the tool pair and keeps some side discussion.
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                values, _, events = run_case("compare", locale=locale)
                full, window = [data["body"]["messages"] for data in of(events, "request")]
                self.assertEqual(len(full), 21)
                self.assertGreater(runtime.message_chars(full), values["char_budget"])
                self.assertLessEqual(runtime.message_chars(window), values["char_budget"])
                self.assertFalse(any(message["role"] == "tool" for message in window))
                self.assertGreater(len(window), 2)
                report = of(events, "lesson.report")[0]
                self.assertEqual([check["passed"] for check in report["checks"]], [True, True, False])
                self.assertEqual([row[0] for row in report["table"]["rows"]],
                                 [texts_for(locale).layout_names[code] for code in ("full", "window")])
        values, _, events = run_case("wide_budget", {"char_budget": 4000})
        full, window = [data["body"]["messages"] for data in of(events, "request")]
        self.assertEqual(full, window)

    def test_english_broken_pair_report(self):
        t = texts_for("en")
        _, answer, events = run_case("broken-pair", {"experiment": "broken_pair", "noise_repeats": 4})
        self.assertEqual(answer, t.pair_answer)
        error = of(events, "lesson.provider_error")[0]
        self.assertEqual((error["status"], error["source"], error["layout"]), (400, "offline_fixture", t.truncation_names["naive"]))
        report = of(events, "lesson.report")[0]
        self.assertEqual(report["checks"][0]["label"], t.check_local.format(name=t.truncation_names["naive"]))
        self.assertTrue(report["checks"][0]["detail"].startswith("rejected: "))
        self.assertEqual(report["table"]["rows"][0][3], t.refused_offline.format(status=400))
        self.assertEqual(report["table"]["rows"][1][3], t.accepted)

    def test_local_checks_are_found_by_id_in_both_languages(self):
        # The lab selects the naive cut's local check by id, so another truncation would not shift it.
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                _, _, events = run_case("broken-pair", {"experiment": "broken_pair", "noise_repeats": 4}, locale=locale)
                checks = of(events, "lesson.report")[0]["checks"]
                self.assertEqual([check["id"] for check in checks], ["local_naive", "local_pair_aware"])
                self.assertFalse(checks[0]["passed"])

    def test_helpers_speak_the_run_language(self):
        proposal = {"choices": [{"message": {"content": None, "tool_calls": [{"function": {"name": "lookup_lesson"}},
                                                                             {"function": {}}]}}]}
        self.assertEqual(runtime.answer_text(proposal, "en"),
                         "(No text answer: the model proposed calling lookup_lesson, unknown; the runner did not run them.)")
        self.assertEqual(runtime.usage_text({}, "en"), "not reported")
        self.assertEqual(runtime.side_talk(1, "en")[0]["content"], helper_texts("en").side_question.format(n=1))
        with self.assertRaisesRegex(ValueError, "No such material"):
            runtime.lookup_lesson(helper_texts("en"), "unknown")
        with self.assertRaisesRegex(ValueError, "cannot hold system"):
            runtime.fit_window([{"role": "system", "content": "s" * 500}, {"role": "user", "content": "q"}], 400,
                               texts_for("en"))

    def test_material_has_the_same_keys_in_both_languages(self):
        self.assertEqual(set(helper_texts("en").facts), set(helper_texts("zh-CN").facts))
        self.assertEqual(set(helper_texts("en").facts), set(runtime.Inputs.model_fields["source_key"].annotation.__args__))


if __name__ == "__main__":
    unittest.main()
