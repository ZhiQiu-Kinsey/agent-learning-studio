# 上下文预算与截取窗口（`context-budget`）

[English](README.md) · 简体中文

本课有两组运行，都需要真实模型连接，`experiment` 输入决定跑哪一组。

| 运行 | 本地工具调用 | 模型请求 | 看什么 |
| --- | --- | --- | --- |
| `layouts` 两种布局 | 1 次 `lookup_lesson` | 2 次：完整历史、截取窗口 | 窗口按 `char_budget` 截掉了哪些消息，回答有没有来源 |
| `broken_pair` 拆开配对 | 1 次 `lookup_lesson` | 2 次：按条数截断、按配对截断 | 孤立的 tool 消息发给服务商后得到什么回应 |

`char_budget` 是截取窗口允许的 JSON 字符数上限，不是 Token 数。`fit_window` 先留下 system 和当前问题，再从最新的消息往回一组一组地装，装不下就停；tool 消息和它的 assistant 调用算同一组，整组进出。响应里有 `usage` 就原样列出，没有就写“未报告”。

历史消息由运行器组装：assistant 工具调用和旁支回复不是模型之前生成的，工具结果来自本次真实的 Python 读取。资料键用课程 slug（`messages-context`、`application-state`）。

拆开配对实验故意绕过“上下文组成与消息协议”一课的本地协议检查，把孤立的 tool 消息原样发出。服务商拒绝时记为 `lesson.provider_error`（状态码、错误类型、原文、`source`），不重试也不改写。只有请求级的 4xx 算拒绝（由“上下文组成与消息协议”一课的 `rejection_status` 判断）；超时、限流、鉴权失败、连接失败和 5xx 不是服务商对这组消息的判断，照常报错。离线测试里的 400 由 `fixtures.py` 模拟，`source` 为 `offline_fixture`；要看服务商真实的回应，需要用真实模型运行。`fixtures.py` 只服务自动化测试。

规则压缩、清理旧工具结果和模型摘要放在下一课“上下文压缩与探针问题”（`lessons/lesson_context_compaction/`）；它从本课 `runtime.py` 导入字符数、本地字符串检查、组装工具配对与旁支讨论等小工具。

**运行语言：**本课有中文和英文两种运行语言。系统提示词、目标、默认追问、布局与截断的名字和两份报告写在 `locales/zh_CN.py` 与 `locales/en.py`；上下文压缩一课也用到的部分（资料原文、旁支讨论、`answer_text` 与 `usage_text` 的文字、读取失败的报错）写在 `locales/helpers/`。英文文字比中文长，同样的字符预算装下的消息更少，但两种语言的结论相同：默认预算会整组舍弃工具配对。

参考与取舍见 `docs/architecture/budget-memory-sources.md`。

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_09_context_budget.test_lesson tests.test_lessons_budget_memory -v
```
