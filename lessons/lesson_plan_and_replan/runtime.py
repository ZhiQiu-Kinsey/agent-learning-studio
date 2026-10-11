"""Plan first, then execute: a static plan, replanning after a failure and a ReAct baseline write the same weekly study report.

The primary source of fetch_quiz_scores(source="primary") always fails in this lesson: a
controlled fault written into the runner, not a network failure. The backup source works.
All three strategies are judged by the same acceptance check. Task decomposition and
"replan iteratively when results affect later steps" follow Microsoft AI Agents for Beginners
07 (MIT); the planner prompt, plan format, executor and experiments are written for this project.
"""
import json
from functools import partial
from typing import Literal

from course.execution import LessonInputs, RunContext
from lessons.lesson_plan_and_replan.locales import Texts, texts_for


class Inputs(LessonInputs):
    strategy: Literal["static", "replan", "react"] = "replan"


INPUT_MODEL = Inputs
LEARNER = "lin"
# Lessons are recorded by slug: display numbers change when the curriculum grows, slugs do not.
PROGRESS = {"learner": LEARNER, "completed": ["messages-context", "application-state", "context-budget"],
            "in_progress": "persistent-memory"}
SCORES = {"learner": LEARNER, "scores": {"messages-context": 82, "application-state": 67, "context-budget": 91},
          "source": "backup"}
MAX_REVISIONS = 2
# The allowlist a plan may use; the names are code, the same in every language.
TOOL_NAMES = ("fetch_progress", "fetch_quiz_scores")


def fetch_progress(t, /, learner: str) -> dict:
    # t (the run's error messages) is positional-only: the model's arguments arrive by name and cannot replace it.
    if learner != LEARNER:
        raise ValueError(t.unknown_learner.format(learner=learner))
    return PROGRESS


def fetch_quiz_scores(t, /, learner: str, source: str = "primary") -> dict:
    if learner != LEARNER:
        raise ValueError(t.unknown_learner.format(learner=learner))
    # Controlled fault: the primary source fails every time. The message says the backup works, so a revision has a lead.
    if source == "primary":
        raise ValueError(t.primary_unavailable)
    if source != "backup":
        raise ValueError(t.bad_source)
    return SCORES


def parse_plan(content: str, t: Texts, used_ids=frozenset()) -> dict:
    """Read the planner's JSON plan; text or a code fence around the JSON is allowed, nothing else is repaired.

    used_ids are the step ids of every earlier plan version: a revised step needs a new id,
    or the diff would list one id as both removed and added.
    """
    start = content.find("{")
    if start < 0:
        raise ValueError(t.plan_no_json)
    plan, _ = json.JSONDecoder().raw_decode(content[start:])
    steps = plan.get("steps") if isinstance(plan, dict) else None
    if not isinstance(steps, list) or not steps:
        raise ValueError(t.plan_no_steps)
    seen = set()
    for item in steps:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in seen:
            raise ValueError(t.plan_step_id)
        if item["id"] in used_ids:
            raise ValueError(t.plan_reused_id.format(step_id=item["id"]))
        if item.get("tool") not in TOOL_NAMES:
            raise ValueError(t.plan_unknown_tool.format(step_id=item["id"], tool=item.get("tool")))
        if not isinstance(item.get("arguments"), dict):
            raise ValueError(t.plan_arguments.format(step_id=item["id"]))
        seen.add(item["id"])
    return {"reason": str(plan.get("reason") or ""), "steps": steps}


def available_tools(locale: str) -> dict:
    """The executable tools, bound to the error messages of the run's language."""
    t = texts_for(locale)
    return {"fetch_progress": partial(fetch_progress, t), "fetch_quiz_scores": partial(fetch_quiz_scores, t)}


def tool_definitions(locale: str) -> list[dict]:
    """The tools the ReAct baseline sends (the planner gets none). Names are code; descriptions follow the locale."""
    t = texts_for(locale)
    return [
        {"type": "function", "function": {"name": "fetch_progress", "description": t.fetch_progress_description,
         "parameters": {"type": "object", "properties": {"learner": {"type": "string"}}, "required": ["learner"],
                        "additionalProperties": False}}},
        {"type": "function", "function": {"name": "fetch_quiz_scores",
         "description": t.fetch_quiz_scores_description,
         "parameters": {"type": "object", "properties": {"learner": {"type": "string"},
                                                         "source": {"type": "string", "enum": ["primary", "backup"]}},
                        "required": ["learner", "source"], "additionalProperties": False}}},
    ]


def _text(response: dict) -> str:
    content = response["choices"][0].get("message", {}).get("content")
    return content if isinstance(content, str) else ""


