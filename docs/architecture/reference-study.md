# AgentStart：当前课程来源与教学取舍

[English](reference-study.en.md) · **简体中文**

更新日期：2026-10-04。课程参考来源为第 1 节表中的正式教程。固定版本与阅读范围用于核对实际借鉴内容，课程讲解和 Python 实验由本项目编写。

## 1. 固定参考快照

| 教程 | 固定 commit | 许可证 | 主要用途 |
| --- | --- | --- | --- |
| [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners) | `25b7985f3b2dc37a84f4a7387ccd3c9f0e5b1595` | MIT | 借鉴学习目标、主题模块、连续课程助教项目和按新增能力验收的学习方式。 |
| [Hugging Face Agents Course](https://github.com/huggingface/agents-course) | `b3946b1d09d29c65736e219d48a8a736a2c52154` | Apache-2.0 | 借鉴基础到框架、场景实践、评估的分层结构，框架选修分支，以及 State/Node/Edge 和 RAG 流程的拆分。 |
| [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book) | `b789c97a8f3de5b405a6f6dfa8289208d679d0b8` | Apache-2.0 | 补足任务验收、上下文实验、工具契约、独立验证器、运行生命周期、成本和多 Agent 工程取舍。 |
| [Hello-Agents](https://github.com/datawhalechina/hello-agents) | `4b014ad47e2658af24b59f21e7bdb3f89a66205e` | CC BY-NC-SA 4.0 | 只借鉴章节组织和讲解顺序，不复制正文、代码和配图（见第 8 节）。 |
| [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) | `04d809ceab9df28f9adaed044884180159172930` | MIT（仓库 `LICENSE.md`，Copyright (c) 2025 Kilian A. Lieret and Carlos E. Jimenez） | 借鉴“文本动作 + 严格解析 + 最小 Agent 循环”的做法，用于文本动作课与第 8 节的“工作流还是 Agent”讲解；只借鉴结构，没有复制代码（见第 8 节）。 |

参考教程不参与平台运行。未读取的文件不计入阅读范围；复用源码或正文时应保留相应许可与版权信息。

## 2. Microsoft：借鉴主题目录、目标和连续项目

根目录有 `00-course-setup` 与 01–18 课：概念、框架、设计模式、工具、Agentic RAG、可信度、规划、多 Agent、反思、生产、协议、上下文工程、记忆、Microsoft Agent Framework、浏览器、部署、本地 Agent、安全。

实际查看了 `04-tool-use/README.md`、工具样例目录、`05-agentic-rag` 和 `13-agent-memory` 的文件组织，以及根目录 `STUDY_GUIDE.md`。课程使用 README 讲解、学习目标、视频和 Python notebook；当前 README 的主要运行栈是 Microsoft Agent Framework / Microsoft Foundry。

最值得借鉴的是学习目标明确、每课目录独立，以及学习指南里的连续项目：每学一课，回答“我的 Agent 新增了什么能力？”我们将沿用现有 `lessons/lesson_NN_*`，每课包含：

1. 前置知识、目标和一个可验证的问题。
2. 实际 Python 入口、工具、必要数据。
3. 默认成功案例与至少一个边界案例。
4. 观察清单：应该在哪个请求、响应或状态中找到证据。
5. 练习与过关条件；只读完页面不代表掌握。

我们保留百炼和普通 Python 作为基础，暂不引入 Azure 账号、Foundry 服务或整套 notebook 运行依赖。跨语言 notebook 可作扩展阅读，不增加初学阶段的环境负担。

## 3. Hugging Face：借鉴阶段、框架分支和评估闭环

已阅读 `units/en/_toctree.yml` 和相关英文单元：

- Unit 1：Agent、LLM、消息、工具、行动/观察循环，穿插小测与实践。
- Unit 2：smolagents、LlamaIndex、LangGraph 三个框架分支。
- Unit 3：用工具构造 Agentic RAG 场景。
- Unit 4：最终项目和基准评估。
- Bonus Unit 2：trace/span、延迟、成本、错误和离线/在线评估。

`unit2/langgraph/building_blocks.mdx` 用 State、Node、Edge、StateGraph 分解编排，适合与我们原生 Python 的状态字典、函数和条件分支逐一对应。`unit4/hands-on.mdx` 展示题集、答案提交和评分 API；我们先借鉴可重复题集与明确评分标准，后续是否参加外部榜单另行决定。

我们的教学顺序先建立原生循环，再用同一任务比较框架，避免把框架 API 的熟练程度误当成 Agent 原理的理解。评估不只放在最后一课：工具选择、依赖顺序、错误处理，从第一阶段就能检查。

## 4. 《深入理解 AI Agent》：机制与工程验证

参考固定快照中的模型、运行层与环境边界，任务验收、工具契约、上下文压缩、持久记忆、成本与多 Agent 工程取舍。实际章节阅读范围见 [第二章来源](chapter2-sources.md)、[消息与状态来源](context-state-sources.md) 和 [预算与记忆来源](budget-memory-sources.md)。不将未复现的配套实验当作平台已具备的能力。

## 5. 平台与课程边界

平台使用 React + TypeScript + Vite、FastAPI 和本机 Python。课程按“概念 → 最小实现 → 运行证据 → 实验 → 自检”组织。框架课程在制作时核对 API 与依赖；运行和回放保持独立，回放不产生新请求。

当前“原生基础”“任务与接口”“上下文与状态”“推理与控制模式”四个单元共 24 门课可运行（来源见第 6 节与各单元的来源文档），其余课次保留为规划。课程目录由 `curriculum/catalog.json` 统一维护；实现方式见 [新增课程指南](adding-lessons.md)，完整验收见 [开发验证](validation.md)。

## 6. 推理与控制模式新课的来源（2026-10）

“推理与控制模式”大类按 `curriculum-research.md` 第 9 节决策 1 编写。每课只登记实际读过的文件；固定版本沿用第 1 节与 `curriculum-research.md` 第 1 节的快照。提示词、解析器、夹具与实验均由本项目编写，没有复制参考项目的代码。

| 课程 | 来源与固定版本 | 实际阅读 | 借鉴了什么 |
| --- | --- | --- | --- |
| 13 `text-actions` | Hugging Face Agents Course `b3946b1`（Apache-2.0） | `units/en/unit1/actions.mdx`、`units/en/unit1/dummy-agent-library.mdx` | stop-and-parse 的讲法；“不加 stop 时模型自己写出 Observation”这一现象。本课改为本地成绩表、严格解析和编造内容的并列记录 |
| 14 `todo-planning` | learn-claude-code 2026-10 浅克隆 `ce8f9f1`（MIT） | `docs/zh/s03-todo-write.md`、`agents/s03_todo_write.py`（TodoWrite 在这套编号里是 s03，s05 是技能加载；同一 commit 另有按目录组织的 `s05_todo_write/`，章节编号不同，两套编号不要混用） | todo_write 整体替换清单、同一时间一项进行中、连续几轮未更新就由运行层提醒。本课把提醒改为 OpenAI 兼容格式下 tool 消息之后的单独 user 消息，并加上独立验收器 |
| 15 `plan-and-replan` | Microsoft AI Agents for Beginners `25b7985`（MIT） | `07-planning-design/README.md`（按固定 commit 的 raw URL 读取） | 任务分解、用结构化输出表示计划、子任务结果影响后续步骤时迭代规划。本课改为单 Agent 的规划器 / 执行器分工，加入固定故障、修订上限和版本差异 |
| 16 `reflection-revision` | Microsoft AI Agents for Beginners `25b7985`（MIT） | `09-metacognition/README.md`（按固定 commit 的 raw URL 读取） | 自我评估与纠正、外部反馈的作用。本课把“外部反馈”落实为真实执行的测试用例，并加上迭代上限与停止原因 |
| 17 `workflow-patterns` | claude-cookbooks 2026-10 稀疏克隆 `d7265d6`（MIT） | `patterns/agents/basic_workflows.ipynb` | 提示链、并行、路由三种工作流的划分。原示例路由遇到未知标签会出错、没有步骤间检查；本课加入检查门、兜底记录、标注对照与服务端计时 |
| 18 `orchestrator-evaluator` | claude-cookbooks `d7265d6`（MIT） | `patterns/agents/orchestrator_workers.ipynb`、`patterns/agents/evaluator_optimizer.ipynb` | 两种模式的角色划分。原示例工人串行、评估循环无上限、用 XML 解析；本课改为并行工人（按 branch 配对）、max_iters、前置格式检查与调用账本 |

## 7. 第二轮新课与拆分课的来源（2026-10-03）

| 课 | 资料 | 用到的部分 | 本课做法 |
| --- | --- | --- | --- |
| `chat-request`、`multi-turn-history`、`sampling-variance` | Hugging Face Agents Course `b3946b1`（Apache-2.0） | `units/en/unit1/messages-and-special-tokens.mdx`、`what-are-llms.mdx` 的消息角色与生成概念 | 只借鉴“先看消息与生成，再讲 Agent”的顺序；三课的请求、对照与报告由本项目编写，结论只来自真实运行 |
| `tool-proposals` | Microsoft AI Agents for Beginners `25b7985`（MIT） | `04-tool-use/README.md` 的工具定义与调用流程 | 把“模型提出调用”和“程序执行”拆成两课，本课只观察提议、不执行 |
| `prompt-caching` | 服务商文档（2026-10-03 核对）：[百炼上下文缓存](https://help.aliyun.com/zh/model-studio/context-cache)、[DeepSeek 缓存](https://api-docs.deepseek.com/guides/kv_cache)、[Anthropic 提示缓存](https://platform.claude.com/docs/en/docs/build-with-claude/prompt-caching) | 各家用量里的缓存字段名 | 只用于字段归一化；正文不写最小长度、有效期等具体数字，命中以响应实际报告为准，未报告不记 0 |
| `skills-disclosure` | — | — | 4 个技能文件与对照实验均为本项目编写；“目录加按需加载”的思路是业界通用做法，没有复用任何上游文本 |
| `context-compaction`、`memory-lifecycle` | 沿用拆分前第 9、10 课的来源，见 [上下文预算、压缩与持久记忆的参考范围](budget-memory-sources.md) | — | 拆课没有新增外部材料 |

另外参考了 [Hello-Agents](https://github.com/datawhalechina/hello-agents)（`4b014ad`，CC BY-NC-SA 4.0）的课程组织方式：每种范式固定讲法、代码按职责分块、自检分层。该许可证不允许商业使用并要求相同方式共享，所以只借鉴组织思路，没有复用正文或代码。第 8 节登记了扩写导学时的具体阅读范围。

## 8. “开始之前”导学与全部课程讲解扩写的来源（2026-10-04）

这一节登记扩写前的阅读范围：导学要讲 Agent 的由来、LLM 怎样工作、模型的局限、Agent 的组成、工作流还是 Agent；各课要加深概念讲解。固定版本见下表，与第 1 节一致。导学自身此前的来源见 [前置学习章节：来源与取舍](onboarding-sources.md)，不重复登记。

- 这里登记的是各写作环节实际用到的范围；某个文件最终没读，就从表里删掉，不计入借鉴。固定版本均已用 `git rev-parse` 与 `git cat-file -e <commit>:<path>` 核对过。
- 讲解、示意、代码、夹具与实验均由本项目重新编写，没有复制参考项目的正文、代码或配图。
- 两种借鉴方式：
  - **借鉴结构**：只取章节顺序、提问方式、例子的安排和概念划分，用自己的话与自己的运行证据重写。
  - **改写复用并署名**：许可证为 MIT 或 Apache-2.0 才允许，改写的段落在此登记来源，并在 `THIRD_PARTY_NOTICES.md` 补登版权声明与许可证文本。目前没有这类段落。
- `THIRD_PARTY_NOTICES.md` 只登记复制或改编的上游代码与资源。下表所有来源都属“借鉴结构”，不进入该清单。

| 资料 | 固定版本 | 许可证 | 登记的阅读范围 | 借鉴方式与用途 |
| --- | --- | --- | --- | --- |
| [Hello-Agents](https://github.com/datawhalechina/hello-agents) | `4b014ad47e2658af24b59f21e7bdb3f89a66205e` | CC BY-NC-SA 4.0（仓库 `LICENSE.txt`） | `docs/前言.md`；`docs/chapter1/第一章 初识智能体.md`、`docs/chapter2/第二章 智能体发展史.md`、`docs/chapter3/第三章 大语言模型基础.md`、`docs/chapter4/第四章 智能体经典范式构建.md`（中文版） | 借鉴结构：章节组织和讲解顺序，即问题驱动、贯穿全章的例子、能力逐级上升的阶梯。许可证禁止商业使用并要求相同方式共享，所以不复制正文、代码和配图，也不翻译或近似改写其段落 |
| [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners) | `25b7985f3b2dc37a84f4a7387ccd3c9f0e5b1595` | MIT | `01-intro-to-ai-agents/README.md`、`04-tool-use/README.md`、`07-planning-design/README.md`、`08-multi-agent/README.md`、`09-metacognition/README.md`、`13-agent-memory/README.md`、`STUDY_GUIDE.md`（各课的 `code_samples/` 与 `images/` 不读不用）。本地是稀疏克隆，这些目录未必检出，按固定 commit 用 `git show` 或 raw URL 读取，已用 `git cat-file -e` 核对文件存在 | 借鉴结构：“什么是 Agent、哪些场景适合用 Agent”的概念划分和组成部分的列法，以及工具、规划、多 Agent、元认知、记忆各主题的讲解范围；说法与例子重写 |
| [Hugging Face Agents Course](https://github.com/huggingface/agents-course) | `b3946b1d09d29c65736e219d48a8a736a2c52154` | Apache-2.0 | `units/en/unit1/` 下的 `what-are-llms.mdx`、`messages-and-special-tokens.mdx`、`tools.mdx`、`actions.mdx`、`observations.mdx`、`dummy-agent-library.mdx`。同名中文页在 `units/zh-CN/unit1/`，本地未检出，需要时用 `git show` 读取 | 借鉴结构：“LLM 与消息 → 工具 → 行动 / 观察循环”的顺序，以及 stop-and-parse 的演示思路。`actions.mdx` 与 `dummy-agent-library.mdx` 在第 6 节、`messages-and-special-tokens.mdx` 与 `what-are-llms.mdx` 在第 7 节已登记过，这里补足范围 |
| [深入理解 AI Agent](https://github.com/bojieli/ai-agent-book) | `b789c97a8f3de5b405a6f6dfa8289208d679d0b8` | Apache-2.0 | `book/introduction.md`；`book/chapter1.md`、`chapter2.md`、`chapter3.md`、`chapter4.md`、`chapter5.md`、`chapter6.md`、`chapter7.md`、`chapter10.md`（中文版；各章配套实验目录不在范围内） | 借鉴结构：Agent 由来、模型与运行层的分工、模型局限、上下文与工具、记忆、规划与多 Agent 的归纳。每个结论仍以本项目自己的真实运行为准 |
| [claude-cookbooks](https://github.com/anthropics/claude-cookbooks) | `d7265d6ae994ccd8429db0594b000073b2f9ad43` | MIT（Copyright (c) 2023 Anthropic） | `tool_use/`：`calculator_tool.ipynb`、`parallel_tools.ipynb`、`extracting_structured_json.ipynb`、`tool_use_with_pydantic.ipynb`、`context_engineering/context_engineering_tools.ipynb`；`misc/`：`how_to_enable_json_mode.ipynb`、`prompt_caching.ipynb`、`speculative_prompt_caching.ipynb`；`patterns/agents/`：`README.md`、`basic_workflows.ipynb`、`orchestrator_workers.ipynb`、`evaluator_optimizer.ipynb`；`extended_thinking/extended_thinking.ipynb`、`capabilities/classification/guide.ipynb`、`skills/README.md` | 借鉴结构：工具调用、结构化输出、提示缓存、工作流模式、扩展思考、分类与技能各主题的讲法和对照安排。`patterns/agents/` 下的三个 notebook 在第 6 节已登记过。示例、工具与数据由本项目重写 |
| [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) | `ce8f9f186058939da54c9d6fead78dfb5d0fd6c3` | MIT（Copyright (c) 2024 shareAI Lab） | `README-zh.md`（开篇“Agency 来自模型，Agent 产品 = 模型 + Harness”一节对应 Agent 由来与运行层）；`s01_agent_loop/README.zh.md`、`s02_tool_use/README.zh.md`、`s08_context_compact/README.zh.md`、`s09_memory/README.zh.md`；`docs/zh/s03-todo-write.md`、`docs/zh/s05-skill-loading.md`、`agents/s03_todo_write.py` | 借鉴结构：“模型负责决策、运行层负责环境”的划分，以及循环、工具、待办、技能、压缩、记忆各讲一件事的拆法。该仓库同一 commit 有两套编号：`docs/zh/`、`agents/` 下 TodoWrite 是 s03、技能加载是 s05；按目录组织的 `s0N_*/` 里待办是 `s05_todo_write`、技能加载是 `s07_skill_loading`，引用时写完整路径。文中的历史案例与论断需另行核对出处，不直接引用 |
| [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) | `04d809ceab9df28f9adaed044884180159172930` | MIT（仓库 `LICENSE.md`，Copyright (c) 2025 Kilian A. Lieret and Carlos E. Jimenez） | `src/minisweagent/agents/default.py`、`src/minisweagent/config/default.yaml`、`src/minisweagent/config/mini_textbased.yaml`、`src/minisweagent/models/utils/actions_text.py` | 借鉴结构：最小 Agent 循环的写法，以及文本动作（从回复里解析动作、解析失败时回传格式错误）与原生工具调用并存的做法。不复制代码或配置；它会把 `os.environ` 原样传给子进程，本项目不沿用这一点（见 `curriculum-research.md`） |

参考仓库在本机多是稀疏克隆，`ls` 看不到的文件不代表仓库没有。核对阅读范围以 `git ls-tree -r --name-only <commit>` 为准。

## 9. Claude Code 官方文档：课程里“对照 Claude Code 公开做法”的段落（2026-10-04）

多门课加了“对照 Claude Code 的公开做法”段落，引用了官方文档。登记如下。

- **资料**：[Claude Code 官方文档](https://code.claude.com/docs)，阅读日期 2026-10-04。
- **性质**：产品文档，没有固定版本，内容会随产品更新。课程里这类段落都写了“以官方文档为准”，不当作稳定规范。
- **借鉴方式**：只引用页面上明确写着的行为，用自己的话概括并给出链接，不复制正文、示例和配图。页面没写的行为不推测。
- **不是**上游代码或正文的复用，不进入 `THIRD_PARTY_NOTICES.md`。

引用的页面（路径均在 `https://code.claude.com/docs/en/` 之下，由 `lessons/*/content.json` 中的链接去重得到）：

| 页面 | 引用它的课 |
| --- | --- |
| `permissions` | `tool-selection`、`fail-safely`、`tool-proposals` |
| `tools-reference`、`tools-reference#task-tool-availability` | `dependent-calls`、`fail-safely`、`text-actions`、`todo-planning` |
| `best-practices`（`#give-claude-a-way-to-verify-its-work`、`#explore-first-then-plan-then-code`、`#add-an-adversarial-review-step`） | `task-contract`、`reflection-revision`、`plan-and-replan`、`orchestrator-evaluator` |
| `hooks`、`hooks-guide`（`#stop-hook-hits-the-block-cap`） | `task-contract`、`reflection-revision`、`workflow-patterns` |
| `agent-sdk/structured-outputs` | `structured-output` |
| `agent-sdk/todo-tracking` | `todo-planning` |
| `memory` | `prompt-experiments`、`messages-context`、`persistent-memory`、`memory-lifecycle` |
| `context-window` | `messages-context`、`application-state`、`context-compaction` |
| `how-claude-code-works` | `application-state`、`context-compaction`、`multi-turn-history` |
| `costs` | `context-budget`、`chat-request`、`multi-turn-history` |
| `prompt-caching` | `prompt-caching` |
| `skills` | `skills-disclosure` |
| `sub-agents` | `orchestrator-evaluator` |
| `permission-modes#analyze-before-you-edit-with-plan-mode` | `plan-and-replan` |

课程 slug 与目录名的对应以 `curriculum/catalog.json` 为准；上表按 `lessons/lesson_*/content.json` 的目录名去掉前缀和序号写出。

## 10. 论文：正文引用结论的研究（2026-10-12）

正文里点名讨论过、但不属于上面任何教程的研究论文登记在这里。只引用论文的结论，用自己的话概括并给出链接；不复制正文、图表、提示词和代码，因此不进入 `THIRD_PARTY_NOTICES.md`。

| 资料 | 固定版本 | 许可证 | 登记的阅读范围 | 借鉴方式与用途 |
| --- | --- | --- | --- | --- |
| [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651v2)（Madaan 等，NeurIPS 2023） | arXiv `2303.17651v2`（2023-05-25） | 论文，CC BY 4.0；只引用结论，不复制 | 摘要与方法概述 | `reflection-revision` 的深入一点“研究怎么看模型的自我纠正”：同一个模型轮流写稿、提意见、修订，在对话回复、代码优化等任务上报告了提升。正文只转述这一结论 |
| [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366v4)（Shinn 等，NeurIPS 2023） | arXiv `2303.11366v4`（2023-10-10） | 论文，CC BY 4.0；只引用结论，不复制 | 摘要与方法概述 | 同上一段：把环境给出的成败信号（这次尝试是否成功、测试是否通过）先写成文字总结，下次尝试时带上。正文只转述这一做法 |
