# 可观测性、usage 与成本

[English](README.md) · **简体中文**

课程 ID：`observability-cost`。课号按目录顺序计算，只在网页上显示；文件里提到课程一律写课名或课程 ID。

状态：`planned`。实现、离线测试和中英文内容已经写完，还没有用真实模型验收，网页上仍然置灰。

## 本课要解决的问题

前面的课只给出模型调用数和 `total_tokens` 合计。用户说“这次等了 6 秒”，合计数说不出时间花在哪一步、哪次调用是多余的；服务商没报告用量时，程序还很容易顺手记成 0。

本课用一个固定的小任务把一次运行拆开看：核对 4 条差旅报销，每条先请模型归类（交通、住宿、餐饮），再调用 `lookup_rate` 查汇率、`category_limit` 查限额，算出可报销金额，和人工标注对照。运行器在每次调用的边界记一本账，每个跨度一行，然后：

- 按耗时排出慢步骤；
- 按指纹找出重复执行的调用；
- 原样抄下服务商报告的 usage，没报告的写“未报告”；
- 只有填写了价格来源和日期，才把用量折算成估算费用；
- 优化之后用同一题集对照，先看质量有没有回归，再看省下了什么。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `runtime.py` | 运行器：任务数据与两个工具、`Tracer` 账本、`run_pass`（三种策略）、`read_usage`、`repeated_groups`、`slowest`、`estimate_cost`、`regressions`，以及报告组装 |
| `locales/zh_CN.py`、`locales/en.py` | 运行时文本：两个系统提示词、4 条报销说明、工具错误、报告的标签与取值 |
| `locales/__init__.py` | 消息目录的字段定义 |
| `fixtures.py` | 离线测试夹具：按人工标注作答，给出脚本化的 usage；可以关掉 usage、只去掉第 2 次的 usage，或让合并请求分错某几条。只服务自动化测试 |
| `test_lesson.py` | 行为测试：用量读取、指纹、工具与结构化错误、三种策略、账本与事件的关联、未报告不写 0、费用估算、回归检测、输入校验、停止与预算、英文运行没有中文 |
| `content.json`、`content.en.json` | 教学内容与英文译文层 |
| `lesson.json`、`lesson.en.json` | 实现清单（练习、输入预设、运行器）与英文译文层 |

## 怎么运行

离线测试（不需要模型密钥，工具真实执行，模型回复与用量来自夹具）：

```bash
.venv/bin/python -m unittest lessons.lesson_observability_cost.test_lesson -v
```

真实运行：课程开放后在网页实验台运行，或启动服务后用脚本（会产生模型用量）：

```bash
.venv/bin/python scripts/run_live.py observability-cost baseline --url http://127.0.0.1:8765
.venv/bin/python scripts/run_live.py observability-cost batched-compare --url http://127.0.0.1:8765 --locale en
```

本课还没有做过真实运行；上面的命令是验收时要做的事。

## 练习

| 练习 | 输入 | 模型调用 | 工具调用 |
| --- | --- | --- | --- |
| 基线：逐条请求、不缓存（`baseline`） | `strategy: baseline` | 4 | 8 |
| 只开工具缓存（`tool-cache`） | `strategy: tool_cache` | 4 | 5，另有 3 次缓存命中 |
| 合并请求，并与基线对照（`batched-compare`） | `strategy: batched`、`compare_with_baseline: true` | 4 + 1 | 8 + 8 |

调用数按模型把 4 条全部分对计算；分错时 `category_limit` 的参数会变，以报告为准。

其他输入：

- `rate_latency_ms`：`lookup_rate` 每次执行前等待的毫秒数（0–1000，默认 200），模拟远端服务，让慢步骤在离线时也看得见。
- `price_input_per_m`、`price_output_per_m`、`price_currency`、`price_source`、`price_date`：价格表。`price_source` 和 `price_date` 必须一起填，否则不折算费用；估算结果写明模型、来源、日期和覆盖的调用次数，注明“估算，不是账单”。

## 实验看什么

1. **找出重复调用和慢步骤**（基线 vs 只开工具缓存）
   - 第 1 步响应里的 `usage`，以及账本 `lesson.ledger` 第一行怎样原样抄下它；
   - 第 4 步的请求体和第 1 步一字不差（r4 和 r1 的说明相同）；
   - 瓶颈报告的“重复执行的调用”和“最慢的一步”；
   - 开缓存后工具调用从 8 次降到 5 次，模型请求那组重复仍在。
2. **合并请求：省了什么，变没变差**（合并请求，并与基线对照）
   - 第 5 步的合并请求；
   - 对照报告的护栏“质量没有退化”，以及从通过变成失败的条目；
   - 已报告的 Token 变化与端到端耗时变化。

## 平台事件与课程账本

平台为每次运行记录事件：`request`/`response` 是模型跨度，`tool_call`/`tool_result` 是工具跨度，同一轮次属于同一个步骤，`response` 带 `duration_ms`。这些是原始记录。本课的 `Tracer` 在运行器里另记一本派生账：每行带步骤号（等于事件轮次）和 `call_id`（等于 `tool_call` 事件的 id），再加上指纹、运行器计的耗时和原样的 usage。账本和事件有出入时以事件为准。

## 参考

- Hugging Face Agents Course，Bonus Unit 2（可观测性与评估）
- 《深入理解 AI Agent》第七章“Agent 的可观测性”“从 Benchmark 报告到系统改进”“生产级 Agent 的评估基础设施”，配套代码 `chapter7/agent-cost-analysis/tracer.py`
- Microsoft AI Agents for Beginners：`10-ai-agents-production`（生产环境中的 Agent：可观测性与评估）
- Claude Cookbooks：`observability/usage_cost_api.ipynb`、`cost_optimization/cost_optimization.ipynb`

链接与固定版本见 `content.json` 理解场景末尾的参考资料。
