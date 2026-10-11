"""structured-output runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_05_structured_output.locales import Texts

TEXTS = Texts(
    facts_lesson_title="任务目标与验收",
    system_prompt=(
        "只输出一个 JSON 对象，字段 lesson_id、lesson_title、prerequisite、exercise。"
        "不得编造给定事实；exercise 是 8 到 120 字的练习说明。"
    ),
    user_prompt="把这些可信课程事实整理为学习任务卡：{facts}。练习要求：用固定输入 19+23 比较运行结束和验收通过。",
    inject_missing_field=" 本轮故意省略 prerequisite 字段，供验证器展示字段错误。",
    inject_wrong_fact=" 本轮故意把 prerequisite 写成 {wrong}，供验证器展示事实错误。",
    repair_prompt="上一版未通过：{reasons}。只按原始可信事实输出完整 JSON 对象。",
    non_json_constant="非标准 JSON 常量：{value}",
    layer_json="JSON 格式",
    detail_json_ok="可解析为 JSON",
    layer_schema="字段 Schema",
    detail_schema_ok="必填、类型、长度及额外字段检查通过",
    layer_facts="业务事实",
    detail_facts_ok="与给定课程事实一致",
    detail_facts_mismatch="与给定资料不符：{fields}",
    missing_content="模型响应没有可读取的 message.content",
    content_not_text="模型响应内容必须为文本",
    stage_first="初稿",
    stage_repair="修复稿",
    report_title="{stage}：结构化输出三层校验",
    summary_passed="{stage}通过已执行的全部检查",
    summary_failed="{stage}未通过；后续层级在上游失败时不作判断",
    label_model_calls="模型调用数",
    label_draft_verdict="本稿验收",
    value_passed="通过",
    value_failed="失败",
    label_note="学习者备注",
    value_empty="（空）",
    columns=("阶段", "结果"),
    answer_passed="验收通过：{card}",
    answer_failed="模型输出未通过校验；请查看响应和三层检查。",
)
