"""plan-and-replan runtime text: Chinese (source language)."""
from lessons.lesson_plan_and_replan.locales import Texts

TEXTS = Texts(
    task="给学习者 {learner} 写一份学习周报：列出已完成的课和每课的练习得分。",
    planner_system="""你是规划器，只负责写计划，不执行工具。可用工具：
- fetch_progress(learner)：查询已完成和正在学的课程。
- fetch_quiz_scores(learner, source)：查询每课练习得分；source 为 primary（主数据源）或 backup（备份，数据相同）。

只输出一个 JSON 对象，不要输出其他文字：
{"reason": "为什么这样计划（修订时写明修订原因）", "steps": [{"id": "s1", "tool": "工具名", "arguments": {...}, "purpose": "这一步要得到什么"}]}
修订计划时，只列出还需要执行的步骤，id 不要和已有步骤重复。""",
    writer_system="你是学习助教。根据给出的工具结果写一段不超过三句话的学习周报，写出每课分数。缺少的数据就直说缺少，不要编造。",
    react_system="你是学习助教。需要数据时调用工具，不要猜测。拿到数据后写一段不超过三句话的学习周报，写出每课分数。",
    writer_input="{task}\n工具结果：{results}",
    revise_request=("执行情况：{status}\n步骤 {step_id} 失败：{error}\n"
                    "请修订计划，只列出还需要执行的步骤，并在 reason 里写明修订原因。"),
    fetch_progress_description="查询学习者已完成和正在学的课程。",
    fetch_quiz_scores_description="查询学习者每课的练习得分。source 为 primary（主数据源）或 backup（备份，数据相同）。",
    unknown_learner="没有学习者 {learner} 的记录。",
    primary_unavailable="成绩主数据源暂时不可用（受控故障：本课固定失败）。可以改用 source=backup。",
    bad_source="source 只能是 primary 或 backup。",
    plan_no_json="计划里没有 JSON 对象。",
    plan_no_steps="计划必须有非空的 steps 列表。",
    plan_step_id="每个步骤需要唯一的字符串 id。",
    plan_reused_id="步骤 id {step_id} 在之前的计划版本里用过了；修订后的步骤要用新的 id。",
    plan_unknown_tool="步骤 {step_id} 使用了未登记的工具：{tool}",
    plan_arguments="步骤 {step_id} 的 arguments 必须是 JSON 对象。",
    check_progress="学习进度来自成功的工具结果",
    detail_progress_ok="fetch_progress 成功",
    detail_progress_missing="没有成功的 fetch_progress",
    check_scores="练习成绩来自成功的工具结果",
    detail_scores_source="来源 {source}",
    detail_scores_missing="没有成功的 fetch_quiz_scores",
    check_report_numbers="周报写出了真实的分数（关键词初筛）",
    detail_numbers="周报包含 {numbers}",
    detail_numbers_missing="周报没有写全真实分数，或本次没有成绩数据",
    list_separator="、",
    row_plan_failed="规划失败",
    row_plan_not_json="计划不是合格的 JSON",
    row_created="创建",
    row_revised="修订",
    row_success="成功",
    row_failure="失败：{error}",
    plan_columns=("计划版本", "事件", "原因", "步骤数"),
    react_columns=("轮次", "工具", "结果", "备注"),
    strategy_titles={"static": "静态计划", "replan": "失败后重新规划", "react": "ReAct 基线"},
    report_summary="主数据源固定失败（受控故障）。验收只看真实工具结果和周报里的分数，不看计划本身。",
    label_verdict="验收结论",
    label_model_calls="模型调用数",
    label_tool_calls="工具调用数",
    label_plan_versions="计划版本数",
    label_revisions="修订次数",
    label_note="学习者备注",
    value_passed="通过",
    value_failed="未通过",
    value_empty_note="（空）",
    verdict_passed="验收通过。",
    verdict_failed="验收未通过。",
    no_report="没有生成周报。",
    answer="{verdict}{report}",
)
