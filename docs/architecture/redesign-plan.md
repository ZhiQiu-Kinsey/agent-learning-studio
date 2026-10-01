# 平台重构方案：可视化学习体验升级

确认日期：2026-10-01。本文是重构的执行依据；课程扩充、平台约束与决策细节见 [课程调研与决策记录](curriculum-research.md)（第 6 节平台约束、第 9 节决策）。两者冲突时以 curriculum-research.md 第 9 节和本文第 1 节为准。

## 1. 已确认的决定

| 项 | 决定 |
| --- | --- |
| 语言 | 先只做中文；多语言架构必须完整，新增语言只需新增文件 |
| 运行记录 | 服务端 append-only SQLite（`.runtime/`），运行是服务端资源：`POST /api/runs`、`GET /api/runs/{id}/events?from_seq=`、`POST /api/runs/{id}/approvals`；界面提供一键清除 |
| 学习进度 | 浏览器 localStorage，只记录本机真实发生的动作，不判定“已掌握” |
| 课程页 | 理解 / 读码 / 实验 / 自检 / 回顾（替代“学习课程 / 实验工作台”双模式和三层 Tabs） |
| 推进方式 | 分阶段，先打地基；每个子任务测试通过后提交一次 Git |
| 课程 ID | slug（如 `tool-selection`），显示课号按 catalog 顺序计算，旧数字 ID 保留为别名 |
| 随课录制 | `provenance=recorded_run`，只能从运行存储原样导出，带模型、服务商、日期、源码哈希、完整性哈希 |
| 术语 | “中文（English）”，每课首次出现中英并列；`glossary.json` 为单一来源 |

红线不变：运行数据只来自真实事件，示意明确标注“非运行记录”；SDK 标准化数据不冒充原始 HTTP；密钥只在后端；尊重减少动画；现有测试保持通过，改动行为处补测试；遵守 React Bits（MIT + Commons Clause）与 OpenMAIC（MIT，© 2026 THU-MAIC）许可。

## 2. 核心构想：Agent 舞台

- 全站唯一视觉母题：用户、运行层、模型、工具、状态/记忆等节点，事件是连线上的信号。拓扑由事件数据决定（span 层级、子 Agent、并行分支、后台泳道），不写死四个节点。
- 同一渲染器三种来源，样式与标签区分：
  - 我的运行（实线，绿色标签）；
  - 录制的真实运行（标注模型与日期）；
  - 教学示意（虚线 + 水印“教学示意 · 非运行记录”；合成事件序列 `provenance=illustration`，契约测试约束：调用与结果成对、id 格式、顺序，不得出现具体执行输出数值）。
- `deriveStage(events, cursor)` 纯函数推导任意位置的舞台、上下文胶片和配对关系；必要时每 N 个事件缓存快照。回放计时器用版本令牌，跳转、暂停、变速时作废旧回调。
- 区间事件（request→response）与瞬时事件（tool_call）在一张常量表中声明，动画与时间线共用。耗时只取服务端时间戳。
- 上下文胶片：每轮 `request.messages` 画成按角色着色的条带，逐轮高亮新增项（jsondiffpatch）；响应体有 usage 才显示 token，否则只显示字符数并注明。
- 时间线按真实时间戳排布，可切换等距 / 1× / 2×。

诚实约定：等待模型只显示三个点和真实计时，不写“思考中”；回答一次性到达就不用打字机效果；停止运行时只把仍在运行的工具调用标为“已停止，无结果”，不覆盖已完成结果；连线信号一个真实事件发一次，不无限循环；估算值标“估算”；工具卡片折叠为一句话摘要 + 耗时，展开看参数 JSON 和原样结果，截断时明示，回放时加载的工具组默认折叠。

## 3. 页面结构

