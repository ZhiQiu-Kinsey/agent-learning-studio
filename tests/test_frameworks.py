"""框架适配层（course/frameworks.py）的协议测试。

模型数据是确定性的，工具是真实执行的 Python 函数。测试证明：框架发出的每次模型调用都经过
RunContext.complete 并记录为 request/response，前后各有一条标注层级的框架事件；预算、取消、
运行语言和离线夹具的约束对框架代码同样有效。
"""
import json
import re
import types
import unittest
from typing import Annotated, TypedDict
from unittest import mock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import ToolException, tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel

from course import frameworks
from course.execution import RunContext, execute_lesson
from course.frameworks import (
    FRAMEWORK_CALLBACK_EVENT,
    FRAMEWORK_INPUT_EVENT,
    FRAMEWORK_OUTPUT_EVENT,
    GRAPH_UPDATE_EVENT,
    RunContextCallbackHandler,
    RunContextChatModel,
    execute_tool_calls,
    local_tracing_only,
    stream_graph,
    to_openai_messages,
    tools_as_callables,
)
from course.locales import texts_for
from course.runner import RunCancelled
from server.envelope import EnvelopeBuilder

CJK = re.compile(r"[　-〿㐀-䶿一-鿿豈-﫿＀-￯]")


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@tool
def lookup(term: str) -> dict:
    """Look up a course term."""
    if term == "missing":
        # 业务失败：工具有意报告的错误，应变成结构化错误结果而不是让运行崩溃。
        raise ToolException("no entry for this term")
    return {"term": term, "found": True}


def call(call_id, name, arguments):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


def tool_reply(*calls):
    return {"model": "fixture-model", "choices": [{"finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": None, "tool_calls": list(calls)}}]}


def text_reply(content, usage=None):
    response = {"model": "fixture-model", "choices": [{"finish_reason": "stop", "message": {
        "role": "assistant", "content": content}}]}
    if usage is not None:
        response["usage"] = usage
    return response


def create_completion(exercise_id, inputs=None, locale="zh-CN"):
    """仿照课程 fixtures.py 的离线夹具：按练习和运行语言给出确定性响应，只服务测试。"""
    final = {"zh-CN": "1 加 2 等于 3。", "en": "1 plus 2 is 3."}[locale]
    script = {
        "add": [tool_reply(call("call_1", "add", '{"a": 1, "b": 2}')),
                text_reply(final, {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16})],
    }[exercise_id]
    replies = iter(script)

    def completion(body, api_key):
        return next(replies)

    return completion


class Recorder:
    """收集事件，并统计真正到达“模型连接”的调用次数。"""

    def __init__(self, replies=None, completion=None):
        self.events = []
        self.calls = 0
        self._replies = iter(replies or [])
        self._completion = completion

    def completion(self, body, api_key):
        self.calls += 1
        if self._completion is not None:
            return self._completion(body, api_key)
        return next(self._replies)

    def emit(self, kind, data, round_number):
        self.events.append((kind, data, round_number))

    def of(self, kind):
        return [data for event, data, _ in self.events if event == kind]

    def kinds(self):
        return [event for event, _, _ in self.events]


def make_context(recorder, *, locale="zh-CN", budget=6, cancelled=lambda: False, representation="sdk_standardized"):
    return RunContext(
        lesson_id="framework-adapter-test", exercise_id="add", question="", mode="offline", model="fixture-model",
        representation=representation, inputs={}, api_key="", completion=recorder.completion,
        emit_event=recorder.emit, cancelled=cancelled, max_model_calls=budget, locale=locale,
    )


