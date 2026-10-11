"""chat-request runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_chat_request.locales import Texts

TEXTS = Texts(
    default_question="用一句话解释什么是 Agent。",
    finish_reasons={"stop": "模型自己写完了", "length": "写到输出上限被截断"},
    empty_content="（这次响应的 content 为空，请看 finish_reason 和 usage。）",
    missing_choices="模型响应缺少 choices[0]，无法读取回答。",
    report_title="一次请求的关键字段",
    report_summary=(
        "用量来自这次 response 事件里的 usage，服务商没有报告的项写“未报告”；"
        "max_tokens 和 system 消息取自请求。"
    ),
    label_system="system 消息",
    label_max_tokens="max_tokens",
    label_answer_length="回答长度（字符）",
    label_finish_reason="finish_reason",
    label_reason_meaning="结束原因的含义",
    label_prompt_tokens="提示 Token",
    label_completion_tokens="完成 Token",
    label_total_tokens="总 Token",
    label_reasoning_tokens="其中推理 Token",
    label_reasoning_chars="推理内容（字符）",
    value_yes="有",
    value_no="无",
    value_not_set="未设置",
    value_not_reported="未报告",
    value_other_reason="其他，见服务商文档",
    column_index="序号",
)
