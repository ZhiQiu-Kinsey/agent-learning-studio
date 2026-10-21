"""Behavior tests for delegation-budget: deterministic model data; the merge check, scheduler, budget and scopes really run."""
import json
import re
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled, execute_tool
from lessons.lesson_delegation_budget import runtime
from lessons.lesson_delegation_budget.budget import Scope, SharedBudget, SubtaskCancelled
from lessons.lesson_delegation_budget.contracts import (DOC_IDS, MAX_VALUE_CHARS, PLAN, SUBTASK_IDS, build_contracts,
                                                        check_reply, merge_check, parse_reply, render)
from lessons.lesson_delegation_budget.fixtures import create_completion
from lessons.lesson_delegation_budget.locales import texts_for
from lessons.lesson_delegation_budget.locales.fixture import texts_for as fixture_texts_for
from server.selectors import select_events

LOCALES = ("zh-CN", "en")
CJK = re.compile(r"[　-〿一-鿿＀-￯]")


def run_case(inputs, completion=None, cancelled=lambda: False, locale="zh-CN", question="", max_calls=5):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="delegation-budget", exercise_id="full-contract", question=question, mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion("full-contract", values, locale), max_model_calls=max_calls,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def report(events):
    return of(events, "lesson.report")[-1]


def metric(events, metric_id):
    return next(item["value"] for item in report(events)["metrics"] if item.get("id") == metric_id)


def check(events, check_id):
    return next(item for item in report(events)["checks"] if item.get("id") == check_id)


def as_trace(events):
    return [{"type": kind, "round": number, "data": data} for kind, data, number in events]


def good_reply(locale, doc):
    f = fixture_texts_for(locale)
    return {"status": "answered", "value": f.values[doc], "evidence": [{"doc": doc, "quote": f.quotes[doc]}]}


class ContractTests(unittest.TestCase):
    def test_fixture_values_and_quotes_fit_the_contract(self):
        for locale in LOCALES:
            t, f = texts_for(locale), fixture_texts_for(locale)
            for doc in DOC_IDS:
                self.assertIn(f.quotes[doc], t.docs[doc], (locale, doc))
                self.assertLessEqual(len(f.values[doc]), MAX_VALUE_CHARS, (locale, doc))

    def test_render_holds_only_the_contract_and_its_own_documents(self):
        for locale in LOCALES:
            t = texts_for(locale)
            for contract in build_contracts(True):
                text = "\n".join(message["content"] for message in render(t, contract))
                self.assertEqual([doc for doc in DOC_IDS if t.docs[doc] in text], list(contract.docs))
                self.assertIn(t.output_with_evidence, text)
                self.assertNotIn(t.card_goal, text)  # the coordinator's own task stays with the coordinator
            plain = "\n".join(message["content"] for message in render(t, build_contracts(False)[0]))
            self.assertIn(t.output_without_evidence, plain)
            self.assertNotIn(t.output_with_evidence, plain)

    def test_tight_deadline_goes_to_one_subtask_only(self):
        contracts = build_contracts(True, "weight", 50)
        self.assertEqual({c.id: c.deadline_ms for c in contracts if c.deadline_ms == 50}, {"weight": 50})
        self.assertEqual([c.id for c in contracts], list(SUBTASK_IDS))

    def test_each_problem_code(self):
        t = texts_for("zh-CN")
        contract = {"id": "deadline-syllabus", "docs": ["d1"]}
        good = good_reply("zh-CN", "d1")
        self.assertEqual(check_reply(t.docs, contract, good), [])
        self.assertEqual(check_reply(t.docs, contract, None), ["not_json"])
        self.assertEqual(check_reply(t.docs, contract, {**good, "status": "done"}), ["bad_status"])
        self.assertEqual(check_reply(t.docs, contract, {"status": "not_found"}), [])
        self.assertEqual(check_reply(t.docs, contract, {**good, "value": " "}), ["no_value"])
        self.assertEqual(check_reply(t.docs, contract, {"status": "answered", "value": "x"}), ["no_evidence"])
        self.assertEqual(check_reply(t.docs, contract, {**good, "value": "x" * 41}), ["too_long"])
        borrowed = {**good, "evidence": [{"doc": "d2", "quote": t.docs["d2"][:10]}]}
        self.assertEqual(check_reply(t.docs, contract, borrowed), ["doc_out_of_scope"])
        made_up = {**good, "evidence": [{"doc": "d1", "quote": "截止时间是 12 月 30 日"}]}
        self.assertEqual(check_reply(t.docs, contract, made_up), ["quote_not_found"])

    def test_parse_reply_takes_the_first_object_and_repairs_nothing(self):
        self.assertEqual(parse_reply('```json\n{"status": "not_found"}\n```'), {"status": "not_found"})
        self.assertIsNone(parse_reply("no json here"))
        self.assertIsNone(parse_reply('{"status": '))
        self.assertIsNone(parse_reply(None))

    def test_merge_lists_conflicts_and_ignores_spacing(self):
        t = texts_for("zh-CN")
        contracts = [c.as_json() for c in build_contracts(True)]
        results = [{"id": "deadline-syllabus", "reply": good_reply("zh-CN", "d1")},
                   {"id": "deadline-notice", "reply": good_reply("zh-CN", "d2")}]
        merged = merge_check(t, contracts=contracts, results=results)
        self.assertEqual([item["id"] for item in merged["conflicts"]], ["deadline"])
        self.assertEqual({item["doc"] for item in merged["conflicts"][0]["values"]}, {"d1", "d2"})
        same = {**good_reply("zh-CN", "d2"), "value": "12月12日 23:59"}
        same["evidence"] = [{"doc": "d2", "quote": t.docs["d2"][:5]}]
        merged = merge_check(t, contracts=contracts, results=[results[0], {"id": "deadline-notice", "reply": same}])
        self.assertEqual(merged["conflicts"], [])

    def test_merge_check_errors_are_structured(self):
        t = texts_for("en")
        call = {"id": "c1", "type": "function",
                "function": {"name": "merge_check", "arguments": json.dumps({"contracts": "x", "results": []})}}
        from functools import partial
        result = execute_tool(call, {"merge_check": partial(merge_check, t)}, "en")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], t.merge_not_list)
        self.assertIn("error_type", result)


