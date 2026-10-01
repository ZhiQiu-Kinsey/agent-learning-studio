# AgentStart：当前课程来源与教学取舍

更新日期：2026-10-01。课程参考来源为以下三份正式教程。固定版本与阅读范围用于核对实际借鉴内容，课程讲解和 Python 实验由本项目编写。

## 1. 固定参考快照

| 教程 | 固定 commit | 许可证 | 主要用途 |
| --- | --- | --- | --- |
| [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners) | `25b7985f3b2dc37a84f4a7387ccd3c9f0e5b1595` | MIT | 借鉴学习目标、主题模块、连续课程助教项目和按新增能力验收的学习方式。 |
| [Hugging Face Agents Course](https://github.com/huggingface/agents-course) | `b3946b1d09d29c65736e219d48a8a736a2c52154` | Apache-2.0 | 借鉴基础到框架、场景实践、评估的分层结构，框架选修分支，以及 State/Node/Edge 和 RAG 流程的拆分。 |
| [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book) | `b789c97a8f3de5b405a6f6dfa8289208d679d0b8` | Apache-2.0 | 补足任务验收、上下文实验、工具契约、独立验证器、运行生命周期、成本和多 Agent 工程取舍。 |

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

当前第 1–10 课可运行，其余课次保留为规划。课程目录由 `curriculum/catalog.json` 统一维护；实现方式见 [新增课程指南](adding-lessons.md)，完整验收见 [开发验证](validation.md)。
