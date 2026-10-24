"""Framework adapter: LangChain and LangGraph code calls the model and tools through RunContext.

Framework lessons compare what a framework does with the native loop, so the evidence has
to come from the same place: every model call a framework makes goes through
``RunContext.complete`` (request and response are recorded unchanged, budget and
cancellation apply), and every tool call goes through ``RunContext.execute_proposal``.

What the framework holds and what the provider receives are different layers. Around each
model call the adapter records two lesson events so neither passes for the other:

- ``lesson.framework_input``: the framework's own messages, tool names and options, before
  conversion. ``layer`` is ``framework_input``; it is not a request body.
- ``request`` / ``response``: recorded by RunContext. The body is the OpenAI-compatible
  request this adapter converted from those messages, labelled with the run's
  representation (``http_body`` or ``sdk_standardized``) like any other request.
- ``lesson.framework_output``: the AIMessage the framework builds from that response
  (parsed tool calls, invalid ones, usage only when the provider reported it).

LangSmith tracing would upload framework inputs to an external service. Course runs keep
data local: wrap framework code in ``local_tracing_only()`` (``stream_graph`` does it), and
the chat model refuses to call the model while tracing is on.
"""
from __future__ import annotations

import json
import threading
import weakref
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Iterator, Sequence

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.output_parsers.openai_tools import make_invalid_tool_call, parse_tool_call
from langchain_core.exceptions import OutputParserException
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool, ToolException
from langchain_core.utils.function_calling import convert_to_openai_tool
from langsmith import tracing_context
from langsmith.utils import tracing_is_enabled
from pydantic import ConfigDict, Field, model_validator

from course.execution import RunContext
from course.locales import texts_for

FRAMEWORK_INPUT_EVENT = "lesson.framework_input"
FRAMEWORK_OUTPUT_EVENT = "lesson.framework_output"
FRAMEWORK_CALLBACK_EVENT = "lesson.framework_callback"
GRAPH_UPDATE_EVENT = "lesson.graph_update"
ADAPTER_NAME = "course.frameworks.RunContextChatModel"

# Request options a framework may pass through to the model; anything else is a mistake
# worth seeing, not a field to forward silently.
_REQUEST_OPTIONS = ("tools", "tool_choice", "parallel_tool_calls", "response_format",
                    "temperature", "max_tokens", "top_p", "seed", "stop")
_TOOL_CHOICE_WORDS = {"auto": "auto", "none": "none", "required": "required", "any": "required"}


def framework_versions() -> dict[str, str | None]:
    """Installed versions of the framework packages, for events and the dependency section of lessons."""
    found = {}
    for name in ("langchain-core", "langgraph"):
        try:
            found[name] = version(name)
        except PackageNotFoundError:
            found[name] = None
    return found


def _framework_identity() -> dict:
    return {"name": "langchain-core", "version": framework_versions()["langchain-core"]}


@contextmanager
def local_tracing_only() -> Iterator[None]:
    """Turn LangSmith tracing off for the framework code inside, whatever the environment says."""
    with tracing_context(enabled=False):
        yield


# Calls are numbered per run, not per model object: a graph with a planner model and an
# answer model still gets one increasing sequence of rounds in the timeline.
_call_counters: dict[int, int] = {}
_counter_lock = threading.Lock()


def _next_call_index(context: RunContext) -> int:
    key = id(context)
    with _counter_lock:
        if key not in _call_counters:
            _call_counters[key] = 0
            weakref.finalize(context, _call_counters.pop, key, None)
        _call_counters[key] += 1
        return _call_counters[key]


# ---------------------------------------------------------------------------
# Message conversion: framework messages <-> OpenAI-compatible chat dicts
# ---------------------------------------------------------------------------

