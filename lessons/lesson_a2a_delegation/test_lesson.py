"""Behavior tests for a2a-delegation: the remote agent is a real child process serving A2A over HTTP on
127.0.0.1, and its BM25 search really runs; only the delegating model's decisions come from the fixture.
"""
import asyncio
import json
import os
import re
import time
import unittest
from pathlib import Path
from unittest import mock

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_data_part, new_message
from a2a.types import Role, SendMessageRequest
from google.protobuf.json_format import MessageToDict
from pydantic import ValidationError

from course.execution import RunContext, execute_lesson, validate_inputs
from course.protocols import spawn_local_service
from course.runner import RunCancelled
from lessons.lesson_a2a_delegation import runtime
from lessons.lesson_a2a_delegation.fixtures import create_completion
from lessons.lesson_a2a_delegation.locales import texts_for
from lessons.lesson_a2a_delegation.locales.worker import texts_for as worker_texts_for
from lessons.lesson_a2a_delegation.worker import SKILL_ID, Handbook, agent_card
from server.catalog import lesson_presets, load_lessons

LOCALES = ("zh-CN", "en")
CJK = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")
SPEC = next(spec for spec in load_lessons(include_planned=True) if spec["id"] == "a2a-delegation")


def presets(exercise_id, locale):
    exercises, defaults = lesson_presets(SPEC, locale)
    exercise = next(item for item in exercises if item["id"] == exercise_id)
    return exercise, {**defaults, **exercise.get("inputs", {})}


def run_exercise(exercise_id, locale="zh-CN", completion=None, cancelled=lambda: False, events=None,
                 question=None, **overrides):
    exercise, inputs = presets(exercise_id, locale)
    values = validate_inputs(runtime, {**inputs, **overrides})
    events = [] if events is None else events
    context = RunContext(
        lesson_id="a2a-delegation", exercise_id=exercise_id,
        question=exercise["question"] if question is None else question, mode="offline", model="fixture-model",
        representation="sdk_standardized", inputs=values, api_key="",
        completion=completion or create_completion(exercise_id, values, locale),
        emit_event=lambda kind, data, number: events.append((kind, data, number)), cancelled=cancelled,
        max_model_calls=SPEC["runtime"]["max_rounds"], locale=locale,
    )
    answer = execute_lesson({"runtime": SPEC["runtime"]}, runtime, context)
    return answer, events


def of(events, kind):
    return [data for event, data, _ in events if event == kind]


def a2a(events, name=None):
    return [data for data in of(events, runtime.A2A_EVENT) if name is None or data["name"] == name]


def report(events):
    return of(events, "lesson.report")[-1]


def checks(events):
    return {item["id"]: item.get("passed") for item in report(events)["checks"]}


def metric(events, metric_id):
    return next(item["value"] for item in report(events)["metrics"] if item["id"] == metric_id)


def states(events):
    return [data["state"] for data in a2a(events) if "state" in data]


def process_gone(pid, wait_seconds=8.0):
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def scripted(*replies):
    """A completion that returns the given assistant messages in order and records each request body."""
    bodies = []

    def complete(body, api_key):
        bodies.append(body)
        message = replies[min(len(bodies), len(replies)) - 1]
        return {"choices": [{"message": {"role": "assistant", "content": None, **message}}]}

    complete.bodies = bodies
    return complete


def call(arguments, call_id):
    return {"id": call_id, "type": "function",
            "function": {"name": runtime.TOOL_NAME, "arguments": json.dumps(arguments, ensure_ascii=False)}}


