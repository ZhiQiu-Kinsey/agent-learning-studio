"""context-budget helpers runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_09_context_budget.locales.helpers import Texts

TEXTS = Texts(
    facts={
        "messages-context": "模型只看到本次请求里的消息；历史由应用程序重发。",
        "application-state": "应用 state 记录目标和证据；消息列表不会自动更新 state。",
    },
    unknown_source="没有这份资料：{source_key}",
    fact_mismatch="实际工具结果缺少与请求匹配的来源和事实。",
    side_question="旁支讨论 {n}：请简短记下这条与本题无关的练习安排。",
    side_reply="已记下旁支讨论 {n}。",
    missing_message="模型响应缺少 choices[0].message。",
    content_not_text="模型响应的 content 不是文本。",
    unknown_tool="未知",
    proposed_calls="（没有文本回答：模型提出调用 {names}，运行器没有执行）",
    name_separator="、",
    usage_not_reported="未报告",
)
