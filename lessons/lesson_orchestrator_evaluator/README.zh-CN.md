# 编排者-工人与评估者-优化者（`orchestrator-evaluator`）

[English](README.md) · 简体中文

任务固定为“为 messages-context、application-state、context-budget 三课各出一道四选一的选择题”；三课用课程 slug 指代，不用会随课程表变化的课号。本课需要真实模型连接。

| 预设 | 模型请求 | 证据 |
| --- | --- | --- |
| 单次调用（基线） | 1 | 三道题的格式检查 |
| 编排者-工人 | 1 + 子任务数 | `lesson.plan`（子任务即计划项）、工人请求带 `branch` 并行发出、`lesson.worker` |
| 评估者-优化者，最多 3 轮 / 1 轮 | 每轮 1–2 | `lesson.draft`、`lesson.review`（`source` 为 `evaluator` 或 `format-check`）、停止原因 |

- 编排者的子任务列表先校验（最多 4 个、id 不重复、lesson 只能是这三课的 slug），不通过就记 `lesson.plan_error`，不派工人。
- 题目格式由程序检查；格式不对时直接退回，不请求评估者。
- 修订循环的四种停止原因：评审通过、评审输出不合格式、修订后没有变化、达到迭代上限。生成者原样交回上一版的题目时（`lesson.draft` 的 `unchanged` 为 true），不再请评估者，直接停下。
- 每次调用记入账本（`lesson.cost`）：角色、轮次、branch、服务商报告的 `total_tokens`；没有报告就记为未报告，不估算。

**运行语言：**本课支持中文和英文运行。三课要点、任务、四个角色的系统提示词、格式问题、停止原因和报告文字写在 `locales/zh_CN.py` 与 `locales/en.py`；课程 slug、角色代号和评审结论是代码，各语言相同。网页按界面语言选择，运行记录里写明这次运行的语言。

格式检查通过不代表题出得好，题目质量需要阅读判断。`fixtures.py` 只服务自动化测试，其中评估者第一次固定要求修订、用量数字都是脚本写的。

两种模式参考 [claude-cookbooks](https://github.com/anthropics/claude-cookbooks)（MIT）`patterns/agents/orchestrator_workers.ipynb` 与 `evaluator_optimizer.ipynb`。原示例的工人串行执行、修订循环没有迭代上限；本课改为并行工人，修订循环设迭代上限，修订后没有变化就提前停。任务、格式检查与实验由本项目编写。

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_orchestrator_evaluator.test_lesson -v
```
