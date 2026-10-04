# 前置学习章节：来源、取舍与内容边界

编写与核查日期：2026-09-30；课程来源调整日期：2026-10-01；扩写为七章、例子改用真实软件：2026-10-04。内容文件为 [onboarding.json](../../curriculum/onboarding.json)，接口为只读 `GET /api/onboarding`。七个章节独立于可执行课程注册表，不占用现有课号，不把规划课程升级为可执行状态。

## 内容约定

固定章节：`intro`（学习前言）、`agent-origins`（Agent 从哪来）、`how-llm-works`（LLM 怎样工作）、`llm-limits`（模型做不到什么）、`what-is-agent`（认识 Agent）、`workflow-or-agent`（工作流还是 Agent）、`learning-path-lab`（路线与工作台）。原 `learning-path` 与 `lab-evidence` 两章已合并进 `learning-path-lab`。

每章按 [讲解深度规范](content-depth.md) 编写：至少 4 节、1 道微测、1 个误区、1–2 个深入块，章末有参考资料和检查点。

例子不再用一个贯穿全章的“学习助手”，改为每章取一两样学习者多半用过的软件或设备（2026-10-04 起）：空调温控、扫地机器人、手机导航、短视频推荐、AlphaGo（Agent 从哪来）；输入法联想、聊天应用的“重新生成”（LLM 怎样工作）；不开联网搜索的聊天应用、编出来的论文链接（模型做不到什么）；Cursor、Claude Code、GitHub Copilot 这类编码 Agent（认识 Agent、路线与工作台）；报销审批、快递分拣、客服菜单（工作流还是 Agent）。对照表在 `intro` 章“导学里的例子”一节。描述真实产品时只写公开可见的行为，不写内部实现、所用模型和价格；功能会变的地方加“部分产品”“以产品文档为准”这类限定。历史事例（ELIZA、AlphaGo、OpenAI 2016 年公开的 CoastRunners 奖励写偏案例）只写公开记载的事实。

数据包含标题、摘要、预计阅读分钟数、学习目标、分节正文、可选列表/对照表、一个带检查点的思考练习和固定版本参考链接。预计分钟数是编辑估计，不是实测学习耗时。章节自检记录准备程度，不声称自动证明能力掌握。

内容用 v2 schema（`server/content_schema.py` 的 `Onboarding`），每章只有理解与自检两个场景。正文块为 prose、compare、steps、callout，另有 micro-quiz、misconception、deep-dive、flow（教学示意）、objectives 与 references；纯文本结构不含任意 HTML、远程脚本或源码执行内容。前置阅读与自检不调用模型。课程可用性、模块和课程数量继续来自现有 curriculum API，前置文字不硬编码可用数量或把未来课程写成已交付。

## 课程资料的参考范围

下表是 2026-10-01 版四章的阅读证据，保留备查。2026-10-04 扩写七章时新增的阅读范围（claude-cookbooks、learn-claude-code、Hello-Agents，以及 Hugging Face 与《深入理解 AI Agent》的更多页面）登记在 [reference-study.md](reference-study.md) 第 8 节。

| 来源与固定版本 | 本次直接读取的原文 | 吸收进前置章节的方法 |
| --- | --- | --- |
| [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners/tree/25b7985f3b2dc37a84f4a7387ccd3c9f0e5b1595) | 本地 STUDY_GUIDE.md；01-intro-to-ai-agents/README.md 不在本地稀疏检出中，已从官方 raw URL 按同一 commit 读取完整原文 | 先说明目标与适用场景；每课检查运行层新增的能力。导学不沿用贯穿全章的项目例子，改为各章分别取常见软件举例（见“内容约定”） |
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

验收应覆盖：无需模型配置即可读取七章；每章的参考链接都固定到 commit，且只来自 reference-study.md 登记过的项目；规划课仍不能运行；加载失败可恢复；首次进入先显示前置入口；完成/返回/继续与课程导航配合；文字、表格与自检在移动端可用。前端自检属于用户自我报告，不对未执行的 Python 实验发放“已掌握”结论。

