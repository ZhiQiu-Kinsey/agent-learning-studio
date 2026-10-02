# 第 9 课：上下文预算与压缩

本课有三组实验，都需要真实模型连接，`experiment` 输入决定跑哪一组。

| 实验 | 本地工具调用 | 模型请求 | 看什么 |
| --- | --- | --- | --- |
| `layouts` 三种布局 | 1 次 `lookup_lesson` | 3 次：完整、窗口、规则压缩 | 每种布局保留了哪些信息，回答有没有来源 |
| `compaction` 压缩策略 | 2 次 `lookup_lesson` | 4 次：1 次摘要 + 3 次探针 | 不压缩、清理旧工具结果、模型摘要之后，最早那次结果还答不答得出来 |
| `broken_pair` 拆开配对 | 1 次 `lookup_lesson` | 2 次：按条数截断、按配对截断 | 孤立的 tool 消息发给服务商后得到什么回应 |

`char_budget` 是 JSON 字符数上限，只约束规则压缩；它不是 token 数。响应里有 `usage` 就原样列出，没有就写“未知”。

历史消息由运行器组装：assistant 工具调用和旁支回复不是模型之前生成的，工具结果来自本次真实的 Python 读取。规则压缩只用读取结果拼模板，不调用模型；压缩对照里的摘要由当前模型生成，原文记录在第 1 轮响应里。

拆开配对实验故意绕过第 7 课的本地校验，把孤立的 tool 消息原样发出。服务商拒绝时记为 `lesson.provider_error`（状态码、错误类型、原文、`source`），不重试也不改写。离线测试里的 400 由 `fixtures.py` 模拟，`source` 为 `offline_fixture`；要看服务商真实的回应，需要用真实模型运行。`fixtures.py` 只服务自动化测试。

参考与取舍见 `docs/architecture/budget-memory-sources.md`。
