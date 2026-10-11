"""先读取本地时间，再用返回值做加法。"""

from course.i18n import SOURCE_LOCALE
from course.runner import AgentSetup, run_cli
from lessons.lesson_01_tool_selection.tools import available_tools, tool_definitions


SYSTEM_PROMPT = (
    "你是一个教学用助手。计算两个数字的和时调用 add_numbers；"
    "询问当前时间或日期时调用 get_current_time。"
    "如果用户同时要求独立的计算和查时间，可以调用两个合适的工具。"
    "时间工具返回的是运行本 Python 程序的机器本地时间和时区；"
    "根据工具结果作答，不要猜时间或把它说成其他时区。"
    "如果用户要求把当前小时和分钟相加，必须先单独调用 get_current_time；"
    "收到真实结果后，再用返回的 hour、minute 调用 add_numbers。"
    "不要并行调用这两个有依赖关系的工具，也不要猜测或编造参数。"
    "拿到工具结果后再回答。"
)


def setup(locale):
    """One native run's system prompt and the tools shared with tool-selection. This lesson only speaks zh-CN so far."""
    return AgentSetup(SYSTEM_PROMPT, tool_definitions(locale), available_tools(locale))


def main(locale=None):
    run_cli(
        setup(SOURCE_LOCALE),
        title="根据工具结果继续调用",
        examples=[
            "把现在的小时和分钟相加。",
            "计算 19 加 23，并告诉我现在几点。",
        ],
        max_tool_rounds=3,
    )


if __name__ == "__main__":
    main()
