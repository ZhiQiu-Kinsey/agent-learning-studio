# 第 3 课：错误处理与安全边界

**目标：**让工具遇到坏参数或业务错误时明确失败；让模型如实说明；遇到 API/网络错误时停止并交给人判断。

## 先跑离线演示

从项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m lessons.lesson_03_fail_safely.offline_demo
```

这段演示不读 API Key、不请求百炼，也不会产生用量。观察四种情况：计算成功、除数为零、未知工具、JSON 参数无效。工具错误会转成 `ok=false` 的结构化结果；未知名称无法通过 allowlist 找到可执行函数。

## 再看真实模型循环

```powershell
.\.venv\Scripts\python.exe main.py --lesson 3
```

分别问 `12 除以 3 等于多少？` 和 `12 除以 0 等于多少？`。第二种情况下，Python 把错误作为 `role: tool` 消息回传；system prompt 要求模型承认失败、请你修正输入，并且不要编造商。

## 失败处理边界

- **工具参数或计算失败：**转成 `ok=false` 的工具结果，让模型根据真实错误作答。
- **未知工具：**只查显式登记的 `AVAILABLE_TOOLS`，绝不动态执行模型返回的名称。
- **API 或网络错误：**显示状态并结束这次运行，不自动重发。超时后服务器是否已处理原请求无法确定；盲目重试可能重复消耗百炼用量。
- **循环控制：**本课最多发出两轮模型请求，防止模型反复请求工具。

观察 `course/runner.py` 的错误封装与 allowlist，以及 `course/api_client.py` 的网络错误处理。该流程让人决定何时修正并重新提交。
