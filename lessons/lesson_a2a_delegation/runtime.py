"""A2A delegation across two processes: a front-desk agent hands claims to a reference checker in another process.

This process is the delegating side. Its model (through RunContext) decides what to delegate and writes the
answer from what comes back. The remote agent (worker.py) is a deterministic program in its own process; it
cannot reach RunContext, so it calls no model and never sees the API key. Every A2A object this side sends or
receives is recorded as a lesson.a2a_message event: the SDK's protobuf object exported with MessageToDict,
not the bytes on the wire.
"""
import json
import re
import socket
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from functools import partial
from typing import Literal

import anyio
import httpx
from a2a.client import A2ACardResolver, A2AClientError, ClientConfig, create_client
from a2a.helpers import get_data_parts, get_message_text, new_data_part, new_message, new_text_part
from a2a.types import CancelTaskRequest, GetTaskRequest, Role, SendMessageRequest
from google.protobuf.json_format import MessageToDict
from pydantic import Field

from course.execution import LessonInputs, RunContext
from course.protocols import LocalService, run_until_cancelled, safe_child_environment, spawn_local_service
from lessons.lesson_a2a_delegation.locales import Texts, texts_for

WORKER_MODULE = "lessons.lesson_a2a_delegation.worker"
TOOL_NAME = "delegate_task"
A2A_EVENT = "lesson.a2a_message"
PROCESS_EVENT = "lesson.a2a_process"
MAX_CLAIMS = 3
MAX_ROUNDS = 3
CANCEL_SECONDS = 5
HTTP_SECONDS = 10
TERMINAL = ("TASK_STATE_COMPLETED", "TASK_STATE_FAILED", "TASK_STATE_CANCELED", "TASK_STATE_REJECTED")
INTERRUPTED = ("TASK_STATE_INPUT_REQUIRED", "TASK_STATE_AUTH_REQUIRED")
SECRET_LIKE = re.compile(r"KEY|TOKEN|SECRET|PASSWORD", re.IGNORECASE)


class Inputs(LessonInputs):
    # Fault injection: the remote agent is started with --fault <value>; the report says so.
    fault: Literal["none", "slow", "fail", "partial"] = "none"
    # How long this side waits for a terminal state before it cancels the remote task.
    deadline_seconds: int = Field(default=3, ge=1, le=10)


INPUT_MODEL = Inputs


class DelegationTimeout(ValueError):
    """No terminal state within the deadline; the task was canceled."""


class RemoteTaskFailed(ValueError):
    """The remote task ended in FAILED or REJECTED, or stopped to ask for input."""


class IncompleteResult(ValueError):
    """COMPLETED, but the artifact does not cover what was delegated."""


class RemoteUnavailable(ValueError):
    """The protocol exchange itself broke: connection error or a stream that ended early."""


@dataclass
class Delegation:
    """What this side saw of the one delegation in a run; the report is built from it."""
    claims: list[dict] = field(default_factory=list)
    outcome: str = "not_delegated"
    task_id: str | None = None
    task_ids: set[str] = field(default_factory=set)
    states: list[str] = field(default_factory=list)
    remote_messages: int = 0
    problems: list[str] | None = None   # None: the completeness check never ran
    cancel_confirmed: bool | None = None
    timeline: list[list] = field(default_factory=list)


def status_of(data: dict) -> dict:
    """The status carried by a Task or a status update, in its dict form; {} for anything else."""
    holder = data.get("task") or data.get("statusUpdate") or data
    return holder.get("status", {})


def task_state(data: dict) -> str | None:
    return status_of(data).get("state")


def short(state: str | None) -> str:
    return (state or "-").removeprefix("TASK_STATE_")


