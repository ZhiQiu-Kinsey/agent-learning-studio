"""Command-line launcher for the native tool-loop lessons (the web lessons use run_web.py).

命令行启动器：在终端里运行原生工具循环的几门课（网页里的课程用 run_web.py）。
"""

import argparse
import importlib

from course.i18n import RUNTIME_LOCALES


# slug -> (module, title per run language)
LESSONS = {
    "tool-selection": ("lessons.lesson_01_tool_selection.main",
                       {"zh-CN": "执行工具与回传结果", "en": "Executing tools and returning results"}),
    "dependent-calls": ("lessons.lesson_02_dependent_calls.main",
                        {"zh-CN": "依赖式多轮调用", "en": "Dependent calls across rounds"}),
    "fail-safely": ("lessons.lesson_03_fail_safely.main",
                    {"zh-CN": "错误处理与安全边界", "en": "Error handling and safety boundaries"}),
}
STARTING = {"zh-CN": "启动：{}", "en": "Starting: {}"}


def main():
    parser = argparse.ArgumentParser(
        description="Run a native tool-loop lesson in the terminal / 在终端运行原生工具循环课程")
    parser.add_argument("--lesson", choices=LESSONS, default="fail-safely",
                        help="lesson id (slug); default: fail-safely / 课程 ID，默认 fail-safely")
    parser.add_argument("--locale", choices=RUNTIME_LOCALES, default="zh-CN",
                        help="run language for prompts, tool descriptions and terminal text / 运行语言")
    args = parser.parse_args()
    module_path, titles = LESSONS[args.lesson]
    print(STARTING[args.locale].format(titles[args.locale]))
    lesson_module = importlib.import_module(module_path)
    lesson_module.main(locale=args.locale)


if __name__ == "__main__":
    main()
