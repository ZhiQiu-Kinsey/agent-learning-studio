"""网页运行的共享服务：原生课程和独立运行器都通过 RunContext 调用模型、执行工具、记录证据。

只有本地登记的可信课程代码会拿到 RunContext，浏览器数据不能决定导入路径或调用哪个函数。
运行开始与结束、序列化、密钥脱敏和执行锁由 HTTP 层负责，课程代码不能自行发布生命周期事件。
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
    """独立运行器的输入约定：未声明的字段一律拒绝。"""
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
    _round: int = field(default=1, init=False)
    _budget_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def check_cancelled(self):
        if self.cancelled():
            raise RunCancelled("已停止后续步骤。")

    def emit(self, kind: str, data: dict, round_number: int | None = None):
        """发布标准证据或 lesson. 前缀的课程事件；开始、结束等生命周期事件由平台发布。"""
        self.check_cancelled()
        if kind not in _STANDARD_EVENTS and not re.fullmatch(r"lesson\.[a-zA-Z0-9_.-]{1,80}", kind):
            raise ValueError("课程事件须使用标准类型或 lesson. 前缀；开始与结束由平台管理。")
        if not isinstance(data, dict):
            raise ValueError("课程事件数据必须为 JSON 对象。")
        if round_number is not None and (type(round_number) is not int or round_number < 1):
            raise ValueError("事件轮次必须为正整数。")
        # 先按 JSON 序列化一次：不可序列化的值在这里就报错，记录下来的也是当时的快照。
        snapshot = json.loads(json.dumps(data, ensure_ascii=False, allow_nan=False))
        if kind == "answer" and not isinstance(snapshot.get("content"), str):
            raise ValueError("最终回答必须包含字符串 content。")
        self.emit_event(kind, snapshot, round_number)
        if kind == "answer":
            self._answered = True

    def complete(self, body: dict, round_number: int = 1, *, branch: str | None = None) -> dict:
        """用当前模型连接发一次请求，请求和响应都原样记成事件。

        并行发出多个请求时，每个分支传不同的 branch，时间线按它把响应配回对应的请求。
        """
        self.check_cancelled()
        if self.completion is None:
            raise ValueError("本课未配置模型调用能力。")
        # 超过 lesson.json 声明的模型调用数就停止，任何循环都不会无限请求。
        self._check_model_budget()
        # 课程代码不能自己换模型。
        if body.get("model", self.model) != self.model:
            raise ValueError("课程模型请求必须使用当前配置的模型。")
        # 复制一份请求体：之后课程代码再改 messages，也不会改动已经记录的证据。
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
            raise RuntimeError(f"本课模型请求超过 {self.max_model_calls} 次，已停止后续调用。")

    def _invoke_completion(self, body, api_key):
        self.check_cancelled()
        if self.completion is None:
            raise ValueError("本课未配置模型调用能力。")
        with self._budget_lock:  # 并行分支共用同一份调用预算
            self._check_model_budget()
            self._model_count += 1
        return self.completion(body, api_key)

    def execute_proposal(self, tool_call: dict, available_tools: dict) -> dict:
        """执行模型提出的一次调用：先记调用提议，再记工具结果，两者用同一个调用 id 配对。"""
        self.check_cancelled()
        self.emit("tool_call", tool_call, self._round)
        result = execute_tool(tool_call, available_tools)
        self.emit("tool_result", {"tool_call_id": tool_call["id"], "name": tool_call["function"]["name"],
                                  "result": result}, self._round)
        return result

    def call_tool(self, name: str, arguments: dict, available_tools: dict,
                  round_number: int = 1, call_id: str | None = None) -> dict:
        """由课程程序（不是模型）发起一次登记过的工具调用，同样记录调用与结果的配对。"""
        self.check_cancelled()
        self._tool_count += 1
        call = {"id": call_id or f"lesson_{self.lesson_id}_{self._tool_count}", "type": "function",
                "origin": "course_program",
                "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}
        self.emit("tool_call", call, round_number)
        self.check_cancelled()
        result = execute_tool(call, available_tools)
        self.emit("tool_result", {"tool_call_id": call["id"], "name": name, "result": result,
                                  "origin": "course_program"}, round_number)
        return result

    def run_native(self, module, max_rounds: int = 3, *, publish_answer: bool = False):
        """运行原生工具循环；publish_answer=False 时，它的回答只记为一个阶段结果。"""
        self.check_cancelled()
        if self.completion is None:
            raise ValueError("原生 Agent 循环需要已配置的模型调用能力。")
        answer = run_agent(self.question, module.SYSTEM_PROMPT, module.TOOLS, module.AVAILABLE_TOOLS,
                           max_rounds, complete=self.complete, execute=self.execute_proposal)
        if publish_answer:
            self.emit("answer", {"content": answer}, self._round)
        else:
            self.emit("lesson.stage_result", {"content": answer, "title": "原生子流程结果",
                                               "summary": answer[:160]}, self._round)
        return answer


def validate_inputs(module, values: dict) -> dict:
    """在拿执行锁、联系模型之前，先按本课的 INPUT_MODEL 校验输入。"""
    input_model = getattr(module, "INPUT_MODEL", LessonInputs)
    if not isinstance(input_model, type) or not issubclass(input_model, LessonInputs):
        raise TypeError("INPUT_MODEL 必须继承 course.execution.LessonInputs。")
    return input_model.model_validate(values).model_dump(mode="json")


def execute_lesson(spec: dict, module, context: RunContext):
    """按课程登记的方式运行：原生课走工具循环，独立运行器可以是同步或异步函数。"""
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
