"""Shared services for native lessons and independently implemented course runtimes.

Only trusted, locally registered Python code receives a RunContext. Browser data
never chooses an import path or a callable. The HTTP layer owns run_start/done,
serialization, secret redaction and the run lock.
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

from course.runner import RunCancelled, execute_tool, run_agent


class LessonInputs(BaseModel):
    """Opt-in input contract for a custom lesson; reject undeclared fields."""
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
    _answered: bool = field(default=False, init=False)
    _tool_count: int = field(default=0, init=False)
    _model_count: int = field(default=0, init=False)
    _budget_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def check_cancelled(self):
        if self.cancelled():
            raise RunCancelled("已停止后续步骤。")

    def emit(self, kind: str, data: dict, round_number: int | None = None):
        """Publish standard evidence or a namespaced lesson event, never lifecycle sentinels."""
        self.check_cancelled()
        if kind not in _STANDARD_EVENTS and not re.fullmatch(r"lesson\.[a-zA-Z0-9_.-]{1,80}", kind):
            raise ValueError("课程事件须使用标准类型或 lesson. 前缀；开始与结束由平台管理。")
        if not isinstance(data, dict):
            raise ValueError("课程事件数据必须为 JSON 对象。")
        if round_number is not None and (type(round_number) is not int or round_number < 1):
            raise ValueError("事件轮次必须为正整数。")
        # Reject unserializable values before handing control back to the stream.
        snapshot = json.loads(json.dumps(data, ensure_ascii=False, allow_nan=False))
        if kind == "answer" and not isinstance(snapshot.get("content"), str):
            raise ValueError("最终回答必须包含字符串 content。")
        self.emit_event(kind, snapshot, round_number)
        if kind == "answer":
            self._answered = True

    def complete(self, body: dict, round_number: int = 1, *, branch: str | None = None) -> dict:
        """Use the configured provider with immutable request/response evidence.

        Parallel callers pass a distinct ``branch`` so each response closes its own request span.
        """
        self.check_cancelled()
        if self.completion is None:
            raise ValueError("本课未配置模型调用能力。")
        self._check_model_budget()
        request = copy.deepcopy(body)
        if request.get("model", self.model) != self.model:
            raise ValueError("课程模型请求必须使用当前配置的模型。")
        request["model"] = self.model
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
            raise RuntimeError(f"本课模型请求超过 {self.max_model_calls} 次，已停止后续调用。")

    def _invoke_completion(self, body, api_key):
        self.check_cancelled()
        if self.completion is None:
            raise ValueError("本课未配置模型调用能力。")
        with self._budget_lock:  # parallel branches share one budget
            self._check_model_budget()
            self._model_count += 1
        return self.completion(body, api_key)

    def call_tool(self, name: str, arguments: dict, available_tools: dict,
                  round_number: int = 1, call_id: str | None = None) -> dict:
        """Execute a declared local tool while preserving call/result linkage."""
        self.check_cancelled()
        self._tool_count += 1
        call = {"id": call_id or f"lesson_{self.lesson_id}_{self._tool_count}", "type": "function",
                "origin": "course_program",
                "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}
        self.emit("tool_call", call, round_number)
        self.check_cancelled()
        result = execute_tool(call, available_tools, quiet=True)
        self.emit("tool_result", {"tool_call_id": call["id"], "name": name, "result": result,
                                  "origin": "course_program"}, round_number)
        return result

    def run_native(self, module, max_rounds: int = 3, *, publish_answer: bool = False):
        """Compose the existing teaching loop inside a more specialized course."""
        self.check_cancelled()
        if self.completion is None:
            raise ValueError("原生 Agent 循环需要已配置的模型调用能力。")
        self._check_model_budget()
        def publish(kind, data, round_number):
            if kind == "request":
                # The native loop publishes before calling its completion. Gate
                # every round here as well, so refused requests aren't counted.
                self._check_model_budget()
            if kind == "answer" and not publish_answer:
                self.emit("lesson.stage_result", {**data, "title": "原生子流程结果",
                                                   "summary": str(data.get("content", ""))[:160]}, round_number)
            else:
                self.emit(kind, data, round_number)
        return run_agent(
            self.question, self.api_key, module.SYSTEM_PROMPT, module.TOOLS,
            module.AVAILABLE_TOOLS, max_rounds, completion=self._invoke_completion,
            model=self.model, emit=publish, cancelled=self.cancelled, quiet=True,
            representation=self.representation,
        )


def validate_inputs(module, values: dict) -> dict:
    """Validate per-course input before claiming the lock or contacting a model."""
    input_model = getattr(module, "INPUT_MODEL", LessonInputs)
    if not isinstance(input_model, type) or not issubclass(input_model, LessonInputs):
        raise TypeError("INPUT_MODEL 必须继承 course.execution.LessonInputs。")
    return input_model.model_validate(values).model_dump(mode="json")


def execute_lesson(spec: dict, module, context: RunContext):
    """Dispatch a registered lesson; support sync or async specialized runtimes."""
    context.check_cancelled()
    runtime = spec["runtime"]
    if runtime["kind"] == "native":
        result = context.run_native(module, max_rounds=runtime.get("max_rounds", 3), publish_answer=True)
    else:
        function_name = runtime["entrypoint"].split(":", 1)[1]
        function = getattr(module, function_name)
        if not callable(function):
            raise TypeError("课程执行入口不是函数。")
        result = function(context)
        if inspect.isawaitable(result):
            result = asyncio.run(result)
    context.check_cancelled()
    if result is not None and not isinstance(result, str):
        raise TypeError("课程执行器应返回回答字符串，或发布 answer 后返回 None。")
    if not context._answered:
        if result is None:
            raise ValueError("课程执行器结束时没有提供结果。")
        context.emit("answer", {"content": result})
    return result