class Session:
    def __init__(self, context: RunContext, t: Texts, inputs: Inputs, service: LocalService):
        self.context, self.t, self.inputs, self.service = context, t, inputs, service
        self.delegation = Delegation()
        self.round = 1
        self.model_calls = 0
        self.started = time.perf_counter()
        self.card = self.client = None

    def emit_a2a(self, name: str, method: str, direction: str, message: dict, state: str | None = None):
        """Record one A2A object as it was handed to or returned by the SDK."""
        data = {"name": name, "method": method, "direction": direction, "captured": "sdk_protobuf_message",
                "message": message}
        if state:
            data["state"] = state
            if state in TERMINAL:
                data["terminal"] = True
        elapsed = round((time.perf_counter() - self.started) * 1000)
        note = status_of(message).get("message", {})
        self.delegation.timeline.append([len(self.delegation.timeline) + 1, self.t.directions[direction], name,
                                         short(state) if state else "-", elapsed,
                                         " ".join(part.get("text", "") for part in note.get("parts", [])) or "-"])
        self.context.emit(A2A_EVENT, data, self.round)

    async def discover(self, http: httpx.AsyncClient):
        """Capability discovery: GET /.well-known/agent-card.json, then decide whether the card is usable."""
        card = await A2ACardResolver(httpx_client=http, base_url=self.service.base_url).get_agent_card()
        self.emit_a2a("AgentCard", "GetAgentCard", "agent_to_client", MessageToDict(card))
        interfaces = [i for i in card.supported_interfaces if i.protocol_binding == "JSONRPC"]
        problem = ("binding" if not interfaces
                   # The card names its own URL; this side only talks to the process it started.
                   else "endpoint" if interfaces[0].url.rstrip("/") != self.service.base_url
                   else None if any("application/json" in s.input_modes for s in card.skills) else "no_skill")
        if problem:
            raise ValueError(self.t.card_unusable.format(problem=self.t.card_problems[problem]))
        self.card = card
        self.client = await create_client(agent=card, client_config=ClientConfig(streaming=True, httpx_client=http))

    def delegation_tool(self) -> dict:
        """The model's only tool, written from the Agent Card: its skills become the allowed skill ids."""
        t, card = self.t, self.card
        skills = "; ".join(f"{skill.id}: {skill.description}" for skill in card.skills)
        return {"type": "function", "function": {
            "name": TOOL_NAME,
            "description": t.tool_description.format(agent=card.name, description=card.description, skills=skills),
            "parameters": {"type": "object", "additionalProperties": False, "required": ["skill_id", "claims"],
                           "properties": {
                               "skill_id": {"type": "string", "enum": [skill.id for skill in card.skills],
                                            "description": t.skill_id_description},
                               "claims": {"type": "array", "minItems": 1, "maxItems": MAX_CLAIMS,
                                          "items": {"type": "string", "minLength": 1, "maxLength": 160},
                                          "description": t.claims_description.format(max=MAX_CLAIMS)}}}}}

    def accept(self, artifacts: list) -> dict:
        """The completeness check: every delegated claim has exactly one result with at least one passage."""
        t, record = self.t, self.delegation
        data = next((d for a in artifacts for d in get_data_parts(a.parts) if isinstance(d, dict)), None)
        results = {r.get("claim_id"): r for r in (data or {}).get("results", []) if isinstance(r, dict)}
        asked = [claim["id"] for claim in record.claims]
        problems = ([t.problem_no_data] if data is None else []) + [
            *(t.problem_missing.format(claim_id=c) for c in asked if c not in results),
            *(t.problem_no_evidence.format(claim_id=c) for c in asked if c in results and not results[c].get("evidence")),
            *(t.problem_unknown.format(claim_id=c) for c in results if c not in asked)]
        record.problems = problems
        if problems:
            record.outcome = "incomplete"
            partial_result = [results[c] for c in asked if c in results]
            raise IncompleteResult(t.incomplete_result.format(problems=t.problem_separator.join(problems),
                                                              partial=json.dumps(partial_result, ensure_ascii=False)))
        record.outcome = "completed"
        return {"remote_agent": self.card.name, "task_id": record.task_id, "state": record.states[-1],
                "results": [results[c] for c in asked]}

    async def converse(self) -> str:
        async with httpx.AsyncClient(timeout=HTTP_SECONDS, trust_env=False) as http:
            # 1. Discover before the model sees anything: the tool is built from the card.
            await self.discover(http)
            tools = [self.delegation_tool()]
            bridge = {TOOL_NAME: self.delegate_task}
            messages = [{"role": "system", "content": self.t.system_prompt},
                        {"role": "user", "content": self.context.question}]
            try:
                for self.round in range(1, MAX_ROUNDS + 1):
                    # 2. The model decides: delegate (once), or answer. After the delegation it may only answer.
                    choice = "auto" if self.delegation.outcome == "not_delegated" else "none"
                    body = {"messages": messages, "tools": tools, "tool_choice": choice}
                    self.model_calls += 1
                    response = await anyio.to_thread.run_sync(partial(self.context.complete, body, self.round))
                    message = response["choices"][0]["message"]
                    calls = message.get("tool_calls") or []
                    if not calls:
                        return message.get("content") or self.t.empty_answer
                    messages.append(message)
                    # 3. Each proposal goes through the platform's checks; the A2A exchange runs inside it.
                    for call in calls:
                        result = await anyio.to_thread.run_sync(self.context.execute_proposal, call, bridge)
                        messages.append({"role": "tool", "tool_call_id": call["id"],
                                         "content": json.dumps(result, ensure_ascii=False)})
                return self.t.rounds_exhausted
            finally:
                await self.client.close()

    def delegate_task(self, skill_id: str, claims: list) -> dict:
        """The tool the model calls. Runs in execute_proposal's worker thread; the A2A calls go back to the loop."""
        t = self.t
        if self.delegation.outcome != "not_delegated":
            raise ValueError(t.delegation_limit)
        if skill_id not in [skill.id for skill in self.card.skills]:
            raise ValueError(t.unknown_skill.format(skill_id=skill_id))
        if (not isinstance(claims, list) or not 1 <= len(claims) <= MAX_CLAIMS
                or not all(isinstance(c, str) and c.strip() for c in claims)):
            raise ValueError(t.bad_claims.format(max=MAX_CLAIMS))
        # This side numbers the claims, so every result can be matched back to what was asked.
        self.delegation.claims = [{"id": f"c{n}", "text": text.strip()} for n, text in enumerate(claims, 1)]
        return anyio.from_thread.run(self.delegate, skill_id)

    async def delegate(self, skill_id: str) -> dict:
        t, record, seconds = self.t, self.delegation, self.inputs.deadline_seconds
        # 1. Send: a text part for people, a data part for the program, the skill in metadata.
        message = new_message([new_text_part(t.delegation_text), new_data_part({"claims": record.claims})],
                              role=Role.ROLE_USER)
        message.metadata.update({"skill_id": skill_id})
        request = SendMessageRequest(message=message)
        self.started = time.perf_counter()
        self.emit_a2a("SendMessageRequest", "SendStreamingMessage", "client_to_agent", MessageToDict(request))
        record.outcome = "unavailable"
        # 2. Follow the task's states, but only until our own deadline.
        try:
            with anyio.fail_after(seconds):
                artifacts, last = await self.follow(request)
        except TimeoutError:
            record.outcome = "timeout"
            state = await self.cancel_after_timeout()
            raise DelegationTimeout(t.timeout_error.format(seconds=seconds, state=short(state))) from None
        except A2AClientError as error:
            raise RemoteUnavailable(t.remote_unavailable.format(error=type(error).__name__)) from None
        # 3. A terminal state other than COMPLETED is a remote failure, reported with the remote's own message.
        state = record.states[-1] if record.states else None
        if state in INTERRUPTED:
            record.outcome = "interrupted"
            raise RemoteTaskFailed(t.remote_interrupted.format(state=short(state)))
        if state not in TERMINAL:
            raise RemoteUnavailable(t.stream_ended.format(state=short(state)))
        if state != "TASK_STATE_COMPLETED":
            record.outcome = "rejected" if state == "TASK_STATE_REJECTED" else "failed"
            raise RemoteTaskFailed(t.remote_failed.format(state=short(state), message=last or "-"))
        # 4. COMPLETED is the remote's claim; accepting the result is this side's check.
        return self.accept(artifacts)

    async def cancel_after_timeout(self) -> str | None:
        """Ask the remote side to cancel, then read the task back: the cancel reply alone is not proof."""
        record, state = self.delegation, None
        if record.task_id is None:
            return self.t.no_task_id
        with anyio.move_on_after(CANCEL_SECONDS):
            try:
                await self.exchange("CancelTask", CancelTaskRequest(id=record.task_id), self.client.cancel_task)
            except A2AClientError as error:
                # Already terminal, or unknown to the remote side: GetTask below still says where it stands.
                self.emit_a2a("Error", "CancelTask", "agent_to_client", {"error": type(error).__name__})
            state = task_state(await self.exchange("GetTask", GetTaskRequest(id=record.task_id), self.client.get_task))
        record.cancel_confirmed = state == "TASK_STATE_CANCELED"
        if state:
            record.states.append(state)
        return state

    async def exchange(self, method: str, request, send) -> dict:
        """One request and its Task reply, both recorded."""
        self.emit_a2a(type(request).__name__, method, "client_to_agent", MessageToDict(request))
        reply = MessageToDict(await send(request))
        self.emit_a2a("Task", method, "agent_to_client", reply, task_state(reply))
        return reply

    async def follow(self, request: SendMessageRequest) -> tuple[list, str]:
        """Read the stream: the Task (SUBMITTED), status updates, artifact updates, until a final state."""
        record, artifacts, last = self.delegation, [], ""
        async for item in self.client.send_message(request):
            data = MessageToDict(item)
            kind, body = next(iter(data.items()))
            state = task_state(data)
            record.remote_messages += 1
            record.task_ids.add(body.get("id") if kind == "task" else body.get("taskId"))
            record.task_id = record.task_id or body.get("id") or body.get("taskId")
            if state:
                record.states.append(state)
                last = get_message_text(item.status_update.status.message) if kind == "statusUpdate" else last
            if kind == "artifactUpdate":
                artifacts.append(item.artifact_update.artifact)
            names = {"task": "Task", "statusUpdate": "TaskStatusUpdateEvent", "artifactUpdate": "TaskArtifactUpdateEvent"}
            self.emit_a2a(names.get(kind, kind), "SendStreamingMessage", "agent_to_client", data, state)
            if state in TERMINAL or state in INTERRUPTED:
                break
        return artifacts, last


