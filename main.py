"""命令行启动器：在终端里运行原生工具循环的几门课（网页里的课程用 run_web.py）。"""

import argparse
import importlib


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
    args = parser.parse_args()
    module_path, lesson_name = LESSONS[args.lesson]
    print("启动：{}".format(lesson_name))
    lesson_module = importlib.import_module(module_path)
    lesson_module.main()


if __name__ == "__main__":
    main()
