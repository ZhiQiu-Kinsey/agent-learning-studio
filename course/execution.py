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
    # Parameters the provider rejects for this model. They are left out of the request that is
    # sent and recorded, and the request event lists them under ``omitted_params``.
    unsupported_params: frozenset = frozenset()
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
        omitted = self._without_unsupported(request)
        self.emit("request", {"body": request, "representation": self.representation, **tag, **omitted}, round_number)
        started = time.perf_counter()
        response = self._invoke_completion(request, self.api_key)
        self.emit("response", {
            "body": response, "representation": self.representation,
            "duration_ms": round((time.perf_counter() - started) * 1000), **tag,
        }, round_number)
        self.check_cancelled()
        return response

    def _without_unsupported(self, request: dict) -> dict:
        """Event fields for the parameters taken out of ``request`` (in place); {} when none were."""
        omitted = {key: request.pop(key) for key in sorted(self.unsupported_params) if key in request}
        if not omitted:
            return {}
        return {"omitted_params": {"values": omitted, "reason": "unsupported_by_model"}}

    def _check_model_budget(self):
        if self._model_count >= self.max_model_calls:
            raise RuntimeError(texts_for(self.locale).model_budget_exceeded.format(limit=self.max_model_calls))

    def _invoke_completion(self, body, api_key):
        if self.completion is None:
            raise ValueError("this lesson has no model connection configured")
        return self._invoke(self.completion, body, api_key)

    def _invoke(self, function, body, api_key):
        """Every model call, chat or embeddings, passes here: cancellation first, then one shared budget."""
        self.check_cancelled()
        with self._budget_lock:  # parallel branches share one call budget
            self._check_model_budget()
            self._model_count += 1
        return function(body, api_key)

    # Embedding connection of this run, next to the method that uses it: embedding(body, api_key)
    # returns an OpenAI-shaped embeddings response. It is None when the live provider has no
    # embedding model, or offline when the lesson declares no testing.embedding_factory.
    embedding: Callable | None = field(default=None, repr=False)
    embedding_model: str | None = None
    # How many texts one embeddings request may carry (Bailian's compatible endpoint takes 10).
    embedding_batch_limit: int = 10

    def embed(self, texts: list[str], round_number: int = 1, *, branch: str | None = None,
              dimensions: int | None = None) -> dict:
        """Send one embeddings request; request and response are recorded with endpoint "embeddings", unchanged.

        It shares the max_model_calls budget with complete(). One request carries at most
        embedding_batch_limit texts: lesson code splits larger sets itself, so every batch
        is a request the learner can see. The result is the provider's response in the
        OpenAI shape: {"data": [{"index": i, "embedding": [...]}], "model": ..., "usage": ...}.
        """
        self.check_cancelled()
        if not isinstance(texts, list) or not texts:
            raise ValueError("embed() needs a non-empty list of strings")
        if not all(isinstance(text, str) and text.strip() for text in texts):
            raise ValueError("every text passed to embed() must be a non-empty string")
        if type(self.embedding_batch_limit) is not int or self.embedding_batch_limit < 1:
            raise ValueError("embedding_batch_limit must be a positive integer")
        if len(texts) > self.embedding_batch_limit:
            raise ValueError(f"embed() got {len(texts)} texts but one request takes at most "
                             f"{self.embedding_batch_limit}; split them into batches")
        if dimensions is not None and (type(dimensions) is not int or not 1 <= dimensions <= 100_000):
            raise ValueError("dimensions must be a positive integer")
        if branch is not None and not isinstance(branch, str):
            raise ValueError("branch must be a string")
        if self.embedding is None or not self.embedding_model:
            # Live: the provider has no embedding model; say so instead of using another model.
            if self.mode == "live":
                raise EmbeddingNotConfigured(texts_for(self.locale).embedding_not_configured)
            raise ValueError("this lesson has no embedding connection configured "
                             "(declare testing.embedding_factory in lesson.json)")
        self._check_model_budget()
        request = {"model": self.embedding_model, "input": list(texts)}
        if dimensions is not None:
            request["dimensions"] = dimensions
        self._round = round_number
        tag = {} if branch is None else {"branch": branch}
        self.emit("request", {"endpoint": "embeddings", "body": request,
                              "representation": self.representation, **tag}, round_number)
        started = time.perf_counter()
        response = self._invoke(self.embedding, copy.deepcopy(request), self.api_key)
        self.emit("response", {
            "endpoint": "embeddings", "body": response, "representation": self.representation,
            "duration_ms": round((time.perf_counter() - started) * 1000), **tag,
        }, round_number)
        self.check_cancelled()
        # The response is already on record; a count mismatch would pair texts with the wrong vectors.
        vectors = response.get("data") if isinstance(response, dict) else None
        count = len(vectors) if isinstance(vectors, list) else 0
        if count != len(texts):
            raise RuntimeError(texts_for(self.locale).embedding_response_invalid.format(
                expected=len(texts), actual=count))
        return response

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

    # ---------- Platform-only events ----------
    def _publish(self, kind: str, data: dict, round_number: int | None = None):
        """Record an event only the platform may write (stream chunks, approvals, checkpoints).

        Unlike emit() it does not refuse after a stop: a stream that is being cancelled still
        records the chunks that arrived before the stop, and an approval still records how it ended.
        Lesson code cannot reach these event types through emit().
        """
        snapshot = json.loads(json.dumps(data, ensure_ascii=False, allow_nan=False))
        self.emit_event(kind, snapshot, round_number)

    # ---------- Streaming ----------
    # Streaming connection of this run: stream_completion(body, api_key) opens one streamed request
    # and returns an iterable of chunk dicts (Bailian: the JSON of each SSE data line; LiteLLM: each
    # chunk's model_dump()). It is None offline when the lesson declares no testing.stream_factory.
    stream_completion: Callable | None = field(default=None, repr=False)
    # Why the run is being stopped: "user_stop" (the Stop button), "page_closed" (the page went
    # away), "api" (any other caller). None while nobody asked to stop.
    cancel_reason: Callable[[], str | None] = field(default=lambda: None, repr=False)

    def complete_stream(self, body: dict, round_number: int = 1, *, branch: str | None = None,
                        include_usage: bool = True, flush_interval_s: float = 0.25, flush_max_chunks: int = 40,
                        stop_when: Callable[[dict], bool] | None = None) -> "StreamResult":
        """Send one streamed request and record its chunks as they really arrive.

        Events: one ``request`` (the body with ``stream: true`` and, by default,
        ``stream_options.include_usage``), then ``response_delta`` events, each carrying the raw
        chunks received since the previous one (the first chunk is published alone, so its
        arrival time is visible; later ones are grouped every ``flush_interval_s`` seconds or
        ``flush_max_chunks`` chunks), then one ``response`` whose body the platform assembled
        from those chunks (``data.stream.assembled_from_chunks``). Timings come from the clock of
        this process when each chunk was handed over by the transport.

        Endings: ``completed`` (the stream ended), ``stopped`` (``stop_when(view)`` returned true),
        ``cancelled`` (the run was asked to stop: the chunks received before that are recorded,
        later ones are only counted, then RunCancelled is raised) and ``error`` (the stream broke
        off or carried an error object: recorded, then raised). One stream is one model call.
        """
        self.check_cancelled()
        if self.stream_completion is None:
            raise ValueError("this lesson has no streaming connection configured "
                             "(declare testing.stream_factory in lesson.json)")
        if body.get("model", self.model) != self.model:
            raise ValueError("lesson requests must use the configured model")
        if "stream" in body or "stream_options" in body:
            raise ValueError("complete_stream() sets stream and stream_options itself")
        if branch is not None and not isinstance(branch, str):
            raise ValueError("branch must be a string")
        if not isinstance(flush_interval_s, (int, float)) or not 0 < flush_interval_s <= 5:
            raise ValueError("flush_interval_s must be between 0 and 5 seconds")
        if type(flush_max_chunks) is not int or not 1 <= flush_max_chunks <= 500:
            raise ValueError("flush_max_chunks must be an integer from 1 to 500")
        if stop_when is not None and not callable(stop_when):
            raise ValueError("stop_when must be callable")
        self._check_model_budget()
        request = {"model": self.model, **copy.deepcopy({k: v for k, v in body.items() if k != "model"}),
                   "stream": True}
        if include_usage:
            request["stream_options"] = {"include_usage": True}
        self._round = round_number
        tag = {} if branch is None else {"branch": branch}
        omitted = self._without_unsupported(request)
        self.emit("request", {"body": request, "representation": self.representation, "stream": True, **tag, **omitted},
                  round_number)
        started = time.perf_counter()
        stream = self._invoke(self.stream_completion, copy.deepcopy(request), self.api_key)
        pump = _ChunkPump(stream)
        assembler = StreamAssembler()
        pending: list[dict] = []
        pending_ms: list[int] = []
        deltas = 0
        outcome, failure, discarded, stop_reason = "completed", None, 0, None
        last_flush = time.perf_counter()

        def flush():
            nonlocal deltas, last_flush, pending, pending_ms
            last_flush = time.perf_counter()
            if not pending:
                return
            deltas += 1
            first = assembler.chunk_count - len(pending) + 1
            self._publish("response_delta", {
                "delta_index": deltas, "chunks": pending, "chunk_range": [first, assembler.chunk_count],
                "received_ms": [pending_ms[0], pending_ms[-1]], **_delta_text(pending),
                "representation": self.representation, **tag,
            }, round_number)
            pending, pending_ms = [], []

        try:
            while True:
                if self.cancelled():
                    outcome = "cancelled"
                    break
                item = pump.next(timeout=0.05)
                if item is None:
                    if pending and time.perf_counter() - last_flush >= flush_interval_s:
                        flush()
                    continue
                kind, value, arrived = item
                if kind == "end":
                    break
                if kind == "error":
                    outcome, failure = "error", value
                    break
                if self.cancelled():
                    # Arrived while the run was being stopped: counted, never recorded.
                    outcome, discarded = "cancelled", 1
                    break
                received_ms = round((arrived - started) * 1000)
                assembler.add(value, received_ms)
                pending.append(value)
                pending_ms.append(received_ms)
                if isinstance(value, dict) and "error" in value:
                    outcome = "error"
                    failure = RuntimeError(texts_for(self.locale).stream_provider_error.format(
                        detail=json.dumps(value["error"], ensure_ascii=False)[:2000]))
                    break
                if stop_when is not None and stop_when(assembler.view()):
                    outcome, stop_reason = "stopped", "lesson"
                    break
                if (assembler.chunk_count == 1 or len(pending) >= flush_max_chunks
                        or time.perf_counter() - last_flush >= flush_interval_s):
                    flush()
        finally:
            discarded += pump.stop()
            flush()
        facts = {"assembled_from_chunks": True, "status": outcome, "chunk_count": assembler.chunk_count,
                 "delta_events": deltas, "first_chunk_ms": assembler.first_chunk_ms,
                 "first_token_ms": assembler.first_token_ms,
                 "done_marker": getattr(stream, "done_marker", None)}
        if outcome == "cancelled":
            facts["cancel_reason"] = self.cancel_reason() or "api"
            facts["discarded_after_cancel"] = discarded
        if stop_reason:
            facts["stop_reason"] = stop_reason
        if failure is not None:
            facts["error"] = str(failure)[:2000]
        duration_ms = round((time.perf_counter() - started) * 1000)
        response = assembler.body()
        self._publish("response", {"body": response, "representation": self.representation,
                                   "duration_ms": duration_ms, "stream": facts, **tag}, round_number)
        if outcome == "cancelled":
            raise RunCancelled(texts_for(self.locale).run_cancelled)
        if failure is not None:
            raise failure
        self.check_cancelled()
        return StreamResult(response=response, status=outcome, chunk_count=assembler.chunk_count,
                            first_chunk_ms=assembler.first_chunk_ms, first_token_ms=assembler.first_token_ms,
                            duration_ms=duration_ms, text=assembler.view()["text"])

    # ---------- Approval gate ----------
    # How a decision arrives. approval_gate(request, timeout_s) is the platform's wait for a person
    # (the web page posts to /api/runs/{id}/approvals); approval_policy(request) is a deterministic
    # decision from a test fixture (testing.approval_factory), offline only. A policy that returns
    # None leaves the decision to the gate.
    approval_gate: Callable | None = field(default=None, repr=False)
    approval_policy: Callable | None = field(default=None, repr=False)
    _approval_count: int = field(default=0, init=False)

    def request_approval(self, kind: str, summary: str, payload: dict, *, timeout_s: float = 300,
                         risk: str | None = None, editable: bool = False,
                         round_number: int | None = None) -> "ApprovalDecision":
        """Pause the run until a person approves or rejects ``payload``; both steps are recorded.

        ``approval_requested`` carries the summary, the exact payload and its digest
        (approval_digest). ``approval_resolved`` records the outcome: ``approved``, ``rejected``,
        ``timeout`` (nobody decided within timeout_s) or ``cancelled`` (the run was stopped while
        waiting; RunCancelled follows). With ``editable=True`` the person may approve an edited
        payload; the decision then carries it and its new digest, and the edit is on record.
        Lesson code must act on ``decision.payload`` and can re-check it with ``decision.matches()``
        right before the side effect.
        """
        self.check_cancelled()
        if not isinstance(kind, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", kind):
            raise ValueError("approval kind must be a short lowercase identifier")
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 1000:
            raise ValueError("approval summary must be a non-empty string of at most 1000 characters")
        if not isinstance(payload, dict):
            raise ValueError("approval payload must be a JSON object")
        snapshot = json.loads(json.dumps(payload, ensure_ascii=False, allow_nan=False))
        if len(json.dumps(snapshot, ensure_ascii=False)) > 16_000:
            raise ValueError("approval payload must stay under 16000 characters of JSON")
        if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or not 1 <= timeout_s <= 3600:
            raise ValueError("timeout_s must be between 1 and 3600 seconds")
        if risk is not None and risk not in APPROVAL_RISKS:
            raise ValueError(f"risk must be one of {APPROVAL_RISKS}")
        if type(editable) is not bool:
            raise ValueError("editable must be a boolean")
        if self.approval_policy is None and self.approval_gate is None:
            raise ValueError("this run has no approval channel (offline tests pass approval_policy)")
        self._approval_count += 1
        number = self._round if round_number is None else round_number
        digest = approval_digest(snapshot)
        request = {"approval_id": f"approval-{self._approval_count}", "kind": kind, "summary": summary,
                   "payload": snapshot, "payload_digest": digest, "editable": editable,
                   "timeout_s": timeout_s,
                   "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=timeout_s)).isoformat()}
        if risk is not None:
            request["risk"] = risk
        self._publish("approval_requested", request, number)
        started = time.perf_counter()
        answer, decided_by = None, "learner"
        if self.approval_policy is not None:
            answer = self.approval_policy(copy.deepcopy(request))
            decided_by = "offline_fixture"
        if answer is None:
            if self.approval_gate is None:
                raise ValueError("the approval policy returned None and this run has no approval gate")
            answer, decided_by = self.approval_gate(copy.deepcopy(request), timeout_s), "learner"
        outcome, note, final = _approval_outcome(answer, request)
        if outcome in ("timeout", "cancelled"):
            decided_by = outcome if outcome == "timeout" else "run_cancelled"
        final_digest = approval_digest(final)
        resolved = {"approval_id": request["approval_id"], "outcome": outcome, "decided_by": decided_by,
                    "payload_digest": final_digest, "requested_digest": digest,
                    "edited": final_digest != digest,
                    "waited_ms": round((time.perf_counter() - started) * 1000)}
        if note:
            resolved["note"] = note
        if resolved["edited"]:
            resolved["payload"] = final
        self._publish("approval_resolved", resolved, number)
        if outcome == "cancelled":
            raise RunCancelled(texts_for(self.locale).run_cancelled)
        return ApprovalDecision(approval_id=request["approval_id"], outcome=outcome, decided_by=decided_by,
                                note=note, payload=final, payload_digest=final_digest,
                                edited=resolved["edited"], waited_ms=resolved["waited_ms"])

    # ---------- Checkpoints and resume ----------
    # resume_state is the state saved by the checkpoint this run resumes from (None for a fresh run);
    # resumed_from says which run and checkpoint that was. thread_id is shared by a run and every run
    # resumed from it. source_hash identifies the lesson code; a checkpoint keeps it so a resume
    # after the code changed can be refused.
    resume_state: dict | None = None
    resumed_from: dict | None = None
    thread_id: str | None = None
    source_hash: str | None = None
    # A resumed run numbers its checkpoints after the last one of the run it came from, so the ids on
    # one thread stay distinct ("cp-1" in the source, "cp-2" in the resumed run).
    checkpoint_offset: int = 0
    _checkpoint_count: int = field(default=0, init=False)

    def checkpoint(self, name: str, state: dict, round_number: int | None = None) -> str:
        """Save a JSON-serializable execution position; returns its checkpoint id ("cp-1", ...).

        The state is recorded in a ``checkpoint`` event in the run store, so it survives a server
        restart. A new run can resume from it (POST /api/runs/{run_id}/resume) and reads it from
        ``context.resume_state``. A checkpoint does not make outside actions idempotent: lesson
        code still has to record which side effects already happened.
        """
        self.check_cancelled()
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", name):
            raise ValueError("checkpoint name must be 1-64 letters, digits, '_', '.' or '-'")
        if not isinstance(state, dict):
            raise ValueError("checkpoint state must be a JSON object")
        snapshot = json.loads(json.dumps(state, ensure_ascii=False, allow_nan=False))
        if len(json.dumps(snapshot, ensure_ascii=False)) > 64_000:
            raise ValueError("checkpoint state must stay under 64000 characters of JSON")
        if self._checkpoint_count >= 100:
            raise ValueError("a run may save at most 100 checkpoints")
        self._checkpoint_count += 1
        checkpoint_id = f"cp-{self.checkpoint_offset + self._checkpoint_count}"
        data = {"checkpoint_id": checkpoint_id, "name": name, "state": snapshot,
                "state_digest": approval_digest(snapshot)}
        if self.thread_id:
            data["thread_id"] = self.thread_id
        if self.source_hash:
            data["source_hash"] = self.source_hash
        self._publish("checkpoint", data, self._round if round_number is None else round_number)
        return checkpoint_id


class EmbeddingNotConfigured(ValueError):
    """The live provider has no embedding model: the run stops instead of quietly using another model.

    ``code`` is stable, so the web page can translate the message and point to the model settings.
    """
    code = "embedding_model_missing"


# Imported here, not at the top: lessons quote the lines above by number in their reading notes.
import hashlib  # noqa: E402
import queue  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402


# ---------- Streaming helpers ----------
@dataclass(frozen=True)
class StreamResult:
    """What complete_stream returns: the assembled response plus the stream's real timings.

    ``response`` has the shape of a non-streamed chat completion (choices[0].message, usage when
    the provider reported it), built by the platform from the chunks. first_chunk_ms and
    first_token_ms count from just before the request was sent; None when nothing arrived.
    """
    response: dict
    status: str
    chunk_count: int
    first_chunk_ms: int | None
    first_token_ms: int | None
    duration_ms: int
    text: str


class StreamAssembler:
    """Merge chat.completion.chunk objects into one completion, the way OpenAI-compatible clients do.

    Text and reasoning fragments are concatenated per choice; tool-call fragments are joined by
    their ``index`` (id, type and name are taken from the first fragment that has them, argument
    pieces are appended, None counts as empty). The last finish_reason and the usage chunk win.
    Nothing is added that no chunk contained.
    """

    def __init__(self):
        self.chunk_count = 0
        self.first_chunk_ms: int | None = None
        self.first_token_ms: int | None = None
        self._head: dict = {}
        self._usage = None
        self._choices: dict[int, dict] = {}

    def add(self, chunk, received_ms: int):
        self.chunk_count += 1
        if self.first_chunk_ms is None:
            self.first_chunk_ms = received_ms
        if not isinstance(chunk, dict):
            return
        for key in ("id", "model", "created", "system_fingerprint"):
            if key not in self._head and chunk.get(key) is not None:
                self._head[key] = chunk[key]
        if chunk.get("usage"):
            self._usage = chunk["usage"]
        for choice in chunk.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            index = choice.get("index", 0) if isinstance(choice.get("index", 0), int) else 0
            merged = self._choices.setdefault(index, {"role": None, "content": None, "reasoning": None,
                                                      "tool_calls": {}, "finish_reason": None})
            delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
            if delta.get("role") and merged["role"] is None:
                merged["role"] = delta["role"]
            for source, target in (("content", "content"), ("reasoning_content", "reasoning")):
                piece = delta.get(source)
                if isinstance(piece, str):
                    merged[target] = (merged[target] or "") + piece
                    if piece and self.first_token_ms is None:
                        self.first_token_ms = received_ms
            for fragment in delta.get("tool_calls") or []:
                if isinstance(fragment, dict):
                    self._merge_tool_call(merged["tool_calls"], fragment, received_ms)
            if choice.get("finish_reason") is not None:
                merged["finish_reason"] = choice["finish_reason"]

    def _merge_tool_call(self, calls: dict, fragment: dict, received_ms: int):
        index = fragment.get("index", len(calls)) if isinstance(fragment.get("index"), int) else len(calls)
        call = calls.setdefault(index, {"id": None, "type": None, "name": None, "arguments": ""})
        for key in ("id", "type"):
            if not call[key] and fragment.get(key):
                call[key] = fragment[key]
        function = fragment.get("function") if isinstance(fragment.get("function"), dict) else {}
        if not call["name"] and function.get("name"):
            call["name"] = function["name"]
        if isinstance(function.get("arguments"), str):
            call["arguments"] += function["arguments"]
        if self.first_token_ms is None:
            self.first_token_ms = received_ms

    def view(self) -> dict:
        """What stop_when sees: the text so far (first choice) and how many chunks arrived."""
        first = self._choices.get(0) or next(iter(self._choices.values()), None)
        return {"text": (first or {}).get("content") or "", "chunk_count": self.chunk_count,
                "first_token_ms": self.first_token_ms}

    def body(self) -> dict:
        choices = []
        for index in sorted(self._choices):
            merged = self._choices[index]
            message = {"role": merged["role"] or "assistant", "content": merged["content"]}
            if merged["reasoning"] is not None:
                message["reasoning_content"] = merged["reasoning"]
            if merged["tool_calls"]:
                message["tool_calls"] = [
                    {"id": call["id"], "type": call["type"] or "function",
                     "function": {"name": call["name"], "arguments": call["arguments"]}}
                    for _, call in sorted(merged["tool_calls"].items())]
            choices.append({"index": index, "message": message, "finish_reason": merged["finish_reason"]})
        body = {**self._head, "choices": choices}
        if self._usage is not None:
            body["usage"] = self._usage
        return body


def _delta_text(chunks: list) -> dict:
    """The text that a group of chunks added to the first choice, for timelines and summaries."""
    text, reasoning = [], []
    for chunk in chunks:
        for choice in (chunk.get("choices") or []) if isinstance(chunk, dict) else []:
            if not isinstance(choice, dict) or choice.get("index", 0) != 0:
                continue
            delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
            if isinstance(delta.get("content"), str):
                text.append(delta["content"])
            if isinstance(delta.get("reasoning_content"), str):
                reasoning.append(delta["reasoning_content"])
    result = {"text": "".join(text)}
    if reasoning:
        result["reasoning"] = "".join(reasoning)
    return result


class _ChunkPump:
    """Read a blocking chunk stream on its own thread, so the run can notice a stop between chunks.

    The run thread takes ("chunk", value, arrived) items with a short timeout and checks for
    cancellation in between, even while no chunk arrives. stop() tells the reader to quit: it
    closes the stream itself (only the iterating thread may), at the latest when the next chunk
    or the network timeout arrives. Items still queued at stop() were never handed to the run;
    stop() returns how many chunks that was.
    """

    def __init__(self, stream):
        self._stream = stream
        self._queue: queue.Queue = queue.Queue()
        self._stopped = threading.Event()
        threading.Thread(target=self._read, name="agent-course-stream", daemon=True).start()

    def _read(self):
        iterator = None
        try:
            iterator = iter(self._stream)
            for chunk in iterator:
                self._queue.put(("chunk", chunk, time.perf_counter()))
                if self._stopped.is_set():
                    break
            else:
                self._queue.put(("end", None, time.perf_counter()))
        except Exception as error:  # reported to the run thread, which records and raises it
            self._queue.put(("error", error, time.perf_counter()))
        finally:
            for target in (iterator, self._stream):
                close = getattr(target, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass

    def next(self, timeout: float):
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self) -> int:
        self._stopped.set()
        unread = 0
        while True:
            try:
                kind, _, _ = self._queue.get_nowait()
            except queue.Empty:
                return unread
            unread += kind == "chunk"


# ---------- Approval helpers ----------
APPROVAL_RISKS = ("low", "medium", "high", "critical")


def approval_digest(payload: dict) -> str:
    """sha256 of the payload as canonical JSON: the exact arguments a person saw and approved."""
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ApprovalDecision:
    """How one approval request ended. ``payload`` is what was approved (edited when ``edited``)."""
    approval_id: str
    outcome: str  # approved | rejected | timeout (cancelled raises RunCancelled instead)
    decided_by: str  # learner | offline_fixture | timeout
    note: str | None
    payload: dict
    payload_digest: str
    edited: bool
    waited_ms: int

    @property
    def approved(self) -> bool:
        return self.outcome == "approved"

    def matches(self, payload: dict) -> bool:
        """True when ``payload`` is exactly the approved one; check it right before the side effect."""
        return approval_digest(json.loads(json.dumps(payload, ensure_ascii=False))) == self.payload_digest


_DECISIONS = {"approve": "approved", "reject": "rejected", "timeout": "timeout", "cancelled": "cancelled"}


def _approval_outcome(answer, request: dict) -> tuple[str, str | None, dict]:
    """Check a decision from the gate or a fixture policy: (outcome, note, approved payload)."""
    if not isinstance(answer, dict) or answer.get("decision") not in _DECISIONS:
        raise ValueError("an approval decision must be a dict with decision approve, reject or timeout")
    outcome = _DECISIONS[answer["decision"]]
    note = answer.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > 2000):
        raise ValueError("an approval note must be a string of at most 2000 characters")
    final = request["payload"]
    edited = answer.get("edited_payload")
    if edited is not None:
        if outcome != "approved" or not request["editable"]:
            raise ValueError("only an editable request can be approved with an edited payload")
        if not isinstance(edited, dict):
            raise ValueError("an edited payload must be a JSON object")
        final = json.loads(json.dumps(edited, ensure_ascii=False, allow_nan=False))
    return outcome, (note.strip() or None) if isinstance(note, str) else None, final


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
