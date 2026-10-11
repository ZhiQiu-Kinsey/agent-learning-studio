"""tools.py runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_01_tool_selection.locales.tools import Texts

TEXTS = Texts(
    add_numbers="把两个数字相加。需要计算两个数的和时调用。",
    add_numbers_a="第一个数字",
    add_numbers_b="第二个数字",
    get_current_time=(
        "读取运行 Python 程序的机器当前本地日期和时间。"
        "返回 local_datetime、timezone、hour、minute 字段。"
        "询问现在几点或今天日期时调用。"
    ),
    not_a_number="参数 {name} 必须是数字。",
    not_finite="参数和两数之和都必须是有限数字，且不超出浮点数范围。",
)
