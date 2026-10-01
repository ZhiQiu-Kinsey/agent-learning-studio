"""本地展示工具成功、参数错误和未知工具；不会读取密钥或连接百炼。"""

import json

from course.runner import execute_tool
from lessons.lesson_03_fail_safely.tools import AVAILABLE_TOOLS


def show_case(title, tool_call):
    print("\n=== {} ===".format(title))
    result = execute_tool(tool_call, AVAILABLE_TOOLS)
    print("回传给模型的工具结果：{}".format(json.dumps(result, ensure_ascii=False)))


def main():
    print("离线错误处理演示：不调用百炼、不需要 API Key。")
    show_case(
        "有效参数",
        {
            "function": {"name": "divide_numbers", "arguments": '{"a": 12, "b": 3}'},
        },
    )
    show_case(
        "除数为零",
        {
            "function": {"name": "divide_numbers", "arguments": '{"a": 12, "b": 0}'},
        },
    )
    show_case(
        "模型请求了未登记的工具",
        {
            "function": {"name": "delete_files", "arguments": "{}"},
        },
    )
    show_case(
        "工具参数不是有效 JSON",
        {
            "function": {"name": "divide_numbers", "arguments": "{bad json"},
        },
    )


if __name__ == "__main__":
    main()
