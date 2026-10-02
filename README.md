# Agent Learning Studio

本地运行的 Python Agent 可视化教学平台。把课程目标、实际源码、完整模型请求/响应、工具执行和回放放在同一网页中。

当前 **第 1–10 课可运行**，覆盖原生基础、任务与接口、上下文与状态。第 1–3、5–7、9 课使用真实模型连接；第 4、8、10 课运行真实本地 Python，分别学习独立验收、状态生命周期和 SQLite 持久记忆，无需模型密钥。

首次打开先进入 **4 节前置导学、19 个小节**：学习前言、认识 Agent、学习路线与准备、使用实验工作台。结合下述三份课程参考材料，用概念对照、学习目标和自检建立基础，再开始第一课；已经进入过课程的浏览器会直接回到课程入口，侧栏可随时返回导学。

侧栏直接读取真实课程目录，按 **大类 → 模块 → 课次** 展开。已实现课程可进入，计划课程置灰；完整课程表仍能查看全部计划详情。课程导读提供分步调用教学示意、概念卡片、原文深读和源码入口；实验工作台的消息流和工具状态来自实际事件，随回放同步。

先看网页侧栏的“完整课程表”，或阅读 [详细课程大纲](docs/course-plan.md)：**8 大类、19 个小模块、29 课、6 个选修方向**，每课有目标、知识点、实验、验收和先修关系。其余 19 课为规划中，保持灰显；前三章已接入真实实验。

`curriculum/catalog.json` 是课程目录、网页和文档的共同数据源。修改后执行 `python scripts/export_curriculum.py` 更新 Markdown；不必维护多套课号。

## 启动网页

环境：Python 3.12+、Node.js 22.12+（本机验证使用 Node 24）、uv、npm。

首次安装或下载项目后，在项目目录执行：

```powershell
uv sync --dev
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe run_web.py
```

打开 **http://127.0.0.1:8765**。保持 Python 进程运行；Ctrl+C 停止服务。依赖和前端构建完成后，之后只需执行最后一行，或运行 `start-web.ps1`。

在 IDE 中，将启动文件设为根目录 `run_web.py`，解释器选本项目 `.venv`。服务会继承 IDE 配置的 `DASHSCOPE_API_KEY`。

## 第一遍如何练习

先阅读侧栏“开始之前”四节导学，确认基本概念、Python 基础和模型配置方式。导学与自检不调用模型。完成后再按以下顺序实践：

1. 在“模型连接设置”配置真实模型，选择第 1 课运行“计算加法”。检查第一次 request 中的 `tools`、response 中的 `tool_calls`，以及 Python 返回的 `42`。
2. 查看第二次 request：找到 `role: tool` 和对应的 `tool_call_id`，理解模型如何收到工具结果。
3. 选择第 2 课，运行“小时与分钟相加”，比较时间工具的实际输出与随后加法工具的参数。
4. 选择第 3 课，运行“除数为零”，观察 `ok: false` 如何回传。未知工具和损坏参数另外由内部程序测试覆盖，不伪称真实模型提出过这些调用。
5. 选择一次执行记录，单步或播放回看。回放使用已经收到的数据，不重新调用模型或工具。
6. 输入自己的问题，比较不同输入下的实际模型决策；之后可用同一题目对照不同模型。
7. 阅读导读里的原理与观察点，进入“课后自测”选择答案，再点“检查答案”查看解释；可以重新作答，自测不调用模型。

继续第二、三章：第 4 课用固定任务卡区分流程结束和验收通过；第 5 课逐层验证 JSON、字段与业务事实；第 6 课做单变量模型对照；第 7–9 课分别研究消息历史、程序状态和上下文压缩；第 10 课在本地 SQLite 中保存、恢复、更新、过期与删除学习记忆。结构化实验的参数可在 JSON 面板中编辑，报告可定位原始事件并随回放变化。固定任务课的问题框明确标为学习者备注。

第 10 课真实运行使用 `.runtime/lesson10-memory.sqlite3`，namespace 是教学分区，不是用户认证。先“保存与重开连接”，再“只读恢复上次记忆”，可以核对跨运行保存的值、来源和版本。内部测试使用临时数据库；它不会改写你的教学记忆。

