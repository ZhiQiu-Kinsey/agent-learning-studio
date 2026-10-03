# 记忆的更新、过期与召回范围（`memory-lifecycle`）

本课不调用模型。三个练习都在一次性临时库里运行，真实运行和离线测试模式走同一段代码，不碰“持久记忆”一课的固定教学库。存储类沿用 `lessons/lesson_10_persistent_memory/store.py`。

| 练习 | 做什么 | 看哪里 |
| --- | --- | --- |
| 两个写入方与过时写入 | A、B 两条连接读到同一个版本；A 先写成功，B 带旧版本写入被 `VersionConflict` 拒绝，重新读取后带新版本写入 | `conflict_and_update` 事件的 `stale_rejected`、`error`、`value_after_reject` |
| 过期、删除与重开核对 | 写一条已到期的提醒：`get` 读不到但 `stored` 找得到；`delete` 后换新连接核对 | `expired`、`deleted` 事件；把 `expires_in_seconds` 改成正数可以对照“还没到期” |
| 按范围召回，召回内容只当数据 | 预置 persistent 与两个任务的 current_task 记录，为 task-now 召回、包装成数据、结束任务、再为 task-next 召回 | `recalled`、`packaged`（`sent_to_model` 为 false）、`task_ended` 事件 |

- 乐观并发控制只防同一个库里的过时写入；本课两个写入方在同一进程里先后执行，不能证明跨机器或数据库副本的一致性。
- 过期是读取规则，删除是存储操作：到期的行仍在表里，直到显式删除。删除不清零版本：`versions` 表记着每个键写到了第几版，同一个键删除后重建，版本接着往上加，删除前读到旧版本的写入方仍会被拒绝。
- `instruction_like` 是正则粗筛，会漏报也会误报，不是安全边界。包装好的消息只展示、不发送；模型读到这类数据会不会照做，留到提示注入课用真实模型检验。

参考与取舍见 `docs/architecture/budget-memory-sources.md`。

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_memory_lifecycle.test_lesson -v
```
