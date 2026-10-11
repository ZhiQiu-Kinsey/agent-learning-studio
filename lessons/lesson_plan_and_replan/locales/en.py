"""plan-and-replan runtime text: English."""
from lessons.lesson_plan_and_replan.locales import Texts

TEXTS = Texts(
    task="Write a weekly study report for learner {learner}: list the completed lessons and the quiz score of each lesson.",
    planner_system="""You are the planner. You only write plans; you do not execute tools. Available tools:
- fetch_progress(learner): look up the completed lessons and the lesson in progress.
- fetch_quiz_scores(learner, source): look up the quiz score of each lesson; source is primary (the main data source) or backup (the spare, with the same data).

Output exactly one JSON object and no other text:
{"reason": "why you plan it this way (when revising, the reason for the revision)", "steps": [{"id": "s1", "tool": "tool name", "arguments": {...}, "purpose": "what this step should get"}]}
When revising the plan, list only the steps that still need to run, and do not reuse the id of any existing step.""",
    writer_system=("You are a teaching assistant. From the tool results given, write a weekly study report of at most "
                   "three sentences that states the score of each lesson. If data is missing, say it is missing; do not "
                   "make it up."),
    react_system=("You are a teaching assistant. Call a tool when you need data; do not guess. Once you have the data, "
                  "write a weekly study report of at most three sentences that states the score of each lesson."),
    writer_input="{task}\nTool results: {results}",
    revise_request=("Execution status: {status}\nStep {step_id} failed: {error}\n"
                    "Revise the plan: list only the steps that still need to run, and give the reason for the revision in reason."),
    fetch_progress_description="Look up the learner's completed lessons and the lesson in progress.",
    fetch_quiz_scores_description=("Look up the learner's quiz score for each lesson. source is primary (the main data "
                                   "source) or backup (the spare, with the same data)."),
    unknown_learner="There is no record for learner {learner}.",
    primary_unavailable=("The primary score source is unavailable for now (controlled fault: it always fails in this "
                         "lesson). You can use source=backup instead."),
    bad_source="source must be primary or backup.",
    plan_no_json="The plan contains no JSON object.",
    plan_no_steps="The plan must have a non-empty steps list.",
    plan_step_id="Every step needs a unique string id.",
    plan_reused_id="Step id {step_id} was already used in an earlier plan version; revised steps need new ids.",
    plan_unknown_tool="Step {step_id} uses an unregistered tool: {tool}",
    plan_arguments="The arguments of step {step_id} must be a JSON object.",
    check_progress="Learning progress comes from a successful tool result",
    detail_progress_ok="fetch_progress succeeded",
    detail_progress_missing="No successful fetch_progress",
    check_scores="Quiz scores come from a successful tool result",
    detail_scores_source="source {source}",
    detail_scores_missing="No successful fetch_quiz_scores",
    check_report_numbers="The report states the real scores (keyword screen)",
    detail_numbers="The report contains {numbers}",
    detail_numbers_missing="The report does not state every real score, or this run has no score data",
    list_separator=", ",
    row_plan_failed="planning failed",
    row_plan_not_json="the plan is not valid JSON",
    row_created="created",
    row_revised="revised",
    row_success="success",
    row_failure="failed: {error}",
    plan_columns=("Plan version", "Event", "Reason", "Steps"),
    react_columns=("Round", "Tool", "Result", "Note"),
    strategy_titles={"static": "Static plan", "replan": "Replan after failure", "react": "ReAct baseline"},
    report_summary=("The primary data source always fails (controlled fault). Acceptance looks only at real tool "
                    "results and the scores in the report, not at the plan itself."),
    label_verdict="Acceptance verdict",
    label_model_calls="Model calls",
    label_tool_calls="Tool calls",
    label_plan_versions="Plan versions",
    label_revisions="Revisions",
    label_note="Learner note",
    value_passed="passed",
    value_failed="failed",
    value_empty="(empty)",
    verdict_passed="Acceptance passed.",
    verdict_failed="Acceptance failed.",
    no_report="No report was written.",
    answer="{verdict} {report}",
)
