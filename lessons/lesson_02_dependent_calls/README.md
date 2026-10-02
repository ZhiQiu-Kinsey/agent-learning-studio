# 依赖式多轮调用（`dependent-calls`）

**目标：**练习工具之间存在依赖时，模型如何先拿到事实，再决定下一步；并对照两个互不依赖的任务为什么可以在同一轮提出。

命令行运行（在项目根目录）：

```powershell
.\.venv\Scripts\python.exe -m lessons.lesson_02_dependent_calls.main
```

练习一（`chain`）：

> 把现在的小时和分钟相加。

预期流程：

1. 第一次模型请求只调用 `get_current_time()`。
2. Python 返回带 `hour`、`minute` 的结构化数据。
3. 模型读取真实返回值，再请求 `add_numbers(hour, minute)`。
4. Python 将结果回传，模型组织最终回答。

练习二（`both`）：

> 计算 19 加 23，并告诉我现在几点。

两个任务互不依赖，模型可以在同一个响应里提出两个调用；`run_agent` 仍按列表逐个执行，两个工具结果各带自己的 `tool_call_id` 进入下一次请求。

这条路径最多用三轮模型请求。`main.py` 只保存本课的任务规则；工具定义与白名单沿用“执行工具与回传结果”一课的 `tools.py`，执行循环是 `course/runner.py` 的 `run_agent`。每轮的完整请求 JSON 会显示在终端中，认证头不会打印。实际百炼调用会产生用量。

本课也可在网页课程导航中进入，查看源码、真实运行事件和回放。
