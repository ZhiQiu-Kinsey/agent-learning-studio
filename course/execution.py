"""Shared services for web runs: native lessons and custom runners call the model, run tools and record evidence through RunContext.

Only trusted lesson code registered on this machine gets a RunContext; browser data
never decides an import path or which function runs. Run start and end, serialization,
secret scrubbing and the execution lock belong to the HTTP layer; lesson code cannot
publish lifecycle events itself.
"""
import asyncio
import copy
import inspect
import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from course.i18n import RUNTIME_LOCALES, SOURCE_LOCALE
from course.locales import texts_for
from course.runner import AgentSetup, RunCancelled, execute_tool, run_agent


class LessonInputs(BaseModel):
    """Input contract of a custom runner: undeclared fields are always rejected."""
    model_config = ConfigDict(extra="forbid")


_STANDARD_EVENTS = {"request", "response", "tool_call", "tool_result", "answer", "error"}


@dataclass
class RunContext:
    lesson_id: str
    exercise_id: str
    question: str
    mode: str
    model: str
    representation: str
    inputs: dict[str, Any]
    api_key: str = field(repr=False)
    completion: Callable | None = field(repr=False)
    emit_event: Callable = field(repr=False)
    cancelled: Callable[[], bool] = field(default=lambda: False, repr=False)
    max_model_calls: int = 3
    # The run's language (course/i18n.py). Lesson code reads its runtime text for this
    # locale; the server picked it from the UI language and the locales the lesson supports.
    locale: str = SOURCE_LOCALE
    _answered: bool = field(default=False, init=False)
    _tool_count: int = field(default=0, init=False)
    _model_count: int = field(default=0, init=False)
    _round: int = field(default=1, init=False)
    _budget_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self):
        if self.locale not in RUNTIME_LOCALES:
            raise ValueError(f"not a runtime locale: {self.locale!r}")

    def check_cancelled(self):
        if self.cancelled():
            raise RunCancelled(texts_for(self.locale).run_cancelled)

    def emit(self, kind: str, data: dict, round_number: int | None = None):
        """Publish standard evidence or a lesson.* event; lifecycle events (start, done) belong to the platform."""
        self.check_cancelled()
        if kind not in _STANDARD_EVENTS and not re.fullmatch(r"lesson\.[a-zA-Z0-9_.-]{1,80}", kind):
            raise ValueError("lesson events must use a standard type or the lesson. prefix; "
                             "start and done are managed by the platform")
        if not isinstance(data, dict):
            raise ValueError("lesson event data must be a JSON object")
        if round_number is not None and (type(round_number) is not int or round_number < 1):
            raise ValueError("event round must be a positive integer")
        # Serialize once as JSON: a value that cannot be serialized fails here, and the
        # recorded data is a snapshot of this moment.
        snapshot = json.loads(json.dumps(data, ensure_ascii=False, allow_nan=False))
        if kind == "answer" and not isinstance(snapshot.get("content"), str):
            raise ValueError("the final answer must contain a string content")
        self.emit_event(kind, snapshot, round_number)
        if kind == "answer":
            self._answered = True

    def complete(self, body: dict, round_number: int = 1, *, branch: str | None = None) -> dict:
        """Send one request over the current model connection; request and response are recorded as events, unchanged.

        Parallel requests pass a different branch each, so the timeline can pair every
        response with its request.
        """
        self.check_cancelled()
        if self.completion is None:
            raise ValueError("this lesson has no model connection configured")
        # Stop past the model calls lesson.json declares: no loop can request forever.
        self._check_model_budget()
        # Lesson code cannot switch models.
        if body.get("model", self.model) != self.model:
            raise ValueError("lesson requests must use the configured model")
        # Copy the request body: if lesson code edits messages later, the recorded evidence stays as sent.
        request = {"model": self.model, **copy.deepcopy({k: v for k, v in body.items() if k != "model"})}
        self._round = round_number
        tag = {} if branch is None else {"branch": branch}
        self.emit("request", {"body": request, "representation": self.representation, **tag}, round_number)
        started = time.perf_counter()
        response = self._invoke_completion(request, self.api_key)
        self.emit("response", {
            "body": response, "representation": self.representation,
            "duration_ms": round((time.perf_counter() - started) * 1000), **tag,
        }, round_number)
        self.check_cancelled()
        return response

    def _check_model_budget(self):
        if self._model_count >= self.max_model_calls:
            raise RuntimeError(texts_for(self.locale).model_budget_exceeded.format(limit=self.max_model_calls))

    def _invoke_completion(self, body, api_key):
        self.check_cancelled()
        if self.completion is None:
            raise ValueError("this lesson has no model connection configured")
        with self._budget_lock:  # parallel branches share one call budget
            self._check_model_budget()
            self._model_count += 1
        return self.completion(body, api_key)

    def execute_proposal(self, tool_call: dict, available_tools: dict) -> dict:
        """Execute one call the model proposed: record the proposal, then the tool result, paired by the call id.

        Some providers omit the call id (or send an empty one). Rejecting the call would
        hide a proposal the model really made, so the platform gives it an id instead:
        ``synthesized_call_<round>_<n>``, deterministic within the run. The id is written
        into the call dict itself, so the assistant message the lesson puts back into the
        history and the tool message that answers it carry the same id, and the next
        request stays well formed. The recorded ``response`` event keeps the provider's
        call as it arrived (without an id); the ``tool_call`` event says
        ``id_synthesized: true``, so nobody mistakes the id for one the provider sent.
        """
        self.check_cancelled()
        synthesized = self._ensure_call_id(tool_call)
        self.emit("tool_call", {**tool_call, "id_synthesized": True} if synthesized else tool_call, self._round)
        result = execute_tool(tool_call, available_tools, self.locale)
        self.emit("tool_result", {"tool_call_id": tool_call["id"], "name": tool_call["function"]["name"],
                                  "result": result}, self._round)
        return result

    def _ensure_call_id(self, tool_call: dict) -> bool:
        """Give a call without a usable id (missing, empty or not a string) a synthesized one; True when it did."""
        if not isinstance(tool_call, dict):
            raise ValueError("a tool call proposal must be a JSON object")
        call_id = tool_call.get("id")
        if isinstance(call_id, str) and call_id.strip():
            return False
        # Shares the counter with submit_call, so the id is unique within the run.
        self._tool_count += 1
        tool_call["id"] = f"synthesized_call_{self._round}_{self._tool_count}"
        return True

    def call_tool(self, name: str, arguments: dict, available_tools: dict,
                  round_number: int = 1, call_id: str | None = None) -> dict:
        """The runner (not the model) makes one call to a registered tool; call and result are recorded as a pair."""
        return self.submit_call(name, json.dumps(arguments, ensure_ascii=False), available_tools,
                                round_number, call_id)

    def submit_call(self, name: str, raw_arguments: str, available_tools: dict,
                    round_number: int = 1, call_id: str | None = None) -> dict:
        """The runner submits a call as is: the name may be unregistered, the arguments a raw (possibly broken) JSON string.

        It goes through the same checks and execution as a model proposal (execute_tool),
        to show the rejection path. The events carry origin=course_program so they never
        pass for a call the model proposed.
        """
        self.check_cancelled()
        self._tool_count += 1
        call = {"id": call_id or f"lesson_{self.lesson_id}_{self._tool_count}", "type": "function",
                "origin": "course_program", "function": {"name": name, "arguments": raw_arguments}}
        self.emit("tool_call", call, round_number)
        self.check_cancelled()
        result = execute_tool(call, available_tools, self.locale)
        self.emit("tool_result", {"tool_call_id": call["id"], "name": name, "result": result,
                                  "origin": "course_program"}, round_number)
        return result

    def run_native(self, module, max_rounds: int = 3, *, publish_answer: bool = False):
        """Run the native tool loop with ``module.setup(locale)``; with publish_answer=False its answer is a stage result."""
        self.check_cancelled()
        if self.completion is None:
            raise ValueError("the native agent loop needs a configured model connection")
        setup = module.setup(self.locale)
        if not isinstance(setup, AgentSetup):
            raise TypeError("setup(locale) must return a course.runner.AgentSetup")
        answer = run_agent(self.question, setup.system_prompt, setup.tools, setup.available_tools, max_rounds,
                           complete=self.complete, execute=self.execute_proposal, locale=self.locale)
        if publish_answer:
            self.emit("answer", {"content": answer}, self._round)
        else:
            self.emit("lesson.stage_result", {"content": answer, "title": texts_for(self.locale).stage_result_title,
                                               "summary": answer[:160]}, self._round)
        return answer


