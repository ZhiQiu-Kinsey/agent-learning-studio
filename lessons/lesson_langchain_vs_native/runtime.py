"""One task, two implementations: the platform's native tool loop and the same loop written with LangChain.

Both sides get the same question, system prompt, tool code, round limit and acceptance
rule; the run records both one after the other, so their requests sit side by side in the
timeline. The two local exercises call no model: they feed runner-built arguments and a
runner-built provider message through both paths to show what the framework does quietly.
Every text that reaches the model or an event comes from locales/.
"""
import copy
import json
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage

from course.execution import LessonInputs, RunContext
from course.frameworks import (
    RunContextCallbackHandler,
    RunContextChatModel,
    ai_message_from_response,
    execute_tool_calls,
    framework_versions,
    local_tracing_only,
    message_record,
    to_openai_messages,
    tools_as_callables,
)
from course.locales import texts_for as platform_texts
from course.runner import run_agent
from lessons.lesson_01_tool_selection import main as tool_selection
from lessons.lesson_01_tool_selection.tools import available_tools as sum_tools
from lessons.lesson_03_fail_safely import main as fail_safely
from lessons.lesson_langchain_vs_native.locales import Texts, texts_for
from lessons.lesson_langchain_vs_native.tools import add_numbers_tool, langchain_tools

# The exercise picks the task, so a local exercise can never ask for a model it does not have.
INPUT_MODEL = LessonInputs
TASKS = {"sum": "sum", "divide-zero": "divide"}
# Both tasks come from earlier lessons: their native setup is reused unchanged.
SETUPS = {"sum": tool_selection.setup, "divide": fail_safely.setup}
MAX_TOOL_ROUNDS = 3  # per side; lesson.json allows 2 x 3 model calls in one run

# Runner-built arguments for the local "arguments" exercise: case id -> raw JSON text.
ARGUMENT_CASES = (
    ("valid", '{"a": 19, "b": 23}'),
    ("string", '{"a": 19, "b": "23"}'),
    ("boolean", '{"a": true, "b": 23}'),
    ("extra", '{"a": 19, "b": 23, "c": 1}'),
)
# A runner-built provider message for the local "parsing" exercise. No model wrote it:
# truncated JSON, a JSON array, and a valid call that came without an id.
SAMPLE_CALLS = (
    {"id": "call_cut", "type": "function", "function": {"name": "add_numbers", "arguments": '{"a": 19, "b":'}},
    {"id": "call_list", "type": "function", "function": {"name": "add_numbers", "arguments": "[19, 23]"}},
    {"type": "function", "function": {"name": "add_numbers", "arguments": '{"a":19,"b":23}'}},
)
ABSENT = object()


@dataclass
class Side:
    """What one implementation did: its request bodies, tool results, answer and why it stopped."""
    name: str
    bodies: list = field(default_factory=list)
    rounds: list = field(default_factory=list)
    results: list = field(default_factory=list)  # (tool name, tool result)
    message_kinds: list = field(default_factory=list)
    valid_calls: int = 0
    invalid_calls: int = 0
    answer: str = ""
    stop: str = "rounds"


def run_native(context: RunContext, task: str) -> Side:
    """The native side: the platform loop course.runner.run_agent with the earlier lesson's setup."""
    setup = SETUPS[task](context.locale)
    side = Side("native")

    def complete(body, round_number):
        side.bodies.append(copy.deepcopy(body))
        side.rounds.append(round_number)
        return context.complete(body, round_number)

    def execute(call, tools):
        side.valid_calls += 1
        result = context.execute_proposal(call, tools)
        side.results.append((call["function"]["name"], result))
        return result

    try:
        side.answer = run_agent(context.question, setup.system_prompt, setup.tools, setup.available_tools,
                                MAX_TOOL_ROUNDS, complete=complete, execute=execute, locale=context.locale)
        side.stop = "answered"
    except RuntimeError as error:
        # Only the loop's own round limit is a result; any other error ends the run.
        if str(error) != platform_texts(context.locale).rounds_exceeded.format(rounds=MAX_TOOL_ROUNDS):
            raise
    side.message_kinds = [message["role"] for message in side.bodies[-1]["messages"]]
    return side


