# AGENTS.md

本文件给在本仓库工作的人和编码代理（Claude Code、Codex 等）看：项目是什么、哪些约束不能破、常用命令、怎么新增和扩展课程、各部分的写法规范。
细节以 `docs/architecture/` 下的文档为准，这里只写要点和入口。

## 项目

Agent Learning Studio 是一个本地运行的 Agent 可视化教学平台，面向有编程基础、想弄懂 Agent 原理并动手实践的学习者。

- 网页把课程讲解、真实源码、完整的模型请求与响应、工具执行和事件回放放在一起。
- 每课按 **概念 → 最小实现 → 运行证据 → 实验 → 自检** 展开。
- 课程路线：先手写原生 Python Agent 循环，再学上下文与记忆、可靠工具、推理与控制模式、RAG、LangChain/LangGraph、评估与观测、多 Agent 和 MCP。
- 模型接入不绑定某一家：百炼走手写的原生 HTTP 教学路径，其他服务商经 LiteLLM 接入。

技术栈：后端 Python 3.12+、FastAPI、SSE、SQLite；前端 React、TypeScript、Vite、Tailwind CSS 4、React Bits、shadcn/ui。

## 红线

下面每一条都有测试或校验守着；改动若需要突破其中一条，先停下来和维护者确认。

1. **运行数据只来自真实事件。** 不为效果伪造或模拟运行结果。
   - 教学示意必须 `provenance=illustration`，并通过 `server/illustrations.py` 的契约；界面标注“教学示意 · 非运行记录”。
2. **回放只读。** 回放只读取已记录的事件，不重新请求模型，也不重新执行工具。
3. **不冒充原始报文。** SDK 标准化的请求与响应要如实标注，不得称为原始 HTTP 报文。
4. **密钥只在后端。**
   - 不提交 `local_config.py`。
   - 不把密钥写进运行记录、日志、提交信息或浏览器存储。
5. **测试数据与真实验证分开说。**
   - 自动化测试用确定性模型数据，但必须执行真实 Python 工具。
   - 夹具（`lessons/*/fixtures.py`）只服务测试，网页上没有模拟入口。
   - 真实模型的验证结果要单独说明：写明模型、样本和调用次数。没做过的，不声称做过。
6. **课程先以 planned 草稿通过校验。** 实现、测试和教学验收都完成后，才把 `curriculum/catalog.json` 里的状态改为 `available`。
7. **测试保持通过。**
   - 现有测试必须保持通过，改了行为的地方要补测试。
   - 前端选择器基线和硬编码中文基线只许减少。
8. **复用前核对许可证。** 复用参考教程或上游代码前，先核对许可证、保留署名，并登记到 `THIRD_PARTY_NOTICES.md`。

## 目录

| 路径 | 职责 |
| --- | --- |
| `course/` | 模型请求与服务商适配（原生 HTTP、LiteLLM）、原生 Agent 循环、`RunContext` 执行接口、运行语言（`i18n.py`）与平台消息目录（`locales/`） |
| `server/` | REST/SSE 接口、课程自动发现与校验、内容 v2 schema、事件信封、运行存储、术语与用词检查、录制 |
| `lessons/lesson_*/` | 每课一个目录：`lesson.json`（实现清单）、`content.json`（教学内容 v2）、Python 实现、`locales/`（运行时文本，每种运行语言一份）、`fixtures.py`、`test_lesson.py`、README（英文 `README.md`，中文 `README.zh-CN.md`） |
| `curriculum/` | `catalog.json`（课程目录唯一数据源）、`glossary.json`（术语表）、`onboarding.json`（前置导学）、`schema/`（导出的 JSON Schema） |
| `frontend/src/` | 前端，结构见 `docs/architecture/frontend-workspace.md` |
| `site/` | 官网静态站（GitHub Pages）：构建时从课程目录和随课录制生成，回放复用 `frontend/src` 的组件，见 `site/README.md` |
| `tests/`、`frontend/e2e/` | Python 测试、Playwright 浏览器测试；前端单元测试在各模块的 `__tests__/` |
| `scripts/` | 校验、生成、脚手架、录制导出、用词报告 |
| `docs/` | `course-plan.md` / `course-plan.en.md`（由目录生成的中英文课程大纲）与 `architecture/`（架构约定与作者指南） |

`frontend/dist/` 是构建产物。`.runtime/` 放本机运行记录、诊断文件和教学数据库，不提交。

## 常用命令

