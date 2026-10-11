"""Behavior tests for workflow-patterns: deterministic model data; gates, routing statistics and timing really run in Python."""
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_workflow_patterns import runtime
from lessons.lesson_workflow_patterns.fixtures import create_completion
from lessons.lesson_workflow_patterns.locales import texts_for
from server.envelope import SpanTracker
from server.selectors import select_events


def run_case(exercise_id, inputs, completion=None, budget=20, cancelled=lambda: False, locale="zh-CN"):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="workflow-patterns", exercise_id=exercise_id, question="", mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def reply(content):
    return {"choices": [{"message": {"content": content}}]}


class ChainTests(unittest.TestCase):
    def test_gates(self):
        zh, en = texts_for("zh-CN"), texts_for("en")
        for t in (zh, en):
            self.assertTrue(runtime.gate(t, 0, "- a\n- b\n- c")[0])
            self.assertFalse(runtime.gate(t, 0, "- a\n- b")[0])
            self.assertFalse(runtime.gate(t, 0, "1. a\n2. b\n3. c")[0])
            self.assertTrue(runtime.gate(t, 1, "Q: 1\nA: 1\nQ: 2\nA: 2\nQ: 3\nA: 3")[0])
            self.assertFalse(runtime.gate(t, 1, "Q: 1\nA: 1")[0])
            self.assertTrue(runtime.gate(t, 2, '["一", "二", "三"]')[0])
            self.assertFalse(runtime.gate(t, 2, "一、二、三")[0])
        self.assertFalse(runtime.gate(zh, 2, '["一个太长太长的标题", "二", "三"]')[0])
        self.assertEqual(runtime.gate(zh, 0, "- a\n- b"), (False, "2 行，需要恰好 3 行且都以“- ”开头"))
        # English titles are longer than Chinese ones, so the English catalog allows more characters.
        self.assertTrue(runtime.gate(en, 2, '["What the model sees", "Messages in pairs", "Choosing context"]')[0])
        self.assertFalse(runtime.gate(en, 2, '["A title that is far too long for the gate", "b", "c"]')[0])
        self.assertEqual(runtime.gate(en, 0, "- a\n- b"), (False, '2 lines; needs exactly 3 lines, all starting with "- "'))

    def test_chain_passes_each_output_forward(self):
        answer, events = run_case("chain", {"pattern": "chain"})
        requests = [d["body"]["messages"][0]["content"] for d in of(events, "request")]
        self.assertEqual(len(requests), 3)
        steps = of(events, "lesson.chain_step")
        self.assertIn(steps[0]["output"], requests[1], "the previous output is the next input")
        self.assertTrue(all(step["gate_passed"] for step in steps))
        self.assertIn("三步都通过", answer)

    def test_english_chain_passes_its_gates(self):
        t = texts_for("en")
        answer, events = run_case("chain", {"pattern": "chain"}, locale="en")
        first = of(events, "request")[0]["body"]["messages"][0]["content"]
        self.assertEqual(first, f"{t.chain[0][1]}\n\n{t.chain_note}")
        self.assertTrue(all(step["gate_passed"] for step in of(events, "lesson.chain_step")))
        self.assertTrue(answer.startswith("All three steps of the prompt chain passed"))
        self.assertEqual(of(events, "lesson.report")[-1]["checks"][2]["label"], "Gate of step 3: Add titles")

    def test_failed_gate_stops_the_chain(self):
        answer, events = run_case("chain", {"pattern": "chain"}, lambda body, key: reply("这是一段散文，没有列表。"))
        self.assertEqual(len(of(events, "request")), 1)
        self.assertFalse(of(events, "lesson.chain_step")[0]["gate_passed"])
        self.assertIn("停在“提取要点”", answer)
        answer, _ = run_case("chain", {"pattern": "chain"}, lambda body, key: reply("Plain prose, no list."), locale="en")
        self.assertEqual(answer, 'The prompt chain stopped at "Extract key points": the gate did not pass.')


