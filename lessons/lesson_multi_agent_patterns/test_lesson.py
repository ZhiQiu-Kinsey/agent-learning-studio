"""Behavior tests for multi-agent-patterns: deterministic model data; the verifier tool, merge and context audit really run."""
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_multi_agent_patterns import runtime
from lessons.lesson_multi_agent_patterns.fixtures import create_completion
from lessons.lesson_multi_agent_patterns.locales import texts_for
from lessons.lesson_multi_agent_patterns.locales.fixture import texts_for as fixture_texts_for
from lessons.lesson_multi_agent_patterns.verifier import GOLD, TOPICS, verify_quiz
from server.selectors import MISSING, count_events, resolve_path, select_events

LOCALES = ("zh-CN", "en")
MODES = {"single": 1, "workflow": 3, "roles": 3, "multi": 5}


def run_case(inputs, completion=None, budget=6, cancelled=lambda: False, locale="zh-CN", question=""):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="multi-agent-patterns", exercise_id=values["mode"], question=question, mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(values["mode"], values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def metric(events, metric_id):
    return next(item["value"] for item in of(events, "lesson.report")[-1]["metrics"] if item.get("id") == metric_id)


def good_question(t, topic):
    f = fixture_texts_for("en" if t is texts_for("en") else "zh-CN")
    doc = {"fallback_label": "d1", "worker_cap": "d2", "max_iters": "d3"}[topic]
    others = {"fallback_label": ["course", "error", "account"], "worker_cap": ["6", "3", "8"],
              "max_iters": ["5", "1", "10"]}[topic]
    return {"topic": topic, "question": "q", "options": [GOLD[topic], *others], "answer": 0,
            "evidence": {"doc": doc, "quote": f.quotes[doc]}}


class VerifierTests(unittest.TestCase):
    def test_fixture_quotes_are_copied_from_the_documents(self):
        for locale in LOCALES:
            t, f = texts_for(locale), fixture_texts_for(locale)
            for doc, quote in f.quotes.items():
                self.assertIn(quote, t.docs[doc], (locale, doc))

    def test_a_correct_list_passes(self):
        for locale in LOCALES:
            t = texts_for(locale)
            result = verify_quiz(t, [good_question(t, topic) for topic in TOPICS])
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["passed_topics"], 3)

    def test_each_problem_code(self):
        t = texts_for("zh-CN")
        good = [good_question(t, topic) for topic in TOPICS]

        def problems(items):
            return {item["topic"]: item["problems"] for item in verify_quiz(t, items)["topics"]}

        outdated = {**good[1], "options": ["6", "4", "3", "8"],
                    "evidence": {"doc": "d4", "quote": fixture_texts_for("zh-CN").quotes["d4"]}}
        self.assertEqual(problems([good[0], outdated, good[2]])["worker_cap"], ["outdated_source", "wrong_answer"])
        made_up = {**good[0], "evidence": {"doc": "d1", "quote": "兜底标签是 course"}}
        self.assertEqual(problems([made_up, good[1], good[2]])["fallback_label"], ["quote_not_found"])
        self.assertEqual(problems([{**good[2], "answer": True}, good[0], good[1]])["max_iters"], ["format"])
        self.assertEqual(problems([{**good[2], "options": ["3", "3", "1", "10"]}, good[0], good[1]])["max_iters"], ["format"])
        self.assertEqual(problems(good[:2])["max_iters"], ["missing"])
        self.assertEqual(problems([*good, good[0]])["fallback_label"], ["duplicate"])
        # "40" is not the value 4; a second option stating the value makes the question ambiguous.
        self.assertEqual(problems([good[0], {**good[1], "options": ["40", "6", "3", "8"]}, good[2]])["worker_cap"],
                         ["wrong_answer"])
        self.assertEqual(problems([good[0], {**good[1], "options": ["4", "4 个", "3", "8"]}, good[2]])["worker_cap"],
                         ["wrong_answer"])

    def test_not_a_list_is_a_value_error(self):
        for locale in LOCALES:
            t = texts_for(locale)
            with self.assertRaises(ValueError) as caught:
                verify_quiz(t, None)
            self.assertEqual(str(caught.exception), t.verifier_not_list)


