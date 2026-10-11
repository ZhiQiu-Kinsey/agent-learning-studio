# 应用状态与运行生命周期（`application-state`）

[English](README.md) · 简体中文

本课不调用模型，只执行本地 Python，不要求模型连接。三组预设分别演示有证据完成、资料缺失、预算结束。状态机真实检查合法转换、完成前的证据与产物和终态原因；`lesson.state` 是本次运行的实际状态快照。每次运行有独立 run_id，结束后仅事件回放保留证据；本课不提供跨运行持久化。

资料来源键与课程 slug 一致：`messages-context`、`application-state`，另有不存在的 `missing`。报告拼装放在 `_report` 中，读码页只展示状态机与运行流程。

**运行语言：**本课有中文和英文两种运行语言。资料原文、步骤名、快照动作、终态原因、状态机的报错和报告文字写在 `locales/zh_CN.py` 与 `locales/en.py`；任务目标 `goal` 没有代码里的默认值，预设按语言写在 `lesson.json`。状态名（`ready`、`running` 等）和资料键是代码，两种语言一样。

流程讲解是教学示意，实际结论请以 `lesson.state` 与 `lesson.report` 为准。参考范围见 `docs/architecture/context-state-sources.md`。

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_08_application_state.test_lesson tests.test_lessons_context_state -v
```
