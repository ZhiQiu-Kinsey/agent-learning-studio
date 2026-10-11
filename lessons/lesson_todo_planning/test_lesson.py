"""Behavior tests for todo-planning: deterministic model data; the tools and the acceptance check really run in Python."""
import json
import unittest

from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.runner import RunCancelled
from lessons.lesson_todo_planning import runtime
from lessons.lesson_todo_planning.fixtures import create_completion
from lessons.lesson_todo_planning.locales import texts_for

ZH = texts_for("zh-CN")
PLAN = [{"id": key, "content": key, "status": "pending"} for key in ("ctx", "state", "budget", "card")]


def run_case(exercise_id, inputs, completion=None, budget=10, cancelled=lambda: False, locale="zh-CN"):
    events = []
    values = validate_inputs(runtime, inputs)
    context = RunContext(
        lesson_id="todo-planning", exercise_id=exercise_id, question="", mode="offline",
        model="fixture-model", representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale), max_model_calls=budget,
        cancelled=cancelled, emit_event=lambda kind, data, number: events.append((kind, data, number)),
        locale=locale,
    )
    answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def report(events):
    return of(events, "lesson.report")[-1]


def metrics(events, locale="zh-CN"):
    """Report metrics keyed by catalog field name, so one assertion covers both languages."""
    t = texts_for(locale)
    names = {getattr(t, field): field for field in vars(t) if field.startswith("label_")}
    return {names[item["label"]]: item["value"] for item in report(events)["metrics"]}


