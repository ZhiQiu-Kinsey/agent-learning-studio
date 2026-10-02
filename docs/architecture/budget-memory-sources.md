# 上下文预算、压缩与持久记忆的参考范围与取舍

适用课程：`context-budget`、`context-compaction`、`persistent-memory`、`memory-lifecycle`（2026-10-03 由原第 9、10 课各拆为两课）。

当前课程参考范围于 2026-10-01 调整为三份正式教程。

仅记录本次实际查看的章节、源码与固定本地 commit。参考实验设计与机制，不复用上游正文或代码，也不表示读完了整个仓库。

| 资料 | 固定 commit | 阅读范围 | 用于本课的取舍 |
| --- | --- | --- | --- |
| 《深入理解 AI Agent》 | `b789c97a8f3de5b405a6f6dfa8289208d679d0b8` | `book/chapter2.md` 的“上下文压缩策略”及“Agent 状态栏”；`chapter2/context-compression/compression_strategies.py` 的 `CompressionStrategy`、`CompressedContent` 与 `compress_for_history`；`book/chapter3.md` 的“用户记忆系统”、轨迹与长期记忆、冲突更新 | 第 9 课做可审计的规则摘要与字符预算，暂不把书中模型摘要实验的效果移植为本课结果，也不把字符数当成 tiktoken 结果；第 10 课用 SQLite 检查明确写入、恢复、冲突和删除。 |
| Microsoft AI Agents for Beginners | `25b7985f3b2dc37a84f4a7387ccd3c9f0e5b1595` | `STUDY_GUIDE.md` 的 Context、Memory 与复习问题；`13-agent-memory/README.md` 的工作、短期、长期记忆及生成、存储、检索、更新、遗忘 | 借鉴分层与生命周期，不移植 Mem0、Azure AI Search 或其账号依赖。 |
| Hugging Face Agents Course | `b3946b1d09d29c65736e219d48a8a736a2c52154` | `units/en/unit1/messages-and-special-tokens.mdx` 的消息历史与角色；`agent-steps-and-structure.mdx` 的观察进入下一次决策 | 第 9 课用合法消息布局比较可见证据；不把教材聊天模板写成单一供应商协议。 |

`context-budget` 报告的本地长度为序列化 JSON 字符数，并单列供应商实际返回的 `usage`；两者不能换算为同一个精确值。`persistent-memory` 的 namespace 只是教学分区，不能替代用户认证。