def run_langchain(context: RunContext, task: str, first_round: int) -> Side:
    """The LangChain side: framework messages, bind_tools and invoke; the loop itself is ours."""
    setup = SETUPS[task](context.locale)
    tools = langchain_tools(task, context.locale)
    # 1. Callbacks: the framework reports its own steps; the handler records them as events.
    handler = RunContextCallbackHandler(context, include_chains=False)
    for item in tools:
        item.callbacks = [handler]
    model = RunContextChatModel(context=context, callbacks=[handler]).bind_tools(tools)
    allowlist = tools_as_callables(tools)
    # 2. Framework message objects instead of role dicts; same system prompt, same question.
    history = [SystemMessage(setup.system_prompt), HumanMessage(context.question)]
    side = Side("langchain")
    with local_tracing_only():
        # 3. langchain-core has no agent loop: the round limit and stop rule are written here.
        for step in range(MAX_TOOL_ROUNDS):
            side.bodies.append(request_body(model, history))
            side.rounds.append(first_round + step)
            reply = model.invoke(history, round_number=first_round + step)
            history.append(reply)
            side.valid_calls += len(reply.tool_calls)
            side.invalid_calls += len(reply.invalid_tool_calls)
            if not reply.tool_calls and not reply.invalid_tool_calls:
                side.answer, side.stop = reply.content if isinstance(reply.content, str) else "", "answered"
                break
            # 4. Every call, valid or not, runs through RunContext and comes back as a ToolMessage.
            for message in execute_tool_calls(context, reply, allowlist):
                history.append(message)
                side.results.append((message.name, json.loads(message.content)))
    side.message_kinds = [message.type for message in history]
    return side


def request_body(bound_model, history) -> dict:
    """The body the adapter sends for this history: converted messages plus the bound options (tools)."""
    return {"messages": to_openai_messages(history), **bound_model.kwargs}


def number_text(value) -> str:
    """42.0 and 42 both read as "42" in an answer."""
    return f"{value:g}" if isinstance(value, float) else str(value)


def accept(task: str, side: Side) -> bool:
    """The acceptance rule both sides share; it reads tool results and request bodies, not the model's wording."""
    if task == "sum":
        sums = [result["result"] for name, result in side.results if name == "add_numbers" and result.get("ok")
                and isinstance(result.get("result"), (int, float))]
        return any(number_text(value) in side.answer for value in sums)
    divisions = [result for name, result in side.results if name == "divide_numbers"]
    fed_back = any(message.get("role") == "tool" and '"ok": false' in (message.get("content") or "")
                   for body in side.bodies for message in body["messages"])
    return bool(divisions) and not any(result.get("ok") for result in divisions) and fed_back


def flatten(value, path=""):
    """JSON paths to leaf values; an empty object or list is a leaf of its own."""
    if isinstance(value, dict) and value:
        for key, item in value.items():
            yield from flatten(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list) and value:
        for index, item in enumerate(value):
            yield from flatten(item, f"{path}[{index}]")
    else:
        yield path, value


def request_diff(native: dict, framework: dict) -> list[tuple[str, object, object]]:
    """Fields whose values differ between two request bodies, in the order they first appear."""
    left, right = dict(flatten(native)), dict(flatten(framework))
    paths = list(left) + [path for path in right if path not in left]
    return [(path, left.get(path, ABSENT), right.get(path, ABSENT)) for path in paths
            if left.get(path, ABSENT) != right.get(path, ABSENT)]


def run_task(context: RunContext, t: Texts, task: str) -> str:
    native = run_native(context, task)
    framework = run_langchain(context, task, first_round=native.rounds[-1] + 1)
    _task_reports(context, t, task, native, framework)
    return t.answer_task.format(native=native.answer or t.stop_reasons[native.stop],
                                langchain=framework.answer or t.stop_reasons[framework.stop])


def run_arguments(context: RunContext, t: Texts) -> str:
    """The same raw arguments go to the native tool, the default @tool and the strict schema; no model."""
    targets = (("native", sum_tools(context.locale)),
               ("default", tools_as_callables([add_numbers_tool(context.locale)])),
               ("strict", tools_as_callables([add_numbers_tool(context.locale, strict=True)])))
    rows = []
    for number, (case, raw) in enumerate(ARGUMENT_CASES, start=1):
        # One round per case; the call id names the side, so the timeline shows which path ran.
        outcomes = {side: context.submit_call("add_numbers", raw, allowlist, number, call_id=f"{side}-{case}")
                    for side, allowlist in targets}
        rows.append((case, raw, outcomes))
    return _arguments_report(context, t, rows)


