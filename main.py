"""命令行启动器：在终端里运行原生工具循环的几门课（网页里的课程用 run_web.py）。"""

import argparse
import importlib

from course.i18n import RUNTIME_LOCALES


LESSONS = {
    "tool-selection": ("lessons.lesson_01_tool_selection.main", "执行工具与回传结果"),
    "dependent-calls": ("lessons.lesson_02_dependent_calls.main", "依赖式多轮调用"),
    "fail-safely": ("lessons.lesson_03_fail_safely.main", "错误处理与安全边界"),
}


def main():
    parser = argparse.ArgumentParser(description="Python Agent 命令行练习（原生工具循环）")
    parser.add_argument(
        "--lesson",
        choices=LESSONS,
        default="fail-safely",
        help="课程 ID（slug）；默认运行错误处理与安全边界",
    )
    parser.add_argument("--locale", choices=RUNTIME_LOCALES, default="zh-CN",
                        help="运行语言：提示词、工具描述和终端文字用这种语言；本课不支持时按源语言运行")
    args = parser.parse_args()
    module_path, lesson_name = LESSONS[args.lesson]
    print("启动：{}".format(lesson_name) if args.locale == "zh-CN" else "Starting: {}".format(args.lesson))
    lesson_module = importlib.import_module(module_path)
    lesson_module.main(locale=args.locale)


if __name__ == "__main__":
    main()
