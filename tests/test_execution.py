"""Runtime extension contract: real custom code, validated inputs and shared lifecycle."""
import importlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import Field, ValidationError

from course.execution import LessonInputs, RunContext, execute_lesson, validate_inputs
from course.runner import AgentSetup, RunCancelled
from run_support import run_and_read, use_temporary_run_store


class ExampleInputs(LessonInputs):
    value: int = Field(default=2, ge=1, le=9)
    label: str = Field(default="example", max_length=30)


def make_context(events, **overrides):
    values = dict(lesson_id="custom-test", exercise_id="same-id", question="question",
                  mode="live", model="configured-model", representation="sdk_standardized",
                  inputs={}, api_key="fixture-secret", completion=None,
                  emit_event=lambda kind, data, number: events.append((kind, data, number)))
    return RunContext(**{**values, **overrides})


class ContextTests(unittest.TestCase):
    def test_custom_events_are_snapshots_and_cannot_end_the_platform_stream(self):
        events = []
        context = make_context(events)
        value = {"state": {"steps": ["read"]}}
        context.emit("lesson.state", value)
        value["state"]["steps"].append("mutated")
        self.assertEqual(events[0][1]["state"]["steps"], ["read"])
        for kind in ("run_start", "done", "arbitrary"):
            with self.assertRaises(ValueError):
                context.emit(kind, {})
        self.assertNotIn("fixture-secret", repr(context))

    def test_custom_completion_reuses_provider_and_exact_request_evidence(self):
        events, bodies = [], []
        def provider(body, key):
            self.assertEqual(key, "fixture-secret")
            bodies.append(json.loads(json.dumps(body)))
            return {"choices": [{"message": {"content": "ok"}}]}
        context = make_context(events, completion=provider)
        body = {"messages": [{"role": "user", "content": "first"}]}
        context.complete(body, round_number=2)
        body["messages"][0]["content"] = "later"
        self.assertEqual(events[0][1]["body"], bodies[0])
        self.assertEqual(events[0][1]["body"]["model"], "configured-model")
        self.assertEqual(events[1][0], "response")
        self.assertEqual(events[1][1]["representation"], "sdk_standardized")
        with self.assertRaises(ValueError):
            context.complete({"model": "different-paid-model", "messages": []})
        self.assertEqual(len(bodies), 1)

    def test_cancelled_completion_and_tools_cannot_continue(self):
        events = []
        cancelled = False
        def provider(body, key):
            nonlocal cancelled
            cancelled = True
            return {"choices": [{"message": {"content": "too late"}}]}
        context = make_context(events, completion=provider, cancelled=lambda: cancelled)
        with self.assertRaises(RunCancelled):
            context.complete({"messages": []})
        called = []
        with self.assertRaises(RunCancelled):
            context.call_tool("write", {}, {"write": lambda: called.append(True)})
        self.assertEqual(called, [])

    def test_declared_tools_keep_evidence_and_unknown_tools_remain_blocked(self):
        events = []
        context = make_context(events)
        self.assertEqual(context.call_tool("double", {"value": 4}, {"double": lambda value: value * 2}),
                         {"ok": True, "result": 8})
        self.assertEqual(events[0][1]["id"], events[1][1]["tool_call_id"])
        self.assertFalse(context.call_tool("missing", {}, {})["ok"])

    def test_specialized_runtimes_share_a_bounded_model_budget(self):
        calls, events = [], []
        def provider(body, key):
            calls.append(body)
            return {"choices": [{"message": {"content": "ok"}}]}
        context = make_context(events, completion=provider, max_model_calls=1)
        context.complete({"messages": []})
        with self.assertRaises(RuntimeError):
            context.complete({"messages": []})
        self.assertEqual(len(calls), 1)
        self.assertEqual([event[0] for event in events], ["request", "response"])

    def test_composed_native_stage_preserves_the_outer_final_summary(self):
        events = []
        native = SimpleNamespace(setup=lambda locale: AgentSetup("system", [], {}))
        context = make_context(events, completion=lambda body, key: {"choices": [{"message": {"content": "child result"}}]})
        def run(context):
            result = context.run_native(native)
            return "Final summary: " + result
        execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}},
                       SimpleNamespace(run=run), context)
        self.assertEqual([data["content"] for kind, data, _ in events if kind == "answer"], ["Final summary: child result"])
        self.assertEqual([data["content"] for kind, data, _ in events if kind == "lesson.stage_result"], ["child result"])

    def test_native_budget_gate_does_not_publish_a_request_that_will_not_run(self):
        events, calls = [], []
        native = SimpleNamespace(setup=lambda locale: AgentSetup("system", [], {"echo": lambda: "result"}))
        def provider(body, key):
            calls.append(body)
            return {"choices": [{"message": {"tool_calls": [{"id": "call-1", "type": "function",
                      "function": {"name": "echo", "arguments": "{}"}}]}}]}
        context = make_context(events, completion=provider, max_model_calls=1)
        with self.assertRaises(RuntimeError):
            context.run_native(native, max_rounds=3)
        self.assertEqual(len(calls), 1)
        self.assertEqual([kind for kind, _, _ in events].count("request"), 1)
        with self.assertRaises(RuntimeError):
            context.run_native(native)
        self.assertEqual([kind for kind, _, _ in events].count("request"), 1)

    def test_input_contract_rejects_unknown_fields_and_invalid_ranges(self):
        module = SimpleNamespace(INPUT_MODEL=ExampleInputs)
        self.assertEqual(validate_inputs(module, {"value": 3}), {"value": 3, "label": "example"})
        for values in ({"value": 30}, {"path": "private.py"}):
            with self.assertRaises(ValidationError):
                validate_inputs(module, values)
        with self.assertRaises(ValidationError):
            validate_inputs(SimpleNamespace(), {"unexpected": 1})

    def test_sync_async_and_composed_runtimes_emit_one_final_answer(self):
        async def async_run(context):
            context.emit("lesson.step", {"summary": "async step"})
            return "async answer"
        def published(context):
            context.emit("answer", {"content": "published"})
            return "do not duplicate"
        for runner in (lambda ctx: "sync answer", async_run, published):
            events = []
            execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}},
                           SimpleNamespace(run=runner), make_context(events))
            self.assertEqual(len([event for event in events if event[0] == "answer"]), 1)
        with self.assertRaises(ValueError):
            execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}},
                           SimpleNamespace(run=lambda ctx: None), make_context([]))