def _step_view(step: dict) -> dict:
    arguments = ", ".join(f"{key}={value}" for key, value in step["arguments"].items())
    return {"id": step["id"], "content": f"{step['tool']}({arguments})", "purpose": step.get("purpose", ""),
            "status": step.get("status", "pending")}


def verify(results: dict[str, dict], report: str, t: Texts) -> list[dict]:
    """Judge only by this run's real tool results and the final report, never by how good the plan looks."""
    progress = results.get("fetch_progress")
    scores = results.get("fetch_quiz_scores")
    numbers = [str(value) for value in (scores or {}).get("scores", {}).values()]
    return [
        {"label": t.check_progress, "passed": progress is not None,
         "detail": t.detail_progress_ok if progress else t.detail_progress_missing},
        {"label": t.check_scores, "passed": scores is not None,
         "detail": t.detail_scores_source.format(source=scores["source"]) if scores else t.detail_scores_missing},
        {"label": t.check_report_numbers, "passed": bool(numbers) and all(n in report for n in numbers),
         "detail": t.detail_numbers.format(numbers=t.list_separator.join(numbers))
         if numbers and all(n in report for n in numbers) else t.detail_numbers_missing},
    ]


class Planner:
    """The planner only writes plans and executes nothing. Its history keeps every plan version and every failure, so a revision sees the whole story."""

    def __init__(self, context: RunContext, t: Texts):
        self.context, self.t = context, t
        self.messages = [{"role": "system", "content": t.planner_system},
                         {"role": "user", "content": t.task.format(learner=LEARNER)}]
        self.rounds = 0
        self.used_ids: set[str] = set()

    def ask(self) -> dict | None:
        """Request one plan version; a malformed plan is recorded as is and gives None, never completed for the planner."""
        self.rounds += 1
        content = _text(self.context.complete({"messages": self.messages, "temperature": 0}, self.rounds))
        self.messages.append({"role": "assistant", "content": content})
        try:
            plan = parse_plan(content, self.t, self.used_ids)
        except ValueError as error:
            self.context.emit("lesson.plan_error", {"error": str(error), "raw": content}, self.rounds)
            return None
        self.used_ids.update(step["id"] for step in plan["steps"])
        return plan

    def revise(self, steps: list[dict], failed: dict, error) -> dict | None:
        """Give the planner the step statuses and the real error of the failed step; it lists only the steps still to run."""
        status = json.dumps([{"id": s["id"], "tool": s["tool"], "status": s["status"]} for s in steps], ensure_ascii=False)
        self.messages.append({"role": "user", "content": self.t.revise_request.format(
            status=status, step_id=failed["id"], error=error)})
        return self.ask()


class Executor:
    """The executor only calls tools as planned and decides nothing; it keeps the real result of every step."""

    def __init__(self, context: RunContext):
        self.context = context
        self.tools = available_tools(context.locale)
        self.results: dict[str, dict] = {}
        self.calls = 0

    def run_step(self, step: dict, round_number: int) -> dict:
        self.calls += 1
        result = self.context.call_tool(step["tool"], step["arguments"], self.tools,
                                        round_number=round_number, call_id=f"plan_{step['id']}_{self.calls}")
        # Keep only successful results: the report may use only data that was really fetched.
        if result.get("ok"):
            self.results[step["tool"]] = result["result"]
        return result


def plan_and_execute(context: RunContext, revise: bool, t: Texts) -> tuple[str, dict, list[list]]:
    """Plan, then execute; with revise=True a failed step goes back to the planner with its real error, at most MAX_REVISIONS times."""
    planner, executor = Planner(context, t), Executor(context)
    # 1. Plan: execution starts only with a validated plan; a malformed plan ends the run here.
    plan = planner.ask()
    if plan is None:
        return "", _outcome(executor, planner.rounds, 0, 0), [[0, t.row_plan_failed, t.row_plan_not_json, 0]]
    steps, version, revisions = [{**item, "status": "pending"} for item in plan["steps"]], 1, 0
    _publish(context, version, steps, planner.rounds, reason=plan["reason"], event="created")
    history = [[version, t.row_created, plan["reason"] or "—", len(steps)]]
    index = 0
    while index < len(steps):
        # 2. Execute: the executor calls the tools as planned; only the real tool result sets a step's status.
        step = steps[index]
        step["status"] = "in_progress"
        result = executor.run_step(step, planner.rounds)
        step["status"] = "done" if result.get("ok") else "failed"
        _publish(context, version, steps, planner.rounds)
        index += 1
        # 3. On success, with a static plan, or with no revisions left, go on to the next step.
        if result.get("ok") or not revise or revisions >= MAX_REVISIONS:
            continue
        # 4. Revise: hand the real failure to the planner and replace only the steps not yet run; executed steps stay.
        revisions += 1
        revised = planner.revise(steps, step, result.get("error"))
        if revised is None:
            break
        old_pending = [s["id"] for s in steps[index:]]
        new_steps = [{**item, "status": "pending"} for item in revised["steps"]]
        steps, version = steps[:index] + new_steps, version + 1
        diff = {"removed": old_pending, "added": [s["id"] for s in new_steps], "failed_step": step["id"]}
        _publish(context, version, steps, planner.rounds, reason=revised["reason"], diff=diff, event="revised")
        history.append([version, t.row_revised, revised["reason"] or "—", len(steps)])
    # 5. Write the report: the writer gets only successful tool results and says plainly what is missing.
    report = write_report(context, executor.results, planner.rounds + 1, t)
    return report, _outcome(executor, planner.rounds + 1, version, revisions), history


