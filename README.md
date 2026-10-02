# Agent Learning Studio

一个在本机运行的 Agent 可视化教学平台。它面向有编程基础、想弄懂 Agent 原理并亲手做出来的学习者。

- 先用几十行原生 Python 写出 Agent 循环，再一步步加上上下文管理、记忆、规划、工作流和多 Agent。
- 每一步都能在网页里看到证据：发给模型的完整请求、模型的响应、Python 工具的执行结果，以及可以逐步回放的事件轨迹。

## 特点

- **证据优先。**
  - 界面上的消息流、工具卡片、时间线都来自真实运行事件。
  - 教学示意单独画成虚线，并标注“非运行记录”。
  - 回放只读取已记录的事件，不会重新调用模型或工具。
- **每课一个完整闭环。** 每课按 **概念 → 最小实现 → 运行证据 → 实验 → 自检** 编排，课程页分五个场景：
  - 理解：概念卡、正文、微型自测、分步示意；
  - 读码：真实源码与行号批注，“本课新增”从 AST 计算；
  - 实验：对照组、观察点、导览回放、实验报告；
  - 自检：选择题、在自己的运行里找证据；
  - 回顾。
- **术语有解释，代码名有出处。**
  - 正文里的课程术语可以悬停查看释义，并区分本课新术语、前面课学过的术语和背景知识。
  - 正文提到的源码名字显示为代码样式，并可附本课说明。
- **多服务商。**
  - 百炼走手写的原生 HTTP 路径，展示完整请求体。
  - OpenAI、Anthropic、Gemini、DeepSeek、OpenRouter、Ollama 和 OpenAI 兼容服务经 LiteLLM 接入，界面如实标为“标准化请求/响应”。
- **课程即数据。**
  - 课程目录、术语表和每课的教学内容都是带 schema 校验的 JSON。
  - 后端自动发现新课程，新增一课不需要改平台代码。

## 学什么

课程分十个方向，从原生循环一路到工程交付：

- 原生基础：工具调用、依赖式多轮调用、错误与执行边界
- 任务与接口：任务验收、结构化输出、提示词与工具描述
- 上下文与状态：消息历史、应用状态、上下文预算与压缩、持久记忆
- 推理与控制模式：文本动作、待办清单、先规划后执行、反思与修订、工作流、编排者与评估者
- 知识与检索：资料处理、检索与引用、Agentic RAG
- 框架与运行编排：LangChain、LangGraph、人工介入与恢复
- 编码 Agent 与执行环境
- 质量与工程可靠性：评估、可观测性、可靠工具与信任边界
- 协议与工具服务：MCP
- 综合实践与交付：多 Agent、长时任务、毕业项目

完整课程表和每课的目标、实验与验收见 [课程大纲](docs/course-plan.md)。规划中的课程在网页里灰显，实现并验收后才开放。首次打开会先进入一段前置导学。

## 快速开始

