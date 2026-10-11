# 多轮对话：程序重发历史（`multi-turn-history`）

[English](README.md) · 简体中文

**目标：**连续提问几轮，比较带上与不带上一轮消息的请求，看清模型不会自己记住上一轮：多轮对话靠程序把消息历史重新发出去。

本课是独立运行器（`runtime.py`）。`run` 用一个 Python 列表 `history` 保存消息历史：

1. 每轮先把这一轮的 user 问题追加进 `history`。
2. 按 `history` 输入决定这次发什么：`full` 发整段历史，`latest_only` 只发 system 和这一轮的问题。
3. 调用 `context.complete` 发请求，再把回答作为 assistant 消息追加进 `history`。

练习：

| 练习 | 设置 | 看什么 |
| --- | --- | --- |
| `with-history` 带历史追问 | `full`，2 轮 | 第二轮请求的四条消息、回答里有没有猫的名字 |
| `without-history` 不带历史追问 | `latest_only`，2 轮 | 第二轮请求只有两条消息；第一轮与上一组完全相同 |
| `three-turns` 三轮对话 | `full`，3 轮 | 每轮的 `prompt_tokens` 怎样增长 |

实验报告列出每轮发出的消息数、提示 Token 和完成 Token；服务商没有报告的用量写“未报告”。

**运行语言：**本课有中文和英文两种运行。系统提示词、三轮问题和实验报告的文字在 `locales/zh_CN.py`、`locales/en.py`；练习说明按语言写在 `lesson.json`。网页按界面语言选择运行语言，每条运行记录都写明它用的语言。

在网页课程导航中进入本课，可以查看源码、真实运行事件和回放。离线测试：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_multi_turn_history.test_lesson -v
```

`fixtures.py` 只服务自动化测试，回答和用量都是假数据。
