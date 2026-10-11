# 提示词与工具描述（`prompt-experiments`）

[English](README.md) · 简体中文

## 运行

在网页打开本课，选预设后运行，右侧实验报告显示检查结果，展开事件可以看原始请求和响应；回放只读已有记录。本课需要真实模型连接。所有预设固定用户任务、模型和 temperature=0。

| 预设 | 改动的变量 | 模型调用数 | 是否执行工具 |
| --- | --- | --- | --- |
| 工具描述：模糊与明确 | function.description | 2 | 否，只初筛提议 |
| 流程规则：答案与核对 | system 规则 | 2 | 无工具 |
| 失败边界：缺少加数 | system 规则 | 2 | 无工具 |
| 工具描述矩阵 | description：空白 / 良好 / 误导，各配求和题与拼接题 | 6 | 是，执行名称与参数合法的 add_numbers 提议 |

问题框里写的是学习者备注，会写进报告，不改变固定任务。

**运行语言：**本课可以用中文或英文运行。配对任务、工具描述、矩阵题目、初筛规则和报告文字在 `locales/zh_CN.py` 与 `locales/en.py`，练习问题和样本标签按语言写在 `lesson.json` 里。网页按界面语言选择运行语言，每条运行记录都写明它用的语言。

## 读源码

消息目录的 `pair_tasks` 固定配对条件，`descriptions` 和 `probes` 定义矩阵；`runtime.py` 的 `MATRIX_GROUPS` 与 `PROBE_EXPECTED` 写明矩阵的行列和每道题期望的调用。配对实验用结构或关键词初筛，命中仍要人工读原始响应。矩阵实验用 `context.execute_proposal` 把模型提出的调用交给真实的 `add_numbers` 执行，事件里记的就是模型给的那条调用；报告并列写出模型的提议和代码的返回值，误导描述和实现故意不一致。

离线测试：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_06_prompt_experiments.test_lesson -v
```

## 限制与参考

每格、每对都只跑一次，不足以证明某种写法普遍更好，需要更多样本和重复运行。离线测试用的 `fixtures.py` 只服务自动化测试，不代表任何真实模型的行为。来源范围与固定 commit 见 [来源记录](../../docs/architecture/chapter2-sources.md)。
