# 采样与不确定性（`sampling-variance`）

[English](README.md) · 简体中文

**目标：**同一个请求原样连发 5 次，比较 `temperature` 为 0 与 1.3 时回答的差异，理解模型输出来自采样，以及为什么一次运行不能证明结论、对照实验要重复运行。

本课是独立运行器（`runtime.py`）：

1. 请求体只拼一次：system 规则、user 问题和 `temperature`。
2. 同一个请求体原样调用 `context.complete` 若干次（默认 5 次，`lesson.json` 的 `max_rounds` 为 5）。
3. `count_distinct` 去掉首尾空白后逐字比较，统计不同回答数；实验报告列出每次回答和用量合计。

| 练习 | 设置 |
| --- | --- |
| `low-temp` | `temperature` 为 0，连发 5 次 |
| `high-temp` | `temperature` 为 1.3，连发 5 次 |

每个练习会调用 5 次模型。服务商没有报告某次用量时，合计写“未报告”。

**运行语言：**本课可以用中文或英文运行。系统提示词、报告标签等运行时文本在 `locales/zh_CN.py` 与 `locales/en.py`，练习问题按语言写在 `lesson.json` 里。网页按界面语言选择运行语言，每条运行记录都写明它用的语言。

在网页课程导航中进入本课，可以查看源码、真实运行事件和回放。离线测试：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_sampling_variance.test_lesson -v
```

`fixtures.py` 只服务自动化测试，回答是轮换的固定店名，不代表真实模型的波动。
