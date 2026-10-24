# 前端结构

[English](frontend-workspace.en.md) · **简体中文**

前端使用 React、TypeScript、Vite 和 Tailwind CSS。全站只有一个视觉母题，即 **Agent 舞台**：舞台、上下文胶片、时间线和工具卡片都由真实运行事件推导。教学示意使用同一个舞台渲染，但会画成虚线，并加上“教学示意 · 非运行记录”水印。

## 页面

| 页面 | 入口 | 内容 |
| --- | --- | --- |
| 首页 | `components/home/Home.tsx` | Agent 循环示意（可逐步查看或点击播放，加载后不会自己开始）、学习旅程（本机真实进度）、继续上次 |
| 导学（第 0 章） | `components/Onboarding.tsx`（子组件在 `components/onboarding/`） | 七个前置章节，示意、微测、误区和深入块按原位渲染，检查点自报并存在本机 |
| 课程地图 | `components/Curriculum.tsx`（子组件与数据 hooks 在 `components/curriculum/`） | 领域卡片（MagicBento）、先修路线图（@xyflow/react + elkjs，懒加载）、列表与搜索 |
| 课程页 | `scenes/LessonScenes.tsx` | 课程条与五个场景：理解 / 读码 / 实验 / 自检 / 回顾 |

五个场景都实现 `scenes/types.ts` 中的 `SceneProps`。场景在首次访问时挂载，之后保留状态；从别的场景发起运行时自动切到实验场景（已在实验场景时不切换、不滚动）。其他组件可以调用 `requestScene()` 切换场景，例如命令面板。

- **理解**（`UnderstandScene`）：`content/blocks/UnderstandBlocks.tsx` 按作者编排的顺序渲染 v2 块，包括概念、正文、分步讲解、示意舞台、微型自测和先预测。
- **读码**（`CodeScene`）：从 `/api/lessons/{id}/code` 读取由真实源码计算出的“本课新增”（比较课程代码和运行时文本的字段 `t.<字段>`，不含平台与测试夹具）、带行号的批注和设计决策。工具函数可以跳到实验中对应的真实 `tool_result`。默认打开有批注的文件，只显示标注范围：范围外的行和 `folds` 折叠的平台代码收起成一行，点击原地展开，“显示完整文件”可切换（`scenes/code/model.ts` 的 `codeSegments`）；定位到收起的行时自动展开。文件列表标出“平台”“测试夹具”“运行时文本”；运行时文本（`locales/`）只列出运行语言那一份，界面语言切换时随详情一起重新获取。
- **实验**（`LabScene`）：宽屏（≥1180px）左右两栏，左栏 `.lab-rail` 固定在工具栏下方、内容超出时栏内滚动，右栏是实验台；窄屏把左栏两张卡片排在实验台上方。
  - 左栏：实验卡（假设、对照组、观察点）和证据核对卡（核对进度、导览、可折叠的“这次实验能说明什么”，默认收起）。
    - 对照组是选练习的入口（提问栏的 `/` 菜单是快捷方式）。切换实验时选中它第一个能真实运行的对照组；离线故障注入的对照组不可选。
    - 观察点只拿本实验对照组的运行核对（`scenes/lab/experimentRun.ts`，按 `runExerciseId` 判断）：别的实验的运行仍留在舞台上，但这里显示“运行后核对”。
    - 当前框住证据的观察点高亮（`data-current`）；运行结束后默认选中第一条找到的观察点，不回退回放。
  - 实验台（`components/workspace/Laboratory.tsx` 只做组装，部件在 `components/workspace/lab/`）：顶部一条提问栏（问题在左，最终回答和连接在右），下面是运行观察台：舞台（在实验台里比别处略矮，约 18rem，节点两行：名称，类型与状态；工具多时画布按工具数增高。运行中成批到达的事件由 `stage/usePacedCursor.ts` 逐条推进，最多补演最后 5 步、每步约 0.45 秒，只作用于舞台；回放、拖动和减少动画不受影响）、等待模型状态、工具调用条、回放与时间线、事件列表与 JSON 检视器、上下文胶片、工具卡片、通用视图；
  - 视角跟随运行（`scenes/lab/useRunFollow.ts`）：开始运行时把运行观察台（`data-run-focus`）滚到工具栏下方，等舞台演完最后几步后回到开始运行时的位置（快速运行也至少停留约 1.2 秒）；运行中学习者自己滚动页面，就不再自动回去。减少动画时直接跳转；
  - 实验场景的课程头图只留标题和场景标签，简介和本课目标在其他场景显示；
  - 运行语言：创建运行时带上界面语言（`RunRequest.locale`），后端按本课支持的运行语言解析，写进 `run_start.data.locale`。本课还没有界面语言的运行器时，提问栏下写明（`lab-runtime-locale`）；屏幕上的运行与界面语言不同时（例如切到英文后还看着中文运行），回答区写明这次运行的语言（`lab-run-locale`），回答标上 `lang`，内容不翻译。界面语言切换时，没改过的问题和预设参数换成新运行语言的预设，改过的保留。随课录制同样按元数据的 `locale` 标注；
  - 沿用上次的运行（`hooks/runCache.ts`）：一次运行完成后，浏览器记下“这一课、这个练习、问题、参数、系统提示词、工具定义、运行语言、课程与平台代码”的哈希对应哪个 `run_id`（只存 id 和哈希，不存问题原文）。再进这课或切回这个练习时，这些都没变就从运行存储读回那次的事件（`GET /api/runs/{id}/events`，回放只读），不再请求模型，提问栏下注明“这是你上次的运行”。改了问题或参数，提示随即消失；运行记录被清除时（404）忘掉这个 id；
  - 导览回放：点“开始导览”后整页变暗，每步只框出一处证据，讲解卡片贴在旁边（`scenes/lab/GuideTour.tsx`，懒加载）。每步一小段讲解：有观察点时跳到对应事件，在 JSON 检视器里框住那几行（`components/workspace/lab/jsonLines.ts` 按 `JSON.stringify` 原样排版并记录字段行号）；实验报告框住证据板；只写舞台角色时框住舞台节点（这次运行没有该节点时框住整个舞台；仍找不到目标就按翻页方向跳过这一步）；开场句和这次运行没有出现的证据居中显示，后者直说没找到。点暗处不响应，被框住的区域照常可滚动、可选中；← / → 换步，Esc 退出，退出后停在最后的证据上，焦点回到“开始导览”。导览期间实验快捷键关闭；
  - 观察点的“定位”与导览共用“证据焦点”（`components/workspace/lab/evidenceFocus.ts`）：切到执行记录、选中事件、框住字段并滚到视野里；
  - 结论卡；有录制时出现来源切换。
