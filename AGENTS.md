# Repository Guidelines（仓库贡献指南）

## 项目背景与建设方向

本项目从 Python 控制台中的百炼工具调用练习发展为长期使用的可视化 Agent 教学平台，面向已有编程基础、希望理解 Agent 原理并动手实践的学习者。网页统一展示课程、真实源码、模型请求与响应、工具执行和事件回放。

教学按“概念 → 最小实现 → 运行证据 → 实验 → 自检”展开：先掌握原生 Python Agent 循环，再逐步学习上下文与记忆、可靠工具、RAG、LangChain/LangGraph、评估观测、多 Agent 和 MCP。模型接入不限定百炼，通过原生 HTTP 教学路径与 LiteLLM 适配多服务商。

先维护分层课程表，再逐课补充实现；规划课程必须明确标注状态。新增课程复用现有页面与事件协议，仅在教学需求确有差异时增加组件。平台基础设施优先采用成熟库，手写最小 Agent 循环用于讲解原理。回放只读取已有事件，不重新请求模型或执行工具。

## 当前课程参考资料

当前参考以下三份教程。它们不参与平台运行；阅读或复现范围应以实际查看的章节和固定版本为准。

| 资料（本地目录） | 主要借鉴方向 |
| --- | --- |
| [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners)（`ai-agents-for-beginners/`） | 主题分类、学习目标、独立课目录和连续项目练习 |
| [Hugging Face Agents Course](https://github.com/huggingface/agents-course)（`agents-course/`） | 原理到框架的分阶段路线、Agentic RAG、练习与评估闭环 |
| [《深入理解 AI Agent》](https://github.com/bojieli/ai-agent-book)（`ai-agent-book/`） | 机制解释、上下文工程、受控实验、任务验收与工程验证 |

具体阅读范围与固定版本见 `docs/architecture/reference-study.md`。复用源码或正文前核对对应许可证并保留署名；不直接搬入参考项目的完整依赖。历史调研不代表当前上游版本，更新依赖时重新核对官方资料。

## 项目结构与模块职责

Agent Learning Studio 是本地 Agent 教学平台，后端采用 Python/FastAPI，前端采用 React、TypeScript、Vite 和 Tailwind。

- `course/`：模型请求、服务商适配和 Agent 执行循环。
- `server/`：REST/SSE 接口、课程注册及确定性测试适配器。
- `lessons/lesson_NN_topic/`：各课 Python 实现、教学内容和说明文档。
- `curriculum/catalog.json`：课程规划的唯一数据源；生成的课程大纲位于 `docs/course-plan.md`。
- `frontend/src/`：前端，结构见 `docs/architecture/frontend-workspace.md`。
  - `scenes/`：课程页五个场景；`stage/`：舞台、胶片、时间线、工具卡片。
  - `content/`：v2 类型、块渲染、选择器、导览；`motion/`：统一动效层。
  - `i18n/`：多语言，文案只写在 locales；`progress/`：本机学习进度。
  - React Bits 组件放在 `components/react-bits/`，shadcn/ui 组件放在 `components/ui/`；业务样式按模块放在 `styles/`，`workspace.css` 仅保留导入入口。
- `tests/`、`frontend/e2e/`：Python 测试和浏览器测试。`frontend/dist/` 为构建产物，`.runtime/` 存放本地诊断文件。

## 构建、测试与开发命令

使用 Windows PowerShell、Python 3.12+ 和 Node.js 22.12+。除特别说明外，在本文件所在目录执行：

```powershell
uv sync --dev                                 # 安装 Python 依赖
npm.cmd --prefix frontend ci                   # 按锁文件安装前端依赖
npm.cmd --prefix frontend run build            # 类型检查并构建前端
.\.venv\Scripts\python.exe run_web.py           # 启动 localhost:8765 服务
npm.cmd --prefix frontend run dev              # 启动 Vite，代理 /api 到后端
# 运行 Python 测试
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
# 修改课程目录后重新生成大纲
.\.venv\Scripts\python.exe scripts/export_curriculum.py
# 修改事件信封常量表（server/envelope.py）后重新生成前端镜像
.\.venv\Scripts\python.exe scripts/export_trace_contract.py
# 新增课程前预览脚手架，课号替换为实际 planned 项
.\.venv\Scripts\python.exe scripts/new_lesson.py --id 11 --slug document_loading --dry-run
# 校验所有实现清单和教学内容（包括 planned 草稿与随课录制，不调用模型）
.\.venv\Scripts\python.exe scripts/validate_lessons.py
# 把一次真实模型运行原样导出为随课录制（规则见 docs/architecture/event-envelope-v2.md 第 6 节）
.\.venv\Scripts\python.exe scripts/export_recording.py --run <run_id> --name <kebab-case 名称>
# 内容 v2：迁移与规范化（--check 只检查）、导出 schema、生成前端类型
.\.venv\Scripts\python.exe scripts/migrate_content.py --check
.\.venv\Scripts\python.exe scripts/export_content_schema.py
npm.cmd --prefix frontend run content:types
# 前端单元测试与翻译键检查
npm.cmd --prefix frontend exec vitest run
npm.cmd --prefix frontend run i18n:check
```

浏览器测试前先构建前端并启动后端，再进入 `frontend/` 执行 `npx.cmd playwright test`（可用 `AGENT_LAB_URL` 指定其他端口）。测试使用已安装的 Chrome；由于后端执行互斥，测试按顺序运行。测试用 role、`data-testid` 和 `e2e/i18n.ts` 的文案键定位，选择器基线与硬编码中文基线都只许减少。

## 编码风格与命名约定

Python 使用 4 空格缩进，TypeScript/CSS 使用 2 空格缩进。Python 函数和变量使用 `snake_case`，React 组件使用 PascalCase，Hooks 使用 `useSomething`。前端已安装 Prettier，仅格式化本次修改涉及的文件，避免无关改动。

优先复用免费 React Bits 组件，缺少的能力再使用 shadcn/ui 补充。保留无障碍支持、减少动态效果设置和上游许可证声明。界面文案写在 `frontend/src/i18n/locales/`，不在组件中硬编码中文；动效判断只用 `frontend/src/motion`，不直接写 `prefers-reduced-motion`；运行数据只来自真实事件，教学示意必须标注“非运行记录”。

## 测试要求

后端使用 Python `unittest`，文件命名为 `test_*.py`；浏览器测试使用 Playwright，文件命名为 `*.spec.ts`。目前没有数值覆盖率门槛。修改执行流程、服务商适配或交互逻辑时，应补充相应行为回归测试。自动化测试使用确定性模型数据并执行真实 Python 工具；真实模型调用的验证结果须单独说明。

## 提交与拉取请求规范

当前目录没有 Git 历史，以下为建议规范：提交标题简洁描述动作，例如 `feat: 添加课程导航`。PR 应说明行为变化、关联相关问题、列出验证结果；涉及界面调整时附上截图。

## 安全与配置

凭据仅保留在服务端。不得提交 `local_config.py`、在执行记录中暴露密钥或将密钥存入浏览器存储。用户练习使用真实模型连接，模拟能力仅用于测试。SDK 标准化请求与响应须准确标注，不得称为原始 HTTP 报文。

新增课程由 `lessons/lesson_*/lesson.json` 自动发现，标题、简介、目标和状态只维护在 `curriculum/catalog.json`。先生成并验证 planned 草稿，实现与验收完成后才改为 available，不再手工向 `server/catalog.py` 增加课程分支。普通课复用原生循环与通用页面；复杂课允许独立运行器和前端插槽，但仍使用共享模型连接、输入校验、停止、事件与回放。完整接口和操作流程见 [新增课程与独立定制](docs/architecture/adding-lessons.md)。
