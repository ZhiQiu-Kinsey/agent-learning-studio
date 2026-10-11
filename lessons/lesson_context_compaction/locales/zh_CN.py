"""context-compaction runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_context_compaction.locales import Texts

TEXTS = Texts(
    goal="目标：先后查阅“上下文组成与消息协议”和“应用状态与运行生命周期”两份资料，再回答问题；约束：不能把无来源的猜测当事实。",
    probe="最早读取的那份资料来自哪一项？它的原话是什么？",
    probe_source_title="上下文组成与消息协议",
    probe_phrase="历史由应用程序重发",
    system_prompt="只根据本次消息回答，不调用工具。缺少依据时明确说明，不要猜测。",
    summary_system="你负责把对话压缩成摘要，供后续继续工作。只写摘要，不调用工具，也不继续执行任务。",
    summary_instructions={
        "keep_sources": "请把以上对话压缩成一段摘要，供后续继续工作使用。保留目标、约束、每次工具调用的来源和结果原文、尚未完成的事项。不超过 200 字。",
        "brief": "请用一两句话概括以上对话。",
    },
    cleared_note="旧工具结果已清理，原内容不在上下文里。",
    source_entry="第 {number} 次读取 {key}",
    list_separator="；",
    rule_record=(
        "此前对话的压缩记录（程序按规则生成）\n目标：先后查阅两份资料，再回答问题\n"
        "约束：不能把无来源的猜测当事实\n来源：{sources}\n事实：{facts}\n待办：继续回答用户的问题"
    ),
    budget_too_small="字符预算 {budget} 小于保留关键证据所需的 {needed} 字符。",
    layout_names={"none": "不压缩", "rule": "规则压缩", "clear": "清理旧工具结果", "summary": "摘要压缩"},
    summary_prefix="此前对话的摘要：",
    final_answer="摘要请求和各组的探针请求都已记录。请对照每组的上下文、探针回答和服务商用量。",
    report_title="三种压缩与同一个探针问题",
    report_summary=(
        "历史由运行器组装，两次工具结果来自本次真实读取，摘要由当前模型生成。“原话还在上下文里”是本地字符串检查，"
        "“答出来源与原话”是关键词初筛，两者分开看；字符数不是 Token。"
    ),
    check_protocol="各组上下文都通过协议检查",
    check_protocol_detail="发出前对每一组运行了协议检查。",
    check_rule_fits="规则压缩装下了关键证据",
    check_rule_fits_detail="记录不超过字符预算 {budget}。",
    check_probe="{name}：探针初筛",
    probe_both="回答同时含来源名与原话",
    probe_missing="回答缺少来源名或原话；仍需读原文复核",
    label_model_calls="模型调用数",
    label_summary_usage="摘要请求的用量",
    label_summary_style="摘要指令",
    label_summary_text="摘要原文",
    label_probe="探针问题",
    label_note="学习者备注",
    value_empty="（空）",
    hit="命中",
    miss="未命中",
    columns=("做法", "消息数", "JSON 字符数", "原话还在上下文里", "探针回答", "答出来源与原话（初筛）", "服务商用量"),
)