def write_report(context: RunContext, results: dict[str, dict], round_number: int, t: Texts) -> str:
    data = {tool: value for tool, value in results.items()}
    user = t.writer_input.format(task=t.task.format(learner=LEARNER), results=json.dumps(data, ensure_ascii=False))
    response = context.complete({"messages": [{"role": "system", "content": t.writer_system},
                                              {"role": "user", "content": user}],
                                 "temperature": 0}, round_number)
    return _text(response)


def _outcome(executor: Executor, model_calls: int, versions: int, revisions: int) -> dict:
    return {"results": executor.results,
            "stats": {"model_calls": model_calls, "tool_calls": executor.calls, "plan_versions": versions,
                      "revisions": revisions}}


def _publish(context: RunContext, version: int, steps: list[dict], round_number: int, *, reason: str = "",
             diff: dict | None = None, event: str = "progress"):
    """Publish one plan version (lesson.plan): every step with its status; a revision adds the reason and the diff."""
    context.emit("lesson.plan", {"version": version, "event": event, "reason": reason, "diff": diff or {},
                                 "steps": [_step_view(step) for step in steps]}, round_number)


def react(context: RunContext, t: Texts) -> tuple[str, dict, list[list]]:
    """ReAct baseline: no plan; the model decides each next step after seeing the tool result."""
    tools = available_tools(context.locale)
    messages = [{"role": "system", "content": t.react_system}, {"role": "user", "content": t.task.format(learner=LEARNER)}]
    results, calls, history = {}, 0, []
    for round_number in range(1, context.max_model_calls + 1):
        response = context.complete({"messages": messages, "tools": tool_definitions(context.locale),
                                     "tool_choice": "auto", "temperature": 0}, round_number)
        message = response["choices"][0].get("message", {})
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            stats = {"model_calls": round_number, "tool_calls": calls, "plan_versions": 0, "revisions": 0}
            return message.get("content") or "", {"results": results, "stats": stats}, history
        messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls})
        for call in tool_calls:
            calls += 1
            result = context.execute_proposal(call, tools)
            name = call.get("function", {}).get("name")
            if result.get("ok"):
                results[name] = result["result"]
            history.append([round_number, name,
                            t.row_success if result.get("ok") else t.row_failure.format(error=result.get("error")), "—"])
            messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": json.dumps(result, ensure_ascii=False)})
    stats = {"model_calls": context.max_model_calls, "tool_calls": calls, "plan_versions": 0, "revisions": 0}
    return "", {"results": results, "stats": stats}, history


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    strategy = Inputs.model_validate(context.inputs).strategy
    context.check_cancelled()
    if strategy == "react":
        report, outcome, history = react(context, t)
        columns = list(t.react_columns)
    else:
        report, outcome, history = plan_and_execute(context, strategy == "replan", t)
        columns = list(t.plan_columns)
    checks = verify(outcome["results"], report, t)
    return _report(context, strategy, checks, outcome, history, columns, report)


def _report(context: RunContext, strategy: str, checks: list[dict], outcome: dict, history: list[list],
            columns: list[str], report: str) -> str:
    """Publish the lab report (lesson.report) and return the final answer: the verdict first, then the report text."""
    t = texts_for(context.locale)
    accepted = all(check["passed"] for check in checks)
    labels = {"model_calls": t.label_model_calls, "tool_calls": t.label_tool_calls,
              "plan_versions": t.label_plan_versions, "revisions": t.label_revisions}
    context.emit("lesson.report", {
        "title": t.strategy_titles[strategy],
        "summary": t.report_summary,
        "checks": checks,
        "metrics": [{"label": t.label_verdict, "value": t.value_passed if accepted else t.value_failed},
                    *({"id": key, "label": labels[key], "value": value} for key, value in outcome["stats"].items()),
                    {"label": t.label_note, "value": context.question or t.value_empty}],
        "table": {"columns": columns, "rows": history},
    })
    return t.answer.format(verdict=t.verdict_passed if accepted else t.verdict_failed, report=report or t.no_report)