在仓库根目录执行。Windows 用 PowerShell；macOS/Linux 把 `.\.venv\Scripts\python.exe` 换成 `.venv/bin/python`，`npm.cmd` 换成 `npm`。

```powershell
uv sync --dev                                   # Python 依赖
npm.cmd --prefix frontend ci                    # 前端依赖（按锁文件）
npm.cmd --prefix frontend run build             # 类型检查并构建前端
.\.venv\Scripts\python.exe run_web.py           # 启动服务：http://127.0.0.1:8765
npm.cmd --prefix frontend run dev               # Vite 开发服务器，/api 代理到 8765
```

校验、测试与生成：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v       # 全部 Python 测试（含各课 test_lesson.py）
.\.venv\Scripts\python.exe scripts/validate_lessons.py             # 实现清单、内容、术语表、用词、录制、译文层
.\.venv\Scripts\python.exe scripts/term_report.py --lesson <slug> --full   # 一课的术语、代码说明与用词问题
.\.venv\Scripts\python.exe scripts/realign_notes.py              # 源码移动后按锚点重新对准读码批注（--check 只检查）
.\.venv\Scripts\python.exe scripts/run_live.py <slug> [练习] --url http://127.0.0.1:8765 [--locale en]   # 真实运行练习并打印事件摘要（会产生模型用量）；--locale 选运行语言
.\.venv\Scripts\python.exe scripts/export_curriculum.py            # 改了 catalog.json、正文小节的标题或第一句、lesson.json、术语表或它们的译文层后重新生成 docs/course-plan.md 与 course-plan.en.md（--check 只检查，--locale 只处理一种）
.\.venv\Scripts\python.exe scripts/cjk_baseline.py --check        # course/、lessons/ 代码里的硬编码中文只许减少（运行时文本写进 locales/；去掉 --check 收紧基线）
.\.venv\Scripts\python.exe scripts/export_trace_contract.py        # 改了 server/envelope.py 后生成前端镜像（--check 只检查）
.\.venv\Scripts\python.exe scripts/migrate_content.py --check      # 内容 v2 迁移与格式规范
.\.venv\Scripts\python.exe scripts/translation_kit.py status --locale en   # 译文层覆盖率；export/apply 导出待译条目、校验并写回（目标 lesson:<slug>、onboarding、catalog、glossary、manifest:<slug>）
.\.venv\Scripts\python.exe scripts/export_content_schema.py        # 改了 server/content_schema.py 后导出 schema
npm.cmd --prefix frontend run content:types                        # 再由 schema 生成前端类型
npm.cmd --prefix frontend run test                                 # 前端单元测试（vitest；不要用 exec vitest run，它不读 vitest.config.ts）
npm.cmd --prefix frontend run i18n:check                           # 各语言翻译键一致
```

浏览器测试的步骤：

1. 先构建前端并启动后端。
2. 在 `frontend/` 下执行 `npx.cmd playwright test`。

注意：

- 测试使用系统 Chrome。后端执行互斥，测试按顺序运行。
- 要测别的端口，用环境变量 `AGENT_LAB_URL` 指定。
- **自动化代理请另起端口**，不要停止或占用使用者正在用的 8765 服务。例如：
  - 启动：`.\.venv\Scripts\python.exe -m uvicorn server.app:app --host 127.0.0.1 --port 8790`
  - 测试：`$env:AGENT_LAB_URL = "http://127.0.0.1:8790"`

## 架构要点

- **课程自动发现。** 后端扫描 `lessons/lesson_*/lesson.json`，不需要在 `server/catalog.py` 加分支。
  - 标题、简介、学习目标、先修和状态只写在 `curriculum/catalog.json`。
  - 显示课号由目录顺序计算，课程 ID 用 slug。
- **两种运行器。**
  - `runtime.kind: native`：复用原生工具循环，`main.py` 导出 `setup(locale)`，返回运行语言的 `AgentSetup(system_prompt, tools, available_tools)`。
  - `runtime.kind: custom`：`runtime.py` 的 `run(context)` 自己组织流程。只通过 `RunContext` 调模型、调工具、发事件：
    - `complete(body, round_number, branch=None)`
    - `call_tool`、`submit_call`（原样提交一条可能有问题的调用，演示拒绝路径）、`run_native`
    - `emit("lesson.*", data)`
    - `check_cancelled`、`locale`
- **运行语言。** 运行时也分中英文，规则见 `adding-lessons.md` 的“多语言运行时”：
  - 前端创建运行时带上界面语言；后端按本课 `runtime.locales` 解析（同语言优先，否则回落到源语言 `zh-CN`），记进 `RunContext.locale`、`run_start.data.locale`、运行存储和录制。回放按记录原样显示，界面语言不同时只加标注。
  - 发给模型或写进事件的文字一律来自 `locales/` 消息目录（`texts_for(locale)`）或清单里按语言填写的预设（`{"zh-CN": …, "en": …}`），不在代码里写死；工具名、参数名、事件名是代码，各语言相同。
  - 英文运行的事件里不能出现中文（`tests/test_runtime_locales.py`）。
- **事件信封 v2。**
  - 每次运行是一串带 `run_id`、`seq` 和 span 的事件：`run_start`、`request`、`response`、`tool_call`、`tool_result`、`answer`、`error`、`done`，以及课程自定义的 `lesson.*`。
  - 运行事件脱敏后存进 SQLite，SSE 按 `seq` 续读。
  - 修改事件常量后，要运行 `export_trace_contract.py`。
  - 详见 `docs/architecture/event-envelope-v2.md`。
- **内容 v2。**
  - `content.json` 的结构由 `server/content_schema.py` 唯一定义。场景依次是理解、读码、实验、自检、回顾。
  - 每个块和条目都有稳定 id；译文层按 id 覆盖可译文本，事实字段（带 `x-fact`）不可覆盖。
- **离线测试模式。**
  - 测试在网络边界换成课程 `fixtures.py` 的确定性响应，工具仍真实执行。
  - 学生网页只提供真实运行；没有可用模型时，引导学生完成配置。
- **标准事件族与通用视图。** 新课优先发以下事件，复用已有视图：
  - `lesson.report`（检查、指标、表格）：由实验报告插槽 `evidence-board` 显示；
  - `lesson.task_card`、`lesson.context_variant`、`lesson.memory`、`lesson.todo`、`lesson.plan`、`lesson.harness_injected`：由 `stage/Lenses.tsx` 的通用视图显示。

## 新增一课

完整流程见 `docs/architecture/adding-lessons.md`，要点：

1. 在 `curriculum/catalog.json` 登记课程（status `planned`），运行 `export_curriculum.py`。
2. 生成脚手架：`scripts/new_lesson.py --id <slug> --dry-run` 预览，确认后去掉 `--dry-run`；复杂流程加 `--kind custom`。
3. 实现课程。
   - 最小实现用原生 Python 写清机制，不引入框架；确实需要依赖时先评估成熟库。
   - 运行时文本写进 `locales/zh_CN.py` 与 `locales/en.py`，练习问题和自然语言预设按语言分别填写；脚手架已生成这套结构。
   - 夹具 `fixtures.py` 提供 `create_completion(exercise_id, inputs, locale)`，按运行语言给出确定性响应，只服务测试。
   - 在 `test_lesson.py` 写行为测试：真实工具执行、错误路径、停止条件、输入校验。
4. 写 `content.json`，规则见下文“教学内容”和“术语与代码名”，并遵守 `adding-lessons.md` 的“节奏与读码规范”：
   - 一课只学一件事，本课引入的课程概念不超过 5 个；`predict` 放在第一道微测之前；
   - 读码批注带锚点，每 8 行至少 1 条、连续无批注不超过 12 行，平台代码用 `folds` 收起，每课最多 3 个读码块；
   - 提到其他课写 `{{lesson:<slug>}}`，课程文本与源码都不写死课号。
5. 验证。
   - 依次运行 `validate_lessons.py`、`term_report.py --lesson <slug> --full`、`migrate_content.py --check`、完整 Python 测试。
   - 用到新前端视图时，再跑构建、vitest 和浏览器测试。
6. 验收通过后，把状态改为 `available`，重新生成课程大纲；每个练习在每种运行语言下用 `run_live.py --locale <语言>` 或网页真实运行一次，核对正文说法，再看一遍回放。
7. 在 `docs/architecture/reference-study.md` 登记借鉴的参考资料（固定版本、范围、许可证）。

## 扩展课程

- **自定义运行器**：用 `RunContext` 的方法，不自建 SSE、不直接读密钥、不伪造生命周期事件；运行时文本用 `texts_for(context.locale)`。
- **改造已有课程为多语言运行时**：按 `docs/architecture/localizing-lessons.md` 的清单逐课进行（参考课 `chat-request`、`tool-selection`）。
  - 并行请求给每个分支不同的 `branch`，时间线按它配对请求和响应。
  - 长循环和副作用操作之前调用 `check_cancelled()`。
- **新事件**：课程事件一律用 `lesson.` 前缀。
  - 能套用已有事件族的就套用。
  - 新的事件族需要通用视图时，在 `stage/Lenses.tsx` 加视图，并补 vitest 与浏览器测试。
- **前端插槽**：确有不同交互时，在 `frontend/src/lesson-extensions/` 写组件，并在 `registry.ts` 登记。
  - 插槽有 `guide`、`lab`、`inspector` 三个。
  - 加载或渲染失败时退回通用界面；JSON 里不能引用任意 URL、脚本或 HTML。
- **平台改动**：改事件信封、内容 schema、执行接口时，同步更新生成物（trace contract、JSON Schema、前端类型）和对应文档。
- **框架课**（LangChain、LangGraph 等）：框架回调映射到统一事件。拿不到原始请求时，标注为框架输入。

## 教学内容与文风

- **结构。** 理解场景按“概念卡 → 正文 → 微型自测 → 分步讲解 / 示意 → 预测”编排。
  - 每连续三段讲解内至少有一个微型自测。
  - 读码场景用真实源码和真实行号，“本课新增”由后端从 AST 计算。
  - 实验写清假设、对照组、观察点、导览、能证明与不能证明的结论；观察点的选择器必须能在确定性运行中命中。
  - 预测题用“”引用对照组或实验标题，只和学习者自己的运行比对。
- **诚实。**
  - 区分“流程结束”“请求成功”“工具执行”和“任务验收通过”这几种结论。
  - 服务商没有报告的用量写“未报告”（英文 not reported），不估算、不写 0 冒充；“未知”只用于确实无法知道的值（`validate_lessons` 会检查）。
  - 离线夹具模拟的错误要在事件里标明来源。
- **文风。** 写自然、直接的中文。
  - 短句，先说结论。
  - 不堆形容词，不写“值得注意的是”“总的来说”这类套话，不重复上一句。
  - 一段最多引入两个新概念，先讲后用。
  - 示意和走查只在说明处标注一次“非运行记录”，不在每一步重复。

## 术语与代码名

规则见 `docs/architecture/terminology.md`，由 `server/vocabulary.py` 检查（`validate_lessons` 和 `tests/test_lesson_vocabulary.py`）。

- **课程概念**（`curriculum/glossary.json`，`kind: concept`）：
  - `first_lesson` 写最早用到它的可运行课。
  - 引入课第一次出现时写“中文（English）”，其他课只写中文。
- **背景词**（`kind: background`，如分词器、消融）：只写中文，靠悬浮卡解释。
- **代码名**：正文里写到的本课源码名字自动显示为代码样式。
  - 需要解释的，在 `content.json` 的 `code_notes` 写 ≤60 字说明。
  - 说明里的名字必须真在源码和正文里出现。
- **普通词**（重试、JSON、正则表达式等）不收录。
  - 术语名要具体，避免误命中更长的词。
  - 名字确实会出现在意思不同的更长词组里时，在 `not_in` 里列出该词组。
- **同一个东西只用一个叫法**：按 `terminology.md` 的统一用词表写；出现新的同义叫法时，先补进那张表。
- **中文术语人工审读**：机器只能检查已收录的词，没收录的中文术语靠作者对照 `term_report.py --full` 逐段审读。
- **英文文本**：英文译文层、英文运行时文本（`locales/**/en.py`、`en.md`）和英文界面文案不能有中文（确需保留的登记到 `server/vocabulary.py` 的 `ENGLISH_CJK_ALLOWED` 并写明理由），服务商没有报告的数写 not reported，引用运行时文本时直接写英文原文，不写 `"中文" ("gloss")`。规则见 `terminology.md` 第 5 节，由 `validate_lessons` 和 `tests/test_english_text.py` 检查。

## 前端规范

- **组件选择**：优先复用免费 React Bits 组件（放在 `components/react-bits/`，文件首行注明来源与许可），缺的能力用 shadcn/ui（`components/ui/`）补，最后才自己写。
  - 保留无障碍支持、减少动画设置和上游许可证声明。
- **样式**：业务样式按模块放在 `styles/`，`workspace.css` 只做导入入口；设计令牌在 `tokens.css`。
- **文案**：只写在 `i18n/locales/<语言>/*.json`，组件里不硬编码中文。后端错误带 `code`，由前端翻译。
- **动效**：判断一律走 `frontend/src/motion`，不直接写 `prefers-reduced-motion`。
  - CSS 用 `:root:not([data-motion="full"])` 写静态降级。
  - 重效果经 `MotionIntent` / `useMotionBudget` 接入：按需加载、离屏暂停（离屏即卸载并释放 WebGL context）。
  - 同屏 WebGL 不设数量上限（使用者 2026-10-06 决定）；着色器卸载时必须调用 `loseContext()`，新页面要确认同时存活的 context 不超过浏览器硬上限（Chrome 约 16 个）。
  - 运行数据不加装饰性特效。
- **数据**：舞台、胶片、时间线、工具卡片都从真实事件推导；等待模型时只显示真实计时，不写“思考中”，不加打字机效果。
- **代码风格**：TypeScript/CSS 用 2 空格缩进；组件用 PascalCase，Hooks 用 `useSomething`。
  - Prettier 只格式化本次改动的文件。
  - 保持原文件的换行符（部分文件是 CRLF）。
- **测试定位**：浏览器测试用 role、`data-testid` 和 `e2e/i18n.ts` 的文案键定位，不用 CSS 类选择器，也不写死中文。

## Python 规范

- 4 空格缩进，函数和变量用 `snake_case`。
- 输入用 Pydantic 校验：课程输入模型继承 `LessonInputs`，枚举用 `Literal`。
- 处理错误和边界，不静默失败；工具失败返回结构化错误（`ok=false`、`error_type`、`error`）。
- 自定义事件数据是可 JSON 序列化的普通结构，不放密钥和本机绝对路径。
- 注释和文档字符串说明“为什么”，不复述代码。`lessons/` 与 `course/` 里写英文（国际惯例；中文讲解放在读码批注里，批注有中英两份），`server/`、`scripts/`、`tests/` 写中文。
- 发给模型或写进事件的文字写进 `locales/` 消息目录；给开发者看的编程错误直接写英文。

## 测试要求

| 改了什么 | 至少运行 |
| --- | --- |
| 课程实现 / `lesson.json` | 该课 `test_lesson.py`、完整 Python 测试（含 `tests/test_runtime_locales.py`）、`validate_lessons.py`、`cjk_baseline.py --check` |
| `content.json` / 术语表 | `validate_lessons.py`、`term_report.py --lesson <slug>`、`migrate_content.py --check`、`export_curriculum.py`（课程表的小节和本课术语来自这里）、`tests/test_lesson_experiments.py`、`tests/test_lesson_vocabulary.py` |
| 英文译文层、英文运行时文本或界面文案 | `validate_lessons.py`、`tests/test_english_text.py`、`translation_kit.py status --locale en` |
| `catalog.json` | `export_curriculum.py`、完整 Python 测试 |
| 执行流程、服务商适配、事件信封 | 完整 Python 测试，并补回归测试；改了信封常量时运行 `export_trace_contract.py --check` |
| 前端 | `run build`、`run test`（vitest）、`i18n:check`；交互变化还要跑相关 Playwright 测试 |

没有数值覆盖率门槛，但改了行为的地方必须有测试证明。

## 提交与拉取请求

- 提交标题用中文，带类型前缀：`feat:`、`fix:`、`docs:`、`test:`、`refactor:`。例如 `feat: 新课“文本动作与原生工具调用”`。
- 一次提交只做一件事。课程内容、平台代码和文档能分开就分开。
- PR 要写清：
  - 行为变化；
  - 验证结果（命令和通过数）；
  - 哪些只做了离线验证，哪些用真实模型验证过。
- 界面有变化的附截图。
- 不提交 `.runtime/`、`local_config.py`、`frontend/dist/`、`node_modules/`。

## 安全与配置

- 服务只绑定 `127.0.0.1`，面向单人本地学习。共享部署需要另行设计身份、存储和执行隔离。
- 模型配置来自环境变量或 `local_config.py`（模板见 `local_config.example.py`）；网页提交的密钥只存在后端内存。
- 源码接口只公开课程清单登记的文件，不提供任意路径读取或代码执行。
- 本地进程中的课程代码不是沙箱。需要执行模型生成代码的课程，必须先有隔离方案。

## 参考资料

课程参考 Microsoft AI Agents for Beginners、Hugging Face Agents Course、《深入理解 AI Agent》等教程。

- 这些参考不参与平台运行。
- 阅读范围、固定版本和许可证见 `docs/architecture/reference-study.md`。
- 复用正文或代码前核对许可证并署名，不直接搬入参考项目的完整依赖。
- 框架和服务商 API 会变化，开发对应课程时重新核对官方文档。
