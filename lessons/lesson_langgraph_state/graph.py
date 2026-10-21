"""The study-plan graph: plan -> call -> verify -> answer, plus a needs-input terminal and a failed terminal.

State, Node and Edge map onto the native runner of application-state: the TypedDict plays the state
dataclass, each node is one step function, each conditional edge is one if branch. The difference is
that the whole flow is declared in one place, so it can be listed, drawn and checked before it runs.
"""
import json
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from course.execution import RunContext
from course.frameworks import RunContextChatModel, execute_tool_calls
from lessons.lesson_langgraph_state.locales import Texts
from lessons.lesson_langgraph_state.study_tools import available_tools, tool_definition

TERMINAL_NODES = ("answer", "ask_user", "fail")
MODEL_NODES = ("plan", "answer")


class StudyState(TypedDict):
    """Everything the nodes share. A node returns only the fields it changes."""
    # Reducers decide how an update meets the old value: these two lists are appended to.
    messages: Annotated[list[AnyMessage], add_messages]
    evidence: Annotated[list[dict], operator.add]
    # No reducer: the last write wins, which is what a status or a counter needs.
    request: dict
    missing: list[str]
    failed_checks: int
    verdict: str | None
    problems: list[str]
    result: dict | None
    status: str
    reason: str | None


def check_evidence(records: list[dict], request: dict) -> list[str]:
    """Problem codes for one attempt; the verifier reads structured tool results, never the model's prose."""
    if not records:
        return ["no_tool_call"]
    problems = []
    if any(not record["ok"] for record in records):
        problems.append("tool_error")
    succeeded = [record for record in records if record["ok"]]
    if succeeded and not any(_same_request(record["arguments"], request) for record in succeeded):
        # The tool worked, but on a different task than the one asked: dropped or extra lessons.
        problems.append("arguments_mismatch")
    return problems


def _same_request(arguments: dict | None, request: dict) -> bool:
    if not isinstance(arguments, dict) or not isinstance(arguments.get("lessons"), list):
        return False
    return (sorted(arguments["lessons"]) == sorted(request["lessons"])
            and arguments.get("minutes_per_day") == request["minutes_per_day"])


def build_graph(context: RunContext, t: Texts, max_repairs: int, trail: list):
    """Declare nodes and edges, then compile; trail collects visited nodes and route decisions for the report."""
    planner = RunContextChatModel(context=context).bind_tools([tool_definition(t)])
    writer = RunContextChatModel(context=context)
    tools = available_tools(t)

    def intake(state: StudyState) -> dict:
        # 1. Missing parameters are a program decision on the structured request; the model never guesses them.
        missing = [name for name in ("lessons", "minutes_per_day") if not state["request"].get(name)]
        return {"missing": missing, "status": "running"}

    def plan(state: StudyState) -> dict:
        # 2. The model turns the request into a tool call; after a failed check it first reads why.
        feedback = []
        if state["verdict"] == "failed":
            reasons = " ".join(t.problem_text[code] for code in state["problems"])
            feedback = [HumanMessage(t.repair_feedback.format(problems=reasons))]
        return {"messages": feedback + [planner.invoke(state["messages"] + feedback)]}

    def call_tools(state: StudyState) -> dict:
        # 3. Our own tool node: every call goes through RunContext, so tool_call/tool_result are recorded.
        proposal = state["messages"][-1]
        arguments = {call["id"]: call["args"] for call in proposal.tool_calls}
        results = execute_tool_calls(context, proposal, tools)
        evidence = [{"attempt": state["failed_checks"] + 1, "call_id": message.tool_call_id,
                     "arguments": arguments.get(message.tool_call_id), **json.loads(message.content)}
                    for message in results]
        return {"messages": results, "evidence": evidence}

    def verify(state: StudyState) -> dict:
        # 4. Judge only this attempt; a failure is counted so the router can bound the repairs.
        attempt = [record for record in state["evidence"] if record["attempt"] == state["failed_checks"] + 1]
        problems = check_evidence(attempt, state["request"])
        if problems:
            return {"verdict": "failed", "problems": problems, "failed_checks": state["failed_checks"] + 1}
        passed = next(record for record in attempt if record["ok"] and _same_request(record["arguments"],
                                                                                    state["request"]))
        return {"verdict": "passed", "problems": [], "result": passed["result"]}

    def answer(state: StudyState) -> dict:
        # 5. Terminal: the writer sees only the checked result, not the whole tool history.
        prompt = t.answer_prompt.format(result=json.dumps(state["result"], ensure_ascii=False))
        reply = writer.invoke([SystemMessage(t.answer_system), HumanMessage(prompt)])
        return {"messages": [reply], "status": "completed", "reason": t.reason_completed}

    def ask_user(state: StudyState) -> dict:
        # Terminal: nothing is guessed; the run ends and names the fields the learner must supply.
        return {"status": "needs_input", "reason": t.reason_missing.format(fields=", ".join(state["missing"]))}

    def fail(state: StudyState) -> dict:
        # Terminal: the repair budget is spent; the evidence stays in the state for the report.
        return {"status": "failed", "reason": t.reason_failed.format(count=state["failed_checks"],
                                                                     problems=", ".join(state["problems"]))}

    def after_intake(state: StudyState) -> str:
        return note_route("intake", "ask_user" if state["missing"] else "plan", missing=state["missing"])

    def after_verify(state: StudyState) -> str:
        # The business budget lives in the state: max_repairs failed checks may go back to plan, no more.
        if state["verdict"] == "passed":
            target = "answer"
        elif state["failed_checks"] <= max_repairs:
            target = "plan"
        else:
            target = "fail"
        return note_route("verify", target, verdict=state["verdict"], failed_checks=state["failed_checks"],
                          max_repairs=max_repairs)

    graph = StateGraph(StudyState)
    for name, node in (("intake", intake), ("plan", plan), ("tools", call_tools), ("verify", verify),
                       ("answer", answer), ("ask_user", ask_user), ("fail", fail)):
        graph.add_node(name, _traced(name, node, trail))
    graph.add_edge(START, "intake")
    graph.add_conditional_edges("intake", after_intake, ["plan", "ask_user"])
    graph.add_edge("plan", "tools")
    graph.add_edge("tools", "verify")
    graph.add_conditional_edges("verify", after_verify, ["answer", "plan", "fail"])
    for name in TERMINAL_NODES:
        graph.add_edge(name, END)

    def note_route(source: str, target: str, **read) -> str:
        """Record which state values a router read and where it sent the graph, at the moment it decided."""
        context.emit("lesson.graph_route", {"from": source, "to": target, "read": read})
        trail.append({"route": source, "to": target, "read": read})
        return target

    return graph.compile()


def _traced(name: str, node, trail: list):
    """Note the node in the trail before it runs, so a run stopped by recursion_limit still shows its path."""
    def run_node(state: StudyState) -> dict:
        trail.append({"node": name})
        return node(state)
    return run_node