- **首页**：示意舞台、学习旅程、继续上次；导学并入为第 0 章。
- **课程地图**：8+ 领域（MagicBento），课程与先修关系画成可缩放路线图（@xyflow/react + elkjs），可运行亮、规划灰。
- **课程页顶部课程条**：课号 · 标题 · 能力徽章（Microsoft 8 项能力：模型、工具、知识、上下文、记忆、规划、编排、信任）· 五个场景切换 · 模型连接状态。
- **理解**：约 720px 单栏；宽屏左文右图，滚动驱动吸顶的示意舞台；每 2–3 节一道微型自测（错误选项逐个解释）；末尾“先预测”块，到实验核对。
- **读码**：“本课新增”卡片（从真实源码 AST 计算，不手写）；文件 · 代码 · 批注三栏；设计决策与被放弃的方案；工具函数可跳到实验中对应的真实 tool_result。
- **实验**：左栏实验列表（假设、预测、对照组、Schema 生成的参数控件）；中间舞台 + 胶片 + 时间线；右栏检视器（JSON、工具卡片、差异）；底部导览回放条与讲解气泡；运行来源切换；结论卡“能证明 / 不能证明”。预留：多组对照、批量运行与评估矩阵、审批卡、终端与 diff 视图（地基阶段只需信封与存储能承载）。
- **自检**：先评信心再作答，选项级反馈；轨迹找错（规则由课程声明，从事件计算）；学习者自报检查点。
- **回顾**：只用本机真实记录：运行次数、实验、找到的证据、自测得分、能力进度、下一课先修。
- **导航**：侧栏收为图标栏 + 抽屉；⌘K 命令面板（cmdk）；快捷键：空格播放/暂停、←/→ 单步、Shift+←/→ 按时间跳、`[` `]` 调速、`?` 帮助；输入框聚焦或按修饰键时不响应。

导览回放：作者写的脚本是带类型的动作列表（`narrate`、`spotlight` 舞台节点、`highlight` JSON 路径、`seek` 事件），在学习者自己那次真实运行上逐步讲解；与观察点共用一套声明式选择器（事件类型、轮次、JSON 路径、span 角色），跳转用 `seq`。目标在本次运行中不存在时如实显示“本次运行没有出现这条证据”。构建时用测试数据校验所有目标存在。跳到某句讲解时重新触发它前面紧挨的视觉提示。

## 4. 数据与接口

### 4.1 文件分工

| 文件 | 职责 |
| --- | --- |
| `curriculum/catalog.json` | 课程目录唯一来源：slug、别名、标题、目标、状态、先修、能力徽章 |
| `lessons/*/lesson.json` | 能运行什么：实现、练习、输入模型、运行器 |
| `lessons/*/content.json`（v2） | 怎么教：按场景分组的内容块，实验通过 `exercise_ref` 引用练习 |
| `curriculum/glossary.json` | 术语表单一来源，块中用 `term_id` 引用 |
| `*.{locale}.json` 译文层 | 只含文本，按稳定 id 合并；中文写在源文件里 |

### 4.2 content v2 结构

```text
{ schema_version: 2, lesson: "<slug>", capabilities: [...],
  scenes: {
    understand: { blocks: [hero, prose, concepts, misconception, statement, flow(illustration_ref),
                           compare, micro-quiz, predict(experiment_ref), callout] },
    code:       { blocks: [whats-new(自动计算), annotated-source(path + 行号 + 批注), decision(alternatives)] },
    lab:        { experiments: [{ id, title, hypothesis, predict, arms: [{ id, exercise_ref, inputs }],
                                  observe: [selector + 讲解], guide: [observe_ref + narrate/spotlight/seek],
                                  conclusion: { proves, does_not_prove } }] },
    check:      { blocks: [quiz(选项级反馈 + 信心), trace-hunt(rule), checkpoint] } },
  illustrations: { "<id>": { provenance: "illustration", events: [...] } } }
```

- 每个块有稳定 id；块类型与场景无关；场景可省略但顺序固定（导学只启用 understand 与 check）。
- 表现形式写语义意图（如 `"reveal": "decode"`、`"layout": "flip"`），由前端动效层映射到组件。
- `predict` 运行后用声明式规则从真实事件计算对照（如统计 `tool_call` 数），只比较可从事件推出的事实。
- Pydantic 判别联合定义块与场景 → 导出 JSON Schema → 生成前端 TS 类型；CI 重新生成并比对已提交文件。内容文件加 `$schema` 获得编辑器补全。
- 迁移阶梯：有序纯函数 `(from, to, fn)`；找不到路径直接报错；比代码新的文件不动。学习记录有独立版本线。
- 校验与补默认值分开；默认值只在 Pydantic 声明一次。

### 4.3 事件信封 v2

`run_id · seq · span_id · parent_span_id · span_kind · actor/role · provenance(live | recorded_run | illustration) · representation(wire | parsed | sdk_standardized | http_body)`。标准教学事件族（`lesson.report`、`lesson.state`、`lesson.memory`、`lesson.context` 等）定义模型并提供 `context.report()` 等辅助方法；通用视图按契约渲染。课程用 `lenses: [...]` 组合通用视图，插槽机制保留给复杂课。

