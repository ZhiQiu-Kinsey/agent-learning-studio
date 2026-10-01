"""第 3 课：一个会明确拒绝非法输入的除法工具。"""

import math


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "divide_numbers",
            "description": (
                "计算 a 除以 b 并返回 quotient。两个参数必须是有限数字；"
                "b 不能为 0。用户要求做除法时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "被除数"},
                    "b": {"type": "number", "description": "除数，不能为 0"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
        },
    }
]


def divide_numbers(a, b):
    """校验输入，并把领域错误作为 ValueError 明确报告。"""
    for name, value in (("a", a), ("b", b)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("参数 {} 必须是数字。".format(name))

    try:
        finite_inputs = math.isfinite(a) and math.isfinite(b)
    except OverflowError:
        finite_inputs = False
    if not finite_inputs:
        raise ValueError("参数必须是有限数字且处于支持范围内。")

    if b == 0:
        raise ValueError("除数不能为 0；请提供非零除数。")

    try:
        quotient = a / b
    except OverflowError:
        raise ValueError("计算结果超出支持范围。") from None
    if not math.isfinite(quotient):
        raise ValueError("计算结果超出支持范围。")
    return {"quotient": quotient}


AVAILABLE_TOOLS = {"divide_numbers": divide_numbers}