class BudgetTests(unittest.TestCase):
    def test_grant_names_the_reason_it_refuses(self):
        now = [0.0]
        budget = SharedBudget(calls=2, tokens=300, run_ms=1000, clock=lambda: now[0])
        self.assertIsNone(budget.grant())
        self.assertEqual(budget.charge({"usage": {"total_tokens": 320}}), 320)
        self.assertEqual(budget.grant(), "tokens")
        budget.tokens = 1000
        self.assertIsNone(budget.grant())
        self.assertEqual(budget.grant(), "calls")
        budget.refund()
        now[0] = 1.5
        self.assertEqual(budget.grant(), "time")

    def test_unreported_usage_is_counted_never_guessed(self):
        budget = SharedBudget(calls=3, tokens=100, run_ms=1000)
        self.assertIsNone(budget.charge({"choices": []}))
        self.assertIsNone(budget.charge({"usage": {"total_tokens": True}}))
        self.assertEqual((budget.tokens_used, budget.unreported), (0, 2))
        self.assertEqual(budget.snapshot()["unreported_calls"], 2)

    def test_cancel_passes_from_parent_to_child(self):
        root = Scope()
        first, second = root.child(), root.child()
        first.cancel("deadline")
        self.assertEqual((first.reason, second.reason, root.reason), ("deadline", None, None))
        root.cancel("run_deadline")
        self.assertEqual(second.reason, "run_deadline")
        self.assertEqual(first.reason, "deadline")  # its own reason came first
        with self.assertRaises(SubtaskCancelled):
            second.check()


