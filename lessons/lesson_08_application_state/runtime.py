"""A typed state machine that calls no model: messages and application state are kept apart, and program events decide
how far the task got."""
from dataclasses import InitVar, asdict, dataclass, field
from typing import Literal
from uuid import uuid4

from pydantic import Field

from course.execution import LessonInputs, RunContext
from lessons.lesson_08_application_state.locales import texts_for


# The two local materials are in the catalog (t.source_excerpts): evidence can only be read from there,
# and the keys are lesson slugs. "missing" has no entry on purpose.
class Inputs(LessonInputs):
    # No default: the preset in lesson.json supplies the goal in the run's language.
    goal: str = Field(min_length=4, max_length=160)
    source_key: Literal["messages-context", "application-state", "missing"] = "messages-context"
    step_budget: int = Field(default=3, ge=1, le=5)


INPUT_MODEL = Inputs
# Transition table: the next states each state may enter; any transition not listed is rejected.
TRANSITIONS = {
    "ready": {"running", "cancelled"},
    "running": {"waiting", "completed", "failed", "cancelled"},
    "waiting": {"running", "failed", "cancelled"},
    "completed": set(), "failed": set(), "cancelled": set(),
}
TERMINAL = {"completed", "failed", "cancelled"}


@dataclass
class TaskState:
    """The application state of one run. Every run creates its own, kept apart from the messages sent to the model."""
    run_id: str
    goal: str
    # The run's language only picks the wording of errors; it is not part of the state snapshot.
    locale: InitVar[str]
    status: str = "ready"
    evidence: list[dict] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    used_steps: int = 0
    result: str | None = None
    terminal_reason: str | None = None

    def __post_init__(self, locale: str) -> None:
        self._t = texts_for(locale)

    def consume_step(self, label: str, budget: int) -> bool:
        """Charge the budget before a step; when it is used up return False and let the caller decide how to finish."""
        if self.status != "running":
            raise ValueError(self._t.not_running)
        if self.used_steps >= budget:
            return False
        self.used_steps += 1
        self.steps.append(label)
        return True

    def transition(self, target: str, reason: str | None = None) -> None:
        """Every state change goes through here: the transition table first, then the terminal rules, only then status."""
        if target not in TRANSITIONS[self.status]:
            raise ValueError(self._t.illegal_transition.format(current=self.status, target=target))
        if target in TERMINAL and not reason:
            raise ValueError(self._t.reason_required)
        # The condition for completion lives in the state machine, so no caller can skip it.
        if target == "completed" and (not self.evidence or not self.result):
            raise ValueError(self._t.completion_unproven)
        self.status = target
        if target in TERMINAL:
            self.terminal_reason = reason


def run(context: RunContext) -> str:
    t = texts_for(context.locale)
    values = Inputs.model_validate(context.inputs)
    # 1. Every run creates its own state and run_id; messages holds only the user's goal and never changes afterwards.
    state = TaskState(run_id=uuid4().hex, goal=values.goal, locale=context.locale)
    messages = [{"role": "user", "content": values.goal}]
    _publish(context, state, t.action_created)
    # 2. Enter running and take the first step: read the material index.
    context.check_cancelled()
    state.transition("running")
    state.consume_step(t.step_read_index, values.step_budget)
    _publish(context, state, t.action_started)
    source = t.source_excerpts.get(values.source_key)
    if source is None:
        # 3a. No material: enter waiting first, then finish as failed once it is clear nothing will arrive.
        state.transition("waiting")
        _publish(context, state, t.action_waiting)
        state.transition("failed", t.reason_missing)
    elif not state.consume_step(t.step_check_source, values.step_budget):
        state.transition("failed", t.reason_budget_check)
    else:
        # 3b. The evidence goes into the state, not into messages.
        state.evidence.append({"source": values.source_key, "excerpt": source})
        _publish(context, state, t.action_evidence)
        context.check_cancelled()
        # 4. The third step also charges the budget first; if it is short, the evidence stays and the state turns failed.
        if not state.consume_step(t.step_summarize, values.step_budget):
            state.transition("failed", t.reason_budget_summary)
        else:
            state.result = t.result.format(source_key=values.source_key, excerpt=source)
            state.transition("completed", t.reason_completed)
    # 5. Whatever the outcome, publish the terminal snapshot and the report.
    _publish(context, state, t.action_terminal)
    _report(context, t, state, messages, values)
    if state.status == "completed":
        return t.answer_completed.format(result=state.result, goal=state.goal)
    return t.answer_failed.format(reason=state.terminal_reason)


def _publish(context: RunContext, state: TaskState, action: str) -> None:
    """Publish a complete state snapshot (lesson.state), so the replay shows the state at every step."""
    context.emit("lesson.state", {"action": action, "state": asdict(state)})


def _report(context: RunContext, t, state: TaskState, messages: list[dict], values: Inputs) -> None:
    """Platform: assemble and publish lesson.report; each check is computed from the state, not from message content."""
    # Without completed, "success has evidence and a result" has nothing to check: give the reason, do not mark it passed.
    success = ({"label": t.check_success, "passed": bool(state.evidence and state.result),
                "detail": t.check_success_detail} if state.status == "completed" else
               {"label": t.check_success, "detail": t.check_success_not_applicable})
    context.emit("lesson.report", {
        "title": t.report_title,
        "summary": t.report_summary,
        "checks": [
            {"label": t.check_reason, "passed": bool(state.terminal_reason), "detail": state.terminal_reason or ""},
            success,
            {"label": t.check_separate, "passed": len(messages) == 1, "detail": t.check_separate_detail},
        ],
        "metrics": [{"label": t.label_status, "value": state.status}, {"label": t.label_evidence, "value": len(state.evidence)},
                    {"label": t.label_messages, "value": len(messages)}, {"label": t.label_step_budget, "value": values.step_budget},
                    {"label": t.label_used_steps, "value": state.used_steps},
                    {"label": t.label_note, "value": context.question or t.note_empty}],
        "table": {"columns": list(t.columns), "rows": [["run_id", state.run_id], ["goal", state.goal],
                                                      ["status", state.status],
                                                      ["terminal_reason", state.terminal_reason or ""]]},
    })