def _text_content(content: Any) -> str:
    """Flatten string or text-block content; other block types are not part of this course."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
            else:
                raise ValueError(f"unsupported content block for the course adapter: {block!r:.80}")
        return "".join(parts)
    raise ValueError(f"unsupported message content type: {type(content).__name__}")


def _openai_tool_call(call_id: str | None, name: str, arguments: str) -> dict:
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


def _assistant_tool_calls(message: AIMessage) -> list[dict]:
    """Valid calls are re-serialized from parsed args; invalid ones keep the raw string the model wrote."""
    calls = [_openai_tool_call(call["id"], call["name"], json.dumps(call["args"], ensure_ascii=False))
             for call in message.tool_calls]
    calls += [_openai_tool_call(call.get("id"), call.get("name") or "", call.get("args") or "")
              for call in message.invalid_tool_calls]
    return calls


def to_openai_messages(messages: Sequence[BaseMessage]) -> list[dict]:
    """Convert framework messages to the chat-completions message list RunContext sends."""
    converted = []
    for message in messages:
        if isinstance(message, SystemMessage):
            converted.append({"role": "system", "content": _text_content(message.content)})
        elif isinstance(message, HumanMessage):
            converted.append({"role": "user", "content": _text_content(message.content)})
        elif isinstance(message, AIMessage):
            calls = _assistant_tool_calls(message)
            content = _text_content(message.content)
            entry = {"role": "assistant", "content": content if content or not calls else None}
            if calls:
                entry["tool_calls"] = calls
            converted.append(entry)
        elif isinstance(message, ToolMessage):
            content = message.content if isinstance(message.content, str) else json.dumps(
                message.content, ensure_ascii=False)
            converted.append({"role": "tool", "tool_call_id": message.tool_call_id, "content": content})
        elif isinstance(message, ChatMessage):
            converted.append({"role": message.role, "content": _text_content(message.content)})
        else:
            raise ValueError(f"unsupported message type for the course adapter: {type(message).__name__}")
    return converted


def message_record(message: BaseMessage) -> dict:
    """A JSON-safe view of one framework message as the framework holds it (its own field names)."""
    record = {"type": message.type, "content": message.content}
    if message.name:
        record["name"] = message.name
    if isinstance(message, AIMessage):
        if message.tool_calls:
            record["tool_calls"] = [dict(call) for call in message.tool_calls]
        if message.invalid_tool_calls:
            record["invalid_tool_calls"] = [dict(call) for call in message.invalid_tool_calls]
        if message.usage_metadata:
            record["usage_metadata"] = dict(message.usage_metadata)
    if isinstance(message, ToolMessage):
        record["tool_call_id"] = message.tool_call_id
        record["status"] = message.status
    if isinstance(message, ChatMessage):
        record["role"] = message.role
    return record


def _reported_usage(usage: Any) -> dict | None:
    """Usage only when the provider reported all three counts; a missing count is not reported, never 0."""
    if not isinstance(usage, dict):
        return None
    counts = {key: usage.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    if not all(type(value) is int for value in counts.values()):
        return None
    return {"input_tokens": counts["prompt_tokens"], "output_tokens": counts["completion_tokens"],
            "total_tokens": counts["total_tokens"]}


def ai_message_from_response(response: dict, *, call_index: int, locale: str) -> tuple[AIMessage, list[str]]:
    """Build the framework's AIMessage from an OpenAI-shaped response; also return any synthesized call ids.

    A call without an id gets ``framework_call_<call>_<n>`` so the tool result can answer it;
    the returned list names those ids, so nobody mistakes them for ids the provider sent.
    """
    choices = response.get("choices") if isinstance(response, dict) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise RuntimeError("the model response has no choices; see the recorded response event")
    choice = choices[0]
    raw = choice.get("message") or {}
    tool_calls, invalid_calls, synthesized = [], [], []
    for position, raw_call in enumerate(raw.get("tool_calls") or [], start=1):
        raw_call = dict(raw_call)
        if not (isinstance(raw_call.get("id"), str) and raw_call["id"].strip()):
            raw_call["id"] = f"framework_call_{call_index}_{position}"
            synthesized.append(raw_call["id"])
        function = raw_call.get("function") or {}
        try:
            parsed = parse_tool_call(raw_call, return_id=True)
        except OutputParserException as error:
            invalid_calls.append(make_invalid_tool_call(raw_call, str(error)))
            continue
        if parsed is None:
            continue
        if not isinstance(parsed["args"], dict):
            # Arguments that parse as JSON but not as an object cannot be keyword arguments.
            invalid_calls.append(make_invalid_tool_call(raw_call, texts_for(locale).tool_arguments_not_object))
            continue
        tool_calls.append({"name": parsed["name"] or function.get("name") or "", "args": parsed["args"],
                           "id": parsed["id"], "type": "tool_call"})
    metadata = {key: value for key, value in (("finish_reason", choice.get("finish_reason")),
                                              ("model_name", response.get("model")),
                                              ("id", response.get("id"))) if value is not None}
    message = AIMessage(content=raw.get("content") or "", tool_calls=tool_calls,
                        invalid_tool_calls=invalid_calls, response_metadata=metadata,
                        usage_metadata=_reported_usage(response.get("usage")))
    return message, synthesized


def _format_tool_choice(choice: Any, tool_names: list[str]) -> Any:
    if choice is None or isinstance(choice, dict):
        return choice
    if isinstance(choice, str):
        if choice in _TOOL_CHOICE_WORDS:
            return _TOOL_CHOICE_WORDS[choice]
        if choice in tool_names:
            return {"type": "function", "function": {"name": choice}}
    raise ValueError(f"tool_choice must be auto, none, required, any or a bound tool name; got {choice!r}")


# ---------------------------------------------------------------------------
# The chat model
# ---------------------------------------------------------------------------

class RunContextChatModel(BaseChatModel):
    """A LangChain chat model whose every call is a recorded RunContext request.

    Usage inside a custom runner::

        model = RunContextChatModel(context=context)
        reply = model.bind_tools([search]).invoke([HumanMessage(question)])
        tool_messages = execute_tool_calls(context, reply, {"search": search})

    Each call takes the next round number of the run unless ``round_number`` is passed
    (``model.invoke(messages, round_number=2)``); parallel calls pass ``branch``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    context: Any = Field(exclude=True, repr=False)
    temperature: float | None = None
    max_tokens: int | None = None
    # A cached answer would reach the lesson without a recorded request.
    cache: bool | None = False

    @model_validator(mode="after")
    def check_context(self):
        if not isinstance(self.context, RunContext):
            raise TypeError("RunContextChatModel needs the run's course.execution.RunContext")
        if self.cache not in (False, None):
            raise ValueError("RunContextChatModel never uses a response cache: every answer must be a recorded call")
        return self

    @property
    def _llm_type(self) -> str:
        return "course-run-context"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": self.context.model, "adapter": ADAPTER_NAME}

    def bind_tools(self, tools: Sequence[Any], *, tool_choice: Any = None, strict: bool | None = None,
                   **kwargs: Any):
        """Convert framework tools (BaseTool, function, Pydantic model or dict) to OpenAI tool definitions."""
        formatted = [convert_to_openai_tool(tool, strict=strict) for tool in tools]
        names = [tool["function"]["name"] for tool in formatted]
        if tool_choice is not None:
            kwargs["tool_choice"] = _format_tool_choice(tool_choice, names)
        return super().bind(tools=formatted, **kwargs)

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None,
                  run_manager: Any = None, **kwargs: Any) -> ChatResult:
        context: RunContext = self.context
        context.check_cancelled()
        if tracing_is_enabled():
            raise RuntimeError("LangSmith tracing is on; course runs keep framework data local. "
                               "Wrap the framework code in course.frameworks.local_tracing_only().")
        round_number = kwargs.pop("round_number", None)
        branch = kwargs.pop("branch", None)
        # LangChain adds this for its own tracing metadata; it is not a request option.
        kwargs.pop("ls_structured_output_format", None)
        unknown = sorted(set(kwargs) - set(_REQUEST_OPTIONS))
        if unknown:
            raise TypeError(f"unsupported options for RunContextChatModel: {', '.join(unknown)}")
        options = {key: value for key, value in (("temperature", self.temperature),
                                                 ("max_tokens", self.max_tokens)) if value is not None}
        options.update({key: value for key, value in kwargs.items() if value is not None})
        if stop:
            options["stop"] = list(stop)
        call_index = _next_call_index(context)
        if round_number is None:
            round_number = call_index
        tag = {} if branch is None else {"branch": branch}
        tool_names = [tool["function"]["name"] for tool in options.get("tools", [])]
        context.emit(FRAMEWORK_INPUT_EVENT, {
            "layer": "framework_input", "framework": _framework_identity(), "adapter": ADAPTER_NAME,
            "call_index": call_index, "messages": [message_record(message) for message in messages],
            "tool_names": tool_names,
            "options": {key: value for key, value in options.items() if key != "tools"},
            # The next request event carries the body converted from these messages.
            "converted_to": "request", **tag,
        }, round_number)
        body = {"messages": to_openai_messages(messages), **options}
        response = context.complete(body, round_number, branch=branch)
        message, synthesized = ai_message_from_response(response, call_index=call_index, locale=context.locale)
        context.emit(FRAMEWORK_OUTPUT_EVENT, {
            "layer": "framework_output", "framework": _framework_identity(), "adapter": ADAPTER_NAME,
            "call_index": call_index, "message": message_record(message),
            "synthesized_call_ids": synthesized,
            # False means the provider did not report usage; the adapter never fills in a number.
            "usage_reported": message.usage_metadata is not None, **tag,
        }, round_number)
        llm_output = {"model_name": response.get("model"), "call_index": call_index}
        if message.usage_metadata is not None:
            llm_output["token_usage"] = dict(message.usage_metadata)
        return ChatResult(generations=[ChatGeneration(message=message)], llm_output=llm_output)


