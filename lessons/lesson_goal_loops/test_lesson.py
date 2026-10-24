"""Behavior tests for goal-loops: deterministic model data; read_note and the goal evaluation really run in Python."""
import json
import re
import unittest
from unittest import mock

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_goal_loops import runtime
from lessons.lesson_goal_loops.fixtures import NOTICE, STALE, create_completion
from lessons.lesson_goal_loops.locales import texts_for

LOCALES = ("zh-CN", "en")
SPEC = json.loads(open(runtime.__file__.replace("runtime.py", "lesson.json"), encoding="utf-8").read())
EXERCISES = {exercise["id"]: exercise for exercise in SPEC["exercises"]}
CJK = re.compile(r"[　-〿一-鿿＀-￯]")


def inputs_for(exercise_id, **overrides):
    return {**SPEC["input_defaults"], **EXERCISES[exercise_id]["inputs"], **overrides}


def run_case(exercise_id, inputs=None, completion=None, locale="zh-CN", budget=20, cancelled=lambda: False):
    events = []
    values = validate_inputs(runtime, inputs if inputs is not None else inputs_for(exercise_id))
    context = RunContext(
        lesson_id="goal-loops", exercise_id=exercise_id, question="", mode="offline", model="fixture-model",
        representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def metric(events, metric_id):
    return next(item["value"] for item in of(events, "lesson.report")[-1]["metrics"] if item.get("id") == metric_id)


def submit(card, status="continue", usage=True):
    response = {"choices": [{"message": {"role": "assistant",
                                         "content": json.dumps({"card": card, "status": status, "note": "x"})}}]}
    if usage:
        response["usage"] = {"total_tokens": 10}
    return response


def read(*notes):
    calls = [{"id": f"c_{note}", "type": "function",
              "function": {"name": "read_note", "arguments": json.dumps({"note_id": note})}} for note in notes]
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": calls}}],
            "usage": {"total_tokens": 10}}


def scripted(*responses):
    """A completion that plays the given responses in order and repeats the last one."""
    position = 0

    def complete(body, api_key):
        nonlocal position
        response = responses[min(position, len(responses) - 1)]
        position += 1
        return response
    return complete


class EvaluateGoalTests(unittest.TestCase):
    def setUp(self):
        self.t = texts_for("zh-CN")
        self.all_notes = {note: self.t.notes[note] for note in runtime.NOTES}

    def test_value_must_appear_in_a_source_note_read_in_this_run(self):
        # The right values without having read the sources are guesses: they fail.
        evaluation = runtime.evaluate_goal(self.t, "notice", NOTICE, {})
        self.assertEqual(evaluation["verdict"], "continue")
        self.assertEqual(evaluation["passed"], 0)
        evaluation = runtime.evaluate_goal(self.t, "notice", NOTICE, self.all_notes)
        self.assertEqual((evaluation["verdict"], evaluation["passed"]), ("complete", 3))

    def test_a_value_from_the_wrong_note_does_not_count(self):
        # A101 and 14:00 are in the minutes, but the condition names booking and speaker as the sources.
        evaluation = runtime.evaluate_goal(self.t, "notice", STALE, self.all_notes)
        statuses = {check["id"]: check["status"] for check in evaluation["checks"]}
        self.assertEqual(statuses, {"date": "pass", "room": "fail", "start_time": "fail"})
        self.assertIn("A101", evaluation["checks"][1]["detail"])

    def test_unreachable_needs_every_source_read(self):
        card = {**NOTICE, "contact_phone": ""}
        partial = {note: self.t.notes[note] for note in ("schedule", "booking", "speaker")}
        evaluation = runtime.evaluate_goal(self.t, "notice_with_phone", card, partial)
        self.assertEqual(evaluation["verdict"], "continue")
        self.assertIn("minutes", evaluation["checks"][3]["detail"])
        evaluation = runtime.evaluate_goal(self.t, "notice_with_phone", card, self.all_notes)
        self.assertEqual(evaluation["verdict"], "unreachable")
        self.assertEqual(evaluation["checks"][3]["status"], "unreachable")

    def test_a_made_up_phone_is_still_unreachable(self):
        card = {**NOTICE, "contact_phone": "138-0000-0000"}
        evaluation = runtime.evaluate_goal(self.t, "notice_with_phone", card, self.all_notes)
        self.assertEqual(evaluation["checks"][3]["status"], "unreachable")

    def test_patterns_find_one_candidate_per_source(self):
        for locale in LOCALES:
            t = texts_for(locale)
            for name, criterion in runtime.CRITERIA.items():
                for note in criterion.sources:
                    found = re.findall(criterion.pattern, t.notes[note])
                    if name == "contact_phone":
                        self.assertEqual(found, [], (locale, note))
                    else:
                        self.assertEqual(found, [NOTICE[name]], (locale, name))