网页运行使用真实模型，会产生服务用量；没有可用模型配置时引导完成接入，不自动生成模拟回答。内部保留确定性适配器供自动化测试使用，没有学生模拟入口。认证请求头不送到前端。

## 模型连接

使用百炼原生入口时，复制 `local_config.example.py` 为 `local_config.py`，填写百炼接入地址和支持工具调用的模型 ID。

在右上角“模型连接设置”选择服务商，填写厂商提供的模型 ID；按需填写 API Base URL 与 API Key。配置只保存在后端内存，重启后恢复环境变量/本地文件配置。已有密钥和地址不回显到浏览器；空白密钥输入表示保留已配置值。

默认百炼使用 `DASHSCOPE_API_KEY` 和 `local_config.py`，保留原生 HTTP 教学路径。其他接入使用 LiteLLM SDK，各自的凭据独立；切换到另一家服务不会借用百炼密钥。

| 入口 | 密钥环境变量 | 模型 / 地址环境变量 |
| --- | --- | --- |
| 百炼（原生 HTTP） | DASHSCOPE_API_KEY | local_config.py 中的 MODEL / API_URL |
| OpenAI | OPENAI_API_KEY | OPENAI_MODEL / OPENAI_BASE_URL |
| Anthropic | ANTHROPIC_API_KEY | ANTHROPIC_MODEL / ANTHROPIC_BASE_URL |
| Google Gemini | GEMINI_API_KEY | GEMINI_MODEL / GEMINI_API_BASE |
| DeepSeek | DEEPSEEK_API_KEY | DEEPSEEK_MODEL / DEEPSEEK_BASE_URL |
| OpenRouter | OPENROUTER_API_KEY | OPENROUTER_MODEL / OPENROUTER_BASE_URL |
| Ollama | 可选 OLLAMA_API_KEY | OLLAMA_MODEL / OLLAMA_BASE_URL，默认本机 11434 |
| OpenAI compatible | CUSTOM_API_KEY | CUSTOM_MODEL / CUSTOM_API_BASE |

托管于百炼的 DeepSeek 模型仍使用百炼或兼容服务入口；“DeepSeek”入口表示直接接入该服务，不能仅凭模型名称切换厂商。Ollama 需要你已有可访问的本地服务和支持工具调用的模型，本平台不自动下载模型。

观察台将原生路径标为完整请求/响应正文，将 SDK 路径标为“标准化请求/响应”。SDK 数据经过适配，不冒充原始线上 HTTP 报文；SDK 事件代表一次 SDK 调用，不保证等于一次底层网络尝试。实现与限制见 [多供应商接入说明](docs/architecture/multi-provider-review.md)。

网页显示的模型名称来自实际后端配置。修改本地 Python 课程或模型配置后重启服务。网页“停止”会阻止后续调用；已发出的上游 HTTP 请求可能继续至返回或 60 秒网络超时，此时下一次运行可能提示仍在执行。

## 目录与扩展

```text
AgentStart/
├── run_web.py                 # 网页服务入口
├── start-web.ps1              # Windows 启动入口
├── main.py                    # 原有百炼命令行课程入口
├── local_config.example.py    # 百炼配置模板；本机配置由 .gitignore 排除
├── course/                    # 请求传输、模型适配、原生 Agent 循环
├── curriculum/
│   ├── catalog.json           # 分类、课次、目标、实验与验收的唯一规划数据源（42 课）
│   ├── onboarding.json        # 前置导学（第 0 章），content v2 格式
│   ├── glossary.json          # 术语表单一来源
│   └── schema/                # 由 Pydantic 导出的内容 JSON Schema
├── lessons/                   # 各课 lesson.json、content.json（v2）、Python、录制与测试 fixture
├── server/
│   ├── app.py                 # HTTP、SSE、运行接口、执行互斥与数据边界
│   ├── catalog.py             # 自动发现课程清单、校验与源码白名单
│   ├── content*.py            # 内容 v2 schema、迁移阶梯、加载与译文层
│   ├── envelope.py / run_store.py  # 事件信封 v2 与 SQLite 运行存储
│   ├── code_reading.py        # 读码场景：从真实源码计算新增符号与批注校验
│   ├── selectors.py / illustrations.py  # 观察点选择器与教学示意契约
│   └── recordings.py          # 随课真实运行录制的导出与校验
├── frontend/                  # React + TypeScript + Vite（结构见 docs/architecture/frontend-workspace.md）
├── tests/                     # Python 行为与 API 测试
└── docs/architecture/         # 架构约定、重构方案、课程来源
```

