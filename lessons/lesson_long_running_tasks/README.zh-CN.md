# 后台与定时任务（`long-running-tasks`）

[English](README.md) · 简体中文

## 本课的问题

耗时的检查不该卡住对话。模型把它放到后台，立刻拿到任务编号，继续做别的事；任务结束后，结果要在之后的某一轮交回模型，并且标明来源和时间。本课回答四个问题：

- 什么任务值得放到后台，启动调用返回什么（任务编号和 `running`，没有结果）；
- 结果什么时候、以什么形式进入对话（下一轮请求之前，作为一条单独的、标明来源的消息）；
- 每轮结束时谁来判断目标完成、无法完成还是继续，预算用完怎么停（运行层的目标检查，不看模型怎么说）；
- 任务怎么取消、有哪些终态和退出码，运行结束时还在跑的任务怎么办（统一取消，不留孤儿线程）；另外，定时触发怎样反复启动，上一次没跑完时怎么办。

本课只在**一次运行内**成立。真实产品里要跨运行保留任务和触发规则，需要外部调度器（系统的 `cron`、定时器）或持久队列，本课不做。

## 任务和时间

巡检助手替助教做两件事：校验 6 份作业提交包的 SHA-256（`checksum_pack`），统计 12 位同学的成绩及格人数（`grade_stats`）。另有两种任务用来演示失败和超时：`late_import`（补交成绩表第 6 行写的是 `8x`，导入每次都在启动后第 6 秒抛错）和 `deep_scan`（扫描 8 个分片要 80 秒，默认期限 40 秒）。

任务在 `executor.py` 的线程里**真实计算**（SHA-256、求和、解析、查重），但它们声明的耗时用**虚拟时钟**：线程不 `sleep`，而是停在时钟上等某个时刻，只有运行器能推进时钟。这样同一次运行的时间线每次都一样，对照实验才可比，测试推进 120 秒也不必真等。事件里写明 `clock: "virtual"`。虚拟时钟上的秒不是测得的耗时。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `runtime.py` | 运行器：工具、每轮循环（时钟前进 → 注入 → 请求 → 目标检查）、报告；`schedule` 场景的本地流程 |
| `executor.py` | `VirtualClock`、后台执行器（线程、取消、超时、`shutdown`）、退出码 |
| `jobs.py` | 四种任务的真实计算和声明的耗时 |
| `goal.py` | 每轮目标检查：`ok`、`impossible`、`continue`，以及预算用完的停止 |
| `scheduler.py` | 固定间隔触发器和三种重叠策略（`skip`、`queue`、`parallel`） |
| `locales/` | 运行时文本（中英各一份）；`locales/fixture/` 只服务测试夹具 |
| `fixtures.py` | 离线测试模型：从收到的历史里读状态，值从注入的消息里照抄 |
| `test_lesson.py` | 执行器、调度器、目标检查、工具和每个练习的行为测试 |

## 工具和事件

模型有五个工具：`start_background_job`（立刻返回编号）、`check_job`（状态和进度，结果交付之前不显示结果）、`cancel_job`、`read_policy`（同步的快速查询）、`submit_report`（提交简报，只记录，不判定）。

| 事件 | 含义 |
| --- | --- |
| `lesson.background_job` | 一个任务的某个阶段：`started`、`finished`、`injected`、`cancelled`；带 `finished_at`、`observed_at`、退出码 |
| `lesson.clock` | 时钟每次前进：从几秒到几秒，原因是 `round` 或 `idle_wait` |
| `lesson.harness_injected` | 运行层插入的消息：`background_result`（后台结果）或 `goal_feedback`（目标反馈），`source` 写明来源 |
| `lesson.goal_check` | 每轮结束时的目标检查：结论、理由、各任务状态；让运行停下的那次带 `outcome` |
| `lesson.schedule_fire` | 触发器每次到点的决定：开始、跳过、排队、丢弃或拒绝，带原因和运行编号 |
| `lesson.report` | 实验报告：检查、指标、任务表或触发表 |