# ---------------------------------------------------------------------------
# Tools: framework tool calls run through RunContext.execute_proposal
# ---------------------------------------------------------------------------

def tools_as_callables(tools: Sequence[BaseTool]) -> dict[str, Any]:
    """Map LangChain tools to the name -> callable allowlist RunContext executes.

    ToolException is a business failure the tool raised on purpose; turning it into
    ValueError makes it a structured error result (ok=false) instead of a crashed run.
    """
    def wrap(tool: BaseTool):
        def call(**arguments):
            try:
                return tool.invoke(arguments)
            except ToolException as error:
                raise ValueError(str(error)) from error
        return call

    return {tool.name: wrap(tool) for tool in tools}


def execute_tool_calls(context: RunContext, message: AIMessage, available_tools: dict) -> list[ToolMessage]:
    """Run every call in an AIMessage through RunContext and return the ToolMessages for the next request.

    Use this instead of LangGraph's prebuilt ToolNode in course runs: ToolNode calls tools
    directly, so its calls would not appear as tool_call / tool_result events. Invalid calls
    (arguments that are not a JSON object) are submitted with their raw arguments, so the
    failure is recorded and answered instead of silently dropped.
    """
    if not isinstance(message, AIMessage):
        raise TypeError("execute_tool_calls needs the AIMessage that proposed the calls")
    results = []
    for call in _assistant_tool_calls(message):
        result = context.execute_proposal(call, available_tools)
        content = json.dumps(result, ensure_ascii=False)
        results.append(ToolMessage(content=content, tool_call_id=call["id"], name=call["function"]["name"],
                                   status="success" if result.get("ok") else "error"))
    return results