def run_parsing(context: RunContext, t: Texts) -> str:
    """Parse a runner-built provider message the way the framework adapter does, then answer every call; no model."""
    sample = {"id": "course_sample", "model": "course-sample", "choices": [{"index": 0, "finish_reason": "tool_calls",
              "message": {"role": "assistant", "content": None, "tool_calls": copy.deepcopy(list(SAMPLE_CALLS))}}]}
    context.emit("lesson.sample_response", {"origin": "course_program", "note": t.sample_note, "body": sample}, 1)
    # 1. Parse: valid calls -> tool_calls (an id is filled in when missing), the rest -> invalid_tool_calls.
    message, synthesized = ai_message_from_response(sample, call_index=1, locale=context.locale)
    # 2. Convert back: the assistant message the framework would put into the next request.
    next_message = to_openai_messages([message])[0]
    context.emit("lesson.parse_result", {
        "layer": "framework_parse", "message": message_record(message), "synthesized_call_ids": synthesized,
        "native_next_message": sample["choices"][0]["message"], "framework_next_message": next_message}, 1)
    # 3. Answer each call in the framework's order, with the framework's ids, marked as runner-initiated.
    allowlist = tools_as_callables([add_numbers_tool(context.locale)])
    results = [(call, context.submit_call(call["function"]["name"], call["function"]["arguments"], allowlist, 1,
                                          call_id=call["id"]))
               for call in next_message["tool_calls"]]
    return _parsing_report(context, t, message, synthesized, next_message, results)


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    context.check_cancelled()
    if context.exercise_id in TASKS:
        return run_task(context, t, TASKS[context.exercise_id])
    if context.exercise_id == "arguments":
        return run_arguments(context, t)
    if context.exercise_id == "parsing":
        return run_parsing(context, t)
    raise ValueError(f"langchain-vs-native has no exercise {context.exercise_id!r}")


# ---------------------------------------------------------------------------
# Reports (lesson.report): assembled from the sides above, nothing estimated
# ---------------------------------------------------------------------------

def _cell(value, t: Texts, limit: int = 90) -> str:
    if value is ABSENT:
        return t.absent
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _outcome(result: dict, t: Texts) -> str:
    if result.get("ok"):
        return t.outcome_ok.format(result=_cell(result.get("result"), t, 40))
    first = " / ".join(line.strip() for line in str(result.get("error", "")).splitlines()[:3])
    return t.outcome_error.format(error_type=result.get("error_type"), error=_cell(first, t, 110))


def _described(tools: list) -> int:
    return sum("description" in schema for item in tools
               for schema in item["function"].get("parameters", {}).get("properties", {}).values())


def _task_reports(context, t, task, native: Side, framework: Side):
    accepted = {side.name: accept(task, side) for side in (native, framework)}
    errors = {side.name: sum(not result.get("ok") for _, result in side.results) for side in (native, framework)}
    stops = {side.name: t.stop_reasons[side.stop] for side in (native, framework)}
    versions = framework_versions()
    rows = [
        [t.row_messages, t.cell_native_messages.format(kinds=", ".join(native.message_kinds)),
         t.cell_langchain_messages.format(kinds=", ".join(framework.message_kinds))],
        [t.row_tools, t.cell_native_tools.format(count=_described(native.bodies[0]["tools"])),
         t.cell_langchain_tools.format(count=_described(framework.bodies[0]["tools"]))],
        [t.row_parsing, t.cell_native_parsing.format(count=native.valid_calls),
         t.cell_langchain_parsing.format(valid=framework.valid_calls, invalid=framework.invalid_calls)],
        [t.row_feedback, t.cell_native_feedback.format(count=len(native.results)),
         t.cell_langchain_feedback.format(count=len(framework.results))],
        [t.row_stop, t.cell_stop.format(limit=MAX_TOOL_ROUNDS, stop=stops["native"]),
         t.cell_stop.format(limit=MAX_TOOL_ROUNDS, stop=stops["langchain"])],
        [t.row_errors, t.cell_errors.format(count=errors["native"]), t.cell_errors.format(count=errors["langchain"])],
        [t.row_acceptance, t.verdicts[accepted["native"]], t.verdicts[accepted["langchain"]]],
    ]
    rule = t.acceptance_rules[task]
    context.emit("lesson.report", {
        "title": t.report_task_title[task], "summary": t.report_task_summary,
        "checks": [{"id": "native_accepted", "label": t.check_native_accepted, "passed": accepted["native"],
                    "detail": rule},
                   {"id": "langchain_accepted", "label": t.check_langchain_accepted, "passed": accepted["langchain"],
                    "detail": rule},
                   {"id": "same_tools", "label": t.check_same_tools,
                    "passed": [item["function"]["name"] for item in native.bodies[0]["tools"]]
                    == [item["function"]["name"] for item in framework.bodies[0]["tools"]],
                    "detail": t.check_same_tools_detail}],
        "metrics": [{"id": "native_calls", "label": t.label_native_calls, "value": len(native.bodies)},
                    {"id": "langchain_calls", "label": t.label_langchain_calls, "value": len(framework.bodies)},
                    {"id": "native_rounds", "label": t.label_native_rounds, "value": _round_span(native.rounds)},
                    {"id": "langchain_rounds", "label": t.label_langchain_rounds,
                     "value": _round_span(framework.rounds)},
                    {"id": "framework_version", "label": t.label_framework_version,
                     "value": versions["langchain-core"] or t.absent}],
        "table": {"columns": list(t.columns_responsibility), "rows": rows},
    })
    diff_rows, counts = [], []
    for index, (left, right) in enumerate(zip(native.bodies, framework.bodies), start=1):
        differences = request_diff(left, right)
        counts.append({"id": f"diff_{index}", "label": t.label_diff_count.format(n=index), "value": len(differences)})
        # Tool definitions are the same in every request of a side: list them once, under the first pair.
        diff_rows += [[t.request_pair.format(n=index), path, _cell(a, t), _cell(b, t)] for path, a, b in differences
                      if index == 1 or path.startswith("messages")]
    context.emit("lesson.report", {
        "title": t.report_diff_title, "summary": t.report_diff_summary,
        "metrics": counts, "table": {"columns": list(t.columns_diff), "rows": diff_rows[:40]},
    })