class RuleTests(unittest.TestCase):
    def evaluation(self, passed, failure_value="x"):
        checks = [{"id": "date", "status": "pass", "value": "d"}] * passed
        checks += [{"id": "room", "status": "fail", "value": failure_value}]
        return {"verdict": "continue", "passed": passed, "total": passed + 1, "checks": checks}

    def test_progress_counts_new_passes_and_identical_failures(self):
        progress = runtime.Progress()
        progress.update(self.evaluation(1))
        self.assertEqual((progress.best, progress.stall, progress.repeats), (1, 0, 1))
        progress.update(self.evaluation(1))
        self.assertEqual((progress.stall, progress.repeats), (1, 2))
        progress.update(self.evaluation(1, failure_value="y"))
        self.assertEqual((progress.stall, progress.repeats), (2, 1))
        progress.update(self.evaluation(2, failure_value="y"))
        self.assertEqual((progress.best, progress.stall), (2, 0))

    def test_decide_order(self):
        values = runtime.Inputs(max_rounds=2, max_model_calls=5, max_stall=2, repeat_limit=2)
        stuck = runtime.Progress(best=1, stall=2, repeats=2)
        spent = runtime.Budget(started=runtime.clock(), rounds=2, calls=4)
        complete = {"verdict": "complete", "checks": [], "passed": 1, "total": 1}
        unreachable = {"verdict": "unreachable", "checks": [], "passed": 0, "total": 1}
        going = {"verdict": "continue", "checks": [], "passed": 0, "total": 1}
        # A met goal wins over every limit; evidence of unreachability comes before the abandon rules.
        self.assertEqual(runtime.decide(complete, stuck, spent, values), ("complete", "goal_met"))
        self.assertEqual(runtime.decide(unreachable, stuck, spent, values), ("abandoned", "unreachable"))
        self.assertEqual(runtime.decide(going, stuck, spent, values), ("abandoned", "repeated_failure"))
        self.assertEqual(runtime.decide(going, runtime.Progress(stall=2, repeats=1), spent, values),
                         ("abandoned", "no_progress"))
        moving = runtime.Progress(best=1, stall=0, repeats=1)
        self.assertEqual(runtime.decide(going, moving, spent, values), ("budget_exhausted", "max_rounds"))
        fresh = runtime.Budget(started=runtime.clock(), rounds=1, calls=3)
        self.assertEqual(runtime.decide(going, moving, fresh, values), ("budget_exhausted", "max_model_calls"))
        self.assertEqual(runtime.decide(going, moving, runtime.Budget(started=runtime.clock(), rounds=1, calls=2),
                                        values), ("continue", "keep_going"))


