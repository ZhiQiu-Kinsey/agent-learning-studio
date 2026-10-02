# 持久记忆：保存、重开与召回（`persistent-memory`）

本课把一条明确给出的记忆写进 SQLite，关闭连接后用新连接读回，再把召回的记忆作为数据放进一次模型请求。

| 练习 | 调用模型 | 做什么 |
| --- | --- | --- |
| 保存与重开连接 | 否 | 写入 namespace / key / value / source，关闭连接，新开连接读回；核对另一个命名空间没有被改变 |
| 只读恢复上次记忆 | 否 | 用 `mode=ro` 只读连接读取，报告用 `total_changes` 核对没有写入 |
| 召回后让模型回答 | 是，1 次 | 只读召回 `learner_demo` 的记录，写成 JSON 放进 user 消息的 `<memory>` 数据块，system 只写规则；回答句末用 `[key]` 标出依据 |
| 换一个没有记忆的命名空间再问 | 是，1 次 | 从 `new_learner` 召回，数据块为空，对照回答有没有依据 |

存储类在 `store.py`，“记忆的更新、过期与召回范围”一课也用它（版本检查、过期、范围与删除在那一课讲）。

- 真实运行读写 `.runtime/persistent-memory.sqlite3`，下次运行仍能读到；先跑“保存与重开连接”，再跑“只读恢复上次记忆”或“召回后让模型回答”。写入类练习会修改你选的 namespace 和 key，请使用教学数据。
- 离线测试模式在临时目录建库，结束后删除；只读的练习会先放一条来源为“离线测试预置的样本”的受控记录。
- `namespace` 是查询分区，没有实现身份认证；知道它的调用方都能读。数据库路径不能由网页输入。
- `fixtures.py` 只服务自动化测试，读请求里的数据块给出确定性回答，不代表任何真实模型。模型会不会按规则引用 key，以真实运行的 response 为准。

参考与取舍见 `docs/architecture/budget-memory-sources.md`。教学示意不是运行记录，实际读写以事件和报告为准。

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_lessons_budget_memory -v
```
