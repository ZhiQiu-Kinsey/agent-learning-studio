# 规划：TODO 清单与状态提示（`todo-planning`）

任务固定为“查 messages-context、application-state、context-budget 三课的要点，连同要点编号存进复习卡”。三课在工具参数里用课程 slug 指代，不用课号：显示课号会随课程表变化。本课需要真实模型连接，三组条件用同一个模型、同一个任务和同一个验收器：

| 预设 | 工具 | 运行层提醒 |
| --- | --- | --- |
| 无 TODO | `lookup_note`、`save_card` | 无 |
| 有 TODO，无提醒 | 再加 `todo_write` | 无 |
| 有 TODO，有提醒 | 再加 `todo_write` | 连续 `reminder_after` 轮没调用 `todo_write`，就在本轮 tool 消息之后追加一条 user 提醒 |

- `todo_write` 整体替换清单，校验通过后版本号加一，并发布 `lesson.todo`（完整清单与差异）。
- 运行层提醒同时发布 `lesson.harness_injected`，`source` 为 `harness`，用来和模型、用户的话区分开。
- `verify_card` 只看复习卡和本次 `lookup_note` 的真实返回；模型最后的说法和清单上的 done 都写进报告，但不参与判定。

每组只跑一次，不足以比较完成率。`fixtures.py` 只服务自动化测试，里面“无 TODO 组漏掉 context-budget 一课”是脚本写的，不代表任何真实模型。

`todo_write` 的约束和“连续几轮没更新就提醒”的做法参考 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code)（MIT）s05，工具、提醒文本、验收器与实验由本项目编写。

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_todo_planning.test_lesson -v
```
