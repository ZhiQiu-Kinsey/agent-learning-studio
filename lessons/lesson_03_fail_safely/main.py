"""工具失败时如实说明，不猜测结果。"""

from course.i18n import SOURCE_LOCALE
from course.runner import AgentSetup, run_cli
from lessons.lesson_03_fail_safely.tools import AVAILABLE_TOOLS, TOOLS


SYSTEM_PROMPT = (
    "你是一个教学用计算助手。用户要求做除法时调用 divide_numbers。"
    "如果工具返回 ok=false，必须如实说明错误并请用户修正输入；"
    "不要编造商，也不要重复同一个无效请求。"
    "只有工具返回 ok=true 后才能报告计算结果。"
)


def setup(locale):
    """One native run's system prompt, tools and allowlist. This lesson only speaks zh-CN so far."""
    return AgentSetup(SYSTEM_PROMPT, TOOLS, AVAILABLE_TOOLS)


def main(locale=None):
    run_cli(
        setup(SOURCE_LOCALE),
        title="错误处理与安全边界",
        examples=[
            "12 除以 3 等于多少？",
            "12 除以 0 等于多少？请说明处理过程。",
        ],
        max_tool_rounds=2,
    )


if __name__ == "__main__":
    main()
