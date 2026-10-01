# 前置学习章节：来源、取舍与内容边界

编写与核查日期：2026-09-30；课程来源调整日期：2026-10-01。内容文件为 [onboarding.json](../../curriculum/onboarding.json)，接口为只读 `GET /api/onboarding`。四个章节独立于可执行课程注册表，不占用现有课号，不把规划课程升级为可执行状态。

## 内容约定

固定章节：`intro`（学习前言）、`what-is-agent`（认识 Agent）、`learning-path`（学习路线与准备）、`lab-evidence`（使用实验工作台）。

数据包含标题、摘要、预计阅读分钟数、学习目标、分节正文、可选列表/对照表、一个带检查点的思考练习和固定版本参考链接。预计分钟数是编辑估计，不是实测学习耗时。章节自检记录准备程度，不声称自动证明能力掌握。

分节 kind 为 explanation、comparison、steps 或 warning；纯文本结构不含任意 HTML、远程脚本或源码执行内容。前置阅读与自检不调用模型。课程可用性、模块和课程数量继续来自现有 curriculum API，前置文字不硬编码可用数量或把未来课程写成已交付。

## 三份课程资料的参考范围

当前课程来源仅保留 Microsoft、Hugging Face 和《深入理解 AI Agent》三份教程。下表保留其已有固定版本阅读证据。

| 来源与固定版本 | 本次直接读取的原文 | 吸收进前置章节的方法 |
| --- | --- | --- |
| [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners/tree/25b7985f3b2dc37a84f4a7387ccd3c9f0e5b1595) | 本地 STUDY_GUIDE.md；01-intro-to-ai-agents/README.md 不在本地稀疏检出中，已从官方 raw URL 按同一 commit 读取完整原文 | 先说明目标与适用场景；保留一个持续演进的学习助手；每课检查新增能力 |
| [Hugging Face Agents Course](https://github.com/huggingface/agents-course/tree/b3946b1d09d29c65736e219d48a8a736a2c52154) | 本地 units/en/unit0/introduction.mdx、onboarding.mdx；unit1/what-are-agents.mdx 和 agent-steps-and-structure.mdx 的定义与循环部分 | 在动手前提供独立导学；说明 Python/LLM 基础；理论、观察、实践和自检形成递进 |
| [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book/tree/b789c97a8f3de5b405a6f6dfa8289208d679d0b8) | 本地 book/introduction.md；book/chapter1.md 的 Model–Harness–Environment、上下文与工具边界段落 | 区分模型决策、程序执行与环境反馈；从开始就强调任务目标、证据和验收，而不是只追求演示跑通 |

参考仓库不属于 API 公开路径。平台参考链接使用官方固定 commit，不依赖特定本机目录。

## 有意纠正或保留的概念边界

- Microsoft 提供更广的智能体分类。当前前置明确只聚焦 LLM Agent，不声称 Agent 一定依赖 LLM，或拥有多个角色才叫 Agent。
- Hugging Face 使用 Thought–Action–Observation 作为教学结构。当前平台只把请求、动作和观察作为可检查事件，不把模拟独白、转圈或动效当作模型隐含推理的证明；提示词也不能取代确定性权限校验。
- 工程公式“模型 + 上下文 + 工具”是帮助理解的组件视角。环境保持在交互边界之外；上下文不等于磁盘上的所有信息，保存记忆也不等于修改模型参数。
- 本平台真实模型请求、Python 工具执行、前端回放是不同动作。回放不再调用模型；SDK 标准化数据不冒充原始 HTTP；停止请求不保证已经发出的上游请求立即结束。
- 正常结束、任务正确、证据充分与过程约束分别检查。前置练习原创，不复制参考课程的长篇正文、图像或代码，也不承诺未来课程已实现。

## 接口与验收

`server/app.py` 从固定的本地 JSON 文件读取前置内容，不接受文件路径参数。读取或解析失败返回简短 503，不回显路径或异常内容。GET 不修改模型连接、运行状态或课程注册表。

验收应覆盖：无需模型配置即可读取四章；三份课程参考都有明确来源；规划课仍不能运行；加载失败可恢复；首次进入先显示前置入口；完成/返回/继续与课程导航配合；文字、表格与自检在移动端可用。前端自检属于用户自我报告，不对未执行的 Python 实验发放“已掌握”结论。

