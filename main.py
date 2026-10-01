"""课程启动器：默认运行最新一课，也可指定课程编号。"""

import argparse
import importlib


LESSONS = {
    "1": ("lessons.lesson_01_tool_selection.main", "第 1 课：工具选择"),
    "2": ("lessons.lesson_02_dependent_calls.main", "第 2 课：依赖式多轮调用"),
    "3": ("lessons.lesson_03_fail_safely.main", "第 3 课：错误处理与安全边界"),
}


def main():
    parser = argparse.ArgumentParser(description="Python Agent 分课练习")
    parser.add_argument(
        "--lesson",
        choices=LESSONS,
        default="3",
        help="选择课程编号；默认运行最新的第 3 课",
    )
    args = parser.parse_args()
    module_path, lesson_name = LESSONS[args.lesson]
    print("启动{}".format(lesson_name))
    lesson_module = importlib.import_module(module_path)
    lesson_module.main()


if __name__ == "__main__":
    main()
