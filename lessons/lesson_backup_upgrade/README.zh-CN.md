# 备份、恢复与升级回退（`backup-upgrade`）

[English](README.md) · 简体中文

**本课的问题：**数据坏了、升级砸了，能不能回来？本课不调用模型，四个练习都在临时目录里对两个真实的 SQLite 文件操作，布局和本机 `.runtime/` 一致（`runs.sqlite3` 存运行记录，`memory.sqlite3` 存记忆），但不会读写你真实的 `.runtime/`。运行结束后临时目录整个删除。接上一课“本地交付”（密钥与配置只在后端）和“持久记忆”“记忆的更新、过期与召回范围”（记忆库的读写）。

本课没有模型调用，所以没有“真实模型验证”这一项：真实运行和离线测试模式走同一段代码，网页上点“运行”就是真实的本地运行。

**状态：**`available`。本课不调用模型；2026-10-21 每个练习在每种运行语言下各经真实运行路径跑过一次（[验证记录](../../docs/verification/live-runs-2026-10-21.md)），没有“真实模型验证”这一项。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `backup.py` | 四种复制方式（逐页复制、SQLite 备份接口、`VACUUM INTO`、停机复制）；备份清单 `manifest.json` 的生成与核对；恢复到新目录；回退用的 `restore_into`；保留最近 N 份的 `prune` |
| `migrate.py` | 数据迁移 v1 到 v2：`migrate_memory` 重建表，`migrate_runs` 改名、加列、回填；可选的事务；故障注入 `Fault`（中途抛异常，或悄悄漏行） |
| `checks.py` | 检查：`integrity_check`、行规则、内容摘要、`service_check`（按版本启动服务读数据）、密钥扫描 |
| `seed.py` | 教学数据目录，和一个真的在提交的写入线程 `LiveWriter` |
| `runtime.py` | 四个练习的流程；`reports.py` 组装 `lesson.report` 和辅助事件 |
| `locales/` | 运行时文本，中英各一份；教学数据（记忆的文字、事件正文）也在这里 |
| `test_lesson.py` | 行为测试：真实的 SQLite、真实的写入线程、两种运行语言、故障矩阵 |

读码页的三个块：复制方式（`backup.py`）、清单与核对（`backup.py`）、事务里的迁移（`migrate.py`）。

## 四个练习

| 练习 | 做什么 | 看哪里 |
| --- | --- | --- |
| 在线备份 | 写 8 个运行和 8 条记忆，写入线程再提交 6 个单位，然后用所选方式备份，复制中间写入线程继续提交；读回两个副本，分别做 `integrity_check` 和行规则检查 | `lesson.backup`（日志模式、`-wal` 文件、复制期间的写入数）、报告里每个文件的两项检查 |
| 恢复演练 | 备份、核对清单、恢复到新目录、用服务读数据的方式验收；可以改备份范围、损坏一个字节或截断文件、关掉清单核对 | `lesson.verify`、`lesson.restore`、报告里的 `damage_caught`、`digest_matches`、`no_secrets` |
| 升级与回退 | 迁移 `memory.sqlite3`，再迁移 `runs.sqlite3`；程序按所选方式制造失败；按所选保护措施回退；最后检查服务和数据 | `lesson.fault`（来源 `fault_injection`）、`lesson.migration`、`lesson.rollback`、报告里的 `service_available`、`data_unchanged` |
| 保留最近 N 份 | 做 6 份备份，损坏最新的几份，按策略清理，再从留下的备份里恢复 | `lesson.retention`、报告里的 `restorable_after_prune`、`runs_lost` |

上表每个练习在 `lesson.json` 里有几个预设变体，对应实验里的各个对照组（离线模式只接受该练习自己预设的结构化输入）：在线备份有 `online-backup`（边写边复制文件）、`online-backup-api`、`online-vacuum-into`、`online-cold-copy`；恢复演练有 `restore-drill`（完整备份）、`restore-bit-flip-verified`、`restore-bit-flip-skipped`、`restore-whole-directory`；升级与回退有 `upgrade-rollback`（备份加事务，第二个文件失败）、`upgrade-no-safeguard`、`upgrade-transaction-first-file`、`upgrade-transaction-second-file`、`upgrade-transaction-bad-result`；保留最近 N 份有 `retention`（最新 N 份加最新一份通过核对的）和 `retention-newest-only`。保留策略这一对在恢复演练的实验里对比。

怎样读结果：

- 在线备份“边写边复制文件”：`runs.sqlite3` 的副本 `integrity_check` 是 ok，却缺 6 个备份开始前已提交的运行（它们还在 `-wal` 里）；`memory.sqlite3` 的副本被撕裂，两张表对不上。备份接口、`VACUUM INTO` 和停机复制的副本两项都通过。
- 恢复演练“翻转一个字节”：清单核对失败、恢复被拒绝；关掉核对再运行，`integrity_check` 通过、记忆照样召回，只有内容摘要一项失败。
- 升级与回退：只靠事务时，第一个文件失败可以完整回滚，第二个文件失败或迁移“成功但漏了行”回退不了；备份加事务三种都能退回升级前，并且检查服务和数据没变。
- 保留最近 N 份：只留最新 N 份在最新几份损坏时无法恢复；再加一份通过核对的，可以恢复，代价是比最新的数据少几个运行。

## 诚实说明

- 数据库、写入线程、复制和检查都是真的；只有故障是程序制造的：翻转的字节、截断、迁移里抛出的异常和漏掉的行。每一个都在 `lesson.fault` 或 `lesson.migration` 事件里标着来源 `fault_injection`，它们不是备份工具或 SQLite 的行为。
- 在线备份默认的写入节奏是“写入与复制交替”：复制每一页，写入线程提交一个单位。这样每次结果相同，写入也是真提交，但重叠的时机是我们安排的。把写入节奏改成“自由运行”，写入线程自己跑，直接复制的结果每次可能不同。测试只对交替节奏断言具体结果，对自由运行只断言不变量。
- 密钥扫描只认本课放进目录里的一个假标记（`sk-demo-canary-…`，不是真密钥）和以 `sk-` 开头的字符串；它不能证明备份里没有别的敏感内容。
- 没做：异地备份、备份加密、断电时的行为、升级与回退之间服务仍在写入的情形、程序版本的回退（只回退数据）。
- 事实来源：SQLite 官方文档的在线备份接口、`VACUUM INTO`、预写日志、如何损坏数据库四页；Microsoft AI Agents for Beginners 的部署与记忆两课；《深入理解 AI Agent》第三章（知识更新与整理）、第九章（持续进化的安全边界）。具体版本与范围登记在 `docs/architecture/reference-study.md`。

## 运行语言

本课支持中文和英文运行。教学数据的文字、报告标签和程序写出的回答在 `locales/zh_CN.py` 与 `locales/en.py`；SQLite 自己的报错（如 `integrity_check` 的第一条问题）是 SQLite 的英文原文，英文运行里没有中文。

## 运行与测试

```powershell
# 本课测试：真实 SQLite、真实写入线程，约十几秒
.\.venv\Scripts\python.exe -m unittest lessons.lesson_backup_upgrade.test_lesson -v
# 在网页上运行（本课不需要模型密钥）
.\.venv\Scripts\python.exe scripts/run_live.py backup-upgrade online-backup --url http://127.0.0.1:8765
# 校验
.\.venv\Scripts\python.exe scripts/validate_lessons.py
```

`run_live.py` 对不调用模型的练习不产生用量。