### 4.4 后端改动

- 运行存储与 runs 接口（创建、按 `from_seq` 续读、审批、导出录制、清除）。
- 自定义课 `INPUT_MODEL` 导出 JSON Schema，前端自动生成参数控件（数值 ScrubField、枚举 RubberSegment、布尔 SquishSwitch），JSON 编辑保留为高级模式；`pattern` 枚举改为 `Literal`。
- 内容接口接受 `?lang=`，合并译文层并返回缺失字段；错误响应增加 `code`，由前端翻译。
- `RunContext` 增加 `locale`；系统提示词与源码不翻译。
- `code` / `annotated-source` 块由后端从白名单源码解析真实代码与行号。

## 5. 多语言架构

- i18next + react-i18next；语言注册表 `as const satisfies`；`CustomTypeOptions` 给翻译键加类型；按语言懒加载 `locales/{locale}/*.json`。
- 回落链用对象形式；切换语言时同步 `<html lang>`；语言由 fetch 封装统一传给后端；日期数字用带 locale 的 Intl；标点也作为文案。
- 检查：键一致性脚本（改编自 OpenMAIC `scripts/check-i18n-keys.mjs`，补占位符一致、空值、复数、与源语言相同警告）；AST 扫描 TSX 与 Python 中硬编码中文的基线测试（只许减少）；译文层覆盖率在原始覆盖文件上校验，禁止覆盖 id、状态、先修、正确答案、代码引用等事实字段。
- 课程内容带独立源语言标签，不由界面语言推断。

## 6. 视觉与动效

- 方向：“夜间观测站 / 仪器面板”，深色默认，浅色是“实验记录本”。角色色：模型紫、运行层青、工具珊瑚橙、状态与记忆绿、错误红；只定义基础色，变体用 `color-mix` 推导；同一色票用于节点、事件标签和 JSON 高亮。
- 动效令牌：缓动 `cubic-bezier(.16,1,.3,1)`，基础 160ms，折叠 220ms。原则：加载时入场一次，之后不主动动；同屏只允许一个持续脉冲。
- 字体用 @fontsource 本地打包（CSP 只允许同源），中文走系统字体；标题 600、加粗 700、`text-spacing-trim`。主题在首屏前设置（沿用 `public/theme-init.js`）。
- `src/motion/`：`MotionProvider` 合并系统减少动画、用户设置（跟随系统 / 完整 / 简洁 / 静态）、WebGL 能力、页面可见性；`useMotionBudget(ref, cost)` 视口内且页面可见才激活，WebGL 同屏最多 1 个，其余显示静态图；意图注册表登记懒加载组件、成本与静态降级；效果写成带版本的声明式轨道数据（参考 OpenMAIC `lib/choreography/descriptors`），每个都有减少动画变体。聚光灯：测量目标矩形 + 0–100 SVG 遮罩 + `AnimatePresence` 按目标键控。
- 页面切换用 View Transitions，带超时与降级。

React Bits 选用（从 213 个免费组件中选；用 `npx shadcn@4.21.0 search|view|add @react-bits/<Name>-TS-TW` 获取，清单见 `https://reactbits.dev/r/registry.json`）：

| 区域 | 组件 |
| --- | --- |
| 首页 | WebThreads、MaskedHeading、RotatingText、TextLoop |
| 课程地图 | MagicBento、GlareHover、CountUp、SpotlightCard |
| 理解 | SplitText、DecryptedText、Shuffle、FoldText、TrueFocus、ScrollReveal、FlipCard、CardSwap、WarmTooltip |
| 读码 | LineSidebar、GradualBlur |
| 实验参数 | PromptBar、ScrubField、RubberSegment、SquishSwitch、GlideSelect |
| 实验舞台 | LatticeLoader、CallChip、StatusMark、ElectricBorder、GlitchText、WakeSlider |
| 课程专属 | SloshGauge（第 9 课预算）、Shredder（第 10 课删除）、TearTicket（第 4 课任务卡）、SpringCheck |
| 自检与回顾 | JellyRadio、PeekRating、SpringCheck、CountUp、ClickSpark |
| 全局 | GooeyNav、SwipeToast、FaultyTerminal（后端离线）、Noise |

不用：替换光标类、图库类、物理玩具、调用摄像头的（ReflectiveCard、GridScan）、three.js / WebGPU 重型背景。