class Delegation(unittest.TestCase):
    def test_delegation_crosses_two_processes_and_records_the_lifecycle(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                answer, events = run_exercise("delegate", locale)
                kinds = [kind for kind, _, _ in events]
                # Discovery comes before the first model request; the A2A exchange sits inside the tool call.
                self.assertLess(kinds.index(runtime.A2A_EVENT), kinds.index("request"))
                self.assertLess(kinds.index("tool_call"), kinds.index(runtime.A2A_EVENT, kinds.index("tool_call")))
                self.assertEqual([d["name"] for d in a2a(events)],
                                 ["AgentCard", "SendMessageRequest", "Task", "TaskStatusUpdateEvent",
                                  "TaskStatusUpdateEvent", "TaskStatusUpdateEvent", "TaskArtifactUpdateEvent",
                                  "TaskStatusUpdateEvent"])
                self.assertEqual(states(events), ["TASK_STATE_SUBMITTED", "TASK_STATE_WORKING", "TASK_STATE_WORKING",
                                                  "TASK_STATE_WORKING", "TASK_STATE_COMPLETED"])
                self.assertEqual({d["captured"] for d in a2a(events)}, {"sdk_protobuf_message"})
                # Two model calls on this side; the remote agent's work leaves no request event here.
                self.assertEqual(len(of(events, "request")), 2)
                result = of(events, "tool_result")[0]["result"]
                self.assertTrue(result["ok"])
                self.assertEqual([r["claim_id"] for r in result["result"]["results"]], ["c1", "c2"])
                self.assertIn("borrowing:7-15", answer)
                # The worker's version rule: the 2025 opening hours never stand alone.
                sunday = result["result"]["results"][1]
                self.assertTrue(all(s["replaced_by"] == "hours" for s in sunday["superseded"]))
                self.assertTrue(sunday["superseded"])
                self.assertFalse(any(p["chunk_id"].startswith("hours-2025") for p in sunday["evidence"]))
                self.assertEqual(checks(events), {"card": True, "endpoint": True, "task_match": True, "bounded": True,
                                                  "result": True, "no_secret": True, "stopped": True})
                self.assertEqual(metric(events, "final_state"), "COMPLETED")
                self.assertEqual(metric(events, "model_calls"), 2)
                started, stopped = of(events, runtime.PROCESS_EVENT)
                self.assertTrue(stopped["port_closed"])
                self.assertTrue(process_gone(started["pid"]))

    def test_every_remote_message_matches_the_task_and_the_artifact_matches_the_claims(self):
        _, events = run_exercise("delegate", "en")
        task_id = a2a(events, "Task")[0]["message"]["task"]["id"]
        for data in a2a(events)[3:]:
            body = next(iter(data["message"].values()))
            self.assertEqual(body["taskId"], task_id)
        sent = a2a(events, "SendMessageRequest")[0]["message"]["message"]
        self.assertEqual(sent["role"], "ROLE_USER")
        self.assertEqual(sent["metadata"], {"skill_id": SKILL_ID})
        claims = sent["parts"][1]["data"]["claims"]
        artifact = a2a(events, "TaskArtifactUpdateEvent")[0]["message"]["artifactUpdate"]["artifact"]
        self.assertEqual([r["claim_id"] for r in artifact["parts"][0]["data"]["results"]], [c["id"] for c in claims])

    def test_the_model_tool_is_written_from_the_agent_card(self):
        completion = create_completion("delegate", locale="en")
        bodies = []

        def recording(body, api_key):
            bodies.append(json.loads(json.dumps(body)))
            return completion(body, api_key)

        _, events = run_exercise("delegate", "en", completion=recording)
        card = a2a(events, "AgentCard")[0]["message"]
        tool = bodies[0]["tools"][0]["function"]
        self.assertEqual(tool["name"], runtime.TOOL_NAME)
        self.assertEqual(tool["parameters"]["properties"]["skill_id"]["enum"], [s["id"] for s in card["skills"]])
        self.assertIn(card["description"], tool["description"])
        # After the one delegation the model may only answer.
        self.assertEqual([body["tool_choice"] for body in bodies], ["auto", "none"])


class FailurePaths(unittest.TestCase):
    def test_timeout_cancels_the_task_and_confirms_it(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                started = time.monotonic()
                answer, events = run_exercise("timeout", locale)
                # The worker would wait 60 s; the delegating side stops after its own 2 s.
                self.assertLess(time.monotonic() - started, 20)
                names = [d["name"] for d in a2a(events)]
                self.assertIn("CancelTaskRequest", names)
                self.assertEqual(names[-2:], ["GetTaskRequest", "Task"])
                self.assertEqual(states(events)[-1], "TASK_STATE_CANCELED")
                self.assertEqual(a2a(events)[-1]["method"], "GetTask")
                result = of(events, "tool_result")[0]["result"]
                self.assertEqual((result["ok"], result["error_type"]), (False, "DelegationTimeout"))
                self.assertIn("DelegationTimeout", answer)
                self.assertEqual(checks(events)["bounded"], True)
                self.assertIsNone(checks(events)["result"])  # never ran: no passed field at all
                self.assertEqual(metric(events, "final_state"), "CANCELED")

    def test_remote_failure_carries_the_remote_message(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                _, events = run_exercise("remote-failure", locale)
                self.assertEqual(states(events), ["TASK_STATE_SUBMITTED", "TASK_STATE_WORKING", "TASK_STATE_FAILED"])
                self.assertEqual(a2a(events)[-1].get("terminal"), True)
                result = of(events, "tool_result")[0]["result"]
                self.assertEqual(result["error_type"], "RemoteTaskFailed")
                self.assertIn(worker_texts_for(locale).status_failed, result["error"])
                self.assertNotIn("TaskArtifactUpdateEvent", [d["name"] for d in a2a(events)])
                self.assertEqual(metric(events, "outcome"), texts_for(locale).outcomes["failed"])

    def test_completed_is_not_accepted_when_the_result_is_incomplete(self):
        for locale in LOCALES:
            with self.subTest(locale=locale):
                _, events = run_exercise("incomplete", locale)
                self.assertEqual(states(events)[-1], "TASK_STATE_COMPLETED")
                result = of(events, "tool_result")[0]["result"]
                self.assertEqual(result["error_type"], "IncompleteResult")
                self.assertIn(texts_for(locale).problem_missing.format(claim_id="c2"), result["error"])
                self.assertEqual(checks(events)["result"], False)
                self.assertEqual(metric(events, "outcome"), texts_for(locale).outcomes["incomplete"])

    def test_stop_during_a_delegation_reaps_the_worker(self):
        events, state = [], {"stop": False}

        class Watch(list):
            def append(self, item):
                super().append(item)
                kind, data, _ = item
                if kind == runtime.A2A_EVENT and data.get("state") == "TASK_STATE_WORKING":
                    state["stop"] = True  # the learner presses stop while the remote task is working

        events = Watch()
        started = time.monotonic()
        with self.assertRaises(RunCancelled):
            run_exercise("timeout", "en", events=events, cancelled=lambda: state["stop"], deadline_seconds=10)
        self.assertLess(time.monotonic() - started, 15)
        pid = of(events, runtime.PROCESS_EVENT)[0]["pid"]
        self.assertTrue(process_gone(pid))
        self.assertEqual(of(events, "lesson.report"), [])

    @unittest.skipUnless(Path("/proc/self/environ").exists(), "reads /proc/<pid>/environ")
    def test_the_worker_process_gets_no_api_key(self):
        seen = {}

        class Peek(list):
            def append(self, item):
                super().append(item)
                kind, data, _ = item
                if kind == runtime.PROCESS_EVENT and data["name"] == "started":
                    raw = Path(f"/proc/{data['pid']}/environ").read_bytes()
                    seen["names"] = {entry.split(b"=", 1)[0].decode() for entry in raw.split(b"\0") if entry}

        with mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": "sk-test-must-not-reach-the-worker"}):
            _, events = run_exercise("delegate", "en", events=Peek())
        self.assertNotIn("DASHSCOPE_API_KEY", seen["names"])
        self.assertEqual(seen["names"], set(of(events, runtime.PROCESS_EVENT)[0]["env_names"]))


class Boundaries(unittest.TestCase):
    def test_bad_proposals_are_refused_before_any_a2a_message(self):
        completion = scripted(
            {"tool_calls": [call({"skill_id": "translate", "claims": ["x"]}, "call_1"),
                            call({"skill_id": SKILL_ID, "claims": []}, "call_2"),
                            call({"skill_id": SKILL_ID, "claims": ["Sunday closing time"]}, "call_3"),
                            call({"skill_id": SKILL_ID, "claims": ["again"]}, "call_4")]},
            {"content": "done"})
        answer, events = run_exercise("delegate", "en", completion=completion)
        results = [data["result"] for data in of(events, "tool_result")]
        self.assertEqual([r["ok"] for r in results], [False, False, True, False])
        t = texts_for("en")
        self.assertEqual(results[0]["error"], t.unknown_skill.format(skill_id="translate"))
        self.assertEqual(results[1]["error"], t.bad_claims.format(max=runtime.MAX_CLAIMS))
        self.assertEqual(results[3]["error"], t.delegation_limit)
        self.assertEqual(len(a2a(events, "SendMessageRequest")), 1)
        self.assertEqual(answer, "done")

    def test_a_model_that_answers_directly_delegates_nothing(self):
        answer, events = run_exercise("delegate", "en", completion=scripted({"content": "I am not sure."}))
        self.assertEqual(answer, "I am not sure.")
        self.assertEqual([d["name"] for d in a2a(events)], ["AgentCard"])
        self.assertNotIn("task_match", checks(events))
        self.assertEqual(metric(events, "outcome"), texts_for("en").outcomes["not_delegated"])

    def test_a_card_pointing_elsewhere_is_refused(self):
        foreign = agent_card(worker_texts_for("en"), "http://127.0.0.1:9")
        with mock.patch.object(runtime.A2ACardResolver, "get_agent_card", return_value=foreign):
            with self.assertRaises(ValueError) as caught:
                run_exercise("delegate", "en")
        t = texts_for("en")
        self.assertEqual(str(caught.exception), t.card_unusable.format(problem=t.card_problems["endpoint"]))

    def test_input_validation(self):
        for bad in ({"deadline_seconds": 0}, {"deadline_seconds": 11}, {"fault": "crash"}, {"extra": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                runtime.Inputs.model_validate({"fault": "none", **bad})
        with self.assertRaises(ValueError) as caught:
            run_exercise("delegate", "en", question="  ")
        self.assertEqual(str(caught.exception), texts_for("en").empty_question)

    def test_english_run_has_no_chinese(self):
        answer, events = run_exercise("incomplete", "en")
        self.assertIsNone(CJK.search(answer))
        self.assertIsNone(CJK.search(json.dumps(events, ensure_ascii=False)))


class Worker(unittest.TestCase):
    def test_old_versions_are_swapped_for_the_current_one(self):
        t = worker_texts_for("zh-CN")
        result = Handbook("zh-CN").check(t, {"id": "c1", "text": "周日几点闭馆"})
        self.assertEqual({s["replaced_by"] for s in result["superseded"]}, {"hours"})
        self.assertTrue(result["evidence"])
        self.assertTrue(all(p["chunk_id"].startswith("hours:") for p in result["evidence"]))
        self.assertLessEqual(len(result["evidence"]), 3)

    def test_a_message_without_the_skill_contract_is_rejected(self):
        async def send(base_url):
            async with httpx.AsyncClient(timeout=10, trust_env=False) as http:
                card = await A2ACardResolver(httpx_client=http, base_url=base_url).get_agent_card()
                client = await create_client(agent=card, client_config=ClientConfig(streaming=True, httpx_client=http))
                seen = []
                # No metadata.skill_id and four claims: both break the skill's input contract.
                message = new_message([new_data_part({"claims": [{"id": f"c{n}", "text": "x"} for n in range(4)]})],
                                      role=Role.ROLE_USER)
                async for item in client.send_message(SendMessageRequest(message=message)):
                    data = MessageToDict(item)
                    seen.append(runtime.task_state(data))
                await client.close()
                return seen

        with spawn_local_service(runtime.WORKER_MODULE, "--locale", "en") as service:
            seen = asyncio.run(send(service.base_url))
        self.assertEqual(seen, ["TASK_STATE_SUBMITTED", "TASK_STATE_REJECTED"])


if __name__ == "__main__":
    unittest.main()
