# 人工介入、检查点与恢复（`human-in-the-loop`）

[English](README.md) · 简体中文

在有副作用的一步（把模型写的练习题保存进本地练习库）之前暂停，等人批准、修改或拒绝；用检查点保存执行位置；重启或写入后中断之后从检查点恢复，先凭操作标识查练习库，再决定要不要写。本课需要真实模型连接（草稿和回执各一次模型调用）。

**状态：**`available`。2026-10-21 用 `claude-haiku-5-5` 对每个练习在每种运行语言下各做了一次真实运行，样本各一份（[验证记录](../../docs/verification/live-runs-2026-10-21.md)）。这是对一个模型的带日期记录，不保证其他模型。

## 本课解决什么问题

“Hooks 与审批闸门”（`hooks-approval`）让运行停在审批点，等人决定。但等待发生在一次运行里：服务一重启，那次运行就没了。本课回答三个问题：怎样把“执行到哪了”存下来；人在暂停处改了参数，改动怎样留下痕迹；恢复之后怎样保证已经完成的写入不重复。结论是三件事分开做：检查点存位置，批准跟着摘要走，“做过没有”要去问外部世界。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `runtime.py` | 输入模型；`run` 是一台小状态机，依次是 `draft_step`（模型写草稿、生成操作标识、存 `drafted`）、`approve_step`（审批、校验人的修改、存 `approved`）、`commit_step`（核对摘要、先查后写、存 `saved`）和 `finish`（回执请求、报告、回答）；`stop_at` 让第一次运行在某一步之后结束，模拟进程中断 |
| `bank.py` | 练习库（SQLite，每条线程一个文件夹）：只读的 `lookup_operation`、追加一行的 `save_exercise`，以及 `exercise_problems` 检查；表上故意没有唯一约束 |
| `report.py` | `RunTrace` 收集一次运行的事实；两份 `lesson.report`：“练习库里的内容”（直接读数据库）和“本次运行”（检查、指标、草稿 / 批准 / 库里的行对照表） |
| `locales/zh_CN.py`、`locales/en.py` | 提示词、工具错误、回答、报告文字 |
| `locales/fixture/` | 离线测试模型写草稿和回执用的模板（只服务测试） |
| `fixtures.py` | 只服务自动化测试的确定性模型和确定性审批人：模型按主题写固定草稿、按事实写回执；审批人批准，`edit-state` 那组还会改难度和标题 |
| `test_lesson.py` | 行为测试：真实的练习库写入、三个检查点、拒绝与超时、人工修改与非法修改、三个中断点、恢复一次与多次、盲目恢复写出两行、摘要被动过就拒绝、检查点与库对不上、取消、英文运行无中文，以及经平台接口重开运行存储后的恢复和 `checkpoint_stale` |

平台部分在 `course/execution.py`：`request_approval` 和 `checkpoint`，恢复接口 `POST /api/runs/{id}/resume` 在 `server/app.py`，事件格式见 `docs/architecture/event-envelope-v2.md` 第 7 节。本课没有用 LangGraph 的 `interrupt`，对照放在正文的深入块里。

## 练习

| 练习 | 参数 | 第一次运行 | 模型调用 |
| --- | --- | --- | --- |
| 正常流程：批准后保存 | 默认 | 草稿、`drafted`、审批、`approved`、先查、写入、`saved`、回执；业务状态 `saved` | 2 次 |
| 批准后暂停，重启并恢复 | `stop_at`=`before_save` | 到 `approved` 为止，练习库 0 行；业务状态 `suspended`；从 `approved` 恢复后写入一行 | 1 次，恢复后再 1 次 |
| 写入后中断：恢复不重复保存 | `stop_at`=`after_save` | 写入已发生，最后一个检查点仍是 `approved`，练习库 1 行；恢复后先查到，业务状态 `already_saved` | 1 次，恢复后再 1 次 |
| 人工修改后恢复 | `stop_at`=`before_save` | 审批卡上改难度和标题；`approved` 检查点里 `draft` 与 `approved` 不同，`edited` 为真 | 1 次，恢复后再 1 次 |

表里的次数来自离线测试模式。真实运行时，审批由你在网页的审批卡上决定，“人工修改后恢复”要你自己改一个字段；模型的草稿格式不对时运行以 `failed` 收尾，原因是 `bad_draft`。

## 实验看什么

- **写入前的确认与人工修改**：先猜正常流程记几条 `checkpoint`（3 条）；再看写入调用只出现在批准之后，`approval_resolved` 里 `edited` 与两份摘要，`approved` 检查点里的草稿与批准版。
- **暂停、重启与恢复**：看第一次运行的业务状态 `suspended`；在 `approved` 检查点上点“从「approved」恢复”（想更接近真实，先重启后端）；恢复出来的运行里看“恢复自”“线程 ID”“模型调用数”，以及“草稿请求没有重发”这条检查。
- **写入后中断，恢复不重复保存**：看写入工具的行号、练习库里的行；恢复后看“写入前查询”是“已找到”、“写入”是“未写入”；再把 `resume_guard` 改成 `blind` 对照，同一个操作标识会有两行，`written-once` 检查未通过。

## 运行

离线测试（确定性模型与审批数据，练习库、检查点、恢复接口都是真实的）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_human_in_the_loop.test_lesson -v
```

测试里的“重启”是关闭运行存储再按同一路径重新打开，新进程只能读到磁盘上的记录；它不是真的重启进程。

真实运行：在网页的实验台选择练习，运行停在审批点时在审批卡上决定，再在事件里的检查点上点恢复。命令行方式（会产生模型用量，`--ask-approvals` 让审批改由终端里的人决定）：

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py human-in-the-loop approve-save --url http://127.0.0.1:8765 --locale en --ask-approvals
```

练习库在 `.runtime/human-in-the-loop/<线程 ID>/bank.sqlite3`（真实运行）或系统临时目录（离线测试模式），事件和报告里只写文件名和行，不写本机路径。2026-10-21 每个练习在中英两种运行语言下各用真实模型运行过一次，`restart-resume` 和 `crash-after-write` 真的重启了后端再恢复（见验证记录）。

**运行语言：**提示词、回答和报告文字写在 `locales/` 里；状态码、检查点名、工具名、字段名是代码，各语言相同。

## 参考

检查点与恢复的概念对照 Hugging Face Agents Course（Apache-2.0）`units/en/unit2/langgraph/building_blocks.mdx`；幂等的两条手段、“预检-确认”两段式参考《深入理解 AI Agent》第四章、第六章（Apache-2.0）；按稳定键续跑的日志对照 learn-claude-code（MIT）`s16_workflow_runtime`；人工介入对照 Microsoft AI Agents for Beginners（MIT）`06-building-trustworthy-agents`。LangGraph 的 `interrupt`、检查点存储与 `update_state` 按 LangChain 官方文档（2026-10-21 核对）。练习库、检查点状态设计、报告和实验由本项目编写。