web = importlib.import_module("server.app")


class CustomRuntimeApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web.app, base_url="http://localhost")
        use_temporary_run_store(self)
        self.spec = {
            "id": "custom-test", "title": "Test extension",
            "runtime": {"kind": "custom", "entrypoint": "runtime:run", "requires_model": False},
            "input_defaults": {"value": 2},
            "exercises": [{"id": "same-id", "title": "Run", "question": "question", "inputs": {"value": 3}}],
        }

    def run_fixture(self, function, **body):
        module = SimpleNamespace(INPUT_MODEL=ExampleInputs, run=function)
        with patch.object(web, "lesson_spec", return_value=self.spec), \
                patch.object(web, "lesson_runtime", return_value=module), \
                patch.object(web.provider_registry, "resolve", side_effect=AssertionError("local runtime needs no model")), \
                patch.object(web.provider_registry, "secrets", return_value=["fixture-secret"]):
            return run_and_read(self.client, {"lesson_id": "custom-test", "exercise_id": "same-id",
                                              "question": "question", "mode": "live", **body})

    @staticmethod
    def events(response):
        return response.events

    def test_new_custom_runtime_receives_inputs_without_model_configuration(self):
        def run(context):
            self.assertEqual(context.inputs, {"value": 5, "label": "example"})
            context.emit("lesson.graph_node", {"title": "Multiply", "value": context.inputs["value"] * 2})
            return "10"
        response = self.run_fixture(run, inputs={"value": 5})
        self.assertEqual(response.status_code, 202)
        events = self.events(response)
        self.assertEqual([e["type"] for e in events], ["run_start", "lesson.graph_node", "answer", "done"])
        self.assertTrue(all(e["schema_version"] == 2 for e in events))
        self.assertEqual([e["seq"] for e in events], [1, 2, 3, 4])
        self.assertEqual({e["representation"] for e in events}, {None})
        self.assertEqual(events[0]["data"]["provider_id"], "local")
        self.assertEqual(events[-1]["data"]["status"], "completed")
        self.assertFalse(web.run_lock.locked())

    def test_invalid_inputs_and_offline_overrides_are_rejected_before_execution(self):
        never = lambda ctx: self.fail("invalid input reached runtime")
        for values in ({"value": 10}, {"private": "fixture-secret"}):
            response = self.run_fixture(never, inputs=values)
            self.assertEqual(response.status_code, 422)
            self.assertNotIn("fixture-secret", response.text)
        self.assertEqual(self.run_fixture(never, mode="offline", inputs={"value": 5}).status_code, 400)
        self.assertFalse(web.run_lock.locked())

    def test_explicit_empty_input_does_not_restore_deleted_preset_values(self):
        seen = []
        def run(context):
            seen.append((context.question, context.inputs))
            return "checked"
        response = self.run_fixture(run, question="", inputs={})
        self.assertEqual(response.status_code, 202)
        # INPUT_MODEL supplies 2; the exercise's preset value 3 was explicitly removed.
        self.assertEqual(seen, [("", {"value": 2, "label": "example"})])

    def test_extension_errors_and_custom_data_are_redacted_and_release_the_lock(self):
        def failed(context):
            context.emit("lesson.note", {"summary": "fixture-secret"})
            raise RuntimeError("failed with fixture-secret")
        response = self.run_fixture(failed)
        self.assertNotIn("fixture-secret", response.text)
        self.assertIn("[REDACTED]", response.text)
        self.assertEqual(self.events(response)[-1]["data"]["status"], "error")
        self.assertFalse(web.run_lock.locked())
        self.assertEqual(self.events(self.run_fixture(lambda ctx: "recovered"))[-1]["data"]["status"], "completed")

    def test_cancellation_and_missing_result_do_not_claim_success(self):
        def cancelled(context):
            raise RunCancelled("stop")
        self.assertEqual(self.events(self.run_fixture(cancelled))[-1]["data"]["status"], "cancelled")
        events = self.events(self.run_fixture(lambda ctx: None))
        self.assertEqual(events[-1]["data"]["status"], "error")
        self.assertEqual([e["type"] for e in events], ["run_start", "error", "done"])


if __name__ == "__main__":
    unittest.main()