class MergeTests(unittest.TestCase):
    def test_duplicates_and_conflicts(self):
        merged = runtime.merge_facts({
            "researcher-2": [{"topic": "worker_cap", "value": "4", "doc": "d2"}],
            "researcher-3": [{"topic": "max_iters", "value": "3", "doc": "d3"},
                             {"topic": "worker_cap", "value": "6", "doc": "d4"}, "not a fact",
                             {"topic": "unknown", "value": "x"}],
        })
        self.assertEqual(merged["duplicates"], ["worker_cap"])
        self.assertEqual(merged["conflicts"], [{"topic": "worker_cap", "values": [
            {"agent": "researcher-2", "value": "4", "doc": "d2"}, {"agent": "researcher-3", "value": "6", "doc": "d4"}]}])
        self.assertEqual(merged["missing"], ["fallback_label"])
        self.assertEqual([fact["agent"] for fact in merged["facts"]], ["researcher-2", "researcher-3", "researcher-3"])

    def test_same_value_twice_is_duplicate_work_not_a_conflict(self):
        merged = runtime.merge_facts({"a": [{"topic": "max_iters", "value": "3"}], "b": [{"topic": "max_iters", "value": " 3 "}]})
        self.assertEqual((merged["duplicates"], merged["conflicts"]), (["max_iters"], []))

    def test_extract_json(self):
        self.assertEqual(runtime.extract_json('结果：```json\n{"facts": []}\n```'), {"facts": []})
        self.assertIsNone(runtime.extract_json("没有 JSON"))
        self.assertIsNone(runtime.extract_json("{broken"))
        self.assertIsNone(runtime.questions_of("[1, 2]"))
        self.assertEqual(runtime.facts_of('{"facts": "no"}'), [])


class ModeTests(unittest.TestCase):
    def test_every_mode_in_both_languages(self):
        for locale in LOCALES:
            for mode, calls in MODES.items():
                with self.subTest(locale=locale, mode=mode):
                    answer, events = run_case({"mode": mode}, locale=locale)
                    self.assertEqual(len(of(events, "request")), calls)
                    self.assertEqual(metric(events, "model_calls"), calls)
                    # The verifier is a real tool call made by the runner, after the last model round.
                    tool_call, tool_result = of(events, "tool_call")[-1], of(events, "tool_result")[-1]
                    self.assertEqual((tool_call["function"]["name"], tool_call["origin"]), ("verify_quiz", "course_program"))
                    self.assertTrue(tool_result["result"]["ok"])
                    rounds = [number for kind, _, number in events if kind == "tool_call"]
                    self.assertEqual(rounds, [max(number for kind, _, number in events if kind == "request") + 1])
                    self.assertIsInstance(metric(events, "total_tokens"), int)
                    plans = of(events, "lesson.plan")
                    self.assertEqual([plan["event"] for plan in plans], ["created", "progress"])
                    self.assertEqual(plans[0]["steps"][-1]["id"], "verify")
                    self.assertTrue(answer)

    def test_baselines_pass_and_minimal_handoff_fails_on_the_old_draft(self):
        for mode in ("single", "workflow", "roles"):
            _, events = run_case({"mode": mode})
            self.assertTrue(of(events, "tool_result")[-1]["result"]["result"]["passed"], mode)
            self.assertEqual(metric(events, "task"), "3/3 个考点通过")
        _, events = run_case({"mode": "multi", "handoff": "minimal"})
        verdict = of(events, "tool_result")[-1]["result"]["result"]
        self.assertFalse(verdict["passed"])
        worker = next(item for item in verdict["topics"] if item["topic"] == "worker_cap")
        self.assertEqual((worker["doc"], worker["problems"]), ("d4", ["outdated_source", "wrong_answer"]))
        check = next(item for item in of(events, "lesson.report")[-1]["checks"] if item["id"] == "worker_cap")
        self.assertFalse(check["passed"])
        self.assertEqual(metric(events, "conflicts"), 1)
        self.assertEqual(metric(events, "duplicates"), 1)
        self.assertEqual(of(events, "lesson.plan")[-1]["steps"][-1]["status"], "failed")

    def test_handoff_with_rules_removes_the_conflict(self):
        for locale in LOCALES:
            _, events = run_case({"mode": "multi", "handoff": "with_rules"}, locale=locale)
            self.assertTrue(of(events, "tool_result")[-1]["result"]["result"]["passed"])
            merge = of(events, "lesson.merge")[0]
            self.assertEqual((merge["conflicts"], merge["duplicates"]), ([], []))
            self.assertEqual(metric(events, "handoff"), texts_for(locale).handoff_names["with_rules"])

    def test_handoff_only_matters_for_independent_agents(self):
        _, minimal = run_case({"mode": "single", "handoff": "minimal"})
        _, rules = run_case({"mode": "single", "handoff": "with_rules"})
        strip = lambda events: [data["body"] for data in of(events, "request")]
        self.assertEqual(strip(minimal), strip(rules))
        self.assertEqual(metric(minimal, "handoff"), texts_for("zh-CN").handoff_not_used)


