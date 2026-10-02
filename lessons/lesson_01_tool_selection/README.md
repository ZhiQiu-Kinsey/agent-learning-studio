# 工具选择（`tool-selection`）

**目标：**让模型在 Python 提供的工具里选出适合当前问题的函数。

运行：

```powershell
# 在项目根目录运行
.\.venv\Scripts\python.exe main.py --lesson 1
```

试着输入：

- `帮我计算 19 加 23，并说明结果。` → `add_numbers`
- `现在本地时间是几点？` → `get_current_time`
- `计算 19 加 23，并告诉我现在几点。` → 两个彼此独立的工具请求

阅读顺序：

1. `tools.py` 中的 JSON Schema 告诉模型函数名称、用途和参数。
2. `main.py` 的 system prompt 告诉模型什么问题应选什么工具。
3. `course/runner.py` 中的 `execute_tool` 使用 allowlist 把名称映射到 Python 实现。
4. `course/api_client.py` 负责调用百炼并在发送前打印请求体。

百炼请求需要本机的 `local_config.py` 和 `DASHSCOPE_API_KEY`。每轮输出的 JSON 请求体不包含 API Key。
