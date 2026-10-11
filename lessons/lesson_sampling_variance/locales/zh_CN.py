"""sampling-variance runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_sampling_variance.locales import Texts

TEXTS = Texts(
    default_question="给一家卖猫咪用品的小店起一个中文店名。",
    system_prompt="你是起名助手。只输出一个店名，不加解释和标点。",
    missing_choices="模型响应缺少 choices[0]，无法读取回答。",
    answer="同一个请求发了 {repeats} 次，得到 {distinct} 种不同的回答（去掉首尾空白后逐字比较）。",
    report_title="temperature={temperature}：{repeats} 次回答",
    report_summary="同一个请求体原样发出；回答都来自各次 response。不同回答数按去掉首尾空白后逐字比较统计。",
    label_temperature="temperature",
    label_repeats="重复次数",
    label_distinct="不同回答数",
    label_most_common="出现最多的回答",
    label_prompt_total="提示 Token 合计",
    label_completion_total="完成 Token 合计",
    label_total_total="总 Token 合计",
    value_times="{count} 次",
    value_not_reported="未报告",
    column_number="次",
    column_answer="回答",
    column_completion_tokens="完成 Token",
)
