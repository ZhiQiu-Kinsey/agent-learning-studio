# AgentStart：当前课程来源与教学取舍

[English](reference-study.en.md) · **简体中文**

更新日期：2026-10-21。课程参考来源为第 1 节表中的正式教程。固定版本与阅读范围用于核对实际借鉴内容，课程讲解和 Python 实验由本项目编写。

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

当前“原生基础”“任务与接口”“上下文与状态”“推理与控制模式”各单元共 53 门课可运行（来源见第 6 节与各单元的来源文档）。其中 29 门新课（知识检索、框架与协议、质量与工程、多 Agent 与交付，来源见第 11 节）已有完整实现与离线测试，并于 2026-10-21 用 `claude-haiku-5-5` 做过一轮真实运行（见 [验证记录](../verification/live-runs-2026-10-21.md)）；`embedding-retrieval`、`hybrid-retrieval` 需要配置有 Embedding 接口的服务商，没有真实模型运行过；`prompt-injection` 的防线没有经过被说服的模型检验。课程目录由 `curriculum/catalog.json` 统一维护；实现方式见 [新增课程指南](adding-lessons.md)，完整验收见 [开发验证](validation.md)。

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

## 11. 知识检索、框架与协议、质量与工程、多 Agent 与交付、执行控制与安全新课的来源（2026-10）

这一节登记本轮新写的 29 门 planned 课（均有完整实现与离线测试，尚未经真实模型验收）和两项平台改动（隔离执行、RAG 共享语料）实际用到的参考资料。

- **依据**：各课编写代理汇报的实际阅读清单，并与各课 `lessons/lesson_*/content.json` 理解场景末尾的 `references` 块核对过路径和链接。某个文件没有读过，就不登记。
- **借鉴方式**：全部是“借鉴结构”，即章节顺序、提问方式、概念划分和对照安排，用自己的话与自己的运行证据重写。讲解、代码、夹具、实验与语料均由本项目编写，没有复制参考项目的正文、代码或配图，因此不进入 `THIRD_PARTY_NOTICES.md`。
- **Hello-Agents 没有使用**：本轮 29 门课与两项平台改动都没有读它。
- **RAG 共享语料**“青石图书馆服务手册”（`lessons/lesson_document_loading/corpus/`，中英两份）是本项目原创的虚构资料，不取自任何参考项目。
- 固定版本沿用第 1 节的短哈希，下表用简称：

