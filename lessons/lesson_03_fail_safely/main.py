"""工具失败时如实说明，不猜测结果。"""

from course.runner import run_cli
from lessons.lesson_03_fail_safely.tools import AVAILABLE_TOOLS, TOOLS


SYSTEM_PROMPT = (
    "你是一个教学用计算助手。用户要求做除法时调用 divide_numbers。"
    "如果工具返回 ok=false，必须如实说明错误并请用户修正输入；"
    "不要编造商，也不要重复同一个无效请求。"
    "只有工具返回 ok=true 后才能报告计算结果。"
)


def main():
    run_cli(
        title="错误处理与安全边界",
        examples=[
            "12 除以 3 等于多少？",
            "12 除以 0 等于多少？请说明处理过程。",
        ],
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        available_tools=AVAILABLE_TOOLS,
        max_tool_rounds=2,
    )


if __name__ == "__main__":
    main()
