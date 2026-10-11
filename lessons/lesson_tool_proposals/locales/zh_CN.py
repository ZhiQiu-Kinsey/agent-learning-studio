"""tool-proposals runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_tool_proposals.locales import Texts

TEXTS = Texts(
    default_question="帮我计算 19 加 23。",
    system_prompt=(
        "你是教学用助手。计算两个数字的和时调用 add_numbers；"
        "询问当前时间或日期时调用 get_current_time；其他问题直接回答。"
    ),
    missing_choices="模型响应缺少 choices[0]，无法读取调用提议。",
    empty_content="（模型没有提出调用，content 也为空。）",
    proposals_answer="模型提出了 {count} 个调用：{calls}。本课不执行工具，所以没有工具结果。",
    call_separator="；",
    report_title="模型提出了什么",
    report_summary="表格只列响应里的 tool_calls；本课没有执行任何工具，事件里也就没有 tool_call 和 tool_result。",
    label_finish_reason="finish_reason",
    label_proposal_count="调用提议数",
    label_content_length="content 长度（字符）",
    columns=("调用 id", "工具名", "arguments（JSON 字符串）", "能解析成 JSON 对象"),
    value_not_reported="未报告",
    value_none="（无）",
    value_empty="（空）",
)
