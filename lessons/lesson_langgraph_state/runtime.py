"""Run the study-plan graph with LangGraph: every node update, route decision, model call and tool call is evidence."""
import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from pydantic import Field

from course.execution import LessonInputs, RunContext
from course.frameworks import stream_graph
from lessons.lesson_langgraph_state.graph import MODEL_NODES, TERMINAL_NODES, build_graph
from lessons.lesson_langgraph_state.locales import texts_for

SLUG = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"


class Inputs(LessonInputs):
    # Lesson ids and numbers are code values, the same in every run language.
    # Presets are scalars, so the lesson list is one comma-separated string; empty means "not given".
    lessons: str = Field(default="", max_length=300, pattern=rf"^\s*(?:{SLUG}(?:\s*,\s*{SLUG}){{0,5}})?\s*$")
    minutes_per_day: int | None = Field(default=None, ge=10, le=240)
    max_repairs: int = Field(default=1, ge=0, le=3)
    recursion_limit: int = Field(default=25, ge=3, le=40)


INPUT_MODEL = Inputs


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    lessons = [slug.strip() for slug in values.lessons.split(",") if slug.strip()]
    trail: list[dict] = []
    graph = build_graph(context, t, values.max_repairs, trail)
    _report_structure(context, t, graph, values)
    # 1. The initial state: the structured request plus the two messages the planner starts from.
    request = {"lessons": lessons, "minutes_per_day": values.minutes_per_day}
    question = t.request_text.format(lessons=", ".join(lessons) or t.lessons_not_given,
                                     minutes=values.minutes_per_day or t.minutes_not_given)
    initial = {"messages": [SystemMessage(t.plan_system), HumanMessage(question)], "evidence": [],
               "request": request, "missing": [], "failed_checks": 0, "verdict": None, "problems": [],
               "result": None, "status": "ready", "reason": None}
    # 2. stream_graph records one lesson.graph_update per node; recursion_limit is LangGraph's own ceiling.
    try:
        final = stream_graph(context, graph, initial, config={"recursion_limit": values.recursion_limit})
    except GraphRecursionError:
        # 3. The ceiling stopped the graph and no final state came back: report where, never a made-up terminal state.
        final = None
    _report_run(context, t, values, trail, final)
    path = [item["node"] for item in trail if "node" in item]
    if final is None:
        return t.answer_stopped.format(limit=values.recursion_limit, steps=len(path), node=path[-1])
    if final["status"] == "completed":
        return final["messages"][-1].content
    if final["status"] == "needs_input":
        return t.answer_needs_input.format(reason=final["reason"])
    return t.answer_failed.format(reason=final["reason"])


def _endpoint(name: str) -> str:
    return {"__start__": "START", "__end__": "END"}.get(name, name)


def _report_structure(context: RunContext, t, graph, values: Inputs) -> None:
    """Platform: publish the compiled graph's real nodes and edges as a lesson.report table."""
    drawable = graph.get_graph()
    nodes = [name for name in drawable.nodes if name not in ("__start__", "__end__")]
    rows = [[_endpoint(edge.source), _endpoint(edge.target), t.edge_conditional if edge.conditional else t.edge_direct]
            for edge in drawable.edges]
    context.emit("lesson.report", {
        "title": t.structure_title, "summary": t.structure_summary,
        "metrics": [{"id": "nodes", "label": t.label_nodes, "value": len(nodes)},
                    {"id": "edges", "label": t.label_edges, "value": len(rows)},
                    {"id": "recursion_limit", "label": t.label_recursion_limit, "value": values.recursion_limit},
                    {"id": "max_repairs", "label": t.label_max_repairs, "value": values.max_repairs}],
        "table": {"columns": list(t.structure_columns), "rows": rows},
    })


def _report_run(context: RunContext, t, values: Inputs, trail: list[dict], final: dict | None) -> None:
    """Platform: assemble the path report; every check is computed from the trail and the final state."""
    path = [item["node"] for item in trail if "node" in item]
    routes = [item for item in trail if "route" in item]
    if final is None:
        terminal = {"id": "terminal", "label": t.check_terminal, "passed": False,
                    "detail": t.detail_stopped.format(limit=values.recursion_limit, steps=len(path), node=path[-1])}
    else:
        terminal = {"id": "terminal", "label": t.check_terminal, "passed": path[-1] in TERMINAL_NODES,
                    "detail": t.detail_terminal.format(node=path[-1], status=final["status"], reason=final["reason"])}
    checks = [terminal]
    if final is not None:
        tool_messages = sum(isinstance(message, ToolMessage) for message in final["messages"])
        checks.append({"id": "evidence-kept", "label": t.check_evidence_kept,
                       "passed": len(final["evidence"]) == tool_messages,
                       "detail": t.detail_evidence_kept.format(evidence=len(final["evidence"]),
                                                               tool_messages=tool_messages)})
    if final is not None and final["status"] == "completed":
        days = final["result"]["days"]
        checks.append({"id": "answer-days", "label": t.check_answer_days,
                       "passed": str(days) in final["messages"][-1].content,
                       "detail": t.detail_answer_days.format(days=days)})
    context.emit("lesson.report", {
        "title": t.report_title, "summary": t.report_summary, "checks": checks,
        "metrics": [
            {"id": "path", "label": t.label_path, "value": " → ".join(path)},
            {"id": "steps", "label": t.label_steps, "value": len(path)},
            {"id": "status", "label": t.label_status, "value": final["status"] if final else t.value_not_reached},
            {"id": "stop", "label": t.label_stop, "value": t.stop_end if final else t.stop_recursion_limit},
            {"id": "failed_checks", "label": t.label_failed_checks,
             "value": final["failed_checks"] if final else sum(r["read"].get("verdict") == "failed" for r in routes)},
            {"id": "model_nodes", "label": t.label_model_nodes, "value": sum(node in MODEL_NODES for node in path)},
            {"id": "note", "label": t.label_note, "value": context.question or t.value_empty},
        ],
        "table": {"columns": list(t.route_columns),
                  "rows": [[route["route"], json.dumps(route["read"], ensure_ascii=False), route["to"]]
                           for route in routes]},
    })