def validate_inputs(module, values: dict) -> dict:
    """Validate inputs against the lesson's INPUT_MODEL before taking the lock or contacting the model."""
    input_model = getattr(module, "INPUT_MODEL", LessonInputs)
    if not isinstance(input_model, type) or not issubclass(input_model, LessonInputs):
        raise TypeError("INPUT_MODEL must subclass course.execution.LessonInputs")
    return input_model.model_validate(values).model_dump(mode="json")


def execute_lesson(spec: dict, module, context: RunContext):
    """Run a lesson the way it is registered: native lessons use the tool loop, custom runners may be sync or async."""
    context.check_cancelled()
    runtime = spec["runtime"]
    if runtime["kind"] == "native":
        result = context.run_native(module, max_rounds=runtime.get("max_rounds", 3), publish_answer=True)
    else:
        function_name = runtime["entrypoint"].split(":", 1)[1]
        function = getattr(module, function_name)
        if not callable(function):
            raise TypeError("the lesson entrypoint is not a function")
        result = function(context)
        if inspect.isawaitable(result):
            result = asyncio.run(result)
    context.check_cancelled()
    if result is not None and not isinstance(result, str):
        raise TypeError("a lesson runner must return the answer string, or publish answer and return None")
    if not context._answered:
        if result is None:
            raise ValueError("the lesson runner finished without a result")
        context.emit("answer", {"content": result})
    return result