需要 Python 3.12+、[uv](https://docs.astral.sh/uv/)、Node.js 22.12+ 和 npm。

Windows（PowerShell）：

```powershell
uv sync --dev
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe run_web.py
```

macOS / Linux：

```bash
uv sync --dev
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python run_web.py
```

打开 http://127.0.0.1:8765。之后只需执行最后一行；Windows 也可以运行 `start-web.ps1`。

## 连接模型

在网页右上角的“模型连接设置”里选择服务商，填写模型 ID，按需填写 API Base URL 和 API Key。

- 网页填写的配置只保存在后端内存，重启后回到环境变量和本地文件中的配置。
- 已有的密钥和地址不会回显到浏览器。

也可以用环境变量预先配置：

| 入口 | 密钥 | 模型 / 地址 |
| --- | --- | --- |
| 百炼（原生 HTTP） | `DASHSCOPE_API_KEY` | `local_config.py` 中的 `MODEL` / `API_URL` |
| OpenAI | `OPENAI_API_KEY` | `OPENAI_MODEL` / `OPENAI_BASE_URL` |
| Anthropic | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL` / `ANTHROPIC_BASE_URL` |
| Google Gemini | `GEMINI_API_KEY` | `GEMINI_MODEL` / `GEMINI_API_BASE` |
| DeepSeek | `DEEPSEEK_API_KEY` | `DEEPSEEK_MODEL` / `DEEPSEEK_BASE_URL` |
| OpenRouter | `OPENROUTER_API_KEY` | `OPENROUTER_MODEL` / `OPENROUTER_BASE_URL` |
| Ollama | 可选 `OLLAMA_API_KEY` | `OLLAMA_MODEL` / `OLLAMA_BASE_URL`（默认本机 11434） |
| OpenAI 兼容服务 | `CUSTOM_API_KEY` | `CUSTOM_MODEL` / `CUSTOM_API_BASE` |

- **百炼**：复制 `local_config.example.py` 为 `local_config.py`，填写接入地址和支持工具调用的模型 ID。这个文件已被 `.gitignore` 排除。
- **凭据互不借用**：每家服务商的凭据独立，切换服务商不会借用别家的密钥。
- **Ollama**：需要你自己准备本地服务和支持工具调用的模型，平台不会自动下载。

网页运行使用真实模型，会产生服务用量。没有可用配置时，网页会引导你完成接入，不会生成模拟回答。实现细节与限制见 [模型接入说明](docs/architecture/multi-provider-review.md)。

## 怎么用

1. 先读网页侧栏“开始之前”的导学。导学和自检都不调用模型。
2. 在“模型连接设置”里配好模型。有的课程只运行本地 Python，不需要模型。
3. 打开一课，按“理解 → 读码 → 实验 → 自检”往下走。实验里可以用预设，也可以换成自己的问题或换一个模型。
4. 在实验台选一条运行记录，单步或播放回放，对照观察点核对请求、响应和工具结果。

## 项目结构

```text
course/        模型请求、服务商适配、原生 Agent 循环与课程执行接口
server/        FastAPI 接口、课程发现与校验、内容 schema、事件信封、运行存储、术语检查
lessons/       每课一个目录：lesson.json、content.json、Python 实现、测试夹具与测试
curriculum/    课程目录 catalog.json、术语表 glossary.json、前置导学、导出的 JSON Schema
frontend/      React + TypeScript + Vite 前端
scripts/       校验、生成、新课脚手架、录制导出、用词报告
tests/         Python 测试（frontend/e2e/ 下是浏览器测试）
docs/          课程大纲与架构文档
```

运行记录脱敏后保存在 `.runtime/runs.sqlite3`，学习进度保存在浏览器本机，都只记录真实发生的动作。服务只监听 `127.0.0.1`，面向单人本地学习。

## 参与贡献

欢迎补课程、改正文、修问题。开始前请先读：

- [AGENTS.md](AGENTS.md)：项目约束、常用命令、各部分规范（人和编码代理都适用）。
- [新增课程与独立定制](docs/architecture/adding-lessons.md)：从登记课程到开放的完整流程。
- [术语与代码名](docs/architecture/terminology.md)：术语收录标准、统一用词表、作者自查流程。
- [开发验证](docs/architecture/validation.md)：测试与校验命令。
- [平台架构](docs/architecture/platform.md)、[前端结构](docs/architecture/frontend-workspace.md)、[事件信封 v2](docs/architecture/event-envelope-v2.md)。

提交前至少运行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts/validate_lessons.py
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend exec vitest run
```

PR 里请写明行为变化和验证结果。哪些只做了离线测试、哪些用真实模型验证过，要分开写。

## 致谢与许可

课程设计参考了以下教程，具体阅读范围、固定版本和许可证见 [课程来源](docs/architecture/reference-study.md)：

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners)
- [Hugging Face Agents Course](https://github.com/huggingface/agents-course)
- [《深入理解 AI Agent》](https://github.com/bojieli/ai-agent-book)
- [claude-cookbooks](https://github.com/anthropics/claude-cookbooks)

这些项目不参与平台运行。

复制或改编的第三方代码见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。其中 React Bits 组件使用 MIT + Commons Clause 许可，限制商业转售，再分发时请注意。