class ContextTests(unittest.TestCase):
    def agents(self, mode, **extra):
        _, events = run_case({"mode": mode, **extra})
        return events, of(events, "lesson.agent")

    def test_role_switching_shares_one_history_and_one_identity(self):
        events, agents = self.agents("roles")
        self.assertEqual({agent["agent"] for agent in agents}, {"assistant"})
        self.assertEqual([agent["role"] for agent in agents], ["researcher", "writer", "reviewer"])
        self.assertEqual([agent["context"]["history"] for agent in agents], [0, 1, 2])
        self.assertTrue(all(agent["context"]["docs"] == ["d1", "d2", "d3", "d4"] for agent in agents))
        bodies = [data["body"]["messages"] for data in of(events, "request")]
        t = texts_for("zh-CN")
        self.assertEqual([messages[0]["content"] for messages in bodies],
                         [t.role_prompts[role] for role in ("researcher", "writer", "reviewer")])
        # Everything after the system prompt in one stage is the prefix of the next stage's history.
        self.assertEqual(bodies[1][1:len(bodies[0])], bodies[0][1:])
        self.assertEqual(metric(events, "identities"), "1 个运行标识、3 种角色")

    def test_workflow_steps_start_fresh(self):
        events, agents = self.agents("workflow")
        self.assertEqual([agent["context"]["messages"] for agent in agents], [2, 2, 2])
        self.assertEqual([agent["context"]["history"] for agent in agents], [0, 0, 0])
        self.assertEqual(agents[1]["context"]["docs"], [])  # the writer step gets facts, not documents
        self.assertEqual(metric(events, "identities"), "3 个运行标识、3 种角色")

    def test_independent_agents_are_isolated_and_parallel_by_branch(self):
        events, agents = self.agents("multi")
        researchers = {agent["agent"]: agent for agent in agents if agent["role"] == "researcher"}
        self.assertEqual({name: agent["context"]["docs"] for name, agent in researchers.items()},
                         {"researcher-1": ["d1"], "researcher-2": ["d2"], "researcher-3": ["d3", "d4"]})
        self.assertEqual({agent["branch"] for agent in researchers.values()}, set(researchers))
        # The reviewer sees d4 too, because the draft cites it.
        self.assertEqual([agent["agent"] for agent in agents if "outdated_docs" in agent], ["researcher-3", "reviewer"])
        self.assertFalse(any(agent["context"]["sees_rule"] for agent in agents))
        requests = of(events, "request")
        self.assertEqual(sorted(data["branch"] for data in requests if "branch" in data), sorted(researchers))
        writer = next(agent for agent in agents if agent["agent"] == "writer")
        self.assertEqual((writer["context"]["docs"], writer["context"]["history"]), ([], 0))
        reviewer = next(agent for agent in agents if agent["agent"] == "reviewer")
        self.assertEqual(reviewer["context"]["docs"], ["d1", "d3", "d4"])
        self.assertEqual(metric(events, "identities"), "5 个运行标识、3 种角色")
        _, with_rules = self.agents("multi", handoff="with_rules")
        self.assertTrue(all(agent["context"]["sees_rule"] for agent in with_rules))

    def test_parallel_researchers_overlap_in_time(self):
        events, _ = self.agents("multi")
        durations = [data["duration_ms"] for data in of(events, "response")]
        self.assertLess(metric(events, "wall_ms"), sum(durations))


