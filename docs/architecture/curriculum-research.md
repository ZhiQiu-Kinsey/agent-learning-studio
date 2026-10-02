# 课程调研：参考教程对照与平台重构约束

调研日期：2026-10-01。状态：**方向已确认**（2026-10-01，决策见第 9 节）。各课的具体设计在编写时仍可调整。本文档没有修改课程目录、课程实现或 `reference-study.md`；正式采用某项来源时，再按原流程登记阅读范围与固定版本。

## 1. 调研来源与许可边界

| 来源 | 版本 | 许可证 | 复用边界 | 本次阅读范围 |
| --- | --- | --- | --- | --- |
| [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners) | `25b7985` | MIT | 可改编，保留版权与许可声明；不得使用 Microsoft 商标或暗示背书 | 本地 04/05/13；其余 00–18 课 README 按固定 commit 的 raw URL 读取 |
| [Hugging Face Agents Course](https://github.com/huggingface/agents-course) | `b3946b1` | Apache-2.0 | 可改编，附许可证并标注改动；Hub 上的图片、notebook、数据集不在许可范围内 | `units/en/` 全部页面 |
| [深入理解 AI Agent](https://github.com/bojieli/ai-agent-book) | `b789c97` | Apache-2.0 | 同上，建议文件头写 “Adapted from … (Apache-2.0); changes: …” | 全书目录与各章标题，第 1、2、4–7、9、10 章重点段落，实验 README |
| [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) | 2026-10 浅克隆 | MIT | 可改编；`skills/*.md` 来源不明，不复制 | s01–s17、测试、`web/` 学习站 |
| [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) | 2026-10 浅克隆 | MIT | 可改编 | 代码、配置、测试、文档 |
| [claude-cookbooks](https://github.com/anthropics/claude-cookbooks) | 2026-10 稀疏克隆 | MIT | 可改编；随附的第三方数据（股东信、论文、合同样本）不转发 | patterns、tool_use、tool_evaluation、evals、misc、cost_optimization |
| [mcp-for-beginners](https://github.com/microsoft/mcp-for-beginners) | `f97a80a6` | MIT（Java 示例为 Apache-2.0） | 可改编；外链安全文章不复制 | 00–05、07–09、11，Python 路线 |
| [hello-agents](https://github.com/datawhalechina/hello-agents) | 2026-10 稀疏克隆 | **CC BY-NC-SA 4.0** | **仅学习参考**，不复制正文或代码 | 全部章节结构，第 4、7、9、10、12、14 章与 Extra 章节 |

另评估过但不建议引用的仓库：

| 原因 | 仓库 |
| --- | --- |
| 非商业许可 | anthropics/courses、NirDiamant 两个仓库、Datawhale 其他仓库 |
| 无许可证 | HF context-course、AgentGuide、ghuntley 工作坊 |

参考仓库是作者本机的只读副本（固定版本见 [课程来源](reference-study.md)），不参与平台运行。

## 2. 结论摘要

1. **最大的主题缺口是“推理与控制模式”**：ReAct 文本协议与原生调用的对照、TODO 规划、先规划后执行、反思与有界修订，以及链式、路由、并行、编排者-工人、评估者-优化者五种工作流模式。四份以上资料都覆盖了这些主题，而我们的计划完全缺失。它们应作为原生课程，放在 LangGraph 之前，让框架课有对照对象。
2. **第二个缺口是“编码 Agent 与执行环境”**：bash 或文件工具、沙箱、编辑证据、Hooks 与审批闸门。书和 learn-claude-code 都把编码 Agent 当作毕业级项目。
3. **上下文工程需要补两课**：提示缓存与稳定前缀、Skills 与渐进式披露。两者都能用真实的 `cached_tokens` 和 prompt tokens 测量。
4. **质量类课程要加深**：Pass@k 与 Pass^k、配对显著性、LLM 评委与人工标注的一致性校准、按任务计算的成本与帕累托前沿、失败归因与轨迹前缀回归。
5. **对平台的影响比对课程更紧迫**：后续课程需要 span 层级、可暂停续跑的交互式运行、持久化运行记录与多次运行对比、由数据驱动的舞台拓扑、协议报文的分级标注。这些必须在重构地基阶段设计进去（见第 6 节）。
6. **两个外部反例**：learn-claude-code 学习站的模拟器是脚本播放，标注不足，还有编造的输出；Microsoft MCP 课主 notebook 在进程内模拟协议。这印证了“真实数据”红线的必要性，平台需要用契约测试来约束教学示意。

## 3. 课程缺口

| 主题 | 出现于 | 优先级 | 建议去处 |
| --- | --- | --- | --- |
| 文本动作与原生工具调用（无 `stop` 时模型编造 Observation、解析失败率） | HF、hello-agents、mini-swe-agent | 高 | 新课 |
| TODO 规划与状态提示 | 书 ch2、learn-claude-code s05、MS 07 | 高 | 新课 |
| 先规划后执行与重新规划 | MS 07、hello-agents ch4、cookbooks | 高 | 新课 |
| 反思与有界修订（模型自评 vs 测试依据） | MS 09、hello-agents ch4、cookbooks | 高 | 新课 |
| 工作流五模式 | cookbooks、openai-agents-python、书 ch1 | 高 | 两节新课 |
| 提示缓存与稳定前缀 | 书 ch2、cookbooks、openai-cookbook | 高 | 新课 |
| Skills 与渐进式披露、工具搜索 | 书 ch2/ch4、learn-claude-code s07、hello-agents Extra05/08 | 高 | 新课 |
| 编码 Agent：bash 工具、沙箱、编辑证据 | 书 ch5、mini-swe-agent、learn-claude-code s01–s03 | 高 | 新大类 |
| Hooks 与审批闸门（暂停/续跑） | learn-claude-code s03/s04、MS 06、书 ch4 | 中高 | 新课 |
| 评委校准、Pass^k、失败归因 | 书 ch7、cookbooks、hello-agents ch12 | 高 | 扩展评估课 |
| 长时任务：后台、定时、目标循环 | learn-claude-code s11/s12/s17、书 ch6 | 中 | 新课 |
| A2A 与跨进程委派 | MS 11、hello-agents ch10 | 中 | 可选课 |
| 流式输出与流式工具参数 | 书 ch2/ch5、langchain-academy | 中 | 并入异步课 |
| 防篡改回执、事件哈希链 | MS 18 | 中低 | 并入注入课，或作为平台回放完整性功能 |

## 4. 课程表调整方案

原则：

- 已实现的第 1–10 课保持原有显示顺序与目录。
- 规划中的课程只存在于 `catalog.json`，可以重新排序。
- 原生机制在前，框架在后。

重构时课程 ID 与显示课号解耦（第 9 节决策 3），下表课号为按目录顺序计算出的显示课号。

| 大类 | 课程（新增标注 ★，扩展标注 ＋） |
| --- | --- |
| A 原生基础 | 1 工具选择 · 2 依赖式多轮调用 · 3 错误处理与安全边界 |
| B 任务与接口 | 4 任务目标与验收＋ · 5 结构化输出与业务校验 · 6 提示词与工具描述＋ |
| C 上下文与状态 | 7 消息与上下文 · 8 应用 state 与生命周期 · 9 上下文预算与压缩＋ · 10 持久记忆＋ · ★11 提示缓存与稳定前缀 · ★12 Skills 与渐进式披露 |
| ★R 推理与控制模式 | ★13 文本动作与原生工具调用 · ★14 规划：TODO 清单与状态提示 · ★15 先规划后执行与重新规划 · ★16 反思、评审与有界修订 · ★17 工作流模式：链式、路由与并行 · ★18 编排者-工人与评估者-优化者 |
| D 知识与检索 | 19 资料加载与分块 · 20 关键词、向量与混合检索 · 21 RAG 回答与引用＋ · 22 Agentic RAG 与有界迭代 |
| E 框架与运行编排 | 23 LangChain 与原生对照 · 24 LangChain 工具与结构化 · 25 LangGraph 状态与分支 · 26 异步、并发、流式与取消＋ · ★27 Hooks 与审批闸门 · 28 人工介入、检查点与恢复 |
| ★X 编码 Agent 与执行环境 | ★29 单 bash 工具编码 Agent 与沙箱 · ★30 文件工具、编辑策略与变更证据 |
| F 质量与工程可靠性 | 31 评估集与验证器＋ · 32 可观测性、用量与成本＋ · 33 可靠工具、重试与幂等 · 34 提示注入与工具权限＋ |
| G 协议与工具服务 | 35 MCP 原理与工具接入 · 36 MCP 连接生命周期与多服务 · ★37 A2A 与跨进程委派（可选） |
| H 综合实践与交付 | 38 多 Agent 模式与子 Agent 隔离＋ · 39 委派、上下文合并与预算 · ★40 长时任务：后台、定时与目标循环 · 41 本地交付、部署与恢复 · 42 毕业项目：本地编码助教 / 本地学习助教两条路线（第 9 节决策 2） |

选修方向保留，并做以下补充：

- smolagents：衔接第 13 课的“代码即行动”。
- 浏览器 Agent：改为本地夹具站点加可访问性树，不需要视觉模型。
- 微调与 RL：补充“轨迹即训练数据”。

### 各课设计要点

| 课 | 真实运行实验 | 界面必须展示的证据 |
| --- | --- | --- |
| 11 | 三组对照：时间戳在前 / 稳定前缀 / 稳定前缀＋预热，各跑 5 次；文档长度超过服务商的最小缓存长度 | 每次调用的 cached/prompt 比例、TTFT、前缀哈希、“服务商报告为 0”状态 |
| 12 | 全量注入技能 vs 目录＋`load_skill` 按需加载；模糊描述 vs 精确描述的触发率，包括不该触发的提示 | 每次请求的分段 token（来自 usage）、加载了哪个技能 |
| 13 | 同一组任务分别用正则文本协议和原生调用；去掉 `stop` 让模型编造 Observation，与真实工具结果对照 | 原始 `content` 与 `tool_calls` 并列、解析失败事件、`finish_reason` |
| 14 | 同一多步任务：有无 `todo_write`、提醒开/关；用第 4 课的验收器判定 | TODO 快照与逐轮差异、标注为“运行层注入”的提醒、距上次更新的轮数 |
| 15 | 夹具工具在第 2 步失败：静态计划 vs 动态重规划 vs ReAct 基线 | 带版本的计划、步骤状态、计划差异与修订原因 |
| 16 | 模型自评 vs 以真实 pytest 结果为依据的评审；设迭代上限 | 草稿 v0…vn 的差异、评审 JSON、验证器输出、停止原因、累计 token |
| 17/18 | 路由用 20 张已标注工单，统计准确率与混淆矩阵；并行 vs 串行墙钟时间；编排的 N+1 次调用成本；评估者-优化者必须有 `max_iters` | 路由决策、并行分支时间线、计划产物与嵌套的工人 span、每轮评审结论 |
| 29 | 带失败测试的夹具仓库，由平台重新运行 pytest 来验收 | 命令、cwd、策略判定、退出码、stdout/stderr 首尾、截断标记、超时/杀进程树、耗时、文件 diff |
| 31 | 4 类用例（单工具 / 多选一 / 并行 / 无关）× 提示变体 × 种子；30–50 条人工标注检验评委 | Pass@k / Pass^k、配对差异与置信区间、评委与人工的混淆矩阵与 κ、位置互换偏差、可跳转到单次回放的矩阵 |
| 32 | 模型 × 配置阶梯，按任务计成本 | $/任务、通过率、帕累托阶梯、价格表日期 |
| 34 | 投毒的工具描述、调用 N 次后跑路并发出 `list_changed`、跨服务遮蔽、审批参数摘要被替换 | 工具描述哈希差异、重新审批记录、审批摘要校验结果 |
| 35/36 | 自写 stdio 服务暴露已有课程工具；两服务都提供 `search` 造成命名冲突；崩溃后重启并重新发现 | 线上原始帧（见 6.5）、连接生命周期时间线、能力差异、命名空间映射 |

### 现有课程的低成本扩展（重构后再做）

| 课 | 扩展内容 |
| --- | --- |
| 第 4 课 | “声称完成 vs 证明完成”，预告目标循环 |
| 第 6 课 | 工具描述“空白 / 良好 / 误导”三组矩阵 |
| 第 9 课 | 拆开 assistant 与 tool 消息时，记录服务商真实返回的 400；对比不压缩 / 清理旧工具结果 / 摘要压缩三组，并用“保留探针问题”检验压缩后信息是否还在；对比隔离与压缩 |
| 第 10 课 | 按 persistent / current_task 范围过滤记忆；召回的“指令”只当作数据处理，关联注入课 |

## 5. 教学做法

| 做法 | 说明 | 来源 |
| --- | --- | --- |
| 连续项目 | 每课回答“我的 Agent 新增了什么能力”，用 8 项能力表标出进度（模型、工具、知识、上下文、记忆、规划、编排、信任） | Microsoft STUDY_GUIDE |
| 测验节奏 | 每 2–3 页一个小测验；**每个错误选项单独解释它针对的误解**，需要扩展测验 schema | HF |
| 先失败再修正 | 先让问题真实发生，例如缺 `stop` 时编造的 Observation、拆开工具消息对导致的 400，再引入修正 | HF、learn-claude-code |
| 轨迹找错练习 | 在回放中找出第一个错误步骤，说明 Agent 如何恢复 | HF code_agents、书 ch7 失败归因 |
| “能证明什么 / 不能证明什么” | 每个实验的结论边界；与平台“证据”定位一致 | Microsoft 18 |
| 决策与替代方案块 | 设计取舍、被放弃的方案及理由 | learn-claude-code annotations |
| 本课新增卡片 | 从真实源码做 AST 提取，比较相邻两课最小实现的新增工具、函数和行数变化 | learn-claude-code `extract-content.ts`；由数据计算，不手写 |
| 量化作业 | 例如“至少 8 个评估用例，其中 2 个必须走审批”；按设计连贯性评分，没有唯一答案 | Microsoft 16/17 |
| 毕业评分服务 | 本地评分服务加隐藏题集；答案规范化规则对学习者可见 | HF Unit 4 |

## 6. 对平台重构的约束

### 6.1 事件信封 v2

现有字段 `schema_version`、`type`、`round`、`timestamp`、`data` 保留，新增：

| 字段 | 用途 |
| --- | --- |
| `run_id`、`seq` | 单次运行内单调递增，用于持久化、回放与哈希链 |
| `span_id`、`parent_span_id`、`span_kind` | 嵌套层级：run → agent → step → llm/tool/retrieval/guard/compaction/eval_case |
| `actor` / `agent_id` / `role` | 多 Agent、子 Agent，以及规划者/执行者/评审者/评委等角色 |
| `provenance` | 数据来源，见 6.5 |
| `representation` | 数据表示层级，见 6.5 |

span 的开始与结束分别发事件，前端把它们合成为树和时间线。现有扁平事件视为根 span 下的子事件，保持兼容。

### 6.2 标准事件族

用通用视图渲染，新课只需输出数据：

| 事件族 | 关键字段 | 服务的课程 | 通用视图 |
| --- | --- | --- | --- |
| `llm.usage`（并入 response） | 归一化后的 prompt / cached_read / cache_write / completion / reasoning、ttft、finish_reason、前缀哈希 | 11、32 等全部模型课 | 上下文胶片、成本面板 |
| `context.segments` / `context.compacted` | 分段（system/tools/history/status/skill）、token、哈希、与上一轮第一处不同的位置；压缩前后对比 | 7、9、11、12 | 上下文胶片 |
| `plan.*` | 版本、步骤（id、依赖、验收条件、状态）、修订原因与差异 | 14、15、18 | 计划板（可切换版本） |
| `reflection.*` / `evaluator.iteration` | 迭代、草稿、评审（量规、裁决、来源：模型/代码）、停止原因 | 16、18、31 | 草稿差异对比 |
| `router.decision` / `parallel.branch` | 候选、选择、兜底；分组与分支 id | 17、18 | 路由卡、并行泳道 |
| `harness.injected` / `hook.fired` | 注入类型与文本；钩子阶段、处理器、裁决 | 14、27、40 | 运行层注入标记 |
| `approval.requested` / `approval.resolved` | 审批 id、风险等级、规范化参数摘要、决定、耗时；运行进入 paused/resumed | 27、28、34 | 审批卡（可交互） |
| `sandbox.exec` / `file.changed` | 第 4 节第 29 课所列字段；文件前后哈希与统一 diff | 29、30 | 终端面板、diff 视图 |
| `bg.*` / `goal.evaluated` | 后台任务起止、退出码、在哪一轮注入；目标评估 ok/impossible/reason | 26、40 | 后台泳道 |
| `retrieval.query` / `retrieval.candidates` | 改写后的查询；候选块的 BM25、向量、融合、重排分数及最终选择 | 19–22 | 候选表、回答到块的引用 |
| `mcp.conn.state` / `mcp.wire` / `mcp.tools.diff` | 见 mcp-for-beginners 调研；线上帧逐帧记录 | 35–37 | 协议时序图（wire 泳道） |
| `eval.case` / `eval.matrix` | 配置、用例、试次、得分、评委与人工标注并列、轨迹引用 | 31、32 | 评估矩阵（可下钻到回放）、帕累托图 |

现有的 `lesson.report`、`lesson.state`、`lesson.memory` 保留，并纳入同一套契约。

### 6.3 运行存储与交互式运行

- **持久化运行记录**（已采纳，第 9 节决策 4）：改为服务端 append-only 的 SQLite，放在 `.runtime/`，每个事件写入后即落盘。原因：
  - 评估矩阵、多次运行对比、检查点恢复都需要它；
  - 事件已在服务端脱敏，不需要存进浏览器存储。

  这项取代此前“浏览器 IndexedDB”的设想。
- **运行成为资源**：`POST /api/runs` 创建运行，`GET /api/runs/{id}/events` 读取事件流（SSE，可从某个 `seq` 续读），`POST /api/runs/{id}/approvals` 提交审批。现有单向 SSE 不能承载暂停续跑。
- **哈希链（可选）**：每个事件带 `prev_hash`，用来证明回放的就是当初收到的事件。

### 6.4 舞台与视图

- **拓扑由数据驱动**：节点由课程清单声明，再根据事件补全（子 Agent、MCP 服务、工具池变化），不写死“用户/运行层/模型/工具”。
- **视图按透镜组合**：上下文胶片、span 树与泳道时间线、计划板、diff 视图、审批卡、终端面板、检索候选表、协议时序图、评估矩阵、成本图。课程清单用 `lenses` 组合。

### 6.5 来源与表示的标注

**来源 `provenance`：**

| 取值 | 含义 |
| --- | --- |
| `real_run` | 本机真实运行 |
| `recorded_run` | 随课程分发的真实运行录制，附模型、时间与服务商；约束见第 9 节决策 5 |
| `offline_recompute` | 依据已记录的 usage 离线重新计算，例如成本 |
| `illustration` | 教学示意 |

**表示 `representation`：**

| 取值 | 含义 |
| --- | --- |
| `wire` | 传输边界上截获的原始字节 |
| `parsed` | 我们自己对原始字节做的 JSON 解析 |
| `sdk_standardized` | SDK 对象，标注 SDK 版本 |
| `http_body` | 现有原生 HTTP 请求体 |

界面不得在 `wire` 标签下展示 SDK 对象。

### 6.6 用量归一化

各服务商的缓存字段不同：

- OpenAI 和 DashScope：`prompt_tokens_details.cached_tokens`
- DeepSeek：`prompt_cache_hit_tokens`
- Anthropic：`cache_read_input_tokens` / `cache_creation_input_tokens`

这几个字段名需要按实际固定的服务商版本逐一核对。归一化后同时保留原始 usage；没有提供的字段显示“未报告”，不填 0。

### 6.7 本机执行安全基线（编码 Agent 课）

| 项目 | 要求 |
| --- | --- |
| 工作区 | 每次运行使用独立的临时工作区，路径解析后校验必须位于其内 |
| 环境变量 | **清理后再传给子进程**；mini-swe-agent 会把 `os.environ` 原样传入，导致密钥泄漏 |
| 超时 | 超时后杀掉整棵进程树：Windows 用 `taskkill /T /F` 或作业对象，只调用 `process.kill()` 会残留子进程 |
| 命令 | 拒绝破坏性命令；默认逐条确认；输出按首尾截断 |
| 限额 | 步数、墙钟时间、成本上限 |

### 6.8 教学示意的约束

- 为每个示意编写契约测试，确保它不违反运行时约束：工具调用与结果成对、id 格式、事件顺序。思路借鉴 learn-claude-code 的 `tests/test_web_scenarios.py`。
- 示意不得出现具体的执行输出数值，例如“12 passed in 0.42s”。确需展示时，使用 `recorded_run`。

## 7. 中文术语约定

2026-10-01 确认（第 9 节决策 6）。用词参考 hello-agents 的用词频率，并沿用本项目现有的习惯。

### 书写格式

- 外来术语在 zh-CN 正文中写作“**中文（英文原词）**”，例如：
  - 运行层（Harness）
  - 渐进式披露（Progressive Disclosure）
  - 人工介入（Human-in-the-Loop）
- 每课、每章或每个导学章节**首次出现**时中英并列，之后只写中文即可。
- 术语表、悬停释义（WarmTooltip）和课程地图的知识点标签**始终**中英对照。
- 下列情况保持原样，不加括号：
  - 已直接使用英文的词：Agent、Token、RAG、MCP、A2A、JSON Schema、SSE。
  - 缩写。
  - 代码标识符，如 `tool_calls`、`tool_call_id`、`role: tool`。
- 英文界面（en）只写英文原词，不附中文。
- 术语表作为单一数据源，与内容 v2 一起结构化维护，翻译覆盖层不得改动术语映射。示意结构如下，具体 schema 在重构中确定：

  ```json
  { "id": "harness", "zh-CN": "运行层", "en": "Harness", "note": "…" }
  ```

  内容校验器可以检查首次出现是否中英并列。

### 术语表

| 英文 | zh-CN 写法 | 说明 |
| --- | --- | --- |
| Agent | Agent | 保持现有项目用法；子 Agent 统一为“子 Agent”，hello-agents 用“智能体” |
| tool calling / function calling | 工具调用（Tool Calling）/ 函数调用（Function Calling） | 前者指概念，后者指 API 机制 |
| evaluation | 评估（Evaluation） | 不用“评测” |
| reflection / revise | 反思（Reflection）/ 修订（Revise） | 不用“优化”，避免与 optimize 混淆 |
| human-in-the-loop | 人工介入（Human-in-the-Loop） | 沿用现有第 19 课名称 |
| progressive disclosure | 渐进式披露（Progressive Disclosure） | |
| context rot / attention budget | 上下文腐蚀（Context Rot）/ 注意力预算（Attention Budget） | |
| harness | 运行层（Harness） | 沿用导学现有译法 |
| prompt caching | 提示缓存（Prompt Caching） | |
| plan-and-execute | 先规划后执行（Plan-and-Execute） | |
| orchestrator-workers / evaluator-optimizer | 编排者-工人（Orchestrator-Workers）/ 评估者-优化者（Evaluator-Optimizer） | 专有模式名，保留“优化者” |
| span / trace | 跨度（Span）/ 轨迹（Trace） | |
| sandbox | 沙箱（Sandbox） | |
| artifact（A2A） | 产物（Artifact） | |

## 8. 外部资料中需要避开的问题

- mcp-for-beginners：课程正文定义的是 2026-07-28 版协议，示例代码却多为 2025-11-25 版 SDK v1；部分 README 代码调用了不存在的 API。第 35–36 课需要先固定 SDK 版本，再按规范核对。
- claude-cookbooks：路由遇到未知标签会崩溃；评估者-优化者是无上限循环；编排者-工人实际串行执行；评委用 assistant 预填，多数 OpenAI 兼容接口不支持；评分换算疑似比例错误。这些都适合作为“先失败再修正”的素材，不能照搬。
- mini-swe-agent：v2 默认已经使用原生工具调用，文本解析改为可选；DashScope 模型会让其成本计算抛出异常。
- learn-claude-code：代码使用 Anthropic Messages 格式。移植到 OpenAI 兼容格式时，注入的提醒文本必须放在全部 tool 消息之后作为单独的 user 消息，否则服务商会拒绝请求。

## 9. 决策记录

2026-10-01 全部按建议确认。

### 决策 1：采用第 4 节的扩充方向

约 42 课，新增“推理与控制模式”“编码 Agent 与执行环境”两个大类。编写优先级：

| 优先级 | 课程 |
| --- | --- |
| P1 | 11–16，以及 29、31 的扩展 |
| P2 | 17、18、27、30、40 |
| P3 | 12、37 |

### 决策 2：毕业项目设两条路线

- 本地编码助教、本地学习助教，学习者二选一。
- 两条路线共用同一套本地评分服务（隐藏题集，答案规范化规则对学习者可见）和验收方式（平台独立验证，Agent 声称完成不算）。

### 决策 3：课程 ID 与显示课号解耦

- 课程使用稳定的 slug ID，例如 `tool-selection`。显示课号由 `catalog.json` 的目录顺序计算，插入新课无需重新编号。
- 现有数字 ID 保留为别名，保证旧链接和测试在迁移期间可用。
- 已有的 `lessons/lesson_NN_*` 目录在重构时决定是否改名；新课目录以 slug 命名，转成合法的 Python 包名。

### 决策 4：运行记录持久化

采用 6.3 的服务端 append-only SQLite 运行存储，运行成为可创建、可续读、可审批的资源。

存储分工如下：

| 数据 | 存放位置 |
| --- | --- |
| 运行记录（事件流、录制导出的来源） | 服务端 SQLite |
| 学习进度（阅读、自测、检查点、能力表） | 浏览器 localStorage，只记录本机真实发生的动作 |

2026-10-01 用户再次确认这一分工。它取代此前“运行记录也存浏览器 IndexedDB”的设想。

### 决策 5：随课分发真实运行录制（`recorded_run`）

为了不违背“运行数据只来自真实事件”的红线，必须满足以下约束：

- **来源**：只能来自平台正常路径产生的真实运行，由导出脚本从运行存储中原样导出。事件内容不得手工编辑、裁剪或拼接。
- **元数据**：模型、服务商、表示方式（`http_body` / `sdk_standardized`）、录制日期、平台版本、课程源码哈希、事件完整性哈希。
- **校验**：校验脚本检查以下内容。
  - 完整性哈希必须一致。
  - 事件结构必须合法。
  - `provenance` 必须为 `recorded_run`。
  - 课程源码哈希与当前实现必须一致；不一致时提示重新录制，不静默沿用旧录制。
- **展示**：界面使用独立标识，例如“录制的真实运行 · 模型 · 日期”。录制不得混入学习者自己的运行记录，也不能显示为“你的运行”。
- **脱敏**：沿用服务端脱敏，录制文件不得包含密钥、认证头或本机私有路径。

### 决策 6：术语

采用第 7 节约定：外来术语写作“中文（英文原词）”，每课首次出现时中英并列；术语表作为单一数据源。

## 10. 后续步骤

1. 第 6 节的约束和第 9 节决策 3–5 并入平台重构的地基设计：
   - 事件信封 v2；
   - 运行存储与交互式运行接口；
   - 数据驱动的舞台；
   - 来源与表示标注；
   - slug ID；
   - 录制格式与校验；
   - 术语表数据结构。
2. 重构完成内容 v2 与渲染器之后，按第 4 节改写 `catalog.json`，按决策 1 的优先级逐课编写新内容，直接使用 v2 格式和翻译覆盖层。
3. 正式采用某个来源时，在 `reference-study.md` 登记固定版本与实际阅读范围；改编内容遵守第 1 节的许可要求。
