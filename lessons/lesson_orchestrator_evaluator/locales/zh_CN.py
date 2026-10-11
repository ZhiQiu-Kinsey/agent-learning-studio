"""orchestrator-evaluator runtime text: Chinese (source language)."""
from lessons.lesson_orchestrator_evaluator.locales import Texts

TEXTS = Texts(
    notes={
        "messages-context": "模型只看到本次请求里的消息，历史要由应用程序重发。",
        "application-state": "应用状态记录目标和证据，消息列表不会自动更新它。",
        "context-budget": "压缩上下文时，工具调用和工具结果要成对保留或成对删除。",
    },
    task=("为 messages-context（上下文组成与消息协议）、application-state（应用状态与运行生命周期）、"
          "context-budget（上下文预算与截取窗口）三课各出一道四选一的选择题，题目要考到该课要点。"),
    single_system=('你是出题老师，一次写完全部题目。只输出一个 JSON 数组，按 messages-context、application-state、'
                   'context-budget 的顺序，每个元素是'
                   '{"question": "题干", "options": ["A", "B", "C", "D"], "answer": 正确选项的下标 0-3, '
                   '"explanation": "为什么这个选项对"}'),
    orchestrator_system=('你是编排者，只负责拆分任务，不写题目。只输出 JSON：'
                         '{"subtasks": [{"id": "w1", "lesson": "messages-context", "instruction": "交给工人的一句话指令"}]}。'
                         "最多 4 个子任务，lesson 只能是 messages-context、application-state、context-budget。"),
    worker_system=('你是出题老师，只完成交给你的一道题。只输出一个 JSON 对象：{"question": "题干", '
                   '"options": ["A", "B", "C", "D"], "answer": 正确选项的下标 0-3, "explanation": "为什么这个选项对"}'),
    evaluator_system=('你是评审。按量规检查一道选择题：题干考的是给定要点；四个选项都合理但只有一个正确；'
                      '解释说明了为什么正确。只输出 JSON：{"verdict": "pass" 或 "revise", "feedback": ["具体问题"]}。'),
    single_request="{task}\n要点：{notes}",
    worker_request="{instruction}\n要点：{note}",
    generator_request="为 {lesson} 这一课出一道选择题。要点：{note}",
    revision_request="为 {lesson} 这一课出一道选择题。要点：{note}\n上一版：{previous}\n评审意见：{feedback}\n请修订。",
    review_request="要点：{note}\n题目：{output}",
    no_json="没有 JSON",
    not_an_object="不是 JSON 对象",
    missing_question="缺少题干",
    options_invalid="options 必须是 4 个非空字符串",
    options_duplicate="四个选项不能重复",
    answer_invalid="answer 必须是 0 到 3 的整数",
    missing_explanation="缺少解释",
    no_json_found="回复里没有 JSON。",
    missing_item="没有这道题",
    format_ok="格式通过",
    problem_separator="；",
    plan_error="编排者的子任务列表不合格式",
    plan_reason="编排者拆出的子任务",
    plan_step="{lesson}：{instruction}",
    no_workers="子任务列表不合格式，没有派出工人",
    roles={"single": "单次调用", "orchestrator": "编排者", "worker": "工人", "generator": "生成者",
           "evaluator": "评估者"},
    stop_reasons={"limit": "达到迭代上限", "passed": "评审通过", "invalid": "评审输出不合格式",
                  "unchanged": "修订后没有变化"},
    report_titles={"single": "单次调用", "orchestrator": "编排者-工人", "evaluator": "评估者-优化者"},
    report_summary="格式由程序检查；题目质量只有评估者模式请了模型评审。用量只累加服务商报告的 total_tokens。",
    check_format="每道题都通过格式检查",
    check_format_detail="{ok}/{total} 道通过",
    label_model_calls="模型调用数",
    label_total_tokens="累计 total_tokens",
    label_role_calls="各角色调用",
    label_stop_reason="停止原因",
    label_note="学习者备注",
    role_count="{role} {count}",
    role_separator="、",
    tokens_partly_reported="{total}（{missing} 次未报告）",
    value_not_reported="未报告",
    value_empty="（空）",
    columns_single=("题目", "格式检查"),
    columns_orchestrator=("工人", "格式检查"),
    columns_evaluator=("轮", "评审来源", "结论", "意见"),
    answer="共 {calls} 次模型调用，{ok}/{total} 道题通过格式检查。",
    answer_with_stop="共 {calls} 次模型调用，{ok}/{total} 道题通过格式检查，停止原因：{reason}。",
)