- **自检**（`CheckScene`）：先评信心再作答，并给出选项级反馈；轨迹找错只使用学习者自己的运行；检查点由学习者自报。
- **回顾**（`ReviewScene`）：只展示本机真实记录，不判定“已掌握”；本机学习徽章（3D 挂牌，懒加载）卡面只印真实数字。

## 模块

| 目录 | 职责 |
| --- | --- |
| `src/stage/` | `deriveStage`（纯函数：拓扑、span、信号、胶片）、`replay.ts`（回放时钟，带版本令牌）、`AgentStage`、`ContextFilm`、`Timeline`、`ToolCards`、`Lenses`（标准教学事件族的通用视图） |
| `src/content/` | 生成的 v2 类型 `types.gen.ts`、`view.ts`、选择器引擎 `selector.ts`、导览 `guide.ts`、预测 `predict.ts`、块渲染 `blocks/`、术语与代码名标注 `glossary/`（术语来自 `/api/glossary`；代码名来自课程详情的 `code_names`，说明来自内容的 `code_notes`；规则见 [术语与代码名](terminology.md)） |
| `src/motion/` | `MotionProvider`（合并系统减少动画、WebGL 与页面可见性）、`useMotionBudget`（离屏暂停；WebGL 同屏不设数量上限，使用者 2026-10-06 决定）、`revealProps`（滚动揭示）、`EffectBoundary`（装饰效果出错时退回静态）、`MotionIntent` 意图注册表、动效令牌 |
| `src/i18n/` | i18next、语言注册表、按命名空间组织的 `locales/zh-CN/*.json`、错误码翻译 |
| `src/progress/` | 本机学习进度（localStorage，有独立版本线与迁移阶梯），只记录真实动作 |
| `src/components/react-bits/` | 改编自 React Bits 的组件（文件首行注明来源与许可）。较长的组件把着色器、常量和纯逻辑放在同名目录（例如 `ElectricLogo/shaders.ts`），组件文件路径与导出保持不变，便于对照上游更新 |
| `src/components/backdrops/` | 英雄带动态背景：`Backdrop` 按预设懒加载 React Bits WebGL 着色器，离屏卸载，静态时退化为同色渐变；`backdropFor(category)` 给每个课程领域分配一种氛围。开发预览：`/dev/backdrops.html` |
| `src/hooks/useStudio.ts` | 课程、参数、运行（`POST /api/runs`，断线后按 seq 续读）与回放状态 |
| `src/components/command/` | ⌘K 命令面板（cmdk，懒加载） |
| `src/components/shell/` | 侧栏（品牌标、开始之前、分支式课程树）与外壳特效 |
| `src/components/toast/` | 全局通知：`notify()` 只报告真实结果，`ToastHost` 负责显示 |
| `src/lib/` | 小工具：课程 ID、颜色换算 `color.ts`、链接校验 `url.ts` 等 |
| `src/scenes/lab/` | 实验面板、导览（`guidePlan.ts` 决定每步框哪里，`GuideTour.tsx` 接到遮罩导览）、录制视图、实验快捷键 |
| `src/tour/` | 通用遮罩导览（React Joyride 受控模式）：遮罩与亮框、讲解卡片（React Bits `SpotlightCard`）、进度条、键盘；`reveal.ts` 先滚动再画亮框。与课程无关，可复用于别的引导 |
| `src/lesson-extensions/` | 构建时登记的课程插槽；扩展加载失败时回退到通用界面 |
| `src/styles/` | 按模块组织的样式；`tokens.css` 存放设计令牌与动效级别开关 |