class ChatModelRecordsEveryCall(unittest.TestCase):
    def test_tool_loop_records_each_call_between_framework_events(self):
        recorder = Recorder([tool_reply(call("call_1", "add", '{"a": 1, "b": 2}')), text_reply("3")])
        context = make_context(recorder)
        model = RunContextChatModel(context=context).bind_tools([add])
        history = [SystemMessage("Use the add tool."), HumanMessage("1 + 2?")]
        proposal = model.invoke(history)
        tool_messages = execute_tool_calls(context, proposal, tools_as_callables([add]))
        answer = model.invoke(history + [proposal] + tool_messages)

        self.assertEqual(answer.content, "3")
        # 两次框架调用 = 两次真实的模型连接调用 = 两条 request 与两条 response。
        self.assertEqual(recorder.calls, 2)
        self.assertEqual(recorder.kinds(), [
            FRAMEWORK_INPUT_EVENT, "request", "response", FRAMEWORK_OUTPUT_EVENT,
            "tool_call", "tool_result",
            FRAMEWORK_INPUT_EVENT, "request", "response", FRAMEWORK_OUTPUT_EVENT,
        ])
        # 每次调用自动取下一个轮次，框架事件与请求在同一轮。
        self.assertEqual([number for _, _, number in recorder.events], [1, 1, 1, 1, 1, 1, 2, 2, 2, 2])

        inputs, requests = recorder.of(FRAMEWORK_INPUT_EVENT), recorder.of("request")
        self.assertEqual({item["layer"] for item in inputs}, {"framework_input"})
        self.assertEqual({item["converted_to"] for item in inputs}, {"request"})
        self.assertEqual(inputs[0]["framework"]["name"], "langchain-core")
        self.assertEqual(inputs[0]["tool_names"], ["add"])
        # 框架输入保留框架自己的字段名（type: human），请求体是转换后的 OpenAI 兼容格式（role: user）。
        self.assertEqual(inputs[0]["messages"][1], {"type": "human", "content": "1 + 2?"})
        self.assertEqual(requests[0]["body"]["messages"][1], {"role": "user", "content": "1 + 2?"})
        self.assertEqual(requests[0]["representation"], "sdk_standardized")
        self.assertEqual(requests[0]["body"]["tools"][0]["function"]["name"], "add")
        # 第二次请求带上了框架回填的 assistant 调用与工具结果，调用 id 前后一致。
        second = requests[1]["body"]["messages"]
        self.assertEqual(second[2]["tool_calls"][0]["id"], "call_1")
        self.assertEqual(second[3], {"role": "tool", "tool_call_id": "call_1",
                                     "content": json.dumps({"ok": True, "result": 3})})
        self.assertEqual(recorder.of("tool_result")[0]["result"], {"ok": True, "result": 3})

    def test_request_layer_follows_the_run_representation(self):
        # 百炼原生路径下请求体就是实际发送的 HTTP 请求体；框架层仍由单独的 lesson 事件说明。
        recorder = Recorder([text_reply("ok")])
        RunContextChatModel(context=make_context(recorder, representation="http_body")).invoke("hi")
        self.assertEqual(recorder.of("request")[0]["representation"], "http_body")
        self.assertEqual(recorder.of(FRAMEWORK_INPUT_EVENT)[0]["layer"], "framework_input")

    def test_envelope_only_marks_model_events_with_representation(self):
        recorder = Recorder([text_reply("ok")])
        RunContextChatModel(context=make_context(recorder)).invoke("hi")
        builder = EnvelopeBuilder("0" * 32, representation="sdk_standardized",
                                  sdk={"name": "deterministic-test-adapter", "version": "test"})
        envelopes = [builder.build(kind, data, number, "2026-10-20T00:00:00Z")
                     for kind, data, number in recorder.events]
        marked = {item["type"]: item["representation"] for item in envelopes}
        self.assertEqual(marked, {FRAMEWORK_INPUT_EVENT: None, "request": "sdk_standardized",
                                  "response": "sdk_standardized", FRAMEWORK_OUTPUT_EVENT: None})
        request, response = envelopes[1], envelopes[2]
        self.assertEqual(request["span_kind"], "llm")
        self.assertEqual(request["span_id"], response["span_id"])

    def test_explicit_round_and_branch(self):
        recorder = Recorder([text_reply("a")])
        RunContextChatModel(context=make_context(recorder)).invoke("hi", round_number=4, branch="left")
        self.assertEqual({number for _, _, number in recorder.events}, {4})
        self.assertEqual(recorder.of("request")[0]["branch"], "left")
        self.assertEqual(recorder.of(FRAMEWORK_OUTPUT_EVENT)[0]["branch"], "left")

    def test_rounds_are_numbered_per_run_across_model_objects(self):
        recorder = Recorder([text_reply("a"), text_reply("b")])
        context = make_context(recorder)
        RunContextChatModel(context=context).invoke("plan")
        RunContextChatModel(context=context).invoke("answer")
        self.assertEqual([item["call_index"] for item in recorder.of(FRAMEWORK_INPUT_EVENT)], [1, 2])

    def test_structured_output_goes_through_a_recorded_tool_call(self):
        class Verdict(BaseModel):
            passed: bool

        recorder = Recorder([tool_reply(call("v1", "Verdict", '{"passed": true}'))])
        verdict = RunContextChatModel(context=make_context(recorder)).with_structured_output(Verdict).invoke("check")
        self.assertEqual(verdict, Verdict(passed=True))
        body = recorder.of("request")[0]["body"]
        self.assertEqual(body["tool_choice"], "required")
        self.assertNotIn("ls_structured_output_format", body)

    def test_unknown_option_and_cache_are_refused(self):
        recorder = Recorder([text_reply("x")])
        model = RunContextChatModel(context=make_context(recorder))
        with self.assertRaises(TypeError):
            model.invoke("hi", logit_bias={"1": 2})
        self.assertEqual(recorder.calls, 0)
        with self.assertRaises(ValueError):
            RunContextChatModel(context=make_context(recorder), cache=True)
        with self.assertRaises(TypeError):
            RunContextChatModel(context=object())


