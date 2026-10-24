"""Behavior tests for langgraph-state: deterministic model data; the graph, routers, verifier and tool really run."""
import json
import re
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.frameworks import GRAPH_UPDATE_EVENT
from course.runner import RunCancelled
from lessons.lesson_langgraph_state import runtime
from lessons.lesson_langgraph_state.fixtures import create_completion
from lessons.lesson_langgraph_state.graph import check_evidence
from lessons.lesson_langgraph_state.locales import texts_for
from lessons.lesson_langgraph_state.study_tools import available_tools, estimate_study_days

CJK = re.compile(r"[　-〿㐀-䶿一-鿿豈-﫿＀-￯]")
PRESETS = {
    "normal": {"lessons": "chat-request, tool-selection, application-state", "minutes_per_day": 30},
    "missing": {"lessons": "chat-request, tool-selection", "minutes_per_day": None},
    "repair-fail": {"lessons": "application-state, agent-magic", "minutes_per_day": 30, "max_repairs": 1},
    "recursion-limit": {"lessons": "application-state, agent-magic", "minutes_per_day": 30, "max_repairs": 3,
                        "recursion_limit": 6},
}


class Recorder:
    def __init__(self, completion):
        self._completion = completion
        self.calls = 0
        self.bodies = []

    def __call__(self, body, api_key):
        self.calls += 1
        self.bodies.append(body)
        return self._completion(body, api_key)


def run_case(exercise_id, inputs=None, completion=None, locale="zh-CN", budget=6, cancelled=lambda: False):
    events = []
    values = validate_inputs(runtime, PRESETS[exercise_id] if inputs is None else inputs)
    recorder = Recorder(completion or create_completion(exercise_id, values, locale))
    context = RunContext(
        lesson_id="langgraph-state", exercise_id=exercise_id, question="", mode="offline", model="fixture-model",
        representation="sdk_standardized", inputs=values, api_key="", completion=recorder, max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events, recorder


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def path_of(events):
    return [data["node"] for data in of(events, GRAPH_UPDATE_EVENT)]


def metric(report, metric_id):
    return next(item["value"] for item in report["metrics"] if item["id"] == metric_id)


def check(report, check_id):
    return next(item for item in report["checks"] if item["id"] == check_id)


def tool_reply(call_id, lessons, minutes):
    return {"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": call_id, "type": "function", "function": {
            "name": "estimate_study_days", "arguments": json.dumps({"lessons": lessons, "minutes_per_day": minutes})}}]}}]}


class ToolTests(unittest.TestCase):
    def test_estimate_is_computed_from_the_table(self):
        t = texts_for("zh-CN")
        self.assertEqual(estimate_study_days(t, ["chat-request", "tool-selection", "application-state"], 30),
                         {"lessons": ["chat-request", "tool-selection", "application-state"],
                          "total_minutes": 95, "minutes_per_day": 30, "days": 4})
        self.assertEqual(estimate_study_days(t, ["chat-request"], 20)["days"], 1)

    def test_business_errors_become_structured_results(self):
        from course.runner import execute_tool
        for locale in ("zh-CN", "en"):
            tools = available_tools(texts_for(locale))
            call = {"id": "c1", "type": "function", "function": {
                "name": "estimate_study_days", "arguments": '{"lessons": ["agent-magic"], "minutes_per_day": 30}'}}
            result = execute_tool(call, tools, locale)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error_type"], "ValueError")
            self.assertIn("agent-magic", result["error"])
            bad = {**call, "function": {**call["function"], "arguments": '{"lessons": [], "minutes_per_day": 30}'}}
            self.assertEqual(execute_tool(bad, tools, locale)["error"], texts_for(locale).tool_lessons_invalid)
            zero = {**call, "function": {**call["function"], "arguments": '{"lessons": ["chat-request"], "minutes_per_day": 0}'}}
            self.assertEqual(execute_tool(zero, tools, locale)["error"], texts_for(locale).tool_minutes_invalid)
        self.assertNotRegex(texts_for("en").tool_unknown_lessons, CJK)

    def test_verifier_reads_structured_evidence(self):
        request = {"lessons": ["chat-request", "tool-selection"], "minutes_per_day": 30}
        ok = {"ok": True, "arguments": {"lessons": ["tool-selection", "chat-request"], "minutes_per_day": 30}}
        self.assertEqual(check_evidence([ok], request), [], "lesson order does not matter")
        self.assertEqual(check_evidence([], request), ["no_tool_call"])
        dropped = {"ok": True, "arguments": {"lessons": ["chat-request"], "minutes_per_day": 30}}
        self.assertEqual(check_evidence([dropped], request), ["arguments_mismatch"])
        self.assertEqual(check_evidence([{"ok": False, "arguments": request}], request), ["tool_error"])
        self.assertEqual(check_evidence([{"ok": False, "arguments": request}, ok], request), ["tool_error"])