## 练习

| 练习 | 看什么 |
| --- | --- |
| 后台任务与结果注入 | 两个任务各自结束，分两轮注入；结果在注入之前不出现在任何请求里 |
| 任务失败与重试 | `late_import` 失败带退出码 1 注入，重试再失败，启动 2 次后判定无法完成 |
| 预算很紧：轮询、取消与重启 | 轮询 2 次、取消、重启，5 轮预算用完，还在跑的任务被统一取消（退出码 143） |
| 定时触发：跳过、排队、有上限的并行（三个练习） | 每 5 秒触发一次 12 秒的任务，三种策略的跳过、排队、拒绝各不同；不调用模型 |

前三个练习需要真实模型连接；后三个是本地练习，不需要密钥。离线测试模式只接受练习预设的输入，所以三种重叠策略各是一个练习；在真实运行里可以直接改参数。实验台的参数可以改：每轮的虚拟秒数、轮数预算、同时运行的任务数、重试上限，以及触发间隔、运行时长、重叠策略和并行上限。

## 怎么运行

离线测试（确定性模型数据，任务和调度器照常真实运行）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_long_running_tasks.test_lesson -v
```

真实运行：启动服务后在网页里选择本课，配置好模型连接，或用命令行：

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py long-running-tasks background-basic --url http://127.0.0.1:8765 --locale zh-CN
```

真实运行的结果取决于模型：它可能不等结果就写简报、反复轮询，或者重试的次数和本课脚本不同。本课正文不预设真实运行的结果，只写能从事件检查的判断方法。离线夹具只服务测试，网页上没有它的入口。

## 实验看什么

- **后台任务与结果注入**：`lesson.background_job` 里 `finished_at` 和 `observed_at` 的差，就是结果在路上耽误的虚拟秒数；`lesson.harness_injected` 的 `round` 是模型第一次看到结果的轮次；报告里的 `not_seen_early` 检查拿注入的每一行去真正发出的请求里找，第一次出现必须正好是注入它的那一轮。把每轮的秒数从 5 改成 10，看注入提前一轮。
- **三种结局**：每一轮的 `lesson.goal_check` 都有理由；`impossible` 要求某种任务启动到上限仍没成功，也没有在运行；预算用完的那次检查带 `outcome: budget_exhausted`，之后报告里的存活线程是 0。
- **重叠策略**：同样是 8 次到点，`skip` 开始 3 次，`queue` 开始 3 次且有 4 次排队、3 次丢弃，`parallel` 开始 6 次、拒绝 2 次；每次到点都有一条 `lesson.schedule_fire`。

## 边界

- 任务是内置的固定代码，不执行模型生成的命令。要运行模型生成的命令，必须先有隔离方案。
- 取消是协作式的：线程没法从外面杀掉，任务停在时钟上等待时看到停止标志才结束。已经做完的步骤和已经发出的请求收不回。
- 运行被停止后，平台不再接受事件，清理的记录发布不出来；线程回收仍有保证，测试在正常结束、报错中途退出、被停止三种情况后都数了线程。
- 目标检查只核对有确定答案的事实（任务状态、简报里的值与结果是否一致），评判不了开放式的回答。

## 参考与署名

后台线程加通知队列、不复用原调用 id 的做法，以及定时调度的五段式表达式、待交付队列与持久化边界，参考 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)（MIT）的 `s11_background_tasks`、`s12_cron_scheduler` 和 `s17_goal_loop`。事件循环里取消式、队列式、并行式三种处理办法，以及任务句柄表达异步语义，参考《深入理解 AI Agent》（[bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book)，Apache-2.0）第 6 章。并发上限与回压参考 [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners)（MIT）的 `16-deploying-scalable-agents`。工具、任务、虚拟时钟、执行器、目标检查、调度器和实验由本项目编写，没有复制参考项目的代码。