async def run(context: RunContext):
    t = texts_for(context.locale)
    inputs = Inputs.model_validate(context.inputs)
    if not context.question.strip():
        raise ValueError(t.empty_question)
    if context.completion is None:
        raise ValueError(t.needs_model)
    passed_env = sorted(safe_child_environment())
    with ExitStack() as stack:
        # The child gets the run language and the fault flag on its command line, and only the SDK's safe variables.
        try:
            service = stack.enter_context(spawn_local_service(WORKER_MODULE, "--locale", context.locale,
                                                              "--fault", inputs.fault))
        except (TimeoutError, RuntimeError) as error:
            raise ValueError(t.worker_start_failed) from error
        context.emit(PROCESS_EVENT, {"name": "started", "pid": service.pid, "port": service.port,
                                     "module": WORKER_MODULE, "fault": inputs.fault, "env_names": passed_env})
        session = Session(context, t, inputs, service)

        async def guarded():
            # A task group wraps exceptions in an ExceptionGroup; hand the error back and re-raise it below.
            try:
                return await session.converse(), None
            except Exception as error:
                return None, error

        answer, error = await run_until_cancelled(context, guarded)
    # Leaving the with block terminated the child; the closed port is the evidence.
    closed = port_closed(service.port)
    context.emit(PROCESS_EVENT, {"name": "stopped", "pid": service.pid, "port": service.port, "port_closed": closed})
    if error is not None:
        raise error
    context.emit("lesson.report", _report(context, t, inputs, session, passed_env, closed))
    return answer


