# 可靠工具、重试与幂等（`reliable-tools`）

[English](README.md) · 简体中文

工具会超时、会撞上别人的锁，写入成功了结果也可能送不回来。本课回答三个问题：哪些失败值得重试，重试到哪里为止，怎样保证一次写入不会因为重试而生效两次。本课不调用模型。

**状态：**`available`。本课不调用模型；2026-10-21 每个练习在每种运行语言下各经真实运行路径跑过一次（[验证记录](../../docs/verification/live-runs-2026-10-21.md)），没有“真实模型验证”这一项。

## 本课的工具和故障

每次运行都在一次性临时目录里新建一个练习提交库（SQLite）和一个批改箱文件夹，真实运行和离线测试模式走同一段代码，起点完全相同：学习者 `learner-a` 有 3 次批改额度，`learner-b` 有 0 次。

| 工具 | 读还是写 | 做什么 |
| --- | --- | --- |
| `read_account` | 只读 | 查剩余额度和有效提交数 |
| `submit_practice` | 写 | 扣 1 次额度、登记 1 条提交；可带 `idempotency_key` |
| `write_outbox` | 写（可安全重复） | 把答案写成 `outbox/<id>.json`，同一份提交写两次仍是一个文件 |
| `cancel_submission` | 写（可安全重复） | `submit_practice` 的补偿：退回额度、把提交标成 `cancelled` |

故障由运行器故意制造，每个故障之前先发一条 `lesson.fault` 事件，`source` 为 `fault_injection`：

- `store_locked`：另一条连接对数据库执行 `BEGIN EXCLUSIVE`，工具真的等满时限（`timeout_ms`）后抛出 `StoreTimeout`；
- `outbox_locked`：批改箱里放一个别人的锁文件，`write_outbox` 真的发现被占用，抛出 `OutboxBusy`；
- `response_lost`：工具真的执行并提交了事务，结果在返回途中被丢弃，调用方收到 `ResponseLost`。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `retry.py` | `CATEGORIES` 分类表、`classify`、`decide`、`backoff_delay`（指数退避加抖动）、`call_with_retry`（次数上限与时间预算，每次失败发一条 `lesson.retry`） |
| `store.py` | `PracticeStore`：四个工具、`operations` 幂等记录表、`snapshot`（直接读数据库和批改箱） |
| `faults.py` | `FaultInjector`：按“操作、第几次尝试”布置故障，并发出 `lesson.fault` |
| `runtime.py` | 四个练习的流程与报告；`run(context)` 是入口 |
| `locales/` | 工具错误、报告文字和程序写出的回答，中英各一份 |
| `test_lesson.py` | 行为测试：真实 SQLite 与文件读写、真实的锁超时、可注入时钟（退避等待不真睡） |

## 练习

| 练习 | 做什么 | 看哪里 |
| --- | --- | --- |
| 只读查询：锁住两次 | 前两次查询撞上被锁的数据库，退避后第三次成功 | `lesson.retry` 的 `wait_ms`；报告表格两次 `StoreTimeout` 各约 200 毫秒；检查“重试前后存储完全相同” |
| 错误分类：哪些失败值得重试 | 不存在的练习、额度为 0、第一次遇锁的提交、第一次遇锁的批改箱写入 | 前两个 `decision` 为 `stop`，后两个 `retry` 后成功；库里只有 1 条提交、1 个文件 |
| 写入生效、结果丢失 | 三个新库，同一个故障：盲目重试、结果不明就停、带幂等键重试 | 三条 `lesson.storage` 的提交数分别是 2、1、1；第 3 轮的工具结果 `replayed` 为 true；`operations` 表里的键 |
| 两步写入：中途失败与补偿 | 第 1 步写库成功，第 2 步写批改箱一直被占用，4 次后放弃并补偿 | 第 3 轮的 `cancel_submission`；`lesson.storage` 里状态 `cancelled`、额度 3、没有文件；最终状态“未完成，已补偿” |

可以在实验台改结构化输入：把 `locked_attempts` 改成 6 看次数上限，把 `budget_ms` 调小、`base_delay_ms` 调大看时间预算先到，把 `outbox_busy_attempts` 改成 1 看两步都完成。问题框是学习者备注，只写进报告。

## 边界

- 本课的 `StoreTimeout` 明确发生在事务开始之前，所以写操作也能重试；远程调用的超时通常只能按结果不明处理。
- 抖动用固定种子，只为让同一组输入可以重现；本课只有一个调用方，看不出抖动错开大量调用方的效果。
- 幂等记录和业务数据在同一个 SQLite 文件里，才能放进同一个事务；远程服务的键怎样保留、保留多久，要看对方的实现。
- 本课没有演示补偿也失败的情况，只在报告里预留了“部分完成，补偿失败”。

**运行语言：**本课支持中文和英文运行。工具错误、报告的标签与取值、程序写出的回答在 `locales/zh_CN.py` 与 `locales/en.py`；工具名、参数名、事件名和错误类名是代码，两种语言相同。

## 怎么运行

离线测试（真实工具、真实锁，退避等待经可注入时钟）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_reliable_tools.test_lesson -v
```

在网页实验台运行，或用 `scripts/run_live.py reliable-tools <练习>`（本课不调用模型，不产生模型用量）。

参考：《深入理解 AI Agent》第 4 章“执行工具”的幂等性与取消语义、第 5 章“故障与错误恢复”；Microsoft AI Agents for Beginners 的 `04-tool-use` 与 `06-building-trustworthy-agents`；Learn Claude Code `s15_integrated_harness` 的退避重试；Claude Cookbooks 的 SRE 事故响应 Agent（读工具与写工具分开约束）。代码与实验为本项目编写。
