# 独立评估集与验证器（`evaluation-sets`）

[English](README.md) · 简体中文

一次跑通说明不了新版本更好。本课把 `tool-selection`、`dependent-calls`、`fail-safely` 三课的工具任务写成一套固定题集，让同一个工具循环用两个版本的系统提示词各跑一遍，再由 Agent 之外的验证器逐题判定、逐题配对比较。## 本课要回答的问题

- 流程结束、答案正确、证据充分、过程无违规，怎样分开判定？哪些情况程序判不了，要记为“不可评估”？
- 开发集和留出集为什么要分开？留出集为什么只在版本定下后跑一次？
- 两个版本的通过率差了几道题，这个差异是改进还是运气？哪些题出现了回归？
- 开放题交给评审模型之前，怎样先和人工标注对一致性？

**状态：**`available`。2026-10-21 用 `claude-haiku-5-5` 对每个练习在每种运行语言下各做了一次真实运行，样本各一份（[验证记录](../../docs/verification/live-runs-2026-10-21.md)）。这是对一个模型的带日期记录，不保证其他模型。评审校准在这些运行里没有出现分歧可读。

## 文件导览

| 文件 | 作用 |
| --- | --- |
| `cases.py` | 版本化题集：每道题的类别、期望调用（参数可以引用另一个工具的结果）、比对规则 `mode`、正确答案；题集版本 `SUITE_VERSION`、单题修订号 `rev`、指纹 `fingerprint()`；评审校准样例 `JUDGE_SAMPLES` |
| `verifier.py` | 独立验证器：`verify()` 只读题目规定和本次轨迹，给出五项检查（流程结束、调用比对、答案正确、证据充分、过程无违规）和整题结论；`same_call()` 解析参数后按数值比较 |
| `runtime.py` | 被测 Agent（前三课的工具循环，每题最多 3 次模型调用）、按版本跑整套题、配对分析 `paired()`、符号检验 `sign_test()`、Wilson 区间、评审模型校准 |
| `locales/zh_CN.py`、`locales/en.py` | 运行时文本：两个版本的系统提示词、每道题的问题、检查说明、报告文字、评审量规和 6 条样例回答 |
| `fixtures.py` | 离线测试用的确定性模型，只服务自动化测试 |
| `test_lesson.py` | 验证器逐条测试、统计函数、四个练习的离线运行、两种运行语言 |

工具直接复用 `lessons/lesson_01_tool_selection/tools.py`（`add_numbers`、`get_current_time`）和 `lessons/lesson_03_fail_safely/tools.py`（`divide_numbers`），没有修改它们。

## 题集

| 题目 | 题集 | 类别 | 期望 |
| --- | --- | --- | --- |
| `add-basic` | 开发集 | 简单 | 调用一次 `add_numbers(19, 23)`，答 42 |
| `clock-sum` | 开发集 | 依赖 | 先 `get_current_time`，下一步用 hour、minute 调 `add_numbers`；答案由验证器自己算 |
| `divide-zero` | 开发集 | 工具失败 | `divide_numbers(100, 0)` 报错后答 NONE |
| `greeting` | 开发集 | 不该调用 | 不调用工具；开放式回答，正确一项不可评估 |
| `two-sums` | 开发集 | 并行 | 两次 `add_numbers`，顺序不限，答 42 和 105 |
| `unknown-balance` | 开发集 | 缺少证据 | 没有工具能查余额，不调用工具，答 NONE |
| `add-holdout` | 留出集 | 简单 | `add_numbers(58, 67)`，答 125 |
| `divide-zero-holdout` | 留出集 | 工具失败 | `divide_numbers(7, 0)` 报错后答 NONE |
| `given-distance` | 留出集 | 不该调用 | 题面已给出 12 公里，不调用工具，答 12 |
| `clock-half` | 留出集 | 依赖 | 先读时钟，再 `divide_numbers(hour, 2)` |

最终回答约定在最后一行写 `<answer>数值</answer>`，拿不到数值写 `<answer>NONE</answer>`。两个版本共用这个格式，版本 B 只多一段规则：计算和查时间必须调用工具、依赖的调用分步发出、工具报错或没有依据时写 NONE。

## 练习