class PathTests(unittest.TestCase):
    def test_normal_path_reaches_answer(self):
        answer, events, recorder = run_case("normal")
        self.assertEqual(path_of(events), ["intake", "plan", "tools", "verify", "answer"])
        self.assertIn("4 天", answer)
        routes = of(events, "lesson.graph_route")
        self.assertEqual([(r["from"], r["to"]) for r in routes], [("intake", "plan"), ("verify", "answer")])
        self.assertEqual(routes[0]["read"], {"missing": []})
        self.assertEqual(routes[1]["read"], {"verdict": "passed", "failed_checks": 0, "max_repairs": 1})
        report = of(events, "lesson.report")[-1]
        self.assertEqual(metric(report, "status"), "completed")
        self.assertTrue(all(item["passed"] for item in report["checks"]))
        # The answer node sees only the checked result: no tools, no tool history.
        writer = recorder.bodies[-1]
        self.assertNotIn("tools", writer)
        self.assertEqual([m["role"] for m in writer["messages"]], ["system", "user"])

    def test_missing_parameter_ends_without_model_calls(self):
        answer, events, recorder = run_case("missing")
        self.assertEqual(path_of(events), ["intake", "ask_user"])
        self.assertEqual(recorder.calls, 0)
        self.assertEqual(of(events, "request"), [])
        self.assertEqual(of(events, GRAPH_UPDATE_EVENT)[0]["update"]["missing"], ["minutes_per_day"])
        self.assertEqual(of(events, GRAPH_UPDATE_EVENT)[1]["update"]["status"], "needs_input")
        self.assertIn("minutes_per_day", answer)
        # An empty lesson list is missing too, and both fields are named.
        _, events, _ = run_case("missing", {"lessons": "", "minutes_per_day": None})
        self.assertEqual(of(events, GRAPH_UPDATE_EVENT)[0]["update"]["missing"], ["lessons", "minutes_per_day"])

    def test_failed_checks_go_back_once_then_fail(self):
        answer, events, recorder = run_case("repair-fail")
        self.assertEqual(path_of(events),
                         ["intake", "plan", "tools", "verify", "plan", "tools", "verify", "fail"])
        verify_routes = [r for r in of(events, "lesson.graph_route") if r["from"] == "verify"]
        self.assertEqual([(r["read"]["failed_checks"], r["to"]) for r in verify_routes], [(1, "plan"), (2, "fail")])
        self.assertTrue(all(not r["result"]["ok"] for r in of(events, "tool_result")))
        # The repair request carries the verifier's feedback after the tool error.
        second = recorder.bodies[1]["messages"]
        self.assertEqual([m["role"] for m in second[-3:]], ["assistant", "tool", "user"])
        self.assertTrue(second[-1]["content"].startswith("校验未通过"))
        report = of(events, "lesson.report")[-1]
        self.assertEqual(metric(report, "status"), "failed")
        self.assertEqual(metric(report, "failed_checks"), 2)
        self.assertTrue(answer.startswith("未完成"))

    def test_no_repairs_fails_at_the_first_check(self):
        inputs = {**PRESETS["repair-fail"], "max_repairs": 0}
        _, events, recorder = run_case("repair-fail", inputs)
        self.assertEqual(path_of(events), ["intake", "plan", "tools", "verify", "fail"])
        self.assertEqual(recorder.calls, 1)

    def test_a_repair_can_succeed(self):
        replies = iter([tool_reply("c1", ["chat-request"], 30), tool_reply("c2", ["tool-selection", "chat-request"], 30),
                        {"choices": [{"message": {"role": "assistant", "content": "需要 2 天。"}}]}])
        _, events, recorder = run_case("normal", {"lessons": "chat-request, tool-selection", "minutes_per_day": 30},
                                       completion=lambda body, key: next(replies))
        self.assertEqual(path_of(events),
                         ["intake", "plan", "tools", "verify", "plan", "tools", "verify", "answer"])
        first_verify = [d["update"] for d in of(events, GRAPH_UPDATE_EVENT) if d["node"] == "verify"][0]
        self.assertEqual(first_verify["problems"], ["arguments_mismatch"])
        self.assertEqual(recorder.calls, 3)
        self.assertTrue(check(of(events, "lesson.report")[-1], "answer-days")["passed"])

    def test_recursion_limit_stops_the_graph_honestly(self):
        answer, events, recorder = run_case("recursion-limit")
        self.assertEqual(path_of(events), ["intake", "plan", "tools", "verify", "plan", "tools"])
        report = of(events, "lesson.report")[-1]
        self.assertFalse(check(report, "terminal")["passed"])
        self.assertEqual(metric(report, "status"), "未到达终态")
        self.assertEqual(metric(report, "stop"), "达到 recursion_limit")
        self.assertNotIn("fail", path_of(events))
        self.assertEqual(answer, "图执行到第 6 步（tools）时达到 recursion_limit=6，LangGraph 抛出 GraphRecursionError，"
                                 "本次运行没有拿到最终状态。")
        self.assertEqual(of(events, "answer")[-1]["content"], answer)

    def test_a_path_of_n_nodes_needs_a_limit_above_n(self):
        # Measured on langgraph 1.2: the step check comes before "nothing left to run", so a limit equal to
        # the path length still raises after the last node, and the final state is not handed back.
        inputs = {**PRESETS["normal"], "recursion_limit": 5}
        answer, events, recorder = run_case("normal", inputs)
        self.assertEqual(path_of(events), ["intake", "plan", "tools", "verify", "answer"])
        self.assertEqual(recorder.calls, 2, "the answer node did run")
        self.assertIn("（answer）", answer)
        self.assertFalse(check(of(events, "lesson.report")[-1], "terminal")["passed"])
        answer, events, _ = run_case("normal", {**PRESETS["normal"], "recursion_limit": 6})
        self.assertIn("4 天", answer)

    def test_business_budget_wins_when_the_ceiling_is_high(self):
        inputs = {**PRESETS["recursion-limit"], "recursion_limit": 40}
        _, events, recorder = run_case("recursion-limit", inputs)
        self.assertEqual(path_of(events)[-1], "fail")
        self.assertEqual(len(path_of(events)), 1 + 3 * 4 + 1)
        self.assertEqual(recorder.calls, 4)

    def test_platform_budget_is_not_swallowed(self):
        with self.assertRaises(RuntimeError) as caught:
            run_case("repair-fail", budget=1)
        self.assertNotEqual(type(caught.exception).__name__, "GraphRecursionError")


