"""长任务一课离线测试模型的文字（中文）。"""
from lessons.lesson_long_running_tasks.locales.fixture import Texts

TEXTS = Texts(
    waiting="任务都已经在后台运行，结果到之前我先等着。",
    still_waiting="已经有一项结果了，另一项还在运行，继续等。",
    gave_up="补交成绩表第 6 行的成绩不是整数，重试仍然失败。我没法提交完整的简报，需要助教先修正数据。",
    restarted="已经重新启动 deep_scan，等它的结果。",
)