## 7. 可借鉴的 OpenMAIC 代码（MIT，复制时保留版权声明并登记第三方声明）

路径相对 `H:\Learn\References\OpenMAIC`：

- 效果描述与适配：`lib/choreography/descriptors/{types,spotlight,laser}.ts`、`components/slide-renderer/Editor/motion-descriptor-adapter.ts`、`SpotlightOverlay.tsx`（测量与遮罩核心）。
- 回放导航：`lib/playback/action-navigation.ts`、`action-resume.ts`（按 `(index, id, type)` 校验续播位置）。
- 快捷键守卫：`components/edit/PlaybackChromeRoot.tsx` 中 `isPresentationShortcutTarget`。
- 工作台：`components/workbench/chat/{tool-group-state,thinking-bar-state,format,status-dot,autoscroll}.ts(x)`、`lib/workbench/session-store.ts` 的 `foldEvent` 与 `compactReplayEvents` 思路。
- 内容版本：`packages/@openmaic/dsl/src/version.ts` 的迁移阶梯（移植为 Python）。
- i18n：`scripts/check-i18n-keys.mjs`、`tests/workbench/workbench-i18n.test.ts` 的硬编码中文 AST 扫描。
- 完成页的减少动画处理：`components/scene-renderers/classroom-complete.tsx`。

不借鉴：打字机式流式缓冲、无测量的循环进度动画、“思考中”微光、绝对坐标幻灯片 DSL、多套 schema 机制、判分失败给一半分、散落的动效参数、首屏后才切主题。Vercel AI Elements 许可证未核实，只参考思路。

## 8. 阶段计划

| 阶段 | 内容 | 完成后可见 |
| --- | --- | --- |
| 1 地基 | 见下表 | 外观接近现状，数据与架构就位 |
| 2 主角 | 舞台、上下文胶片、时间线、工具卡片、参数控件 | 真实运行驱动舞台 |
| 3 课程页 | 五个场景、全部内容块、导览回放、回顾页、课程专属视图 | 按新结构学一课 |
| 4 全局入口 | 首页、课程地图、⌘K、本机进度 | 打开就想往下学 |
| 5 收尾 | 文档、性能与无障碍检查、按 curriculum-research.md 扩充课程 | 可交付 |

第一阶段子任务（按顺序，每项测试通过后提交）：

1. 设计令牌与 `src/motion/` 动效层，迁移现有 `useMotionPreference` / `useExperienceMotion` 用法，增加动效设置。
2. 多语言架构：i18n 初始化与语言注册表、抽取全部界面文案到 `zh-CN`、键检查脚本、硬编码中文基线测试、后端错误码。
3. 事件信封 v2、运行存储（SQLite）与 runs 接口，前端改为基于 runs 接口运行与续读；保持现有事件类型兼容。
4. slug 课程 ID（数字别名）、`glossary.json`、`recorded_run` 录制格式与校验脚本。
5. content v2：Pydantic schema、JSON Schema 与 TS 类型生成、迁移阶梯、迁移现有 10 课与导学、渲染器（外观先接近现状）、译文层合并与覆盖率校验。
6. 学习进度 localStorage 记录。
7. 浏览器测试选择器迁移到角色与 `data-testid`；补充 schema、示意契约、预测计算、事件映射测试。

## 9. 现状速查（重建上下文用）

- 后端：`server/app.py`（SSE `/api/run`、执行互斥、脱敏）、`server/catalog.py`（课程发现与 `_content` 手写校验）、`course/execution.py`（`RunContext`）、`course/runner.py`（原生循环）。事件类型：`run_start/request/response/tool_call/tool_result/answer/error/done` + `lesson.*`。
- 前端：`App.tsx`（壳与导航）、`hooks/useStudio.ts`（课程、运行、回放状态）、`components/workspace/{LearningWorkspace,Laboratory,ExecutionFlow,ModelSettings}.tsx`、`components/learning/*`、`Onboarding.tsx`、`Curriculum.tsx`、`lesson-extensions/`；样式在 `styles/`。已有约 25 个 React Bits 组件在 `components/react-bits/`。
- 测试：Python 92 个（`python -m unittest discover -s tests`）；Playwright 5 个 spec，大量依赖中文文案和 CSS 类名（`.event-detail pre`、“运行练习”等）。
- 用户自己在 8765 端口运行着服务，不要停止它。
- Git：本地仓库，基线 `f84e316`；`core.autocrlf=false`。