class ToolCallEvidence(unittest.TestCase):
    def test_invalid_arguments_and_missing_ids_stay_visible(self):
        recorder = Recorder([tool_reply(
            {"type": "function", "function": {"name": "add", "arguments": '{"a": 1, "b": 2}'}},
            call("call_bad", "add", "{broken"),
            call("call_list", "add", "[1, 2]"),
        )])
        context = make_context(recorder, locale="en")
        proposal = RunContextChatModel(context=context).bind_tools([add]).invoke("add")
        output = recorder.of(FRAMEWORK_OUTPUT_EVENT)[0]
        # 服务商没有给 id：适配层补的 id 写进 synthesized_call_ids，不冒充服务商发来的 id。
        self.assertEqual(output["synthesized_call_ids"], ["framework_call_1_1"])
        self.assertNotIn("id", recorder.of("response")[0]["body"]["choices"][0]["message"]["tool_calls"][0])
        self.assertEqual([item["id"] for item in proposal.invalid_tool_calls], ["call_bad", "call_list"])
        self.assertEqual(proposal.invalid_tool_calls[1]["error"], texts_for("en").tool_arguments_not_object)

        results = execute_tool_calls(context, proposal, tools_as_callables([add]))
        # 无效调用也按原始实参真实提交，失败记录为结构化错误，而不是被框架悄悄丢掉。
        self.assertEqual([item.status for item in results], ["success", "error", "error"])
        tool_results = recorder.of("tool_result")
        self.assertEqual([item["tool_call_id"] for item in tool_results],
                         ["framework_call_1_1", "call_bad", "call_list"])
        self.assertEqual(tool_results[1]["result"]["error_type"], "JSONDecodeError")
        self.assertEqual(recorder.of("tool_call")[1]["function"]["arguments"], "{broken")

    def test_tool_exception_becomes_a_structured_failure(self):
        recorder = Recorder([tool_reply(call("c1", "lookup", '{"term": "missing"}'))])
        context = make_context(recorder)
        proposal = RunContextChatModel(context=context).bind_tools([lookup]).invoke("find")
        [message] = execute_tool_calls(context, proposal, tools_as_callables([lookup]))
        self.assertEqual(message.status, "error")
        self.assertEqual(json.loads(message.content), {"ok": False, "error_type": "ValueError",
                                                       "error": "no entry for this term"})

    def test_usage_is_not_invented(self):
        recorder = Recorder([text_reply("a"), text_reply("b", {"prompt_tokens": 3})])
        model = RunContextChatModel(context=make_context(recorder))
        self.assertIsNone(model.invoke("one").usage_metadata)
        self.assertIsNone(model.invoke("two").usage_metadata)
        self.assertEqual([item["usage_reported"] for item in recorder.of(FRAMEWORK_OUTPUT_EVENT)], [False, False])

    def test_conversion_rejects_what_the_course_does_not_support(self):
        with self.assertRaises(ValueError):
            to_openai_messages([HumanMessage(content=[{"type": "image_url", "image_url": {"url": "x"}}])])
        self.assertEqual(to_openai_messages([HumanMessage(content=[{"type": "text", "text": "a"}, "b"])]),
                         [{"role": "user", "content": "ab"}])
        with self.assertRaises(TypeError):
            execute_tool_calls(make_context(Recorder()), HumanMessage("x"), {})


class State(TypedDict):
    messages: Annotated[list, add_messages]
    steps: int