class ExerciseTests(unittest.TestCase):
    def test_reachable_goal_completes_within_budget(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("reachable", locale=locale)
                records = of(events, "lesson.goal_evaluation")
                self.assertEqual([r["decision"] for r in records], ["continue", "continue", "complete"])
                self.assertEqual([r["passed"] for r in records], [1, 2, 3])
                self.assertEqual(records[-1]["evidence"]["notes_read"], ["schedule", "booking", "speaker"])
                self.assertEqual(metric(events, "outcome"), t.decisions["complete"])
                self.assertEqual(metric(events, "model_calls"), 6)
                self.assertEqual(metric(events, "total_tokens"), 900)
                self.assertTrue(answer.startswith(t.answers["complete"][:6]))
                self.assertTrue(all(check["passed"] for check in of(events, "lesson.report")[-1]["checks"]))

    def test_missing_information_is_abandoned_with_its_reason(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("missing-info", locale=locale)
                last = of(events, "lesson.goal_evaluation")[-1]
                self.assertEqual((last["verdict"], last["decision"], last["reason_code"]),
                                 ("unreachable", "abandoned", "unreachable"))
                self.assertEqual(last["evidence"]["notes_read"], list(runtime.NOTES))
                self.assertTrue(last["claim_agrees"])
                self.assertEqual(metric(events, "outcome"), t.decisions["abandoned"])
                self.assertIn("contact_phone", metric(events, "stop_reason"))
                self.assertNotEqual(metric(events, "outcome"), t.decisions["complete"])
                self.assertIn("3/4", answer)

    def test_small_budget_stops_as_budget_exhausted_not_abandoned(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("tight-budget", locale=locale)
                records = of(events, "lesson.goal_evaluation")
                self.assertEqual(len(records), 2)
                self.assertEqual(records[-1]["progress"]["stall"], 0)
                self.assertEqual((records[-1]["decision"], records[-1]["reason_code"]),
                                 ("budget_exhausted", "max_rounds"))
                self.assertEqual(metric(events, "outcome"), t.decisions["budget_exhausted"])
                self.assertEqual(metric(events, "progress"), "2/3")

    def test_claimed_done_does_not_stop_the_loop(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("false-done", locale=locale)
                claims = of(events, "lesson.completion_claim")
                records = of(events, "lesson.goal_evaluation")
                self.assertEqual([c["status"] for c in claims], ["done", "done"])
                self.assertEqual(records[0]["decision"], "continue")
                self.assertFalse(records[0]["claim_agrees"])
                self.assertEqual((records[-1]["decision"], records[-1]["reason_code"]),
                                 ("abandoned", "repeated_failure"))
                self.assertEqual(metric(events, "claims_done"), 2)
                self.assertEqual(metric(events, "claims_disagree"), 2)
                self.assertEqual(metric(events, "outcome"), t.decisions["abandoned"])
                # The evaluator's reasons go back to the worker in the next request.
                second = [data for kind, data, _ in events if kind == "request"][2]["body"]["messages"][-1]
                self.assertEqual(second["role"], "user")
                self.assertIn("A101", second["content"])
                self.assertIn(t.verdicts["continue"], second["content"])

    def test_task_card_comes_first_and_report_last(self):
        _, events = run_case("reachable")
        lesson_events = [kind for kind, _, _ in events if kind.startswith("lesson.")]
        self.assertEqual(lesson_events[0], "lesson.task_card")
        self.assertEqual(lesson_events[-1], "lesson.report")
        card = of(events, "lesson.task_card")[0]
        self.assertEqual(set(card), {"goal", "input_scope", "output", "evidence", "failure", "stop"})


class AbandonAndBudgetTests(unittest.TestCase):
    def test_changing_wrong_answers_end_as_no_progress(self):
        # Different wrong rooms each round: never the same failure, never a new pass.
        completion = scripted(submit({"date": "", "room": "C301", "start_time": ""}),
                              submit({"date": "", "room": "C302", "start_time": ""}),
                              submit({"date": "", "room": "C303", "start_time": ""}))
        _, events = run_case("reachable", inputs_for("reachable", repeat_limit=4, max_stall=2), completion)
        last = of(events, "lesson.goal_evaluation")[-1]
        self.assertEqual((last["decision"], last["reason_code"]), ("abandoned", "no_progress"))
        self.assertEqual(len(of(events, "lesson.goal_evaluation")), 2)

    def test_model_call_budget_is_checked_before_a_round(self):
        _, events = run_case("reachable", inputs_for("reachable", max_model_calls=5))
        last = of(events, "lesson.goal_evaluation")[-1]
        self.assertEqual((last["decision"], last["reason_code"]), ("budget_exhausted", "max_model_calls"))
        self.assertEqual(metric(events, "model_calls"), 4)

    def test_time_budget(self):
        ticks = iter(range(0, 10_000, 100))
        with mock.patch.object(runtime, "clock", lambda: next(ticks)):
            _, events = run_case("reachable", inputs_for("reachable", max_seconds=10))
        last = of(events, "lesson.goal_evaluation")[-1]
        self.assertEqual((last["decision"], last["reason_code"]), ("budget_exhausted", "max_seconds"))
        self.assertEqual(last["loop_round"], 1)

    def test_broken_reply_keeps_the_card_and_is_recorded(self):
        completion = scripted(read("schedule"), submit({"date": NOTICE["date"], "room": "", "start_time": ""}),
                              {"choices": [{"message": {"role": "assistant", "content": "我还在想"}}]})
        _, events = run_case("reachable", inputs_for("reachable", max_stall=1, repeat_limit=4), completion)
        claims = of(events, "lesson.completion_claim")
        self.assertEqual(claims[-1]["status"], "invalid")
        self.assertEqual(claims[-1]["parse_error"], texts_for("zh-CN").no_json_object)
        self.assertEqual(claims[-1]["card"]["date"], NOTICE["date"])
        self.assertEqual(of(events, "lesson.goal_evaluation")[-1]["reason_code"], "no_progress")

    def test_a_round_that_never_hands_in(self):
        _, events = run_case("reachable", inputs_for("reachable", max_rounds=1), scripted(read("schedule")))
        claim = of(events, "lesson.completion_claim")[0]
        self.assertEqual(claim["status"], "invalid")
        self.assertEqual(claim["parse_error"], texts_for("zh-CN").no_submission.format(steps=runtime.ROUND_STEPS))
        self.assertEqual(len(of(events, "request")), runtime.ROUND_STEPS)

    def test_unknown_note_is_a_structured_error_and_no_evidence(self):
        bad = {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "read_note", "arguments": '{"note_id": "phonebook"}'}}]}}]}
        completion = scripted(bad, submit({"date": "", "room": "", "start_time": ""}))
        _, events = run_case("reachable", inputs_for("reachable", max_rounds=1), completion)
        result = of(events, "tool_result")[0]["result"]
        self.assertEqual((result["ok"], result["error_type"]), (False, "ValueError"))
        self.assertIn("phonebook", result["error"])
        self.assertEqual(of(events, "lesson.goal_evaluation")[0]["evidence"]["notes_read"], [])

    def test_unreported_usage_is_written_as_not_reported(self):
        completion = scripted(submit({"date": "", "room": "", "start_time": ""}, usage=False))
        for locale in LOCALES:
            _, events = run_case("reachable", inputs_for("reachable", max_rounds=1), completion, locale=locale)
            self.assertEqual(metric(events, "total_tokens"), texts_for(locale).value_not_reported)

    def test_completion_in_the_last_round_is_still_complete(self):
        # decide reads the goal verdict before the budget: the round that uses up max_rounds may still finish the goal.
        _, events = run_case("reachable", inputs_for("reachable", max_rounds=3))
        last = of(events, "lesson.goal_evaluation")[-1]
        self.assertEqual((last["loop_round"], last["decision"], last["reason_code"]), (3, "complete", "goal_met"))
        self.assertEqual(last["budget"]["rounds"], last["budget"]["max_rounds"])

    def test_impossible_claim_with_unread_sources_is_a_disagreement(self):
        # Claiming impossible after two notes is giving up early: the evaluation still says continue.
        completion = scripted(read("schedule", "booking"),
                              submit({"date": NOTICE["date"], "room": NOTICE["room"], "start_time": ""}, "impossible"),
                              read("speaker"), submit(NOTICE, "done"))
        _, events = run_case("reachable", completion=completion)
        first, last = of(events, "lesson.goal_evaluation")[0], of(events, "lesson.goal_evaluation")[-1]
        self.assertEqual((first["claim"], first["verdict"], first["claim_agrees"]), ("impossible", "continue", False))
        self.assertEqual((last["decision"], last["claim_agrees"]), ("complete", True))
        # The feedback names the claim and the verdict, and the evaluation decides.
        feedback = [data for kind, data, _ in events if kind == "request"][2]["body"]["messages"][-1]["content"]
        self.assertIn("impossible", feedback)
        self.assertIn(texts_for("zh-CN").verdicts["continue"], feedback)

    def test_a_worker_that_never_hands_in_a_card_is_caught_by_repeated_failure(self):
        # Every reply is unreadable, so the card stays empty and the same failure comes back.
        junk = {"choices": [{"message": {"role": "assistant", "content": "still thinking"}}], "usage": {"total_tokens": 5}}
        _, events = run_case("reachable", completion=scripted(junk))
        claims = of(events, "lesson.completion_claim")
        self.assertEqual({claim["status"] for claim in claims}, {"invalid"})
        last = of(events, "lesson.goal_evaluation")[-1]
        self.assertEqual((last["decision"], last["reason_code"]), ("abandoned", "repeated_failure"))
        self.assertEqual(last["passed"], 0)

    def test_every_record_names_a_known_reason_code(self):
        codes = set(texts_for("zh-CN").reasons)
        keys = {"loop_round", "evidence", "claim", "verdict", "passed", "total", "checks", "claim_agrees",
                "progress", "budget", "decision", "reason_code", "reason"}
        for exercise_id in EXERCISES:
            _, events = run_case(exercise_id)
            for record in of(events, "lesson.goal_evaluation"):
                with self.subTest(exercise=exercise_id, round=record["loop_round"]):
                    self.assertEqual(set(record), keys)
                    self.assertIn(record["reason_code"], codes)
                    self.assertEqual(record["decision"] == "continue", record["reason_code"] == "keep_going")

    def test_cancel_stops_the_loop(self):
        calls = {"n": 0}

        def cancelled():
            calls["n"] += 1
            return calls["n"] > 6
        with self.assertRaises(RunCancelled):
            run_case("reachable", cancelled=cancelled)


