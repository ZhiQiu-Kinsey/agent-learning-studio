"""TODO 规划课行为测试：确定性模型数据，工具与验收器在 Python 中真实执行。"""
import json
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_todo_planning import runtime
from lessons.lesson_todo_planning.fixtures import create_completion


def run_case(exercise_id, inputs, completion=None, budget=10, cancelled=lambda: False):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="todo-planning", exercise_id=exercise_id, question="", mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def report(events):
    return of(events, "lesson.report")[-1]


def metric(events, label):
    return next(item["value"] for item in report(events)["metrics"] if item["label"] == label)


class WorkspaceTests(unittest.TestCase):
    def test_todo_write_validates_and_versions(self):
        workspace = runtime.Workspace()
        first = workspace.todo_write([{"id": "a", "content": "查资料", "status": "in_progress"}])
        self.assertEqual(first["version"], 1)
        for bad in ([], [{"id": "a", "content": "x", "status": "doing"}],
                    [{"id": "a", "content": " ", "status": "pending"}],
                    [{"id": "a", "content": "x", "status": "pending"}, {"id": "a", "content": "y", "status": "pending"}],
                    [{"id": "a", "content": "x", "status": "in_progress"}, {"id": "b", "content": "y", "status": "in_progress"}],
                    [{"id": "a", "content": "x", "status": "pending", "owner": "me"}]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                workspace.todo_write(bad)
        self.assertEqual(workspace.version, 1, "失败的更新不改变清单")

    def test_diff_reports_added_removed_and_status_changes(self):
        before = [{"id": "a", "content": "x", "status": "pending"}, {"id": "b", "content": "y", "status": "pending"}]
        after = [{"id": "a", "content": "x", "status": "done"}, {"id": "c", "content": "z", "status": "pending"}]
        self.assertEqual(runtime.todo_diff(before, after),
                         {"added": ["c"], "removed": ["b"], "changed": [{"id": "a", "from": "pending", "to": "done"}]})

    def test_verifier_needs_all_lessons_with_real_note_ids(self):
        real = {key: value["note_id"] for key, value in runtime.NOTES.items()}
        card = [{"lesson": key, "note_id": note_id, "summary": "s"} for key, note_id in real.items()]
        self.assertTrue(all(c["passed"] for c in runtime.verify_card(card, real)))
        self.assertFalse(runtime.verify_card(card[:2], real)[1]["passed"])
        forged = [{**card[0], "note_id": "mc-99"}, *card[1:]]
        self.assertFalse(runtime.verify_card(forged, real)[2]["passed"])
        self.assertFalse(runtime.verify_card(card, {"messages-context": "mc-31"})[2]["passed"], "没查过的课不能算数")
        self.assertFalse(any(c["passed"] for c in runtime.verify_card(None, real)))


class RunTests(unittest.TestCase):
    def test_no_todo_claim_is_not_accepted(self):
        answer, events = run_case("no-todo", {"condition": "no_todo"})
        tools = [tool["function"]["name"] for tool in of(events, "request")[0]["body"]["tools"]]
        self.assertNotIn("todo_write", tools)
        self.assertIn("做好了", answer)
        self.assertTrue(answer.startswith("验收未通过"))
        self.assertEqual([c["passed"] for c in report(events)["checks"]], [True, False, True])
        self.assertEqual(of(events, "lesson.todo"), [])

    def test_todo_without_reminder_tracks_snapshots_but_injects_nothing(self):
        answer, events = run_case("todo", {"condition": "todo"})
        self.assertTrue(answer.startswith("验收通过"))
        self.assertEqual(len(of(events, "lesson.todo")), 1)
        self.assertEqual(of(events, "lesson.harness_injected"), [])
        self.assertEqual(metric(events, "TODO 自报完成"), "0/4")

    def test_reminder_is_a_separate_user_message_after_tool_results(self):
        answer, events = run_case("todo-reminder", {"condition": "todo_reminder", "reminder_after": 2})
        self.assertTrue(answer.startswith("验收通过"))
        injected = [(data, number) for kind, data, number in events if kind == "lesson.harness_injected"]
        self.assertEqual([number for _, number in injected], [3, 6])
        self.assertTrue(all(data["source"] == "harness" for data, _ in injected))
        request = of(events, "request")[3]["body"]["messages"]
        self.assertEqual([m["role"] for m in request[-3:]], ["assistant", "tool", "user"])
        self.assertEqual(request[-1]["content"], injected[0][0]["text"])
        snapshots = of(events, "lesson.todo")
        self.assertEqual([s["version"] for s in snapshots], [1, 2, 3])
        self.assertEqual(snapshots[1]["diff"]["changed"][0], {"id": "ctx", "from": "in_progress", "to": "done"})
        self.assertEqual(metric(events, "运行层提醒次数"), 2)
        self.assertEqual(metric(events, "TODO 自报完成"), "4/4")

    def test_todo_claims_do_not_override_the_card(self):
        def lying(body, key):
            done = [{**item, "status": "done"} for item in runtime_plan()]
            if any(m["role"] == "tool" for m in body["messages"]):
                return {"choices": [{"message": {"content": "全部完成。"}, "finish_reason": "stop"}]}
            return {"choices": [{"message": {"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
                "name": "todo_write", "arguments": json.dumps({"todos": done})}}]}, "finish_reason": "tool_calls"}]}
        answer, events = run_case("todo", {"condition": "todo"}, lying)
        self.assertEqual(metric(events, "TODO 自报完成"), "4/4")
        self.assertTrue(answer.startswith("验收未通过"))

    def test_budget_and_cancel(self):
        def forever(body, key):
            return {"choices": [{"message": {"content": None, "tool_calls": [{"id": "c", "type": "function", "function": {
                "name": "lookup_note", "arguments": "{\"lesson\": \"messages-context\"}"}}]}}]}
        answer, events = run_case("todo", {"condition": "todo"}, forever, budget=3)
        self.assertEqual(len(of(events, "request")), 3)
        self.assertIn("3 次调用内没有结束", answer)
        with self.assertRaises(RunCancelled):
            run_case("todo", {"condition": "todo"}, cancelled=lambda: True)
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {"condition": "todo", "reminder_after": 9})


def runtime_plan():
    from lessons.lesson_todo_planning.fixtures import PLAN
    return PLAN


if __name__ == "__main__":
    unittest.main()