# ---------------------------------------------------------------------------
# Callbacks and graph steps as lesson events
# ---------------------------------------------------------------------------

class RunContextCallbackHandler(BaseCallbackHandler):
    """Record framework callbacks as ``lesson.framework_callback`` events (names and nesting only).

    Inputs and outputs are left out: model inputs and outputs are already in the
    framework_input / request / response / framework_output events, and arbitrary
    chain values are not always JSON. Run ids become ``fw-1``, ``fw-2``... in order of
    appearance, so a replay reads the same nesting without random UUIDs.
    raise_error is on, so a cancelled run stops the framework instead of being swallowed.
    """

    raise_error = True

    def __init__(self, context: RunContext, *, include_chains: bool = True):
        self.context = context
        self.include_chains = include_chains
        self._ids: dict[str, str] = {}
        self._lock = threading.Lock()

    def _short(self, run_id: Any) -> str | None:
        if run_id is None:
            return None
        with self._lock:
            key = str(run_id)
            if key not in self._ids:
                self._ids[key] = f"fw-{len(self._ids) + 1}"
            return self._ids[key]

    def _record(self, callback: str, run_id: Any, parent_run_id: Any, name: str | None = None, **extra):
        data = {"callback": callback, "run": self._short(run_id), "parent_run": self._short(parent_run_id)}
        if name:
            data["name"] = name
        data.update(extra)
        self.context.emit(FRAMEWORK_CALLBACK_EVENT, data)

    @staticmethod
    def _name(serialized: Any, kwargs: dict) -> str | None:
        if kwargs.get("name"):
            return str(kwargs["name"])
        if isinstance(serialized, dict):
            if serialized.get("name"):
                return str(serialized["name"])
            ids = serialized.get("id")
            if isinstance(ids, list) and ids:
                return str(ids[-1])
        return None

    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
        self._record("on_chat_model_start", run_id, parent_run_id, self._name(serialized, kwargs))

    def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
        self._record("on_llm_end", run_id, parent_run_id)

    def on_llm_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        self._record("on_llm_error", run_id, parent_run_id, error_type=type(error).__name__)

    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kwargs):
        self._record("on_tool_start", run_id, parent_run_id, self._name(serialized, kwargs))

    def on_tool_end(self, output, *, run_id, parent_run_id=None, **kwargs):
        self._record("on_tool_end", run_id, parent_run_id)

    def on_tool_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        self._record("on_tool_error", run_id, parent_run_id, error_type=type(error).__name__)

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        if self.include_chains:
            self._record("on_chain_start", run_id, parent_run_id, self._name(serialized, kwargs))

    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs):
        if self.include_chains:
            self._record("on_chain_end", run_id, parent_run_id)

    def on_chain_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        if self.include_chains:
            self._record("on_chain_error", run_id, parent_run_id, error_type=type(error).__name__)


def to_jsonable(value: Any) -> Any:
    """Graph state values as plain JSON: messages become their framework record; unknown objects are an error."""
    if isinstance(value, BaseMessage):
        return message_record(value)
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        return to_jsonable(value.model_dump(mode="json"))
    raise TypeError(f"graph state value of type {type(value).__name__} cannot be recorded as JSON")


def stream_graph(context: RunContext, graph: Any, inputs: Any, *, config: dict | None = None) -> Any:
    """Run a compiled LangGraph graph step by step, recording each node's update; return the final state.

    Every update becomes a ``lesson.graph_update`` event (``step``, ``node``, ``update``), so
    a replay shows how the graph moved and what each node changed. Cancellation is checked
    between steps, which also covers nodes that never call the model. Set the graph's own
    loop bound with ``config={"recursion_limit": n}``.
    """
    final = None
    step = 0
    with local_tracing_only():
        for mode, chunk in graph.stream(inputs, config, stream_mode=["updates", "values"]):
            context.check_cancelled()
            if mode == "values":
                final = chunk
                continue
            for node, update in (chunk or {}).items():
                step += 1
                context.emit(GRAPH_UPDATE_EVENT, {"step": step, "node": node, "update": to_jsonable(update)})
    context.check_cancelled()
    return final
