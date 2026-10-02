"""工作流模式课行为测试：确定性模型数据；检查门、路由统计和计时在 Python 中真实执行。"""
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_workflow_patterns import runtime
from lessons.lesson_workflow_patterns.fixtures import create_completion
from server.envelope import SpanTracker


def run_case(exercise_id, inputs, completion=None, budget=20, cancelled=lambda: False):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="workflow-patterns", exercise_id=exercise_id, question="", mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def reply(content):
    return {"choices": [{"message": {"content": content}}]}


class ChainTests(unittest.TestCase):
    def test_gates(self):
        self.assertTrue(runtime.gate(0, "- a\n- b\n- c")[0])
        self.assertFalse(runtime.gate(0, "- a\n- b")[0])
        self.assertFalse(runtime.gate(0, "1. a\n2. b\n3. c")[0])
        self.assertTrue(runtime.gate(1, "Q: 1\nA: 1\nQ: 2\nA: 2\nQ: 3\nA: 3")[0])
        self.assertFalse(runtime.gate(1, "Q: 1\nA: 1")[0])
        self.assertTrue(runtime.gate(2, '["一", "二", "三"]')[0])
        self.assertFalse(runtime.gate(2, '["一个太长太长的标题", "二", "三"]')[0])
        self.assertFalse(runtime.gate(2, "一、二、三")[0])

    def test_chain_passes_each_output_forward(self):
        answer, events = run_case("chain", {"pattern": "chain"})
        requests = [d["body"]["messages"][0]["content"] for d in of(events, "request")]
        self.assertEqual(len(requests), 3)
        steps = of(events, "lesson.chain_step")
        self.assertIn(steps[0]["output"], requests[1], "上一步的输出是下一步的输入")
        self.assertTrue(all(step["gate_passed"] for step in steps))
        self.assertIn("三步都通过", answer)

    def test_failed_gate_stops_the_chain(self):
        answer, events = run_case("chain", {"pattern": "chain"}, lambda body, key: reply("这是一段散文，没有列表。"))
        self.assertEqual(len(of(events, "request")), 1)
        self.assertFalse(of(events, "lesson.chain_step")[0]["gate_passed"])
        self.assertIn("停在“提取要点”", answer)


class RoutingTests(unittest.TestCase):
    def test_accuracy_confusion_and_fallback(self):
        answer, events = run_case("routing", {"pattern": "routing"})
        routes = of(events, "lesson.route")
        self.assertEqual(len(routes), 20)
        fallback = [r for r in routes if r["fallback"]]
        self.assertEqual([(r["ticket"], r["raw"], r["predicted"]) for r in fallback], [("t12", "billing", "other")])
        self.assertEqual(sum(r["correct"] for r in routes), 18)
        reports = of(events, "lesson.report")
        self.assertEqual(reports[0]["metrics"][0], {"label": "准确率", "value": "18/20"})
        matrix = reports[1]["table"]["rows"]
        self.assertEqual(sum(sum(row[1:]) for row in matrix), 20)
        diagonal = sum(row[index + 1] for index, row in enumerate(matrix))
        self.assertEqual(diagonal, 18)
        self.assertEqual(matrix[1], ["账号与登录", 0, 4, 1, 0])
        self.assertIn("18/20", answer)

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
        self.assertGreater(p["sum_of_branches_ms"], p["wall_ms"], "并行时各分支耗时之和大于墙钟时间")
        self.assertEqual({d.get("branch") for d in of(parallel, "request")}, {"messages-context", "application-state", "context-budget"})
        self.assertTrue(all("branch" not in d for d in of(serial, "request")))
        self.assertEqual(sorted(n for k, _, n in serial if k == "request"), [1, 2, 3])

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