def port_closed(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return False
    except OSError:
        return True


def _report(context: RunContext, t: Texts, inputs: Inputs, session: Session, env: list[str], closed: bool) -> dict:
    record, card = session.delegation, session.card
    states = t.state_separator.join(short(s) for s in record.states) or t.value_none
    final = record.states[-1] if record.states else None
    delegated = record.outcome != "not_delegated"
    bounded = ("terminal" if final in TERMINAL and record.outcome != "timeout"
               else "canceled" if record.cancel_confirmed else "unconfirmed" if record.outcome == "timeout" else "open")
    result = "skipped" if record.problems is None else "failed" if record.problems else "passed"
    secret = [name for name in env if SECRET_LIKE.search(name)]
    checks = [
        {"id": "card", "label": t.check_card, "passed": True,
         "detail": t.detail_card.format(name=card.name, version=card.version, streaming=card.capabilities.streaming,
                                        skills=", ".join(skill.id for skill in card.skills))},
        {"id": "endpoint", "label": t.check_endpoint, "passed": True, "detail": t.detail_endpoint.format(
            card_url=card.supported_interfaces[0].url, base_url=session.service.base_url)},
    ]
    if delegated:
        checks += [
            {"id": "task_match", "label": t.check_task_match, "passed": len(record.task_ids) == 1,
             "detail": t.detail_task_match.format(count=record.remote_messages, task_id=record.task_id or "-")},
            {"id": "bounded", "label": t.check_bounded, "passed": bounded in ("terminal", "canceled"),
             "detail": t.detail_bounded[bounded].format(seconds=inputs.deadline_seconds, state=short(final))},
            {"id": "result", "label": t.check_result, **({"passed": result == "passed"} if result != "skipped" else {}),
             "detail": t.detail_result[result].format(problems=t.problem_separator.join(record.problems or []))},
        ]
    checks += [
        {"id": "no_secret", "label": t.check_no_secret, "passed": not secret,
         "detail": t.detail_env.format(names=", ".join(env))},
        {"id": "stopped", "label": t.check_stopped, "passed": closed,
         "detail": t.detail_stopped["closed" if closed else "open"].format(port=session.service.port)},
    ]
    return {
        "title": t.report_title,
        "summary": t.report_summary.format(outcome=t.outcomes[record.outcome], states=states,
                                           model_calls=session.model_calls),
        "checks": checks,
        "metrics": [
            {"id": "outcome", "label": t.label_outcome, "value": t.outcomes[record.outcome]},
            {"id": "final_state", "label": t.label_final_state, "value": short(final) if final else t.value_none},
            {"id": "states", "label": t.label_states, "value": states},
            {"id": "deadline", "label": t.label_deadline, "value": t.deadline_value.format(seconds=inputs.deadline_seconds)},
            {"id": "model_calls", "label": t.label_model_calls, "value": session.model_calls},
            {"id": "a2a_messages", "label": t.label_a2a_messages, "value": len(record.timeline)},
            {"id": "worker_pid", "label": t.label_worker_pid, "value": session.service.pid},
            {"id": "fault", "label": t.label_fault, "value": t.faults[inputs.fault]},
            {"id": "note", "label": t.label_note, "value": context.question or t.value_empty},
        ],
        "table": {"columns": list(t.columns_timeline), "rows": record.timeline},
    }
