# 上下文组成与应用状态的参考范围与取舍

适用课程：`messages-context`（上下文组成与消息协议）、`application-state`。

当前课程参考范围于 2026-10-01 调整为三份正式教程。

以下是本次实际阅读的固定本地快照；只借鉴机制与教学组织，课程文字和实验为原创，不表示读完了这些仓库。

| 资料 | 固定 commit | 本次阅读位置 | 借鉴与取舍 |
| --- | --- | --- | --- |
| Hugging Face Agents Course | `b3946b1d09d29c65736e219d48a8a736a2c52154` | `units/en/unit1/messages-and-special-tokens.mdx` 的消息角色、chat template；`agent-steps-and-structure.mdx` 的行动/观察循环 | 借鉴角色和消息历史说明；不把某个模型的特殊 token 格式当作所有供应商的原始报文。 |
| Microsoft AI Agents for Beginners | `25b7985f3b2dc37a84f4a7387ccd3c9f0e5b1595` | `STUDY_GUIDE.md` 的 Context、Memory、Evaluation and Observability 及 15-Minute Review Routine 小节；`13-agent-memory/README.md` 的记忆范围 | 借鉴每课目标、风险、验证问题的组织；第 8 课不提前声称已实现跨运行记忆。 |
| 《深入理解 AI Agent》 | `b789c97a8f3de5b405a6f6dfa8289208d679d0b8` | `book/chapter1.md` 的“现代 Agent = LLM + 上下文 + 工具”及 Model–Harness–Environment；`chapter1/context/agent.py` 的 `_prepare_messages_for_api`、`_build_context` 和上下文消融 | 借鉴观察经 Harness 构造成可见上下文、对照应改变输入信息的实验方法；本课只删除完整可移除消息，不留下失配的工具回执。 |

本课的 `presentation.flow` 仅为教学示意。模型请求、响应以及状态快照须从本次事件查看；离线 fixture 只用于自动测试。
