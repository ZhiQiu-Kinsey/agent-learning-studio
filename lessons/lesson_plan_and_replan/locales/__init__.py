"""Runtime text of plan-and-replan: the task, the three system prompts, tool descriptions and errors, plan errors, the report.

zh_CN.py and en.py each fill every field; runtime.py reads them with texts_for(context.locale).
Tool names, parameter names, sources (primary / backup), step ids and plan JSON keys are code
and stay the same in every language.
"""
from dataclasses import dataclass

from course.i18n import catalog


@dataclass(frozen=True)
class Texts:
    # The fixed task and the three system prompts.
    task: str  # {learner}
    planner_system: str
    writer_system: str
    react_system: str
    # The writer's user message: the task followed by the successful tool results.
    writer_input: str  # {task} {results}
    # The status report the planner gets after a failed step.
    revise_request: str  # {status} {step_id} {error}
    # Tool descriptions for the ReAct baseline (tool_definitions).
    fetch_progress_description: str
    fetch_quiz_scores_description: str
    # Tool errors; they reach the model as structured errors.
    unknown_learner: str  # {learner}
    primary_unavailable: str
    bad_source: str
    # Plan errors (parse_plan), recorded in lesson.plan_error.
    plan_no_json: str
    plan_no_steps: str
    plan_step_id: str
    plan_reused_id: str  # {step_id}
    plan_unknown_tool: str  # {step_id} {tool}
    plan_arguments: str  # {step_id}
    # Acceptance checks (verify).
    check_progress: str
    detail_progress_ok: str
    detail_progress_missing: str
    check_scores: str
    detail_scores_source: str  # {source}
    detail_scores_missing: str
    check_report_numbers: str
    detail_numbers: str  # {numbers}
    detail_numbers_missing: str
    list_separator: str
    # Table rows and columns.
    row_plan_failed: str
    row_plan_not_json: str
    row_created: str
    row_revised: str
    row_success: str
    row_failure: str  # {error}
    plan_columns: tuple[str, ...]
    react_columns: tuple[str, ...]
    # Lab report.
    strategy_titles: dict[str, str]
    report_summary: str
    label_verdict: str
    label_model_calls: str
    label_tool_calls: str
    label_plan_versions: str
    label_revisions: str
    label_note: str
    value_passed: str
    value_failed: str
    value_empty_note: str
    # The final answer written by the runner.
    verdict_passed: str
    verdict_failed: str
    no_report: str
    answer: str  # {verdict} {report}


texts_for = catalog(__name__, Texts)