def build_graph(context, tools):
    """规划-调用-回答的最小图：模型节点、工具节点（经 RunContext 执行）和条件边。"""
    model = RunContextChatModel(context=context).bind_tools(tools)
    available = tools_as_callables(tools)

    def agent(state):
        return {"messages": [model.invoke(state["messages"])], "steps": state["steps"] + 1}

    def run_tools(state):
        return {"messages": execute_tool_calls(context, state["messages"][-1], available)}

    def route(state):
        last = state["messages"][-1]
        return "tools" if isinstance(last, AIMessage) and (last.tool_calls or last.invalid_tool_calls) else END

    graph = StateGraph(State)
    graph.add_node("agent", agent)
    graph.add_node("tools", run_tools)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route, ["tools", END])
    graph.add_edge("tools", "agent")
    return graph.compile()


class LangGraphUsesTheSameModel(unittest.TestCase):
    def test_graph_steps_and_model_calls_are_recorded(self):
        recorder = Recorder([tool_reply(call("call_1", "add", '{"a": 1, "b": 2}')), text_reply("3")])
        context = make_context(recorder)
        final = stream_graph(context, build_graph(context, [add]),
                             {"messages": [HumanMessage("1 + 2?")], "steps": 0}, config={"recursion_limit": 8})
        self.assertEqual(final["messages"][-1].content, "3")
        self.assertEqual(final["steps"], 2)
        self.assertEqual(recorder.calls, len(recorder.of("request")), "每次模型调用都有 request 事件")
        self.assertEqual(recorder.calls, 2)
        updates = recorder.of(GRAPH_UPDATE_EVENT)
        self.assertEqual([item["node"] for item in updates], ["agent", "tools", "agent"])
        self.assertEqual([item["step"] for item in updates], [1, 2, 3])
        # 状态差异里的消息是框架记录，工具节点的更新就是 RunContext 真实执行得到的结果。
        tool_update = updates[1]["update"]["messages"][0]
        self.assertEqual(tool_update["type"], "tool")
        self.assertEqual(json.loads(tool_update["content"]), recorder.of("tool_result")[0]["result"])

    def test_model_budget_stops_the_graph(self):
        looping = Recorder(completion=lambda body, key: tool_reply(call("again", "add", '{"a": 1, "b": 1}')))
        context = make_context(looping, budget=2)
        with self.assertRaises(RuntimeError) as caught:
            stream_graph(context, build_graph(context, [add]),
                         {"messages": [HumanMessage("loop")], "steps": 0}, config={"recursion_limit": 50})
        self.assertEqual(str(caught.exception), texts_for("zh-CN").model_budget_exceeded.format(limit=2))
        # 超出预算的第三次调用没有发出请求，也没有到达模型连接。
        self.assertEqual(looping.calls, 2)
        self.assertEqual(len(looping.of("request")), 2)

    def test_cancel_after_first_response_stops_tools_and_requests(self):
        flag = {"cancelled": False}

        def completion(body, key):
            flag["cancelled"] = True  # 用户在第一次响应返回时点了停止
            return tool_reply(call("call_1", "add", '{"a": 1, "b": 2}'))

        recorder = Recorder(completion=completion)
        context = make_context(recorder, cancelled=lambda: flag["cancelled"])
        with self.assertRaises(RunCancelled):
            stream_graph(context, build_graph(context, [add]), {"messages": [HumanMessage("1 + 2?")], "steps": 0})
        self.assertEqual(recorder.calls, 1)
        self.assertEqual(recorder.of("tool_call"), [])
        # 停止发生在请求途中：平台的 emit 先检查取消，所以连这次响应也不再记录，更不会有下一步。
        self.assertEqual(recorder.kinds(), [FRAMEWORK_INPUT_EVENT, "request"])

    def test_cancel_between_nodes_without_model_calls(self):
        flag = {"cancelled": False}

        def first(state):
            flag["cancelled"] = True
            return {"steps": state["steps"] + 1}

        def second(state):
            raise AssertionError("取消后不应再执行下一个节点")

        graph = StateGraph(State)
        graph.add_node("first", first)
        graph.add_node("second", second)
        graph.add_edge(START, "first")
        graph.add_edge("first", "second")
        graph.add_edge("second", END)
        recorder = Recorder()
        context = make_context(recorder, cancelled=lambda: flag["cancelled"])
        with self.assertRaises(RunCancelled):
            stream_graph(context, graph.compile(), {"messages": [], "steps": 0})
        self.assertEqual(recorder.events, [])

    def test_graph_state_must_be_json(self):
        graph = StateGraph(State)
        graph.add_node("odd", lambda state: {"steps": object()})
        graph.add_edge(START, "odd")
        graph.add_edge("odd", END)
        with self.assertRaises(TypeError):
            stream_graph(make_context(Recorder()), graph.compile(), {"messages": [], "steps": 0})


