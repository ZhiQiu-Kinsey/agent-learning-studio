# LangGraph 状态与分支（`langgraph-state`）

[English](README.md) · 简体中文

用 State、Node、Edge 把“规划、调用、验证、回答”写成一张有终态的图：正常、缺参、失败三条路各停在一个终态节点，验证失败后的修正由状态里的计数收住，LangGraph 的 `recursion_limit` 只当安全网。本课需要真实模型连接（缺参那组不会调用模型），课程仍是 `planned`。

## 本课解决什么问题

“应用状态与运行生命周期”（`application-state`）用一个数据类和几处 if 管住任务进度。流程一旦有了“验证不通过就回去修正，修正次数用完就失败”这样的环，函数里的分支和计数器就很难一眼看全。本课把同一类流程交给 LangGraph：状态集中声明，节点只返回改了的字段，边（含条件边）在一处列出，编译后的图可以直接列出全部的边，逐条检查是否都走到 `END`。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `graph.py` | `StudyState`（两个列表字段挂归并函数）、`check_evidence` 验证规则、七个节点、两个路由函数和建图代码 |
| `runtime.py` | 输入模型、初始状态、用 `stream_graph` 运行图并接住 `GraphRecursionError`，生成“图结构”和“本次运行的路径”两份报告 |
| `study_tools.py` | 唯一的工具 `estimate_study_days`：按本课自带的课时表求总分钟数，除以每天分钟数向上取整；查不到的课程返回结构化错误 |
| `locales/zh_CN.py`、`locales/en.py` | 提示词、工具描述与错误、验证反馈、终态原因、报告文字 |
| `locales/fixture/` | 离线测试模型写回答用的模板（只服务测试） |
| `fixtures.py` | 只服务自动化测试的确定性模型：规划时按练习输入原样提出调用，回答时按收到的工具结果写一句话 |
| `test_lesson.py` | 行为测试：真实工具执行、三条路径与终态、修正成功、两层上限、归并规则、事件不冒充模型响应、英文运行无中文、输入校验与停止 |

框架适配层在 `course/frameworks.py`：模型调用经 `RunContextChatModel` 记录为 `request`/`response`，工具调用经 `execute_tool_calls` 记录为 `tool_call`/`tool_result`，每个节点的更新由 `stream_graph` 记为 `lesson.graph_update`。本课没有使用 LangGraph 预置的工具节点，因为它直接调用函数，平台记录不到。

## 练习

| 练习 | 输入 | 路径 | 模型调用 |
| --- | --- | --- | --- |
| 正常路径：规划、调用、验证、回答 | 三门课，每天 30 分钟 | intake → plan → tools → verify → answer | 2 次 |
| 缺参：没说每天学多久 | 两门课，`minutes_per_day` 为 null | intake → ask_user | 0 次 |
| 失败终态：修正一次仍不通过 | 含一门课时表里没有的课，`max_repairs`=1 | intake → plan → tools → verify → plan → tools → verify → fail | 2 次 |
| 上限截停：recursion_limit 先到 | 同上，`max_repairs`=3，`recursion_limit`=6 | 第 6 个节点 tools 之后被截停，没有终态 | 2 次 |

表里的路径和次数来自离线测试模式。真实运行时，模型在 plan 节点可能改动实参（例如删掉查不到的课），验证会记为 `arguments_mismatch`，路径不变。

## 实验看什么

- **规划、调用、验证、回答图**：先看“图结构”报告里的 11 条边；再对照每条 `lesson.graph_route` 的 `read`，说出那次分支为什么这样走；最后看报告的终态检查。
- **循环预算与递归上限**：业务预算先到时走到 `fail`，有原因、有证据；递归上限先到时 LangGraph 抛错，运行器只报告最后执行的节点。实测 langgraph 1.2.16：路径有 N 个节点时，`recursion_limit` 至少要 N+1。
- **状态差异与归并函数**：`tools` 的更新只含这一轮证据，`evidence` 用 `operator.add` 追加，`failed_checks` 直接覆盖；“调用模型的节点执行次数”等于 `request` 事件数。

## 运行

离线测试（确定性模型数据，工具真实执行）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_langgraph_state.test_lesson -v
```

真实运行：课程开放后，在网页的实验台选择练习，或在后端启动后执行（会产生模型用量）：

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py langgraph-state normal --url http://127.0.0.1:8765 --locale en
```

本课尚未用真实模型验证；开放前每个练习在中英两种运行语言下各真实运行一次，核对正文说法。

**运行语言：**提示词、工具描述与错误、验证反馈和报告文字写在 `locales/` 里；节点名、状态字段、问题代码和课程标识是代码，各语言相同。

## 参考

State、Node、Edge 与条件边的讲法参考 Hugging Face Agents Course（Apache-2.0）`units/en/unit2/langgraph/`；运行层的约束、验证、纠正参考《深入理解 AI Agent》第一章（Apache-2.0）；脚本式编排对照 learn-claude-code（MIT）`s16_workflow_runtime`；规划分派对照 Microsoft AI Agents for Beginners（MIT）`07-planning-design`。LangGraph 接口按 1.2 官方文档（2026-10-20 核对）与本机 langgraph 1.2.16 实测。图、工具、验证规则和实验由本项目编写。