| 简称 | 资料 | 固定 commit | 许可证 |
| --- | --- | --- | --- |
| 书 | [深入理解 AI Agent](https://github.com/bojieli/ai-agent-book) | `b789c97` | Apache-2.0 |
| MS | [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners) | `25b7985` | MIT |
| HF | [Hugging Face Agents Course](https://github.com/huggingface/agents-course) | `b3946b1` | Apache-2.0 |
| cookbooks | [claude-cookbooks](https://github.com/anthropics/claude-cookbooks) | `d7265d6` | MIT |
| lcc | [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) | `ce8f9f1`（与第 6 节一致） | MIT |
| mini | [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) | `04d809c` | MIT |

lcc 同一 commit 有两套编号（见第 8 节）：`docs/zh/s0N-*.md` 与 `agents/` 一套，按目录组织的 `s0N_*/` 另一套。下面都写完整路径，两套编号不要混用。

### 11.1 知识检索（共享语料与 6 门课）

6 门课共用一份固定语料和一套查询集，语料和查询集放在 `lessons/lesson_document_loading/corpus/`（`zh-CN/`、`en/`、`problems/`、`queries.json`），由 `tests/test_rag_corpus.py` 守住结构。

| 课程 | 来源与固定版本 | 实际阅读 | 借鉴了什么 / 本课做法 |
| --- | --- | --- | --- |
| 平台：RAG 共享语料与检索模块 | 书 `b789c97`；HF `b3946b1` | 书：`book/chapter3.md` 第 243–423、594–636 行；`chapter3/sparse-embedding/bm25_engine.py`、`README.md`；`chapter3/retrieval-pipeline/fusion.py`、`document_store.py`、`README.md`、`evaluate.py`（只看切分部分）；`chapter3/contextual-retrieval/chunking.py`、`config.py`。HF：`units/en/unit2/llama-index/components.mdx` | 语料要有固定版本、可按路径与行号回到原文、查询集标注指向小节锚点；BM25、融合与切分的讲法。语料、查询集、分块、BM25、向量索引、融合与评测代码由本项目编写 |
| `document-loading` | 书 `b789c97`；HF `b3946b1`；cookbooks `d7265d6`；MS `25b7985` | 书：`book/chapter3.md`（RAG 基础、文档分块、上下文感知检索）、`book/chapter2.md`（上下文安全、外部内容与来源标记）、`chapter3/contextual-retrieval/chunking.py`、`chapter3/retrieval-pipeline/evaluate.py`（字符窗口切分部分）。HF：`units/en/unit2/llama-index/components.mdx`。cookbooks：`capabilities/contextual-embeddings/guide.ipynb`。MS：`05-agentic-rag/README.md` | 分块策略与“片段丢失上下文”；Document / Node 与元数据；外部内容的来源标记；上下文感知检索的数字来自 cookbooks，读的是原文。本课做法：用自己的语料做分块对照，并让问题文件留下加载异常记录 |
| `keyword-retrieval` | 书 `b789c97`；HF `b3946b1`；MS `25b7985` | 书：`book/chapter3.md` 第 243–423、542–636 行（稀疏嵌入、混合检索、检索指标）、`chapter3/sparse-embedding/README.md`、`bm25_engine.py`。HF：`units/en/unit2/llama-index/components.mdx`。MS：`05-agentic-rag/README.md` | BM25 公式与逆文档频率、逐词贡献日志、`recall@k` 实为命中率的脚注、“精确词找得准、同义词读不懂”的对照；检索流程的五个阶段；MS 只作为通往 `agentic-rag` 的铺垫。本课做法：中文字二元组切词、按小节锚点人工标注、漏检原因分类 |
| `embedding-retrieval` | 书 `b789c97`；cookbooks `d7265d6`；MS `25b7985`；HF `b3946b1` | 书：`book/chapter3.md`（第 312–322、408、412 行：ANN 与 HNSW、`recall@k` 脚注）、`chapter3/dense-embedding/README.md`。cookbooks：`capabilities/contextual-embeddings/guide.ipynb`（Pass@k 定义与代码、Pass@5/10/20 表、30–40% 的结论）。MS：`05-agentic-rag/README.md`。HF：`units/en/unit2/llama-index/components.mdx`。**核对方式**：接手的代理核对了上面标出的断言所在原文；其余署名项由第一个编写代理引用，接手后没有逐项重读 | 余弦相似度的手算、精确检索与 ANN 的取舍、分批编码并把向量存盘、查询必须用建索引时的同一个 Embedding 模型。本课做法：分批、过期判断、测试向量与实验由本项目编写 |
| `hybrid-retrieval` | 书 `b789c97`；cookbooks `d7265d6`；HF `b3946b1`；MS `25b7985` | 书：`book/chapter3.md` 第 243–445、505–636 行；`chapter3/retrieval-pipeline/README.md`、`fusion.py`、`reranker.py`、`retrieval_pipeline.py`（相关部分）。cookbooks：`capabilities/contextual-embeddings/guide.ipynb`。HF：`units/en/unit3/agentic-rag/invitees.mdx`、`units/en/unit2/llama-index/components.mdx`。MS：`05-agentic-rag/README.md`（只作背景浏览） | RRF 公式与 k=60、加权融合、双编码器与交叉编码器的对比、失效内容按版本元数据在检索时过滤、索引是可重建的派生物；“重排只对少量候选做”。本课做法：自写融合与重排，按阶段看排名变化 |
| `rag-citations` | 书 `b789c97`；MS `25b7985`；HF `b3946b1`；cookbooks `d7265d6` | 书：`book/chapter3.md`（RAG 基础、检索指标、RAG 的安全边界）、`book/chapter2.md`（来源标记，指令与数据分开）。MS：`05-agentic-rag/README.md`。HF：`units/en/unit3/agentic-rag/agentic-rag.mdx`。cookbooks：`misc/using_citations.ipynb`、`capabilities/retrieval_augmented_generation/guide.ipynb`、`capabilities/contextual-embeddings/guide.ipynb`。**核对方式**：由第一个编写代理阅读；接手的代理只核对了引用文件存在与 commit，没有重读 | 接口原生引用与引用粒度、分开衡量检索与端到端、来源标记。本课做法：引用由程序对照语料核对，语料、查询集、核对规则与实验由本项目编写 |
| `agentic-rag` | 书 `b789c97`；MS `25b7985`；HF `b3946b1`；mini `04d809c` | 书：`book/chapter3.md`（实验 3-8、上下文感知检索）、`chapter3/agentic-rag/README.md`、`agent.py`、`campaign.py`、`config.py`。MS：`05-agentic-rag/README.md`。HF：`units/en/unit3/agentic-rag/agentic-rag.mdx`；第一个编写代理另读了同目录的 `agent.mdx`、`tools.mdx`，接手的代理没有重读。mini：`src/minisweagent/agents/default.py`（`step_limit`、`cost_limit`、`wall_time_limit_seconds`） | 把检索做成工具、一次检索与分解检索的离线对照、检索预算与强制最终回答；迭代与步骤间保留状态；每次请求前检查三道上限。本课做法：三道上限在每次请求前检查，每轮尝试写回请求，引用由程序核对 |

### 11.2 框架与协议

| 课程 | 来源与固定版本 | 实际阅读 | 借鉴了什么 / 本课做法 |
| --- | --- | --- | --- |
| `langchain-vs-native` | HF `b3946b1`；MS `25b7985`；书 `b789c97`；lcc `ce8f9f1`；LangChain 官方文档（见 11.6） | HF：`units/en/unit2/introduction.mdx`、`units/en/unit2/langgraph/when_to_use_langgraph.mdx`、`units/en/unit2/llama-index/introduction.mdx`。MS：`02-explore-agentic-frameworks/README.md`、`04-tool-use/README.md`。书：`book/chapter1.md`（Harness 工程：上下文管理、工具接口、约束、验证、纠正）。lcc：`agents/s01_agent_loop.py`。**核对方式**：书第 1 章由接手的代理重新核对；其余由第一个编写代理阅读 | 什么时候需要框架、框架应提供的部件、运行层五要素里框架主要覆盖上下文与工具；lcc 的无上限最小循环作“框架在骨架上叠层”的对照。LangChain 的行为在本机 `langchain-core` 1.6.12 上实测核对。代码与正文由本项目编写 |
| `langchain-tools` | MS `25b7985`；HF `b3946b1`；书 `b789c97`；cookbooks `d7265d6`；LangChain 官方文档（见 11.6） | MS：`04-tool-use/README.md`（函数 Schema 与错误处理）。HF：`units/en/unit3/agentic-rag/invitees.mdx`、`units/en/unit2/llama-index/tools.mdx`、`units/en/unit2/langgraph/document_analysis_agent.mdx`。书：`book/chapter4.md`（工具设计的通用原则、工具描述）。cookbooks：`tool_use/extracting_structured_json.ipynb`、`tool_use/tool_use_with_pydantic.ipynb`。**核对方式**：本课内容由第一个编写代理完成；接手的代理只核对了引用的文件存在并浏览了开头，没有重新通读 | 函数 Schema 与错误处理要素；同一个工具在三个框架里的登记方式，以及“捕获异常返回空字符串”的反例；工具描述与参数保真；用强制工具调用提取结构化 JSON。`with_structured_output` 的组成、`handle_tool_error` 等行为在本机 `langchain-core` 1.6.12 上实测。任务、业务表、夹具与实验由本项目编写 |
| `langgraph-state` | HF `b3946b1`；MS `25b7985`；书 `b789c97`；lcc `ce8f9f1`；LangGraph 官方文档（见 11.6） | HF：`units/en/unit2/langgraph/` 下的全部 7 个文件（含 `building_blocks.mdx`、`first_graph.mdx`、`document_analysis_agent.mdx`）。MS：`07-planning-design/README.md`。书：`book/chapter1.md`（Harness 工程、编排模式）。lcc：`s16_workflow_runtime/README.zh.md` | State、Node、Edge 与条件边的拆法，对应原生 Python 的状态字典、函数与分支；运行层的约束、验证、纠正；lcc 的脚本式编排作对照；MS 的规划分派作对照。LangGraph 接口按官方文档并在本机 `langgraph` 1.2.16 上实测。图、工具、验证规则与实验由本项目编写 |
| `mcp-basics` | 书 `b789c97`；MS `25b7985`；HF `b3946b1`；lcc `ce8f9f1`；MCP 官方文档（见 11.6） | 书：`book/chapter4.md`（工具生态：MCP 与 Skill Hub、工具太多怎么办）、`chapter4/DOCKER_DEPLOYMENT.md`（开头）、`chapter4/perception-tools/src/main.py`。MS：`11-agentic-protocols/README.md`（MCP 部分）。HF：`units/en/unit1/tools.mdx`（MCP 小节）、`units/en/unit2/smolagents/tools.mdx`、`units/en/unit4/additional-readings.mdx`。lcc：`s14_mcp_plugin/README.zh.md`、`s14_mcp_plugin/code.py`（前 60 行） | 客户端-服务器架构与三类原语、`tools/list` 的 token 成本、第三方服务端的三类风险；宿主、客户端、服务端的划分；MCP 作为统一工具接口；宿主侧权限表与“注解不能当授权依据”。服务端、运行器、实验与语料用法由本项目编写 |
| `mcp-lifecycle` | 书 `b789c97`；MS `25b7985`；lcc `ce8f9f1`；HF `b3946b1`；MCP 官方文档（见 11.6） | 书：`book/chapter4.md`（工具生态、工具太多怎么办）、`chapter4/docker-compose.yml`、`chapter4/DOCKER_DEPLOYMENT.md`。MS：`11-agentic-protocols/README.md`。lcc：`s14_mcp_plugin/README.zh.md`、`code.py`（`normalize_mcp_name`）。HF：`units/en/unit1/tools.mdx`、`units/en/unit2/smolagents/tools.mdx` | 多服务的宿主划分、工具遮蔽、按需暴露、服务端各自的环境与重启策略；一对一连接；服务前缀 `mcp__{server}__{tool}`、改名后再查重名、宿主权限表。生命周期、能力协商、关闭顺序、超时与传输按 MCP 规范核对。服务端、宿主、故障注入、实验与测试由本项目编写 |
| `a2a-delegation` | MS `25b7985`；书 `b789c97`；A2A 官方资料（见 11.6） | MS：`11-agentic-protocols/README.md`（整篇）。书：`book/chapter10.md`（分类框架、不共享上下文的协作、通信与控制、去中心化 handoff、跨组织 A2A、失败模式）、`book/chapter4.md`（协作工具）、`chapter10/parallel-web-research/message_bus.py` 与同目录 README | Agent Card、Agent 执行器、产物与事件队列的划分，MCP 与 A2A 的分工；状态查询、优雅与强制终止、级联取消；消息信封的最小写法。任务状态、取消语义、`contextId`、轮询与推送按 A2A 规范核对，SDK 用法按 `a2a-sdk` 1.2.x 核对。远端服务、运行器、实验与语料用法由本项目编写 |

### 11.3 质量与工程

| 课程 | 来源与固定版本 | 实际阅读 | 借鉴了什么 / 本课做法 |
| --- | --- | --- | --- |
| `reliable-tools` | 书 `b789c97`；MS `25b7985`；lcc `ce8f9f1`；cookbooks `d7265d6` | 书：`book/chapter4.md`（工具设计的通用原则、执行工具：幂等性与取消语义）、`book/chapter5.md`（故障与错误恢复）、`book/chapter1.md` 里检索熔断与重试上限的段落。MS：`04-tool-use/README.md`、`06-building-trustworthy-agents/README.md`。lcc：`s02_tool_use/README.zh.md`、`code.py`；`s15_integrated_harness/README.md`、`code.py`；`s16_workflow_runtime/code.py`。cookbooks：`claude_agent_sdk/03_The_site_reliability_agent.ipynb` | 幂等性与取消语义；先分类再计数、分级恢复与熔断上限；错误处理与参数校验；资源过载与连锁错误的防护；限流与过载时的指数退避重试；读工具与写工具分开约束。代码与实验由本项目编写 |
| `evaluation-sets` | 书 `b789c97`；cookbooks `d7265d6`；HF `b3946b1`；MS `25b7985` | 书：`book/chapter7.md`（开篇、τ²-bench、评估指标、评估数据集的设计、自动化评估、统计显著性）、`chapter1/context/grounding.py`、`chapter7/user-memory-policy-eval/README.md`、`runner.py`、`cases.json`。cookbooks：`tool_evaluation/tool_evaluation.ipynb`、`evaluation.xml`、`misc/building_evals.ipynb`；`evals/agentic_search/utils/agentic_search.py` 只浏览。HF：`units/en/bonus-unit2/what-is-agent-observability-and-evaluation.mdx`、`units/en/unit4/hands-on.mdx`、`units/en/unit4/what-is-gaia.mdx`；`monitoring-and-evaluating-agents-notebook.mdx` 只浏览。MS：`10-ai-agents-production/README.md` | 借鉴的是方法：拆开的检查、答案数字溯源、精确匹配、确定性规则给可观察动作评分、配对与小样本不确定性、离线与在线评估。题集、验证器、版本与实验由本项目编写 |
| `observability-cost` | HF `b3946b1`；书 `b789c97`；MS `25b7985`；cookbooks `d7265d6` | HF：`units/en/bonus-unit2/` 下的全部 4 个文件。书：`book/chapter7.md`（成本分析、可观测性、从 Benchmark 报告到系统改进、从外部评估到内部评估）、`chapter7/agent-cost-analysis/tracer.py`、`config.py`、`README.md`。MS：`10-ai-agents-production/README.md`。cookbooks：`observability/usage_cost_api.ipynb`、`cost_optimization/cost_optimization.ipynb` | trace 与 span、延迟、成本和错误这些指标的讲法；按步骤拆解用量与成本；先建基线再逐项优化；用接口核对真实花费。tracer 里“usage 为空就记 0”的做法**不采用**，本课服务商没有报告的用量写“未报告” |
| `goal-loops` | lcc `ce8f9f1`；书 `b789c97`；MS `25b7985` | lcc：`s17_goal_loop/README.zh.md`、`code.py`、`tests/test_goal_loop.py`（只看开头）。书：`book/chapter9.md`、`book/chapter1.md`（停止条件、熔断器、Harness 工程）、`book/chapter7.md`（Pass@k 与 Pass^k、预算与能力曲线、验证器）。MS：`09-metacognition/README.md` | 在停止边界放一个独立判断、`ok` 与 `impossible` 两种结论、连续拦截次数的上限；三层验证与“完成不等于进步”；自我评估只能当参考。程序验收器、进展与重复失败规则、结局划分与实验由本项目编写 |
| `long-running-tasks` | lcc `ce8f9f1`；书 `b789c97`；MS `25b7985` | lcc：`s11_background_tasks/README.zh.md`、`code.py`；`s12_cron_scheduler/README.zh.md`、`code.py`；`s17_goal_loop/README.zh.md`；`docs/zh/s08-background-tasks.md`。书：`book/chapter6.md`（异步与事件驱动）、`chapter6/async-agent/README.md`、`events.py`、`runtime.py`（前约 200 行）。MS：`16-deploying-scalable-agents/README.md` | 后台线程加通知队列、不复用原调用 id；五段式调度表达式、待交付队列与持久化边界；事件循环里取消式、队列式、并行式三种处理办法与任务句柄；并发上限与回压。虚拟时钟、执行器、调度器与实验由本项目编写 |

### 11.4 多 Agent 与交付

| 课程 | 来源与固定版本 | 实际阅读 | 借鉴了什么 / 本课做法 |
| --- | --- | --- | --- |
| `multi-agent-patterns` | 书 `b789c97`；MS `25b7985`；HF `b3946b1`；lcc `ce8f9f1`；cookbooks `d7265d6` | 书：`book/chapter10.md`（分类框架、何时优于单 Agent、共享与不共享上下文、管理者模式、去中心化、失败模式）、`chapter10/multi-role-transfer/README.md`、`chapter10/parallel-web-research/README.md`。MS：`08-multi-agent/README.md`。HF：`units/en/unit2/smolagents/multi_agent_systems.mdx`。lcc：`docs/zh/s04-subagent.md`、`docs/zh/s09-agent-teams.md`、`s06_subagent/README.*`、`s13_agent_teams/README.zh.md`，并浏览了 `code.py` 的结构。cookbooks：`patterns/agents/README.md`、`async_multi_agent_orchestration.ipynb`、`latency_multi_agent.ipynb` | 上下文共享与不共享的分类、交接包的三部分、新信息判据和失败模式；子 Agent 与团队的做法；场景与可见性；团队编排与共享计时。任务、资料、验证器、运行器与实验由本项目编写 |
| `delegation-budget` | 书 `b789c97`；cookbooks `d7265d6`；lcc `ce8f9f1`；MS `25b7985` | 书：`book/chapter10.md`、`chapter10/parallel-web-research/README.md`。cookbooks：`patterns/agents/orchestrator_workers.ipynb`、`latency_multi_agent.ipynb`。lcc：`s06_subagent/README.zh.md`、`s10_task_system/README.zh.md`。MS：`08-multi-agent/README.md`。**核对方式**：由第一个编写代理阅读，接手后没有重读 | 结构化交接、第一个已验证的成功点、取消沿父子传播、预算意识；编排者与工人、共享计时；子 Agent 的消息隔离与一层委派；任务状态与依赖。任务、资料、校验与实验由本项目编写 |
| `bash-coding-agent` | mini `04d809c`；书 `b789c97`；lcc `ce8f9f1`；HF `b3946b1` | mini：`src/minisweagent/agents/default.py`、`agents/interactive.py`、`environments/local.py`、`environments/docker.py`、`environments/README.md`、`config/mini.yaml`、`README.md`、`docs/faq.md`、`docs/advanced/control_flow.md`、`docs/advanced/environments.md`。书：`book/chapter5.md`（Coding Agent 的实现技巧、故障恢复、搜索与编辑工具、安全）、`chapter5/coding-agent/tools/bash_tool.py`、`system-prompt.md`、`sandbox_evaluator.py`（前 80 行）。lcc：`s03_permission/README.md`、`s04_hooks/README.md`，并浏览了 `s03_permission/code.py` 的结构。HF：`units/en/unit2/smolagents/code_agents.mdx` | “只有 bash、每条命令独立执行”的设计、超时时终止整个进程组、确认模式；输出截断、沙箱选型；执行前的权限检查与把审批挂在钩子上；代码动作与 JSON 动作的对比。mini 会把 `os.environ` 原样传给子进程，本项目不沿用。代码、提示词与实验由本项目编写 |
| `file-edit-evidence` | 书 `b789c97`；lcc `ce8f9f1`；mini `04d809c` | 书：`book/chapter4.md` 第 38–100、270–382 行；`book/chapter5.md` 第 84–126、227–309 行（文件编辑工具的五种方案、行号漂移）；`book/chapter2.md` 第 614–645 行；`chapter5/coding-agent/tools/edit_tool.py`、`write_tool.py`、`read_tool.py`、`multi_edit_tool.py`（前 80 行）、`system-prompt.md`。lcc：`s02_tool_use/README.md`、`code.py`（前 120 行）。mini：`docs/index.md`（前 80 行），`docs/faq.md`、`docs/quickstart.md` 只用 grep 查过 | 专用工具与通用执行器的取舍、参数传递的保真、Edit 的唯一匹配规则与写后语法检查、带行号的读取；从一个 Bash 工具扩成五个工具、路径限制只用在文件工具上；mini 只给 Bash 的路线作对照。代码与实验由本项目编写 |
| `local-delivery` | MS `25b7985`；书 `b789c97`；lcc `ce8f9f1` | MS：`16-deploying-scalable-agents/README.md`、`17-creating-local-ai-agents/README.md`、`10-ai-agents-production/README.md`（全文）；`STUDY_GUIDE.md` 只看了前约 80 行，没有引用。书：`chapter4/DOCKER_DEPLOYMENT.md`（全文）、`book/chapter7.md`（Agent 的可观测性、生产级评估基础设施）。lcc：`s15_integrated_harness/README.md`、`code.py` 里进程组清理的部分（约第 880–960 行） | 从原型到生产与冒烟测试；本地运行的隐私、成本与边界；环境变量、健康检查与生产注意事项；进程组清理。代码与实验由本项目编写 |
| `backup-upgrade` | MS `25b7985`；书 `b789c97`；SQLite 官方文档（见 11.6） | MS：`16-deploying-scalable-agents/README.md`、`13-agent-memory/README.md`（全文）。书：`book/chapter3.md`（记忆压缩与整理机制、知识应该如何更新、本章小结）、`book/chapter9.md`（持续进化的闭环与睡眠学习的安全边界） | 部署的生命周期与冒烟测试；记忆的管理与维护；增量更新与定期整理、持续进化的安全边界。备份、`VACUUM INTO`、预写日志与“怎样损坏数据库”的事实来自 SQLite 官方文档。代码与实验由本项目编写 |
| 平台：隔离执行（`sandbox.md`） | mini `04d809c`；书 `b789c97`；lcc `ce8f9f1` | mini：`environments/local.py`、`environments/docker.py`、`environments/extra/bubblewrap.py`。书：`book/chapter5.md`（实现技巧、安全）、`chapter5/coding-agent/tools/bash_tool.py`、`sandbox_evaluator.py`。lcc：`s03_permission/README.md`、`s04_hooks/README.md` | 本地与容器两种执行环境的接口划分、Linux 无守护进程隔离方案（bubblewrap 暂不实现，留作以后的后端）、Bash 工具的超时与输出上限、权限检查与钩子。设计与实现见 [`sandbox.md`](sandbox.md)，该文末“参考资料”一节登记了同样的链接 |

### 11.5 执行控制、安全与毕业项目

| 课程 | 来源与固定版本 | 实际阅读 | 借鉴了什么 / 本课做法 |
| --- | --- | --- | --- |
| `streaming-cancel` | 书 `b789c97`；MS `25b7985`；cookbooks `d7265d6`；百炼与 OpenAI 流式文档（见 11.6） | 书：`book/chapter6.md`（事件处理、取消式处理、半截输出不是合法前缀、取消点）、`chapter6/streaming-speech/interruption_manager.py`、`book/chapter2.md`（流式响应、参数完整即可提前执行工具调用）；`chapter6/async-agent/async_demos.py` 翻阅过，没有借用。MS：`10-ai-agents-production/README.md`（延迟指标）。cookbooks：`extended_thinking/extended_thinking.ipynb`（带类型的流式事件）。lcc 与 HF 没有流式或打断的章节，没有引用 | 被打断的一轮按实际送达的内容截断并标注、取消点要能安全收尾、首字延迟的量法。拼合、编号核对、续写对照与实验由本项目编写 |
| `async-concurrency` | 书 `b789c97`；cookbooks `d7265d6`；MS `25b7985`；lcc `ce8f9f1` | 书：`book/chapter6.md`（异步的动机，取消式、队列式、并行式三种处理，取消点与占位）、`chapter6/async-agent/README.md`、`tasks.py`、`book/chapter10.md`（优雅终止与强制终止、取消级联、并发额度、实验 10-4 的超时与错误隔离）。cookbooks：`patterns/agents/latency_multi_agent.ipynb`、`async_multi_agent_orchestration.ipynb`。MS：`16-deploying-scalable-agents/README.md`（并发与背压）。lcc：`s11_background_tasks/README.md`、`code.py` | 串行与并行的墙钟对照、`MAX_HELPERS` 是成本护栏而不是机制本身、`finally` 里先取消再收齐的收尾方式、没完成的结果用占位而不伪造成功。依赖解析、调度器、峰值并发的计算与实验由本项目编写 |
| `hooks-approval` | lcc `ce8f9f1`；书 `b789c97`；MS `25b7985`；HF `b3946b1` | lcc：`s03_permission/README.zh.md`、`code.py`，`s04_hooks/README.zh.md`、`code.py`，`s15_integrated_harness/README.zh.md`（钩子与权限段）。书：`book/chapter4.md`（执行工具的安全层次、事前审批、幂等性）、`book/chapter1.md`（护栏、思考题 7）、`book/chapter5.md`（安全、致命三要素）。MS：`06-building-trustworthy-agents/README.md`、`code_samples/06-human-in-the-loop.ipynb`。HF：`units/en/unit2/langgraph/when_to_use_langgraph.mdx`；`units/en/unit1/actions.mdx` 只读过，没有引用 | 三道闸门（拒绝列表、规则匹配、询问用户）、钩子注册表与四个事件、关键字匹配不是安全边界；拒绝理由作为工具结果放回轨迹、风险分级、执行层护栏在上下文之外；动作前的闸门而不是事后确认。钩子链、参数摘要核对、工单台与实验由本项目编写 |
| `human-in-the-loop` | HF `b3946b1`；书 `b789c97`；lcc `ce8f9f1`；MS `25b7985`；LangChain 官方文档（见 11.6） | HF：`units/en/unit2/langgraph/building_blocks.mdx`、`when_to_use_langgraph.mdx`。书：`book/chapter4.md`（幂等性与取消语义：先查后变更、唯一标识去重、预检-确认两段式）、`book/chapter6.md`（异步的可打断与可恢复）。lcc：`s16_workflow_runtime/README.zh.md`、`code.py`（日志、稳定键续跑、运行锁）。MS：`06-building-trustworthy-agents/README.md`（Human-in-the-Loop 小节） | 状态、节点、边与“人工介入由框架内置”的定位；“检查点存位置，日志存结果”的对照；MS 示例用同步 `input()` 等审批、进程一死等待就没了，作为反面对照。检查点、恢复守卫、业务状态与实验由本项目编写 |
| `prompt-injection` | 书 `b789c97`；MS `25b7985`；lcc `ce8f9f1`；cookbooks `d7265d6` | 书：`book/chapter2.md`（提示注入、来源标记、结构化角色、输入清洗、实验 2-5 的防御对照）、`book/chapter4.md`（第三方能力的风险、工具描述投毒、执行工具的层次化安全、提议者与审核者、拒绝熔断器）、`book/chapter5.md`（致命三要素、出口控制、服务端真值校验）、`book/chapter1.md`（护栏分层、误拒绝）。MS：`06-building-trustworthy-agents/README.md`（威胁清单）、`18-securing-ai-agents/README.md`（审计是账本，权限才是闸门）。lcc：`s03_permission/README.md`、`code.py`。cookbooks：`claude_agent_sdk/scheduled_repository_reviewer/scheduled_review.py` 与对应 notebook；`claude_agent_sdk/README.md`、`managed_agents/self_hosted_sandboxes/docker/README.md` 只核对了最小权限的说法 | 三种防线的对照安排、执行侧权限检查与“名单只是字符串匹配”、可用工具与允许工具分开、路径限制与拒绝钩子。权限守卫、本课资料与诱饵文件、效果账本、探针与实验由本项目编写 |
| `capstone-study-assistant` | MS `25b7985`；HF `b3946b1`；书 `b789c97`；cookbooks `d7265d6` | MS：`STUDY_GUIDE.md`（课程助手示例、毕业练习）、`13-agent-memory/README.md`（学习者记忆）。HF：`units/en/unit4/introduction.mdx`、`what-is-gaia.mdx`、`hands-on.mdx`。书：`book/chapter1.md` 第 263–345、466–540 行（运行层五要素、护栏分层、人工介入）、`book/chapter3.md` 第 15–112、221–242、505–545 行（用户记忆与更新）、`book/chapter7.md` 第 129–300、434–560、672–720 行（验证器、Pass@k 与 Pass^k、失败归因、回归任务、统计、可观测性）。cookbooks：`capabilities/retrieval_augmented_generation/evaluation/eval_end_to_end.py`、`docs_evaluation_dataset.json` | 课程助手的路线；固定题集、通过线、精确匹配与排行榜上的诚实；检索评估与端到端评估分开。本课做法：任务契约写在模型之前，每次调用先过纯函数门禁，写进度要检查点、审批和操作标识；独立验收器把“流程结束”“通过率”“验收通过”分开，运行器探针单独记。课程笔记语料（中英各 11 份，冻结版本）、题集、门禁、验收器、只读 MCP 服务端与实验由本项目编写 |

### 11.6 官方文档与规范

下列资料是官方文档或协议规范，**不是固定 commit 的仓库快照**；内容会随版本更新，课程里只引用页面明确写着的事实，用自己的话概括并给出链接，不复制正文和示例。

| 资料 | 版本 / 核对日期 | 引用它的课 | 用到的部分 |
| --- | --- | --- | --- |
| [LangChain 文档：tools](https://docs.langchain.com/oss/python/langchain/tools) | 2026-10-20 核对，配合本机 `langchain-core` 1.6.12 | `langchain-vs-native`、`langchain-tools` | `@tool` 装饰器、Schema 推断、工具执行与错误处理 |
| [LangChain 文档：models](https://docs.langchain.com/oss/python/langchain/models) | 列为 `langchain-tools` 的参考链接；核对日期没有单独记录 | `langchain-tools` | 模型的工具调用与结构化输出 |
| [LangGraph 文档：Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) | 2026-10-20 核对，配合本机 `langgraph` 1.2.16 | `langgraph-state` | 状态、归并函数、边与递归上限 |
| [MCP 规范 2025-11-25：Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) | 规范版本 2025-11-25；`mcp-basics` 的 README 另记录对照过 2026-07-28 版的同一节；阅读日期没有逐条记录，是课程写作期间（2026-10-20 至 21）所读 | `mcp-basics` | 工具、两类错误与安全要求 |
| [MCP 规范 2025-11-25：lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)、[transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) | 规范版本 2025-11-25；阅读日期同上，没有逐条记录 | `mcp-lifecycle` | 生命周期、能力协商、关闭与超时；stdio 与 Streamable HTTP 传输 |
| [MCP Python SDK：v2 迁移指南](https://py.sdk.modelcontextprotocol.io/v2/migration/) | 2026-10-20 核对 | `mcp-basics` | 从 1.x 迁移到 2.x 的差异 |
| [A2A 规范](https://a2a-protocol.org/latest/specification/)（Apache-2.0）、[a2a-python](https://github.com/a2aproject/a2a-python)（Apache-2.0） | 规范链接是 `latest`，没有固定版本，阅读日期没有单独记录，是课程写作期间所读；SDK 用法按 `a2a-sdk` 1.2.x 核对，仓库没有固定 commit | `a2a-delegation` | 任务状态、取消（`TaskNotCancelableError`）、`contextId`、推送与轮询；SDK 用法 |
| SQLite 官方文档：[backup](https://www.sqlite.org/backup.html)、[VACUUM](https://www.sqlite.org/lang_vacuum.html)、[howtocorrupt](https://www.sqlite.org/howtocorrupt.html)（1.2–1.4）、[wal](https://www.sqlite.org/wal.html) | 2026-10-21 阅读 | `backup-upgrade` | 在线备份接口、`VACUUM INTO`、备份与日志文件错配如何损坏数据库、预写日志 |
| [LangGraph 文档：interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)、persistence、[use-time-travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel) | 2026-10-21 核对；persistence 页读过，课程里没有链接 | `human-in-the-loop` | 中断需要检查点保存器与 `thread_id`、恢复时被中断的节点从头重跑、中断之前的副作用要幂等；内存保存器重启即丢；改状态会产生新的检查点分支。只用于对照讲解 |
| [百炼流式输出文档](https://help.aliyun.com/zh/model-studio/stream) | 2026-10-21 核对 | `streaming-cancel` | 流式请求的写法与数据块格式 |
| OpenAI 聊天补全流式事件文档（developers.openai.com） | 2026-10-21 核对；课程里没有链接 | `streaming-cancel` | 最后一块的 `choices` 可以为空；中断或取消的流可能拿不到用量 |
| 百炼 Embedding 接口文档（Model Studio 的 Embedding 指南） | 2026-10 核对（`course/api_client.py` 的注释记录）；具体日期与页面链接没有单独记录 | `embedding-retrieval`（平台适配） | `text-embedding-v4` 每次请求最多 10 条输入；兼容接口的 `/embeddings` 路径 |

### 11.7 本节的保守说明

- 第一个编写代理读过、接手代理只核对了存在或抽查断言的条目，已在表里的“核对方式”写明（`langchain-tools`、`langchain-vs-native`、`rag-citations`、`embedding-retrieval`、`delegation-budget`）；它们的阅读范围依据编写代理的汇报，不是本节作者逐文件重读的结果。
- 参考资料里的具体数字（例如 cookbooks 的 Pass@k 表）只有 `embedding-retrieval` 一行写明核对过原文；其余课的数字以各课自己的运行证据为准。
- 官方文档没有固定版本，页面内容可能已变；复用或扩写前以当时的官方文档为准。
- 真实模型验收尚未做，上表只登记参考资料，不代表这些课已通过真实模型验证。