class InputAndBoundaryTests(unittest.TestCase):
    def test_input_validation(self):
        for bad in ({"mode": "swarm"}, {"handoff": "everything"}, {"mode": "single", "extra": 1}):
            with self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)
        self.assertEqual(validate_inputs(runtime, {}), {"mode": "single", "handoff": "minimal"})

    def test_call_budget_stops_the_multi_mode(self):
        with self.assertRaises(RuntimeError):
            run_case({"mode": "multi"}, budget=4)

    def test_cancel_stops_before_the_first_request(self):
        with self.assertRaises(RunCancelled):
            run_case({"mode": "roles"}, cancelled=lambda: True)

    def test_unparsable_output_reaches_the_verifier_as_a_structured_error(self):
        def broken(body, api_key):
            return {"choices": [{"message": {"content": "我不输出 JSON"}}]}

        answer, events = run_case({"mode": "single"}, completion=broken)
        result = of(events, "tool_result")[-1]["result"]
        self.assertEqual((result["ok"], result["error_type"]), (False, "ValueError"))
        report = of(events, "lesson.report")[-1]
        self.assertEqual(report["checks"][0]["id"], "verifier")
        self.assertEqual(metric(events, "total_tokens"), "未报告")
        self.assertIn("0/3", answer)

    def test_partly_reported_usage_is_not_estimated(self):
        script = create_completion("workflow", None, "en")
        calls = []

        def partly(body, api_key):
            response = script(body, api_key)
            calls.append(1)
            if len(calls) == 2:
                response.pop("usage")
            return response

        _, events = run_case({"mode": "workflow"}, completion=partly, locale="en")
        self.assertIn("calls not reported: 1", metric(events, "total_tokens"))
        self.assertIn("not reported", json.dumps(of(events, "lesson.report")[-1]["table"]))

    def test_learner_note_is_recorded_but_never_sent(self):
        _, events = run_case({"mode": "single"}, question="只是备注")
        self.assertNotIn("只是备注", json.dumps([data["body"] for data in of(events, "request")], ensure_ascii=False))
        self.assertIn("只是备注", json.dumps(of(events, "lesson.report")[-1]["metrics"], ensure_ascii=False))

    def test_english_runs_have_no_chinese(self):
        for mode in MODES:
            _, events = run_case({"mode": mode}, locale="en")
            dumped = json.dumps([data for _, data, _ in events], ensure_ascii=False)
            self.assertIsNone(next((ch for ch in dumped if "一" <= ch <= "鿿"), None), mode)


class ExperimentTests(unittest.TestCase):
    """While the lesson is planned the shared experiment test skips it; this checks the same things offline."""

    def test_observe_points_hit_and_predict_counts_real_events(self):
        content = json.loads((Path(__file__).parent / "content.json").read_text(encoding="utf-8"))
        manifest = json.loads((Path(__file__).parent / "lesson.json").read_text(encoding="utf-8"))
        presets = {item["id"]: item["inputs"] for item in manifest["exercises"]}
        for locale in LOCALES:
            for experiment in content["scenes"]["lab"]["experiments"]:
                runs = {}
                for arm in experiment["arms"]:
                    _, raw = run_case(arm.get("inputs") or presets[arm["exercise"]], locale=locale)
                    runs[arm["id"]] = [{"type": kind, "round": number, "data": data} for kind, data, number in raw]
                for point in experiment["observe"]:
                    with self.subTest(locale=locale, experiment=experiment["id"], observe=point["id"]):
                        self.assertTrue(any(select_events(point["selector"], events) for events in runs.values()))
                self.assertEqual({step["observe"] for step in experiment["guide"] if step.get("observe")},
                                 {point["id"] for point in experiment["observe"]})
            predict = next(block for block in content["scenes"]["understand"]["blocks"] if block["type"] == "predict")
            _, raw = run_case(presets[predict["arm"]], locale=locale)
            events = [{"type": kind, "round": number, "data": data} for kind, data, number in raw]
            self.assertEqual(count_events(predict["rule"], events), 5)

    def test_handoff_arms_differ_where_the_guide_says(self):
        def first(events, path, round_number=None):
            for kind, data, number in events:
                event = {"type": kind, "round": number, "data": data}
                value = resolve_path(event, path)
                if value is not MISSING and (round_number is None or number == round_number):
                    return value
            return MISSING

        _, minimal = run_case({"mode": "multi", "handoff": "minimal"})
        _, rules = run_case({"mode": "multi", "handoff": "with_rules"})
        self.assertEqual(first([e for e in minimal if e[0] == "lesson.agent"], "data.outdated_docs", 1), ["d4"])
        self.assertFalse(first([e for e in minimal if e[0] == "lesson.agent"], "data.context.sees_rule", 1))
        self.assertTrue(first([e for e in rules if e[0] == "lesson.agent"], "data.context.sees_rule", 1))
        self.assertGreater(metric(rules, "input_chars"), metric(minimal, "input_chars"))


if __name__ == "__main__":
    unittest.main()
