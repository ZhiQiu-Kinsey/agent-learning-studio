# 前端结构

前端使用 React、TypeScript、Vite 和 Tailwind CSS。全站只有一个视觉母题，即 **Agent 舞台**：舞台、上下文胶片、时间线和工具卡片都由真实运行事件推导。教学示意使用同一个舞台渲染，但会画成虚线，并加上“教学示意 · 非运行记录”水印。

## 页面

| 页面 | 入口 | 内容 |
| --- | --- | --- |
| 首页 | `components/home/Home.tsx` | Agent 循环示意（只能手动逐步）、学习旅程（本机真实进度）、继续上次 |
| 导学（第 0 章） | `components/Onboarding.tsx` | 四个前置章节，示意块按原位渲染，检查点自报并存在本机 |
| 课程地图 | `components/Curriculum.tsx` | 领域卡片（MagicBento）、先修路线图（@xyflow/react + elkjs，懒加载）、列表与搜索 |
| 课程页 | `scenes/LessonScenes.tsx` | 课程条与五个场景：理解 / 读码 / 实验 / 自检 / 回顾 |

五个场景都实现 `scenes/types.ts` 中的 `SceneProps`。场景在首次访问时挂载，之后保留状态；运行开始时自动切到实验场景。其他组件可以调用 `requestScene()` 切换场景，例如命令面板。

- **理解**（`UnderstandScene`）：`content/blocks/UnderstandBlocks.tsx` 按作者编排的顺序渲染 v2 块，包括概念、正文、分步讲解、示意舞台、微型自测和先预测。
- **读码**（`CodeScene`）：从 `/api/lessons/{id}/code` 读取由真实源码计算出的“本课新增”、带行号的批注和设计决策。工具函数可以跳到实验中对应的真实 `tool_result`。
- **实验**（`LabScene`）：
  - 实验面板：假设、对照组、观察点，观察点按学习者自己的运行核对；
  - 实验台：舞台、时间线、上下文胶片、工具卡片、通用视图，以及 JSON 检视器；
  - 导览回放条、结论卡；有录制时出现来源切换。
- **自检**（`CheckScene`）：先评信心再作答，并给出选项级反馈；轨迹找错只使用学习者自己的运行；检查点由学习者自报。
- **回顾**（`ReviewScene`）：只展示本机真实记录，不判定“已掌握”。

## 模块

| 目录 | 职责 |
| --- | --- |
| `src/stage/` | `deriveStage`（纯函数：拓扑、span、信号、胶片）、`replay.ts`（回放时钟，带版本令牌）、`AgentStage`、`ContextFilm`、`Timeline`、`ToolCards`、`Lenses`（标准教学事件族的通用视图） |
| `src/content/` | 生成的 v2 类型 `types.gen.ts`、`view.ts`、选择器引擎 `selector.ts`、导览 `guide.ts`、预测 `predict.ts`、块渲染 `blocks/` |
| `src/motion/` | `MotionProvider`（合并系统减少动画、WebGL 与页面可见性）、`useMotionBudget`（离屏暂停，WebGL 同屏最多两个）、`MotionIntent` 意图注册表、动效令牌 |
| `src/i18n/` | i18next、语言注册表、按命名空间组织的 `locales/zh-CN/*.json`、错误码翻译 |
| `src/progress/` | 本机学习进度（localStorage，有独立版本线与迁移阶梯），只记录真实动作 |
| `src/components/backdrops/` | 英雄带动态背景：`Backdrop` 按预设懒加载 React Bits WebGL 着色器，离屏卸载，静态时退化为同色渐变；`backdropFor(category)` 给每个课程领域分配一种氛围。开发预览：`/dev/backdrops.html` |
| `src/hooks/useStudio.ts` | 课程、参数、运行（`POST /api/runs`，断线后按 seq 续读）与回放状态 |
| `src/components/command/` | ⌘K 命令面板（cmdk，懒加载） |
| `src/scenes/lab/` | 实验面板、导览栏、录制视图、实验快捷键 |
| `src/lesson-extensions/` | 构建时登记的课程插槽；扩展加载失败时回退到通用界面 |
| `src/styles/` | 按模块组织的样式；`tokens.css` 存放设计令牌与动效级别开关 |

## 诚实约定（界面层）

- 运行数据只来自真实事件。示意事件带 `provenance=illustration`；录制标注模型和日期，不混入“我的运行”。
- 等待模型时只显示三个点和真实计时，不写“思考中”；回答一次性到达，不加打字机效果。
- 停止运行时，只把仍在执行的工具调用标为“已停止，无结果”，不覆盖已经完成的结果。
- 耗时只取服务端时间戳；回放压缩了过长的真实等待时会注明。响应没有报告 usage 时，只显示字符数并写明原因。
- SDK 标准化数据不会被标成原始 HTTP 报文。
- 进度只记录真实发生的动作：后台预载课程不算“打开”，同一个 run_id 只计一次。

## 动效

- **动效级别**：`<html data-motion="full|static">` 由首屏脚本和 `MotionProvider` 写入，只跟随系统的“减少动画”设置，没有页面内开关。
- **CSS 写法**：统一使用 `:root:not([data-motion="full"])`，Tailwind 的 `motion-reduce:` 和 `motion-safe:` 已跟随这个属性。
- **重效果**：通过 `MotionIntent` 或 `useMotionBudget` 接入，做到按需加载、离屏暂停、WebGL 同屏最多一个，并且都有静态降级。
- **装饰与数据分开**：英雄带动态背景、入场与滚动揭示、悬停反馈、点击火花都只装饰静态界面；运行数据不加装饰性特效，每个真实事件只发一次信号，运行中的流光边框只在真实运行时出现。滚动揭示统一用 `revealProps`，系统中途开启减少动画时尚未滚到的内容也会立即完整显示。

## 文案与多语言

- 界面文案全部放在 `locales/<语言>/<命名空间>.json`，`npm run i18n:check` 检查各语言的键是否一致。
- `src/i18n/__tests__/hardcoded-cjk.test.ts` 用 AST 统计组件里的硬编码中文，数量只许减少。
- 后端错误带 `code`，由前端翻译。
- 课程内容的译文是独立的译文层（`content.<语言>.json`），接口通过 `?lang=` 合并。

## 验证

单元测试使用 vitest（`npx vitest run`），浏览器测试使用 Playwright。浏览器测试的定位方式：

- 用 role、`data-testid` 和 `e2e/i18n.ts` 读取的文案键定位；
- 选择器基线只许减少；
- `e2e/a11y.spec.ts` 用 axe-core 按 WCAG 2.1 A/AA 扫描主要页面。

截图检查可用 `scripts/capture-lab.mjs` 和 `scripts/capture-scenes.mjs`。命令见 [开发验证](validation.md)。