class EvidenceTests(unittest.TestCase):
    def test_structure_report_comes_from_the_compiled_graph(self):
        _, events, _ = run_case("missing")
        structure = of(events, "lesson.report")[0]
        self.assertEqual(metric(structure, "nodes"), 7)
        self.assertEqual(metric(structure, "edges"), 11)
        rows = {(row[0], row[1]): row[2] for row in structure["table"]["rows"]}
        self.assertEqual(rows[("START", "intake")], "普通边")
        self.assertEqual(rows[("verify", "plan")], "条件边")
        self.assertEqual({row[1] for row in structure["table"]["rows"] if row[0] in ("answer", "ask_user", "fail")},
                         {"END"})

    def test_reducers_keep_messages_and_evidence(self):
        _, events, _ = run_case("repair-fail")
        tool_updates = [d["update"] for d in of(events, GRAPH_UPDATE_EVENT) if d["node"] == "tools"]
        # Each update carries only its own attempt; the reducer appends it to what is already there.
        self.assertEqual([[r["attempt"] for r in u["evidence"]] for u in tool_updates], [[1], [2]])
        self.assertTrue(check(of(events, "lesson.report")[-1], "evidence-kept")["passed"])
        # Fields without a reducer are overwritten: the last verify update sets failed_checks to 2.
        verify_updates = [d["update"] for d in of(events, GRAPH_UPDATE_EVENT) if d["node"] == "verify"]
        self.assertEqual([u["failed_checks"] for u in verify_updates], [1, 2])

    def test_state_updates_are_not_model_responses(self):
        for exercise_id in PRESETS:
            with self.subTest(exercise=exercise_id):
                _, events, recorder = run_case(exercise_id)
                report = of(events, "lesson.report")[-1]
                # Every model call is a request event, made by a model node; graph updates are lesson events.
                self.assertEqual(metric(report, "model_nodes"), len(of(events, "request")))
                self.assertEqual(recorder.calls, len(of(events, "response")))
                self.assertTrue(all("choices" not in json.dumps(d["update"]) for d in of(events, GRAPH_UPDATE_EVENT)))
                self.assertEqual(len(of(events, "tool_call")), len(of(events, "tool_result")))

    def test_english_runs_have_no_chinese(self):
        for exercise_id in PRESETS:
            with self.subTest(exercise=exercise_id):
                answer, events, _ = run_case(exercise_id, locale="en")
                leaks = [kind for kind, data, _ in events if CJK.search(json.dumps(data, ensure_ascii=False))]
                self.assertEqual(leaks, [])
                self.assertNotRegex(answer, CJK)


class InputAndStopTests(unittest.TestCase):
    def test_inputs_are_validated(self):
        for bad in ({"lessons": "Chat Request", "minutes_per_day": 30}, {"lessons": "a, b, c, d, e, f, g"},
                    {"minutes_per_day": 5}, {"recursion_limit": 2}, {"max_repairs": 4}, {"model": "x"}):
            with self.subTest(inputs=bad), self.assertRaises(ValidationError):
                validate_inputs(runtime, bad)
        self.assertEqual(validate_inputs(runtime, {})["lessons"], "")

    def test_cancel_stops_before_any_node(self):
        with self.assertRaises(RunCancelled):
            run_case("normal", cancelled=lambda: True)


if __name__ == "__main__":
    unittest.main()
