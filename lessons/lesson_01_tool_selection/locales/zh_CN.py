"""tool-selection runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_01_tool_selection.locales import Texts

TEXTS = Texts(
    system_prompt=(
        "你是一个教学用助手。计算两个数字的和时调用 add_numbers；"
        "询问当前时间或日期时调用 get_current_time。"
        "根据工具返回值作答，不要猜时间。"
    ),
    cli_title="执行工具与回传结果",
    cli_examples=("帮我计算 19 加 23。", "现在本地时间是几点？"),
)
