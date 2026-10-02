# 一次模型请求（`chat-request`）

**目标：**发出一次不带工具的真实模型请求，读懂请求体里的 `model` 与 `messages`、响应里的回答、结束原因 `finish_reason` 和用量 `usage`。

本课是独立运行器（`runtime.py`），只调用一次 `context.complete`：

1. `build_request` 拼请求体：可选的 system 消息、user 问题，以及可选的 `max_tokens`。
2. `context.complete` 发出请求；平台补上 `model`，把请求和响应原样记成 `request`、`response` 事件。密钥由 `course/api_client.py` 的 `send_bailian` 放进 HTTP 请求头，不进请求体。
3. `read_reply` 从响应取回答、结束原因和用量；服务商没有报告的用量写“未报告”。

练习：

| 练习 | 改了什么 | 看什么 |
| --- | --- | --- |
| `basic` 带系统提示词 | 默认设置 | messages 的两条消息、回答、usage |
| `no-system` 去掉系统提示词 | `system_prompt` 留空 | messages 只剩 user，提示 Token 的变化 |
| `short-limit` 把输出上限设得很小 | `max_tokens` 设为 16 | `finish_reason` 是否为 `length`，回答是否被截断 |

先推理的模型（响应里有 `reasoning_content`）把推理也算进 `completion_tokens`，上限很小时 content 可能是空的；实验报告会列出推理 Token。

在网页课程导航中进入本课，可以查看源码、真实运行事件和回放。离线测试：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_chat_request.test_lesson -v
```

`fixtures.py` 只服务自动化测试，回答和用量都是固定的假数据。
