"""fail-safely runtime text: Simplified Chinese (the source language)."""
from lessons.lesson_03_fail_safely.locales import Texts

TEXTS = Texts(
    system_prompt=(
        "你是一个教学用计算助手。用户要求做除法时调用 divide_numbers。"
        "如果工具返回 ok=false，必须如实说明错误并请用户修正输入；"
        "不要编造商，也不要重复同一个无效请求。"
        "只有工具返回 ok=true 后才能报告计算结果。"
    ),
    divide_numbers=(
        "计算 a 除以 b 并返回 quotient。两个参数必须是有限数字；"
        "b 不能为 0。用户要求做除法时调用。"
    ),
    divide_numbers_a="被除数",
    divide_numbers_b="除数，不能为 0",
    not_a_number="参数 {name} 必须是数字。",
    not_finite="参数必须是有限数字且处于支持范围内。",
    zero_divisor="除数不能为 0；请提供非零除数。",
    out_of_range="计算结果超出支持范围。",
    fault_answer=(
        "本组没有调用模型。运行器构造的调用 {name}（参数 {arguments}）"
        "在执行前被拒绝：{error_type}：{error}。没有任何工具函数被执行。"
    ),
    cli_title="错误处理与安全边界",
    cli_examples=("12 除以 3 等于多少？", "12 除以 0 等于多少？请说明处理过程。"),
    demo_intro="离线错误处理演示：不调用百炼、不需要 API Key。",
    demo_result="回传给模型的工具结果：{result}",
    demo_cases={
        "valid": "有效参数",
        "zero": "除数为零",
        "unknown": "模型请求了未登记的工具",
        "malformed": "工具参数不是有效 JSON",
    },
)