## 诚实约定（界面层）

- 运行数据只来自真实事件。示意事件带 `provenance=illustration`；录制标注模型和日期，不混入“我的运行”。
- 等待模型时只显示“等待模型响应”和从请求事件时间戳起算的真实计时，不写“思考中”；非流式回答一次性到达，不加打字机效果。
- 停止运行时，只把仍在执行的工具调用标为“已停止，无结果”，不覆盖已经完成的结果。
- 流式响应（`components/workspace/lab/streaming.ts`）：回答区只显示已经到达的分块拼出的文字，随事件逐条出现，没有打字机效果；时间线按 `response_delta` 的 `received_ms` 画真实到达的块，结束时写明“完成 / 已停止 / 被取消 / 出错”，被取消的流只留停止前到达的内容。最终的 `response` 标注“由分块拼合”。
- 审批（`components/workspace/lab/ApprovalPanel.tsx`、`approvals.ts`）：运行停在 `approval_requested` 时显示审批卡（摘要、参数、风险、剩余时间，可写理由，`editable` 时可改参数），批准 / 拒绝经 `POST /api/runs/{id}/approvals` 提交，请求体带参数摘要；卡片只在当前这次运行里可操作，回放、录制和上次运行里同一张卡只读，只显示记录。审批期间运行状态显示“等待审批”。
- 停止与断开：停止按钮发 `user_stop`，等服务端的 `done` 才显示终态；“断开事件连接（运行继续）”只关事件流，不停止运行，“重新连接”从最后一条事件续读。
- 检查点（`checkpoint` 事件详情里的“从「检查点名」恢复”按钮）调用 `POST /api/runs/{id}/resume` 启动新运行；新运行的回答区注明来源运行与检查点，说明没有重放旧请求。
- 耗时只取服务端时间戳；回放压缩了过长的真实等待时会注明。响应没有报告 usage 时，只显示字符数并写明原因。
- SDK 标准化数据不会被标成原始 HTTP 报文。
- 进度只记录真实发生的动作：后台预载课程不算“打开”，同一个 run_id 只计一次。

## 动效