def _round_span(rounds: list[int]) -> str:
    return f"{rounds[0]}–{rounds[-1]}" if len(rounds) > 1 else str(rounds[0])


def _arguments_report(context, t, rows) -> str:
    agree = {side: [case for case, _, outcomes in rows if outcomes[side]["ok"] == outcomes["native"]["ok"]]
             for side in ("default", "strict")}
    masked = [case for case, _, outcomes in rows if outcomes["default"]["ok"] and not outcomes["native"]["ok"]]
    context.emit("lesson.report", {
        "title": t.report_arguments_title, "summary": t.report_arguments_summary,
        "checks": [{"id": "default_agrees", "label": t.check_default_agrees, "passed": len(agree["default"]) == len(rows),
                    "detail": t.agree_detail.format(ok=len(agree["default"]), total=len(rows))},
                   {"id": "strict_agrees", "label": t.check_strict_agrees, "passed": len(agree["strict"]) == len(rows),
                    "detail": t.agree_detail.format(ok=len(agree["strict"]), total=len(rows))}],
        "metrics": [{"id": "masked", "label": t.label_masked, "value": len(masked)},
                    {"id": "masked_cases", "label": t.label_masked_cases,
                     "value": t.list_separator.join(t.argument_cases[case] for case in masked) or t.none}],
        "table": {"columns": list(t.columns_arguments),
                  "rows": [[t.argument_cases[case], raw, *(_outcome(outcomes[side], t)
                                                           for side in ("native", "default", "strict"))]
                           for case, raw, outcomes in rows]},
    })
    return t.answer_arguments.format(masked=len(masked), total=len(rows), strict=len(agree["strict"]))


def _parsing_report(context, t, message, synthesized, next_message, results) -> str:
    invalid_ids = [call.get("id") for call in message.invalid_tool_calls]
    framework_order = [call["id"] for call in next_message["tool_calls"]]
    by_id = {call["id"]: (call, result) for call, result in results}
    table = []
    for index, raw in enumerate(SAMPLE_CALLS):
        # The id the framework used: the provider's, or the one the adapter filled in for the call without one.
        used = raw.get("id") or synthesized[0]
        call, result = by_id[used]
        place = t.place_invalid if used in invalid_ids else t.place_valid
        table.append([index + 1, raw.get("id") or t.absent, raw["function"]["arguments"], place, used,
                      call["function"]["arguments"], _outcome(result, t)])
    provider_order = [raw.get("id") or synthesized[0] for raw in SAMPLE_CALLS]
    context.emit("lesson.report", {
        "title": t.report_parsing_title, "summary": t.report_parsing_summary,
        "checks": [{"id": "all_answered", "label": t.check_all_answered,
                    "passed": len(results) == len(SAMPLE_CALLS), "detail": t.answered_detail.format(
                        answered=len(results), total=len(SAMPLE_CALLS))},
                   {"id": "same_order", "label": t.check_same_order, "passed": framework_order == provider_order,
                    "detail": t.order_detail.format(provider=", ".join(provider_order),
                                                    framework=", ".join(framework_order))}],
        "metrics": [{"id": "valid", "label": t.label_valid_calls, "value": len(message.tool_calls)},
                    {"id": "invalid", "label": t.label_invalid_calls, "value": len(message.invalid_tool_calls)},
                    {"id": "synthesized", "label": t.label_synthesized,
                     "value": t.list_separator.join(synthesized) or t.none}],
        "table": {"columns": list(t.columns_parsing), "rows": table},
    })
    return t.answer_parsing.format(valid=len(message.tool_calls), invalid=len(message.invalid_tool_calls),
                                   synthesized=len(synthesized))
