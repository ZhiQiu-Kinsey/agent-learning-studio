# 持久记忆与会话恢复（`persistent-memory`）

本课只调用本地 Python 与 SQLite，不调用模型。live 运行写入 `.runtime/lesson10-memory.sqlite3`，同一 namespace/key 会保留到下次；offline 运行在临时目录建库，结束后清理。先执行“保存与重开连接”，再执行“只读恢复上次记忆”，可以看到跨次运行保留下来的值、来源与版本。只读预设不写入，它的 offline 模式会先在临时库放一条受控样本。其余写入类预设会修改你选的键，请使用教学数据。

`namespace` 是教学用的查询分区，没有实现账户认证。过期记录在读取时不可见；用 `expected_version=None` 重写过期键时版本继续递增，只有显式删除才从数据库移除。冲突预设先拒绝一次过时写入，再做一次合法更新。数据库路径不能由网页输入。

“按范围召回”预设在一次性临时库（live 模式也一样）里预置四条记录，演示两件事：

- 范围：`persistent` 跨任务召回；`current_task` 只召回 `task_id` 相同的记录，任务结束时由 `end_task` 清理。
- 召回内容只当数据：记忆放进 user 消息的 `<memory>` 数据块，尖括号转义，疑似指令打上 `instruction_like` 标记。包装好的消息只展示、不发送。模型会不会照着记忆里的指令做，要在提示注入课用真实模型检验；启发式标记不是安全边界。

旧版教学库在打开时会补上 `scope`、`task_id` 两列，已有记录按 `persistent` 处理。参考与取舍见 `docs/architecture/budget-memory-sources.md`。教学动画是示意，实际读取与删除以事件和报告为准。
