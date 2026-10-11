# 文本动作与原生工具调用（`text-actions`）

[English](README.md) · 简体中文

同一个问题（查询学生最近一次练习的得分并判断是否及格），用三种方式完成。本课需要真实模型连接。

| 预设 | 请求 | 动作写在哪 | 程序做什么 |
| --- | --- | --- | --- |
| 文本协议，带 stop | `stop: ["Observation:"]` | content 文本 | 正则解析 Action / Action Input，执行工具，把结果写成 `Observation:` 贴回 |
| 文本协议，去掉 stop | 不带 stop | content 文本 | 同上；模型自己写出的 Observation 被切下来记成 `lesson.fabricated_observation`，不进入上下文 |
| 原生工具调用 | `tools` 参数 | `tool_calls` 字段 | 按 `tool_call_id` 配对，用 tool 消息回传结果 |
| 去掉 stop，不及格的学生 | 不带 stop | content 文本 | 真实分数在及格线以下，便于看出编造的结论与真实结果相反 |

每次文本输出都记成 `lesson.parse`（原文、解析结果、finish_reason）。解析器只用 `raw_decode` 读 Action Input 开头的 JSON，其余格式错误一律记为失败并停止，不猜测修复。工具 `lookup_quiz_score` 查的是 `runtime.py` 里的本地成绩表，模型猜不到这些数字。

模型会不会在没有 stop 时编造 Observation，取决于所用模型和这一次采样，以本次记录为准。`fixtures.py` 只服务自动化测试，其中“编造”的内容是脚本写的，不代表任何真实模型。

**运行语言：**本课支持中文和英文运行。两份系统提示词、问题、工具描述与工具错误、解析错误和实验报告的文字写在 `locales/zh_CN.py` 与 `locales/en.py`；Thought、Action、Action Input、Observation、Final Answer 是解析器认的格式，两种语言一样。网页按界面语言选择运行语言，运行记录里写明这次运行的语言。

文本协议的 stop-and-parse 做法参考 [Hugging Face Agents Course](https://github.com/huggingface/agents-course)（Apache-2.0）Unit 1 的 `actions.mdx` 与 `dummy-agent-library.mdx`，提示词、解析器与实验由本项目编写，阅读范围见 `docs/architecture/reference-study.md`。

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_text_actions.test_lesson -v
```