- **动效级别**：`<html data-motion="full|static">` 由首屏脚本和 `MotionProvider` 写入，只跟随系统的“减少动画”设置，没有页面内开关。
- **CSS 写法**：统一使用 `:root:not([data-motion="full"])`，Tailwind 的 `motion-reduce:` 和 `motion-safe:` 已跟随这个属性。
- **重效果**：通过 `MotionIntent` 或 `useMotionBudget` 接入，做到按需加载、离屏暂停，并且都有静态降级。WebGL 同屏不设数量上限（使用者 2026-10-06 决定：课程地图每张领域卡一直显示自己的动态背景）；离屏的着色器卸载并调用 `loseContext()` 释放 context，避免滚动时累积到浏览器硬上限（Chrome 约 16 个，旧 context 会被强制回收）。课程地图实测同时存活最多 12 个。
- **装饰与数据分开**：英雄带动态背景、入场与滚动揭示、悬停反馈、点击火花都只装饰静态界面；运行数据不加装饰性特效，每个真实事件只发一次信号，运行中的流光边框只在真实运行时出现。滚动揭示统一用 `revealProps`，系统中途开启减少动画时尚未滚到的内容也会立即完整显示。

## 术语与代码名

课程页由 `LessonVocabulary` 包住全部场景，提供当前课程、本课代码名和代码说明。

- 术语只在每页第一次出现处加下划线（`GlossaryScope` 决定归属），`data-tier` 区分三档：
  - `new`：本课引入，实线渐变；
  - `review`：前面课程引入，点线；
  - `background`：背景知识，虚线。
- 本课源码里的名字（含消息角色、事件名、运行终态）显示为代码样式；有 `code_notes` 的带点线，悬停或聚焦显示说明卡。
- 匹配顺序：代码样式片段 → 术语 → 代码名。术语表的 `not_in` 词组整体跳过，避免中文子串误命中。

## 文案与多语言

- 已注册 `zh-CN`（源语言）与 `en`（`src/i18n/locales.ts`）。新增语言 = 在注册表加一项 + 新建 `locales/<语言>/*.json`，键与 zh-CN 一致。
- 界面文案全部放在 `locales/<语言>/<命名空间>.json`，`npm run i18n:check` 检查各语言的键、占位符与复数形式。zh-CN 只写普通键；需要单复数的语言可以把同一个键写成 `<键>_one` / `<键>_other`，此时源文本必须用 `{{count}}`。
- `src/i18n/__tests__/hardcoded-cjk.test.ts` 用 AST 统计组件里的硬编码中文，数量只许减少；目前已经为 0。
- 后端错误带 `code`，由前端翻译。服务商名称按 `provider_id` 查 `settings:providerNames`，没有对应键的用服务端的名字（品牌名）。
- 语言切换：顶栏的 `LocaleSwitch`（与主题同一个 GlideSelect）和命令面板的“界面语言”条目都调用 `changeLocale`，选择存在 localStorage（`agent-lab-locale`），`<html lang dir>` 与页面标题随之更新。手机宽度下语言与主题收成图标加箭头。
- 课程内容（课程目录、课程详情、读码、导学、术语表）按界面语言请求 `?lang=`（`api.ts` 的 `withLocale`）。取这些接口的副作用都把 `useContentLanguage()` 列为依赖，共享缓存按语言分开（`lib/languageCache.ts`、`hooks/useCurriculum`、`useGlossary`、`useOnboarding`）；切换语言就地重取，不刷新页面，当前课程、场景、练习、输入和屏幕上的运行都保留。
- 回落与标注：译文缺失时那条文本显示中文原文。界面不是中文时，主要以中文为主的课程文本标 `lang="zh-CN"`（`i18n/textLanguage.ts`，正文、标题、导航课名、课程表）；整课或导学没有译文、或只译了一部分时，标题下显示一行说明（`TranslationNotice`）。
- 术语与代码名：英文正文按英文名与别名匹配术语（见 `content/glossary/match.ts`）。中文正文里源码名字一律显示为代码；英文正文里只标“像代码”的名字（含 `_ . - ( ) :`、数字或词中大写），`messages`、`is` 这类普通词保持正文。
- 日期与数字一律用 `Intl` 加当前界面语言格式化，组件里不写死语言代码。

## 验证

单元测试使用 vitest（`npx vitest run`），浏览器测试使用 Playwright。浏览器测试的定位方式：

- 用 role、`data-testid` 和 `e2e/i18n.ts` 读取的文案键定位；
- 选择器基线只许减少；
- `e2e/a11y.spec.ts` 用 axe-core 按 WCAG 2.1 A/AA 扫描主要页面。

截图检查可用 `scripts/capture-lab.mjs` 和 `scripts/capture-scenes.mjs`。命令见 [开发验证](validation.md)。
