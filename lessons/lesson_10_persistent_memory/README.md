# 第 10 课：持久记忆与会话恢复

本课只调用本地 Python 与 SQLite，不调用模型。live 运行固定写入 `.runtime/lesson10-memory.sqlite3`，同一 namespace/key 会保留到下次；offline 运行在临时目录建库并于结束后清理。先执行“保存与重开连接”，再执行“只读恢复上次记忆”，可检查跨次运行保留的值、来源与版本。只读预设不写入；其 offline 模式会在临时库预先写入一条受控样本。其余预设会修改选中的键，请使用教学数据。

`namespace` 是教学查询分区，未实现账户认证。过期记录在读取时不可见；以 `expected_version=None` 重写过期键会保留版本递增，显式删除才从数据库移除。冲突预设会拒绝一次陈旧写入，随后合法更新。源码只接受经过校验的 namespace/key，数据库路径不能由网页输入。

参考与取舍见 `docs/architecture/budget-memory-sources.md`。教学动画是示意，实际读取与删除以事件和报告为准。
