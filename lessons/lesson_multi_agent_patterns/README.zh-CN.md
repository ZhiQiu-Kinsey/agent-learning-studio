# 多 Agent 模式与取舍（`multi-agent-patterns`）

[English](README.md) · 简体中文

拆成几个 Agent 之前，先用同一份验收集量一量。本课让同一个“课程助教出题”任务用四种做法各跑一遍：单 Agent、固定流程、角色切换、独立多 Agent，最后都交给同一个程序验证器，并排比较通过与否、模型调用数、服务商报告的用量和墙钟时间。本课需要真实模型连接。

**状态：**`available`。2026-10-21 用 `claude-haiku-5-5` 对每个练习在每种运行语言下各做了一次真实运行，样本各一份（[验证记录](../../docs/verification/live-runs-2026-10-21.md)）。这是对一个模型的带日期记录，不保证其他模型。

## 任务与验收集

- 资料包四份：`d1` 工作流模式、`d2` 编排者-工人、`d3` 修订循环、`d4` 补充笔记。`d4` 的标题看不出旧，只有任务说明里的规则写着“d4 是旧版草稿，冲突时不能当证据”；它写的子任务上限（6）和 `d2`（4）矛盾。
- 三个考点：`fallback_label`、`worker_cap`、`max_iters`，每个考点出一道四选一题，题目带证据 `{doc, quote}`。
- 验证器 `verifier.py` 的 `verify_quiz` 对每个考点查：有且只有一道题；格式正确；`quote` 逐字出现在 `doc` 那份资料里；`doc` 不是 `d4`；正确选项写出资料里的原值、别的选项没写。运行器在最后一轮之后以工具形式调用它（事件标 `origin: course_program`）。

## 四种做法

| 练习 | 模型调用 | 上下文 | 运行标识 |
| --- | --- | --- | --- |
| 单 Agent（基线） | 1 | 一个请求装下任务、规则和四份资料 | `solo` |
| 固定流程 | 3 | 研究 → 出题 → 审核，每步新请求，输入由程序挑 | `step-research`、`step-write`、`step-review` |
| 角色切换 | 3 | 一份共享的消息历史，每阶段只换系统提示词 | `assistant`（3 种角色） |
| 独立多 Agent | 5 | 三个研究员各看一个分片、带各自的 `branch` 并行；程序合并；出题人、审核人各在新上下文里工作 | `researcher-1..3`、`writer`、`reviewer` |

参数 `handoff` 只影响独立多 Agent：`minimal`（默认）只交任务和分到的资料；`with_rules` 再加上“d4 已过时”这条规则。练习 `multi` 预设 `minimal`，单独的练习 `multi-with-rules` 预设 `with_rules`，所以第二个实验的两组是两个练习，而不是改过的输入。

## 证据

- `lesson.agent`：每次模型调用一条，记运行标识、角色、`branch`，以及从实际发出的消息里查出的上下文：消息数、输入字符、看到的资料、`sees_rule`、历史里有几条助手回复；上下文里有 `d4` 时多一个 `outdated_docs` 字段。
- `lesson.merge`（只在独立多 Agent）：全部事实、`duplicates`（同一考点被多个研究员查过）、`conflicts`（同一考点的值互相矛盾）、`missing`。程序只记录，不裁决。
- `lesson.plan`：四种做法的任务图，开始时 `created`，结束时 `progress`，最后一项是验证器。
- `lesson.report`：每个考点一条检查；指标有任务验收、模型调用数、累计 `total_tokens`（只加服务商报告的数，没报告写“未报告”）、墙钟时间、运行标识与角色、输入字符合计、合并冲突与重复（独立多 Agent）、交接包；表格每行是一次调用。

## 实验看什么

1. **研究、出题与审核的模式比较**：四组同一个任务。看第一次调用的上下文、运行标识与角色数、验证器调用、任务验收、模型调用数（1、3、3、5）、用量和墙钟时间。
2. **交接包漏掉一条规则**：两组都是独立多 Agent（练习 `multi` 与 `multi-with-rules`），只差 `handoff`。最小交接时 `researcher-3` 的上下文里有 `d4` 却没有规则，合并出现重复与冲突，验证器判 `worker_cap` 不通过；带规则时冲突消失，输入字符变多。

离线夹具（`fixtures.py`）只服务自动化测试：研究员只在上下文里有规则时跳过 `d4`；出题人对每个考点取最后一条允许的事实，所以最小交接固定以 `d4` 出题失败；审核人原样放行；用量按请求长度编出，每次调用暂停 20 毫秒。真实模型可能做出不同选择，结论以你自己的真实运行为准。

## 文件

- `runtime.py`：输入模型、四种做法、上下文审计（`audit_context`）、账本、合并（`merge_facts`）、任务图与报告。
- `verifier.py`：同一个程序验证器。
- `locales/zh_CN.py`、`locales/en.py`：资料、任务说明、规则、各角色提示词、报告文字；`locales/fixture/` 是离线脚本的题干与引文。
- `fixtures.py`、`test_lesson.py`：确定性测试模型与行为测试（含两种运行语言、预算、取消、结构化错误和实验观察点）。

## 运行

```powershell
# 离线测试（确定性模型数据，验证器真实执行）
.\.venv\Scripts\python.exe -m unittest lessons.lesson_multi_agent_patterns.test_lesson -v
# 真实运行一个练习（会产生模型用量）；--locale en 用英文运行
.\.venv\Scripts\python.exe scripts/run_live.py multi-agent-patterns multi --url http://127.0.0.1:8765
```

**运行语言：**资料、任务、规则、提示词和报告文字按运行语言来自 `locales/`；考点、资料编号、原值（`other`、`4`、`3`）和运行标识是代码，各语言相同。

## 参考与署名

上下文共享与不共享的分类、交接包的三部分、新信息判据和失败模式参考《深入理解 AI Agent》第十章（[bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book)，Apache-2.0）；子 Agent 与团队的做法参考 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)（MIT）s06、s13；多 Agent 场景与可见性参考 Microsoft AI Agents for Beginners 的 `08-multi-agent`（MIT）；团队编排与共享计时参考 [claude-cookbooks](https://github.com/anthropics/claude-cookbooks)（MIT）`patterns/agents/`。任务、资料、验证器、运行器与实验由本项目编写，没有复制上述代码。
