# 第 8 课：应用 state 与运行生命周期

本课只执行本地 Python，不要求模型连接。三组预设分别演示有证据完成、资料缺失、预算结束。状态机真实检查合法边、完成前证据和终态原因；`lesson.state` 是本次运行的实际快照。每次运行有独立 run_id，结束后仅事件回放保留证据；本课尚未提供跨运行持久化。

流程动效是教学示意，实际结论请以 `lesson.state` 与 `lesson.report` 为准。参考范围见 `docs/architecture/context-state-sources.md`。
