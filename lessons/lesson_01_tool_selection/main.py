"""执行模型提出的调用，把工具结果交回模型，直到模型给出回答。"""

from course.runner import run_cli
from lessons.lesson_01_tool_selection.tools import AVAILABLE_TOOLS, TOOLS


SYSTEM_PROMPT = (
    "你是一个教学用助手。计算两个数字的和时调用 add_numbers；"
    "询问当前时间或日期时调用 get_current_time。"
    "根据工具返回值作答，不要猜时间。"
)


def main():
    run_cli(
        title="执行工具与回传结果",
        examples=[
            "帮我计算 19 加 23。",
            "现在本地时间是几点？",
        ],
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        available_tools=AVAILABLE_TOOLS,
        max_tool_rounds=3,
    )


if __name__ == "__main__":
    main()