class InputAndLocaleTests(unittest.TestCase):
    def test_rejects_invalid_inputs(self):
        for bad in ({"max_rounds": 0}, {"max_rounds": 9}, {"max_model_calls": 2}, {"repeat_limit": 1},
                    {"max_stall": 0}, {"max_seconds": 5}, {"goal": "poem"}, {"worker_style": "lazy"}, {"extra": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                runtime.Inputs(**{**SPEC["input_defaults"], **bad})

    def test_english_runs_have_no_chinese(self):
        for exercise_id in EXERCISES:
            with self.subTest(exercise=exercise_id):
                answer, events = run_case(exercise_id, locale="en")
                self.assertIsNone(CJK.search(answer))
                for kind, data, _ in events:
                    self.assertIsNone(CJK.search(json.dumps(data, ensure_ascii=False)), kind)

    def test_texts_have_the_same_codes(self):
        zh, en = texts_for("zh-CN"), texts_for("en")
        self.assertEqual(set(zh.notes), set(runtime.NOTES))
        for field in ("note_titles", "notes", "goal_names", "field_labels", "worker_system", "verdicts",
                      "decisions", "reasons", "answers", "fixture_notes"):
            self.assertEqual(set(getattr(zh, field)), set(getattr(en, field)), field)
        self.assertEqual(set(zh.reasons), {"goal_met", "unreachable", "repeated_failure", "no_progress",
                                           "max_rounds", "max_model_calls", "max_seconds", "keep_going"})


if __name__ == "__main__":
    unittest.main()