规划新课先修改 `curriculum/catalog.json`。使用 `python scripts/new_lesson.py --id 11 --slug document_loading --dry-run` 预览脚手架；去掉 `--dry-run` 创建目录，复杂课程加 `--kind custom`。课号需替换为实际仍处于 `planned` 的课程。生成器不会解锁课程或覆盖已有目录。

每课通过自己的 `lesson.json` 声明源码、练习、运行器和测试 fixture；后端自动发现，无须再编辑 `server/catalog.py`。执行 `python scripts/validate_lessons.py` 检查清单与内容，完成实现、教学和测试后才把目录状态改为 `available`。普通课复用平台循环和页面，复杂课可独立实现 Python 运行器或 React 插槽，同时沿用停止、事件、模型连接与回放。详细流程见 [新增课程与独立定制](docs/architecture/adding-lessons.md)；架构背景见 [平台架构](docs/architecture/platform.md)。源码在网页中只读，本地编辑器负责修改。

课程参考 Microsoft AI Agents for Beginners、Hugging Face Agents Course 和《深入理解 AI Agent：设计原理与工程实践》。它们不参与平台运行，也不需要下载到特定本机目录。固定版本与借鉴范围见 [课程来源](docs/architecture/reference-study.md)。

前置章节实际如何取三份课程材料之长，见 [导学来源与教学取舍](docs/architecture/onboarding-sources.md)。

## 交互与动效

全站的视觉母题是 **Agent 舞台**：用户、运行层、模型、工具、状态与记忆之间的连线由每个真实事件点亮。实验场景同时提供：

- 时间线：可切换按真实时间排布或等距排布；
- 上下文胶片：每轮实际发送的消息，新增项高亮；
- 工具卡片；
- 导览回放：讲解你自己的那次运行，证据缺失时会如实说明。

教学示意由同一个舞台渲染，但画成虚线，并加上“教学示意 · 非运行记录”水印。

动效由统一的动效层管理，只跟随系统的“减少动画”设置：系统开启时页面静止，动态背景退化为同色渐变；重效果按需加载、离屏暂停，WebGL 同屏最多两个。⌘K（Ctrl+K）打开命令面板；实验中可用空格、方向键和 `[ ]` 控制回放，`?` 查看全部快捷键。结构见 [前端结构](docs/architecture/frontend-workspace.md)，方案见 [平台重构方案](docs/architecture/redesign-plan.md)。

## 开发与验证

后端保持运行，前端开发可执行：

```powershell
npm.cmd --prefix frontend run dev
```

使用终端显示的 Vite 地址，`/api` 代理到本机 `8765`。发布到本地 Python 服务前重新 `npm.cmd --prefix frontend run build` 并重启服务。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend exec vitest run
# 服务与前端构建已就绪时，在 frontend 目录执行浏览器测试
Set-Location frontend
npx.cmd playwright test
```

浏览器测试使用系统 Chrome，默认连接 `http://127.0.0.1:8765`。测试在网络边界切换到内部确定性适配器，验证真实 Python 工具与界面而不产生模型用量；用户网页仍只提供真实运行。验证范围、运行方式与边界见 [开发验证](docs/architecture/validation.md)。

## 原有命令行课程

```powershell
.\.venv\Scripts\python.exe main.py --lesson 1
.\.venv\Scripts\python.exe main.py --lesson 2
.\.venv\Scripts\python.exe main.py --lesson 3
.\.venv\Scripts\python.exe -m lessons.lesson_03_fail_safely.offline_demo
```

`main.py` 默认第 3 课；网页入口为 `run_web.py`，构建源入口为 `frontend/index.html`。

本平台面向单人本地学习：运行记录脱敏后保存在 `.runtime/runs.sqlite3`，学习进度保存在浏览器本机，都只记录真实发生的动作。共享部署需要另行设计身份与存储。

