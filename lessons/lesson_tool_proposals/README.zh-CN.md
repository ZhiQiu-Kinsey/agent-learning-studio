# 工具定义与调用提议（`tool-proposals`）

[English](README.md) · 简体中文

**目标：**把工具定义随请求发给模型，只看模型提出的调用：选了哪个工具、参数是什么。本课不执行任何工具。

本课是独立运行器（`runtime.py`），只发一次请求：

1. 请求体在 `messages` 之外多了 `tools`（工具定义，由“执行工具与回传结果”一课 `tools.py` 的 `tool_definitions` 生成）和 `tool_choice: "auto"`。
2. `context.complete` 发出请求，平台记录 `request`、`response` 事件。
3. `read_proposals` 原样列出响应里的 `tool_calls`：调用 id、工具名、JSON 字符串形式的 `arguments`，并标出它能不能解析成 JSON 对象。本课没有登记任何可执行的函数，所以事件里没有 `tool_call` 和 `tool_result`。

| 练习 | 问题 | 看什么 |
| --- | --- | --- |
| `sum` 问加法 | 帮我计算 19 加 23。 | 是否提出 `add_numbers`，参数怎么写 |
| `time` 问时间 | 现在本地时间是几点？ | 是否提出 `get_current_time`，参数为空对象 |
| `chat` 闲聊 | 你好，用一句话介绍一下你自己。 | 不提出调用、直接回答，`finish_reason` 为 `stop` |

执行调用提议、把结果交回模型，是下一课“执行工具与回传结果”的内容。

**运行语言：**本课有中文和英文两种运行。系统提示词、程序写出的回答和实验报告的文字在 `locales/zh_CN.py`、`locales/en.py`；工具描述在 `tool-selection` 共用的 `locales/tools/`；练习问题按语言写在 `lesson.json`。网页按界面语言选择运行语言，每条运行记录都写明它用的语言。工具名和参数名是代码，两种语言相同。

在网页课程导航中进入本课，可以查看源码、真实运行事件和回放。离线测试：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_tool_proposals.test_lesson -v
```

`fixtures.py` 只服务自动化测试，提议是固定脚本，不代表真实模型的选择。
