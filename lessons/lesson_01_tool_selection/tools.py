"""工具定义和实现：“工具定义与调用提议”只把 TOOLS 发给模型，“执行工具与回传结果”再用 AVAILABLE_TOOLS 执行。"""

import math
from datetime import datetime


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_numbers",
            "description": "把两个数字相加。需要计算两个数的和时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "第一个数字"},
                    "b": {"type": "number", "description": "第二个数字"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": (
                "读取运行 Python 程序的机器当前本地日期和时间。"
                "返回 local_datetime、timezone、hour、minute 字段。"
                "询问现在几点或今天日期时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]


def add_numbers(a, b):
    """校验两个有限数字后求和；和也必须是有限数字。"""
    if isinstance(a, bool) or not isinstance(a, (int, float)):
        raise ValueError("参数 a 必须是数字。")
    if isinstance(b, bool) or not isinstance(b, (int, float)):
        raise ValueError("参数 b 必须是数字。")
    try:
        finite = math.isfinite(a) and math.isfinite(b) and math.isfinite(a + b)
    except OverflowError:
        # 10**400 这样的超大整数转不成浮点数；不拦下来，异常会越过 execute_tool 让运行崩溃。
        finite = False
    if not finite:
        raise ValueError("参数和两数之和都必须是有限数字，且不超出浮点数范围。")
    return a + b


def get_current_time():
    """读取 Python 进程所在机器的本地时钟和时区。"""
    local_now = datetime.now().astimezone()
    return {
        "local_datetime": local_now.isoformat(timespec="seconds"),
        "timezone": local_now.tzname() or "local time zone",
        "hour": local_now.hour,
        "minute": local_now.minute,
    }


AVAILABLE_TOOLS = {
    "add_numbers": add_numbers,
    "get_current_time": get_current_time,
}