class WorkspaceTests(unittest.TestCase):
    def test_todo_write_validates_and_versions(self):
        workspace = runtime.Workspace(ZH)
        first = workspace.todo_write([{"id": "a", "content": "查资料", "status": "in_progress"}])
        self.assertEqual(first["version"], 1)
        for bad in ([], [{"id": "a", "content": "x", "status": "doing"}],
                    [{"id": "a", "content": " ", "status": "pending"}],
                    [{"id": "a", "content": "x", "status": "pending"}, {"id": "a", "content": "y", "status": "pending"}],
                    [{"id": "a", "content": "x", "status": "in_progress"}, {"id": "b", "content": "y", "status": "in_progress"}],
                    [{"id": "a", "content": "x", "status": "pending", "owner": "me"}]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                workspace.todo_write(bad)
        self.assertEqual(workspace.version, 1, "a failed update leaves the list unchanged")

    def test_tool_errors_follow_the_run_language(self):
        for locale in ("zh-CN", "en"):
            t = texts_for(locale)
            workspace = runtime.Workspace(t)
            with self.subTest(locale=locale):
                with self.assertRaises(ValueError) as caught:
                    workspace.todo_write([{"id": "a", "content": "x", "status": "in_progress"},
                                          {"id": "b", "content": "y", "status": "in_progress"}])
                self.assertEqual(str(caught.exception), t.todo_one_in_progress)
                with self.assertRaises(ValueError) as caught:
                    workspace.lookup_note("tool-selection")
                self.assertEqual(str(caught.exception), t.unknown_lesson)
                self.assertEqual(workspace.lookup_note("context-budget"),
                                 {"lesson": "context-budget", "note_id": "cb-47", "note": t.notes["context-budget"]})
        self.assertEqual(ZH.notes["messages-context"], "模型只看到本次请求里的消息，历史要由程序重发。")

    def test_diff_reports_added_removed_and_status_changes(self):
        before = [{"id": "a", "content": "x", "status": "pending"}, {"id": "b", "content": "y", "status": "pending"}]
        after = [{"id": "a", "content": "x", "status": "done"}, {"id": "c", "content": "z", "status": "pending"}]
        self.assertEqual(runtime.todo_diff(before, after),
                         {"added": ["c"], "removed": ["b"], "changed": [{"id": "a", "from": "pending", "to": "done"}]})

    def test_verifier_needs_all_lessons_with_real_note_ids(self):
        real = dict(runtime.NOTE_IDS)
        card = [{"lesson": key, "note_id": note_id, "summary": "s"} for key, note_id in real.items()]
        self.assertTrue(all(c["passed"] for c in runtime.verify_card(card, real, ZH)))
        self.assertFalse(runtime.verify_card(card[:2], real, ZH)[1]["passed"])
        forged = [{**card[0], "note_id": "mc-99"}, *card[1:]]
        self.assertFalse(runtime.verify_card(forged, real, ZH)[2]["passed"])
        self.assertFalse(runtime.verify_card(card, {"messages-context": "mc-31"}, ZH)[2]["passed"],
                         "a lesson that was never looked up does not count")
        self.assertFalse(any(c["passed"] for c in runtime.verify_card(None, real, ZH)))
        self.assertEqual(runtime.verify_card(card[:2], real, ZH)[1]["detail"],
                         "卡片里的课：application-state、messages-context")
        self.assertEqual(runtime.verify_card(card[:2], real, texts_for("en"))[1]["detail"],
                         "Lessons on the card: application-state, messages-context")


class RunTests(unittest.TestCase):
    def test_no_todo_claim_is_not_accepted(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                t = texts_for(locale)
                answer, events = run_case("no-todo", {"condition": "no_todo"}, locale=locale)
                request = of(events, "request")[0]["body"]
                self.assertNotIn("todo_write", [tool["function"]["name"] for tool in request["tools"]])
                self.assertEqual(request["messages"][0]["content"], t.base_system)
                self.assertEqual(request["messages"][1]["content"], t.task)
                self.assertTrue(answer.startswith(t.verdict_failed))
                self.assertEqual([c["passed"] for c in report(events)["checks"]], [True, False, True])
                self.assertEqual(of(events, "lesson.todo"), [])
        answer, _ = run_case("no-todo", {"condition": "no_todo"})
        self.assertIn("做好了", answer)

    def test_todo_groups_add_the_rules_to_the_system_prompt(self):
        _, events = run_case("todo", {"condition": "todo"})
        self.assertEqual(of(events, "request")[0]["body"]["messages"][0]["content"],
                         "你是学习助教。需要资料时调用工具，不要猜测要点内容或编号。全部完成后用一两句话说明结果。"
                         "开始动手前，先用 todo_write 列出步骤。每完成一步就调用 todo_write 更新状态："
                         "pending 未开始，in_progress 进行中，done 已完成；同一时间最多一项 in_progress。")
        en = texts_for("en")
        _, events = run_case("todo", {"condition": "todo"}, locale="en")
        self.assertEqual(of(events, "request")[0]["body"]["messages"][0]["content"],
                         en.base_system + " " + en.todo_rules)

    def test_todo_without_reminder_tracks_snapshots_but_injects_nothing(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                answer, events = run_case("todo", {"condition": "todo"}, locale=locale)
                self.assertTrue(answer.startswith(texts_for(locale).verdict_passed))
                self.assertEqual(len(of(events, "lesson.todo")), 1)
                self.assertEqual(of(events, "lesson.harness_injected"), [])
                self.assertEqual(metrics(events, locale)["label_todo_done"], "0/4")

    def test_reminder_is_a_separate_user_message_after_tool_results(self):
        for locale in ("zh-CN", "en"):
            with self.subTest(locale=locale):
                answer, events = run_case("todo-reminder", {"condition": "todo_reminder", "reminder_after": 2},
                                          locale=locale)
                self.assertTrue(answer.startswith(texts_for(locale).verdict_passed))
                injected = [(data, number) for kind, data, number in events if kind == "lesson.harness_injected"]
                self.assertEqual([number for _, number in injected], [3, 6])
                self.assertTrue(all(data["source"] == "harness" for data, _ in injected))
                # Only the first reminder carries first: the trace hunt looks for "the first reminder".
                self.assertEqual(["first" in data for data, _ in injected], [True, False])
                request = of(events, "request")[3]["body"]["messages"]
                self.assertEqual([m["role"] for m in request[-3:]], ["assistant", "tool", "user"])
                self.assertEqual(request[-1]["content"], injected[0][0]["text"])
                self.assertEqual(injected[0][0]["text"], runtime.reminder_text(2, texts_for(locale)))
                snapshots = of(events, "lesson.todo")
                self.assertEqual([s["version"] for s in snapshots], [1, 2, 3])
                self.assertEqual(snapshots[1]["diff"]["changed"][0], {"id": "ctx", "from": "in_progress", "to": "done"})
                values = metrics(events, locale)
                self.assertEqual(values["label_reminders"], 2)
                self.assertEqual(values["label_todo_done"], "4/4")
        self.assertEqual(runtime.reminder_text(2, ZH),
                         "<reminder>已经 2 轮没有更新 TODO。请先用 todo_write 更新清单，再继续。</reminder>")

    def test_self_report_metric_is_found_by_its_id(self):
        # The lab's observation point selects data.metrics[id=last_claim], not a position.
        from server.selectors import resolve_path
        for locale in ("zh-CN", "en"):
            _, events = run_case("todo", {"condition": "todo"}, locale=locale)
            metric = resolve_path({"data": report(events)}, "data.metrics[id=last_claim]")
            self.assertEqual(metric["label"], texts_for(locale).label_last_claim)

    def test_todo_claims_do_not_override_the_card(self):
        def lying(body, key):
            done = [{**item, "status": "done"} for item in PLAN]
            if any(m["role"] == "tool" for m in body["messages"]):
                return {"choices": [{"message": {"content": "全部完成。"}, "finish_reason": "stop"}]}
            return {"choices": [{"message": {"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
                "name": "todo_write", "arguments": json.dumps({"todos": done})}}]}, "finish_reason": "tool_calls"}]}
        answer, events = run_case("todo", {"condition": "todo"}, lying)
        self.assertEqual(metrics(events)["label_todo_done"], "4/4")
        self.assertTrue(answer.startswith("验收未通过"))

    def test_budget_and_cancel(self):
        def forever(body, key):
            return {"choices": [{"message": {"content": None, "tool_calls": [{"id": "c", "type": "function", "function": {
                "name": "lookup_note", "arguments": "{\"lesson\": \"messages-context\"}"}}]}}]}
        answer, events = run_case("todo", {"condition": "todo"}, forever, budget=3)
        self.assertEqual(len(of(events, "request")), 3)
        self.assertIn("3 次调用内没有结束", answer)
        answer, _ = run_case("todo", {"condition": "todo"}, forever, budget=3, locale="en")
        self.assertEqual(answer, "Acceptance failed: not finished within 3 calls.")
        with self.assertRaises(RunCancelled):
            run_case("todo", {"condition": "todo"}, cancelled=lambda: True)
        with self.assertRaises(ValidationError):
            validate_inputs(runtime, {"condition": "todo", "reminder_after": 9})

    def test_tool_definitions_keep_names_and_default_to_all_three(self):
        zh, en = runtime.tool_definitions("zh-CN"), runtime.tool_definitions("en")
        self.assertEqual([tool["function"]["name"] for tool in zh], ["lookup_note", "save_card", "todo_write"])
        self.assertEqual([tool["function"]["name"] for tool in en], ["lookup_note", "save_card", "todo_write"])
        self.assertEqual(zh[0]["function"]["description"], "查询某一课的复习要点和要点编号。")
        self.assertEqual(len(runtime.tool_definitions("en", "no_todo")), 2)


if __name__ == "__main__":
    unittest.main()
