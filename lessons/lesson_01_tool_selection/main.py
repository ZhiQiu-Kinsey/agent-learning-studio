"""第 1 课：根据问题，在加法和本地时间工具之间选择。"""

from course.runner import run_cli
from lessons.lesson_01_tool_selection.tools import AVAILABLE_TOOLS, TOOLS


SYSTEM_PROMPT = (
    "你是一个教学用助手。计算两个数字的和时调用 add_numbers；"
    "询问当前时间或日期时调用 get_current_time。"
    "如果用户独立地请求计算和查时间，可以调用两个工具。"
    "根据工具返回值作答，不要猜时间。"
)


def main():
    run_cli(
        title="第 1 课：工具选择",
        examples=[
            "帮我计算 19 加 23。",
            "现在本地时间是几点？",
            "计算 19 加 23，并告诉我现在几点。",
        ],
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        available_tools=AVAILABLE_TOOLS,
        max_tool_rounds=3,
    )


if __name__ == "__main__":
    main()