| 练习 | 预设 | 最多模型调用 | 主要证据 |
| --- | --- | --- | --- |
| 开发集：版本 A 对比版本 B | `split=dev`、`versions=both` | 36 | 12 条 `lesson.case_result`、两份版本报告、一份配对分析报告 |
| 留出集：定好版本后跑一次 | `split=holdout`、`versions=both` | 24 | 同上，题目换成 4 道留出题 |
| 同一版本跑两次 | `split=dev`、`versions=B`、`repeats=2` | 36 | 每道题两次结论、`Pass^2`、`Pass@2`、结论翻转的题数 |
| 评审模型与人工标注对照 | `task=judge` | 6 | 6 条 `lesson.judgement`、一致率、误判为合格、kappa |

- 每道题一条 `lesson.case_result`：五项检查各自的状态（通过、未通过、不适用、不可评估）和说明，`violations`、`failures`、`unassessable` 三个列表。
- 每个版本一份 `lesson.report`：流程结束数和验收通过数并排，另有不可评估数、Wilson 区间、题集版本与指纹。
- 两个版本都跑时再加一份配对分析：改善数、回归数、结论不一致的题数、符号检验 p 值；不一致的题少于 6 道时，报告直接写明只当方向线索。
- 运行开始的 `lesson.task_card` 写明这次跑哪份题、题集指纹和停止条件。
- 运行前按“题数 × 版本数 × 重复次数 × 3”检查最多需要的模型调用数，超出本课上限（80）就拒绝运行，不会跑到一半停下。

## 实验看什么

1. **版本对照**：先看任务卡里的题集指纹；再看第一道有违规的题、被记为不可评估的检查；对照版本报告里的流程结束数和验收通过数；最后看配对分析的回归数和 p 值。
2. **同一版本跑两次**：两次都通过的题数和至少过一次的题数差多少，有没有结论翻转的题。
3. **评审模型校准**：读评审模型和人工标注不一致的那几条，尤其是误判为合格的。

## 怎么运行

离线测试（确定性模型数据，工具真实执行，时钟题用本机真实时间）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_evaluation_sets.test_lesson -v
```

`fixtures.py` 给两个版本安排了固定行为：版本 A 在依赖题上同一步猜参数、工具报错后仍给数值、编造余额；版本 B 在留出集的 `given-distance` 上多调用一次工具，形成一道回归；评审模型脚本只把 `j6` 判错。这些都是脚本写的，只用来测试报告和验证器，不代表任何真实模型的表现。

真实运行：在网页实验台选择练习运行，或使用 `scripts/run_live.py evaluation-sets <练习> --url http://127.0.0.1:8765 [--locale en]`。一次“开发集对比”最多 36 次模型调用，会产生相应用量。

**运行语言：**本课支持中文和英文运行。系统提示词、题目、检查说明、报告文字、评审量规和样例回答写在 `locales/zh_CN.py` 与 `locales/en.py`；题目 id、类别、检查状态和评审结论（`pass`、`fail`）是代码，各语言相同。网页按界面语言选择，运行记录里写明这次运行的语言。

## 边界

- 验证器只按题目规定判定，规定本身写错了，结论也会错；所以 `test_lesson.py` 先用手写轨迹逐条测验证器。
- 6 道或 4 道题的结果只能说明这套题上的情况；p 值只作参考，同时比较多个版本时还要收紧门槛或复跑。
- 评审校准的 6 条回答和人工标注由课程作者编写，是评估数据，不是运行记录；6 条样例不足以证明评审模型可靠。

## 参考

- 深入理解 AI Agent（Apache-2.0）第 7 章“评估指标：成功的定义”“评估数据集的设计”“自动化评估方法”“评估结果的统计显著性”；配套代码 `chapter1/context/grounding.py`（答案数字有无来源、不可评估的判定）与 `chapter7/user-memory-policy-eval/runner.py`（确定性规则评分）。
- claude-cookbooks（MIT）`tool_evaluation/tool_evaluation.ipynb`、`misc/building_evals.ipynb`。
- Hugging Face Agents Course（Apache-2.0）`units/en/bonus-unit2/`、`units/en/unit4/hands-on.mdx`；Microsoft AI Agents for Beginners（MIT）`10-ai-agents-production/README.md`。

借鉴的是方法（拆开的检查、数字溯源、精确匹配、配对与小样本不确定性），题集、验证器、版本与实验由本项目编写，没有复制参考代码。
