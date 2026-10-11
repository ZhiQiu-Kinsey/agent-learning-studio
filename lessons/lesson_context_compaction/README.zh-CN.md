# 上下文压缩与探针问题（`context-compaction`）

[English](README.md) · 简体中文

同一段历史，比较三种压缩做法，用一个探针问题检查最早那次工具结果还在不在。本课需要真实模型连接。

运行器先后真实读取两份资料（`messages-context`、`application-state`），中间夹着 `noise_repeats` 轮旁支讨论。目标、第一次读取和旁支讨论是“较早部分”，第二次读取和最后一轮旁支讨论是“最近部分”。每种压缩只改写较早部分，最近部分原样保留。

| 轮次 | 请求 | 较早部分变成什么 |
| --- | --- | --- |
| 1 | 不压缩（对照） | 原样保留 |
| 2 | 规则压缩 | `rule_record` 按目标、约束、来源、事实、待办拼的一条记录；超过 `char_budget` 就拒绝，这一轮不发请求 |
| 3 | 清理旧工具结果 | 消息条数不变，较早那条工具结果的内容换成 `cleared` 说明 |
| 4 | 摘要请求 | 较早部分原文加一条压缩指令（`summary_style` 决定用哪条） |
| 5 | 摘要压缩 | 第 4 轮模型写的摘要 |

第 1、2、3、5 轮都问同一个探针问题：“最早读取的那份资料来自哪一项？它的原话是什么？”实验报告分开写两件事：原话还在不在上下文里（本地字符串检查，记在 `lesson.compaction` 的 `phrase_in_context`），回答有没有同时答出来源名和原话（关键词初筛，命中也要读原文复核）。

| 练习 | 输入 | 模型调用数 |
| --- | --- | --- |
| 三种压缩，同一个探针问题 | 预算 300，保留来源的摘要指令 | 5 |
| 规则压缩的预算装不下证据 | 预算 100 | 4 |
| 换一条简短的摘要指令 | `summary_style=brief` | 5 |

字符数是本地 JSON 长度，不是 Token；用量只展示服务商响应实际返回的 `usage`，没有就写“未报告”。字符数、本地字符串检查、组装工具配对与旁支讨论、资料读取这些小工具从“上下文预算与截取窗口”一课的 `runtime.py` 导入。`fixtures.py` 只服务自动化测试，其中的摘要和回答是脚本写的。

**运行语言：**本课有中文和英文两种运行语言。目标、探针问题、系统提示词、摘要指令、规则压缩记录的模板、四组的名字和报告文字写在 `locales/zh_CN.py` 与 `locales/en.py`；资料原文和旁支讨论来自“上下文预算与截取窗口”一课的 `locales/helpers/`。英文的规则压缩记录同样装得进默认预算 300、装不进 100，两种语言的结论相同。

规则压缩与模型摘要的取舍参考《深入理解 AI Agent》第 2 章“上下文压缩策略”与 `chapter2/context-compression/compression_strategies.py` 的思路，代码与实验由本项目编写；阅读范围见 `docs/architecture/budget-memory-sources.md`。

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_context_compaction.test_lesson -v
```