class RoutingTests(unittest.TestCase):
    def test_accuracy_confusion_and_fallback(self):
        answer, events = run_case("routing", {"pattern": "routing"})
        routes = of(events, "lesson.route")
        self.assertEqual(len(routes), 20)
        fallback = [r for r in routes if r["fallback"]]
        self.assertEqual([(r["ticket"], r["raw"], r["predicted"]) for r in fallback], [("t12", "billing", "other")])
        # Only fallback records carry fallback_reason; the guided tour finds the fallback ticket by it.
        self.assertEqual([r["ticket"] for r in routes if "fallback_reason" in r], ["t12"])
        # Only misrouted records carry misrouted, so the trace hunt accepts only those; t12 took the fallback,
        # but the fallback label equals its label, so it is not misrouted.
        self.assertEqual([r["ticket"] for r in routes if "misrouted" in r], ["t18", "t20"])
        self.assertEqual(sum(r["correct"] for r in routes), 18)
        reports = of(events, "lesson.report")
        self.assertEqual(reports[0]["metrics"][0], {"id": "accuracy", "label": "准确率", "value": "18/20"})
        matrix = reports[1]["table"]["rows"]
        self.assertEqual(sum(sum(row[1:]) for row in matrix), 20)
        diagonal = sum(row[index + 1] for index, row in enumerate(matrix))
        self.assertEqual(diagonal, 18)
        self.assertEqual(matrix[1], ["账号与登录", 0, 4, 1, 0])
        self.assertIn("18/20", answer)

    def test_english_routing_sends_english_tickets(self):
        t = texts_for("en")
        answer, events = run_case("routing", {"pattern": "routing"}, locale="en")
        first = of(events, "request")[0]["body"]["messages"]
        self.assertEqual(first[0]["content"], runtime.router_system(t))
        self.assertIn("account (account and sign-in)", first[0]["content"])
        self.assertEqual(first[1]["content"], t.tickets["t01"])
        self.assertEqual([r["ticket"] for r in of(events, "lesson.route") if "misrouted" in r], ["t18", "t20"])
        reports = of(events, "lesson.report")
        self.assertEqual(reports[0]["metrics"][0], {"id": "accuracy", "label": "Accuracy", "value": "18/20"})
        self.assertEqual(reports[1]["table"]["rows"][1], ["account and sign-in", 0, 4, 1, 0])
        self.assertEqual(answer, "Routing finished: 18/20 match the labels, 1 took the fallback.")

    def test_router_prompt_is_unchanged_in_chinese(self):
        self.assertEqual(runtime.router_system(texts_for("zh-CN")),
                         "你负责给学习平台的工单分类。只输出一个标签，不要解释。可选标签："
                         "course（课程内容）；account（账号与登录）；error（运行报错）；other（其他）。")

    def test_trace_hunt_accepts_only_misrouted_tickets(self):
        # The frontend judgeHunt accepts only events the target selector hits: it must hit misrouted tickets only.
        content = json.loads((Path(__file__).parent / "content.json").read_text(encoding="utf-8"))
        hunt = next(block for block in content["scenes"]["check"]["blocks"] if block["type"] == "trace-hunt")
        _, events = run_case("routing", {"pattern": "routing"})
        trace = [{"type": kind, "round": number, "data": data} for kind, data, number in events]
        self.assertEqual([trace[index]["data"]["ticket"] for index in select_events(hunt["target"], trace)],
                         ["t18", "t20"])

    def test_parse_label(self):
        self.assertEqual(runtime.parse_label("Course"), ("course", False))
        self.assertEqual(runtime.parse_label("`error`\n因为报错"), ("error", False))
        self.assertEqual(runtime.parse_label("我觉得是账号问题"), ("other", True))
        self.assertEqual(runtime.parse_label(""), ("other", True))


class FanoutTests(unittest.TestCase):
    def test_parallel_overlaps_and_serial_does_not(self):
        _, serial = run_case("serial", {"pattern": "serial"})
        _, parallel = run_case("parallel", {"pattern": "parallel"})
        s, p = of(serial, "lesson.parallel")[0], of(parallel, "lesson.parallel")[0]
        self.assertGreaterEqual(s["wall_ms"], 140)
        self.assertLess(p["wall_ms"], s["wall_ms"])
        self.assertGreater(p["sum_of_branches_ms"], p["wall_ms"], "in parallel the branch durations add up to more than the wall-clock time")
        self.assertEqual({d.get("branch") for d in of(parallel, "request")}, {"messages-context", "application-state", "context-budget"})
        self.assertTrue(all("branch" not in d for d in of(serial, "request")))
        self.assertEqual(sorted(n for k, _, n in serial if k == "request"), [1, 2, 3])
        answer, events = run_case("parallel", {"pattern": "parallel"}, locale="en")
        self.assertTrue(answer.startswith("Parallel run finished: wall-clock time "))
        self.assertEqual(of(events, "request")[0]["body"]["messages"][0]["content"], texts_for("en").summary_system)
        self.assertEqual(of(events, "lesson.report")[-1]["title"], "Parallel")

    def test_parallel_spans_pair_by_branch(self):
        _, events = run_case("parallel", {"pattern": "parallel"})
        tracker = SpanTracker()
        opened, closed = {}, {}
        for kind, data, number in events:
            span = tracker.place(kind, data, number)[0]
            if kind == "request":
                opened[data["branch"]] = span
            elif kind == "response":
                closed[data["branch"]] = span
        self.assertEqual(opened, closed)

    def test_budget_is_shared_across_parallel_branches(self):
        with self.assertRaises(RuntimeError):
            run_case("parallel", {"pattern": "parallel"}, budget=2)

    def test_inputs_and_cancel(self):
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {"pattern": "swarm"})
        with self.assertRaises(RunCancelled):
            run_case("routing", {"pattern": "routing"}, cancelled=lambda: True)


if __name__ == "__main__":
    unittest.main()
