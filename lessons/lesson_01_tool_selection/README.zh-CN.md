# 执行工具与回传结果（`tool-selection`）

[English](README.md) · 简体中文

**目标：**让 Python 按白名单执行模型提出的调用，把工具结果用同一个调用 id 写回消息历史，再请求一次模型，形成最小的 Agent 循环。

调用提议本身（工具定义、`tool_calls`、JSON 字符串参数）在上一课“工具定义与调用提议”里已经看过；本课接着执行它。

阅读顺序：

1. `course/runner.py` 的 `execute_tool`：解析 `arguments`，只在白名单（`available_tools` 返回的字典）里按名字找函数，执行后包成 `{"ok": true, "result": ...}`，出错时是 `ok: false` 加 `error_type`、`error`。
2. `course/runner.py` 的 `run_agent`：四步循环——建立消息历史、请求模型、没有 `tool_calls` 就返回回答、有就执行并把 `role: tool` 消息（带 `tool_call_id`）写回历史；最多 `max_tool_rounds` 轮。
3. `tools.py`：`tool_definitions`（发给模型的工具定义）、`add_numbers`、`get_current_time` 的实现和 `available_tools`。
4. `main.py`：`setup(locale)` 给出一次运行的系统提示词、工具定义和白名单，`main` 是命令行入口。

练习：`sum`（计算加法）、`time`（查询本地时间）。同一轮提出两个独立调用的情况放在“依赖式多轮调用”一课。

**运行语言：**系统提示词、工具描述和工具错误提示写在 `locales/`（`locales/tools/` 是 `tools.py` 的部分，提议课和依赖式多轮调用也用它），中文、英文各一份；工具名和参数名是代码，两种语言一样。网页按界面语言选择运行语言。

命令行运行（在项目根目录）：

```powershell
.\.venv\Scripts\python.exe -m lessons.lesson_01_tool_selection.main             # 中文
.\.venv\Scripts\python.exe -m lessons.lesson_01_tool_selection.main --locale en # 英文
```

百炼请求需要本机的 `local_config.py` 和 `DASHSCOPE_API_KEY`。终端打印的每轮请求体不包含 API Key。也可以在网页课程导航中进入本课，查看源码、真实运行事件和回放；回放只读已记录的事件，不会再请求模型或执行工具。