class CallbacksAndTracing(unittest.TestCase):
    def test_callbacks_become_lesson_events_with_stable_ids(self):
        recorder = Recorder([tool_reply(call("call_1", "add", '{"a": 1, "b": 2}'))])
        context = make_context(recorder)
        handler = RunContextCallbackHandler(context, include_chains=False)
        RunContextChatModel(context=context).bind_tools([add]).invoke("add", config={"callbacks": [handler]})
        add.invoke({"a": 1, "b": 2}, config={"callbacks": [handler]})
        callbacks = recorder.of(FRAMEWORK_CALLBACK_EVENT)
        self.assertEqual([item["callback"] for item in callbacks],
                         ["on_chat_model_start", "on_llm_end", "on_tool_start", "on_tool_end"])
        self.assertEqual([item["run"] for item in callbacks], ["fw-1", "fw-1", "fw-2", "fw-2"])
        self.assertEqual(callbacks[2]["name"], "add")
        # 回调事件在模型请求之前开始、响应之后结束，夹住同一次调用。
        kinds = recorder.kinds()
        self.assertLess(kinds.index(FRAMEWORK_CALLBACK_EVENT), kinds.index("request"))

    def test_cancelled_callback_is_not_swallowed(self):
        recorder = Recorder()
        context = make_context(recorder, cancelled=lambda: True)
        # LangChain 会先记一条回调错误日志再抛出；这里接住日志，只看异常没有被吞掉。
        with self.assertLogs("langchain_core.callbacks.manager", level="WARNING"), self.assertRaises(RunCancelled):
            add.invoke({"a": 1, "b": 2}, config={"callbacks": [RunContextCallbackHandler(context)]})

    def test_tracing_must_stay_local(self):
        recorder = Recorder([text_reply("ok")])
        model = RunContextChatModel(context=make_context(recorder))
        with mock.patch.object(frameworks, "tracing_is_enabled", return_value=True):
            with self.assertRaises(RuntimeError):
                model.invoke("hi")
        self.assertEqual(recorder.calls, 0)
        self.assertEqual(recorder.of("request"), [])
        with local_tracing_only():
            self.assertEqual(model.invoke("hi").content, "ok")


class OfflineFixturesAndLocales(unittest.TestCase):
    """框架代码放进 custom 运行器，由离线夹具驱动，两种运行语言各跑一次。"""

    @staticmethod
    def run_lesson(locale):
        def run(context):
            model = RunContextChatModel(context=context).bind_tools([add])
            question = {"zh-CN": "1 加 2 等于几？", "en": "What is 1 plus 2?"}[context.locale]
            history = [HumanMessage(question)]
            proposal = model.invoke(history)
            history += [proposal, *execute_tool_calls(context, proposal, tools_as_callables([add]))]
            return model.invoke(history).content

        recorder = Recorder(completion=create_completion("add", {}, locale))
        context = make_context(recorder, locale=locale)
        answer = execute_lesson({"runtime": {"kind": "custom", "entrypoint": "runtime:run"}},
                                types.SimpleNamespace(run=run), context)
        return answer, recorder

    def test_fixture_drives_both_locales(self):
        zh_answer, zh = self.run_lesson("zh-CN")
        en_answer, en = self.run_lesson("en")
        self.assertEqual(zh_answer, "1 加 2 等于 3。")
        self.assertEqual(en_answer, "1 plus 2 is 3.")
        for recorder in (zh, en):
            self.assertEqual(recorder.kinds()[-1], "answer")
            self.assertEqual(recorder.calls, 2)
            self.assertEqual(recorder.of(FRAMEWORK_OUTPUT_EVENT)[-1]["message"]["usage_metadata"],
                             {"input_tokens": 12, "output_tokens": 4, "total_tokens": 16})

    def test_english_run_has_no_chinese(self):
        _, recorder = self.run_lesson("en")
        leaks = [kind for kind, data, _ in recorder.events if CJK.search(json.dumps(data, ensure_ascii=False))]
        self.assertEqual(leaks, [])


if __name__ == "__main__":
    unittest.main()
