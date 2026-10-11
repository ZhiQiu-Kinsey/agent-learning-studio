"""context-budget runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_09_context_budget.locales import Texts

TEXTS = Texts(
    system_prompt="只根据本次消息回答；指出证据来源与未完成步骤。缺少来源时明确说明，不要猜测。",
    goal="目标：回答课程结论并给出来源；约束：不能把无来源的猜测当事实。",
    default_question="根据已见资料，本课关键结论是什么？来源是哪一项？下一步还要做什么？",
    budget_too_small="字符预算 {budget} 装不下 system 和当前问题。",
    layout_names={"full": "完整历史", "window": "截取窗口"},
    variant_detail="消息由运行器组装：assistant 工具调用与旁支回复不是模型生成的，工具结果来自本次真实的 lookup_lesson。",
    layouts_answer="两种布局的真实请求与回答已记录。请对照 request 里的消息、response 里的回答和服务商用量。",
    layouts_title="完整历史与截取窗口",
    layouts_summary=(
        "两种布局都由运行器组装，工具结果来自本次真实读取。字符数是本地 JSON 长度，不是 Token；"
        "用量只展示服务商实际返回的值。"
    ),
    check_protocol="两种布局都通过协议检查",
    check_protocol_detail="发出前对每个布局运行了协议检查。",
    check_in_budget="截取窗口在字符预算内",
    check_in_budget_detail="预算 {budget} 字符，窗口 {chars} 字符。",
    check_source_kept="截取窗口保留了来源",
    check_source_kept_detail="在窗口实际发出的消息里查找来源名。",
    label_model_calls="模型调用数",
    label_char_budget="字符预算",
    label_usage_count="返回用量的请求数",
    label_question="实际追问",
    layouts_columns=("布局", "消息数", "JSON 字符数", "在预算内", "有来源", "有事实", "模型回答", "服务商用量"),
    truncation_names={
        "naive": "按条数截断（保留最后 2 条）",
        "pair_aware": "按配对截断（切点不拆开调用与工具结果）",
    },
    local_valid="合法",
    local_rejected="拒绝：{error}",
    check_local="{name}：本地协议检查",
    refused="被拒绝（HTTP {status}）",
    refused_offline="被拒绝（HTTP {status}），离线夹具模拟",
    no_answer="无",
    accepted="已接受",
    pair_answer="两种截断的请求都已原样发送，服务商的回应见报告与 lesson.provider_error 事件。",
    pair_title="拆开工具调用与工具结果",
    pair_summary="同一段历史按两种方式截断后原样发送。服务商是否拒绝以本次记录为准；离线测试模式下的拒绝由测试夹具模拟。",
    label_history="历史消息数",
    label_mode="运行模式",
    mode_offline="离线测试（夹具）",
    mode_live="真实模型",
    pair_columns=("截断方式", "消息数", "本地协议检查", "服务商结果", "模型回答"),
)