class RunTests(unittest.TestCase):
    def test_full_contract_merges_and_lists_the_conflict(self):
        for locale in LOCALES:
            answer, events = run_case({"contract": "full"}, locale=locale)
            t = texts_for(locale)
            requests = of(events, "request")
            self.assertEqual(sorted(item["branch"] for item in requests), sorted(SUBTASK_IDS))
            for delegate in of(events, "lesson.delegate"):
                docs = next(docs for sid, _, docs, _ in PLAN if sid == delegate["subtask"])
                self.assertEqual(delegate["context"]["docs_seen"], list(docs))
            # Dispatch follows priority; ties keep plan order.
            self.assertEqual([item["subtask"] for item in of(events, "lesson.delegate")], list(SUBTASK_IDS))
            merge = of(events, "lesson.merge")[0]
            self.assertEqual(merge["status"], "needs_review")
            self.assertEqual([item["id"] for item in merge["conflicts"]], ["deadline"])
            self.assertEqual(metric(events, "verdict"), t.verdicts["needs_review"])
            self.assertTrue(all(check(events, sid)["passed"] for sid in SUBTASK_IDS))
            self.assertTrue(check(events, "required")["passed"])
            self.assertEqual(metric(events, "model_calls"), 5)
            self.assertIsInstance(metric(events, "total_tokens"), int)
            f = fixture_texts_for(locale)
            self.assertIn(f.values["d1"], answer)
            self.assertIn(f.values["d2"], answer)
            plan = of(events, "lesson.plan")[-1]
            self.assertEqual({step["status"] for step in plan["steps"]}, {"done"})

    def test_contract_without_evidence_returns_everything_and_passes_nothing(self):
        answer, events = run_case({"contract": "no_evidence"})
        t = texts_for("zh-CN")
        self.assertFalse(of(events, "lesson.delegate")[0]["evidence_required"])
        self.assertEqual(of(events, "lesson.task_card")[0]["evidence"], t.card_evidence_missing)
        self.assertEqual({item["status"] for item in of(events, "lesson.subtask")}, {"returned"})
        verdicts = of(events, "tool_result")[0]["result"]["result"]["verdicts"]
        self.assertEqual({tuple(item["problems"]) for item in verdicts}, {("no_evidence",)})
        self.assertEqual(of(events, "lesson.merge")[0]["status"], "incomplete")
        self.assertFalse(check(events, "required")["passed"])
        self.assertTrue(answer.startswith(t.answer_header.format(verdict=t.verdicts["incomplete"])))

    def test_tight_budget_stops_by_priority_and_lists_the_rest(self):
        answer, events = run_case({"budget_calls": 3})
        self.assertEqual(sorted(item["branch"] for item in of(events, "request")),
                         sorted(["deadline-syllabus", "team-size", "weight"]))
        stop = of(events, "lesson.budget_stop")[0]
        self.assertEqual((stop["reason"], stop["not_started"]), ("calls", ["deadline-notice", "late-policy"]))
        merge = of(events, "lesson.merge")[0]
        # The cross-check never ran, so the conflict it would have found is not there: fewer checks, not more truth.
        self.assertEqual((merge["status"], merge["conflicts"]), ("complete_with_gaps", []))
        self.assertNotIn("passed", check(events, "deadline-notice"))  # no check ran, so no passed flag
        steps = {step["id"]: step["status"] for step in of(events, "lesson.plan")[-1]["steps"]}
        self.assertEqual(steps["late-policy"], "skipped")
        self.assertEqual(metric(events, "model_calls"), 3)
        self.assertIn("deadline-notice", answer)

    def test_timeout_cancels_one_subtask_charges_it_and_merges_the_rest(self):
        for locale in LOCALES:
            answer, events = run_case({"tight_subtask": "weight", "tight_deadline_ms": 50}, locale=locale)
            timed_out = [item for item in of(events, "lesson.subtask") if item["status"] == "timed_out"]
            self.assertEqual([(item["subtask"], item["reason"]) for item in timed_out], [("weight", "deadline")])
            late = of(events, "lesson.late_response")
            self.assertEqual(late[0]["subtask"], "weight")
            self.assertTrue(late[0]["discarded"])
            self.assertIsInstance(late[0]["total_tokens"], int)
            # The late request was really sent and recorded; its result is not among the merged ones.
            self.assertIn("weight", [item["branch"] for item in of(events, "response")])
            merged_ids = [item["id"] for item in of(events, "tool_result")[0]["result"]["result"]["verdicts"]]
            self.assertNotIn("weight", merged_ids)
            merge = of(events, "lesson.merge")[0]
            self.assertEqual((merge["status"], merge["required_missing"]), ("incomplete", ["weight"]))
            self.assertEqual(metric(events, "model_calls"), 5)
            self.assertEqual(metric(events, "late"), 1)
            self.assertNotIn("passed", check(events, "weight"))
            self.assertIn("weight", answer)

    def test_token_budget_refuses_once_reported_usage_reaches_it(self):
        _, events = run_case({"budget_tokens": 100, "max_parallel": 1})
        self.assertEqual(len(of(events, "request")), 1)
        stop = of(events, "lesson.budget_stop")[0]
        self.assertEqual(stop["reason"], "tokens")
        self.assertEqual(len(stop["not_started"]), 4)

    def test_run_deadline_cancels_every_running_subtask_from_the_root(self):
        _, events = run_case({"run_deadline_ms": 100, "max_parallel": 2})
        timed_out = [item for item in of(events, "lesson.subtask") if item["status"] == "timed_out"]
        self.assertEqual({item["reason"] for item in timed_out}, {"run_deadline"})
        self.assertEqual(len(timed_out), 2)
        stop = of(events, "lesson.budget_stop")[0]
        self.assertEqual((stop["reason"], len(stop["not_started"])), ("time", 3))
        self.assertEqual(len(of(events, "lesson.late_response")), 2)
        self.assertEqual(of(events, "lesson.merge")[0]["status"], "incomplete")

    def test_unreported_usage_shows_as_not_reported(self):
        offline = create_completion("full-contract", None, "en")

        def no_usage(body, api_key):
            response = offline(body, api_key)
            response.pop("usage")
            return response

        _, events = run_case({"contract": "full"}, completion=no_usage, locale="en")
        t = texts_for("en")
        self.assertEqual(metric(events, "total_tokens"), t.value_not_reported)
        self.assertIsNone(of(events, "lesson.subtask")[0]["total_tokens"])
        self.assertIn("5", metric(events, "budget_tokens"))

    def test_one_failing_subtask_does_not_stop_the_others(self):
        offline = create_completion("full-contract", None, "zh-CN")
        t = texts_for("zh-CN")

        def flaky(body, api_key):
            if t.docs["d5"] in body["messages"][1]["content"]:
                raise ConnectionError("provider unreachable")
            return offline(body, api_key)

        _, events = run_case({"contract": "full"}, completion=flaky)
        failed = [item for item in of(events, "lesson.subtask") if item["status"] == "failed"]
        self.assertEqual([(item["subtask"], item["error_type"]) for item in failed], [("late-policy", "ConnectionError")])
        self.assertEqual(of(events, "lesson.merge")[0]["status"], "needs_review")
        self.assertNotIn("passed", check(events, "late-policy"))

    def test_a_stop_request_ends_the_run(self):
        calls = []

        def stop_after_first(body, api_key):
            calls.append(1)
            return create_completion("full-contract")(body, api_key)

        with self.assertRaises(RunCancelled):
            run_case({"contract": "full"}, completion=stop_after_first, cancelled=lambda: bool(calls))

    def test_inputs_are_validated(self):
        for bad in ({"budget_calls": 0}, {"budget_calls": 6}, {"max_parallel": 0}, {"tight_subtask": "other"},
                    {"contract": "loose"}, {"tight_deadline_ms": 0}, {"label": "x"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)

    def test_english_run_has_no_chinese_and_selectors_hit(self):
        _, events = run_case({"tight_subtask": "weight", "tight_deadline_ms": 50}, locale="en",
                             question="note")
        self.assertIsNone(CJK.search(json.dumps([data for _, data, _ in events], ensure_ascii=False)))
        trace = as_trace(events)
        for selector in ({"event": "lesson.subtask", "path": "data.timed_out_after_ms"},
                         {"event": "lesson.late_response", "path": "data.discarded"},
                         {"event": "lesson.merge", "path": "data.conflicts[id=deadline]"},
                         {"event": "lesson.report", "path": "data.metrics[id=verdict]"},
                         {"event": "tool_result", "path": "data.result.result.verdicts[id=team-size]"}):
            self.assertTrue(select_events(selector, trace), selector)


if __name__ == "__main__":
    unittest.main()
