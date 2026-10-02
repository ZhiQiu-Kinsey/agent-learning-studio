# 应用状态与运行生命周期（`application-state`）

本课不调用模型，只执行本地 Python，不要求模型连接。三组预设分别演示有证据完成、资料缺失、预算结束。状态机真实检查合法转换、完成前的证据与产物和终态原因；`lesson.state` 是本次运行的实际状态快照。每次运行有独立 run_id，结束后仅事件回放保留证据；本课不提供跨运行持久化。

资料来源键与课程 slug 一致：`messages-context`、`application-state`，另有不存在的 `missing`。报告拼装放在 `_report` 中，读码页只展示状态机与运行流程。

流程讲解是教学示意，实际结论请以 `lesson.state` 与 `lesson.report` 为准。参考范围见 `docs/architecture/context-state-sources.md`。
