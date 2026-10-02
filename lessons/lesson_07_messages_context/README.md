# 上下文组成与消息协议（`messages-context`）

本课把一次请求的上下文拆成四部分：系统提示词、之前的对话、工具调用与工具结果、本轮问题。一次运行准备五组上下文，每组只比完整上下文少一部分，问同一个问题：

| 组 | 拿掉的部分 | 是否发送 |
| --- | --- | --- |
| 完整上下文 | 无 | 发送 |
| 去掉系统提示词 | system 消息 | 发送 |
| 去掉之前的对话 | 那条 user 消息 | 发送 |
| 去掉工具调用和结果 | 带 tool_calls 的 assistant 消息与对应的 tool 消息 | 发送 |
| 只去掉工具结果 | tool 消息（留下调用） | 被 `validate_tool_history` 在发送前拦下 |

本课使用当前配置的真实模型，每次运行发出 4 次请求（被拦下的那组不发送），运行前请注意模型开销。工具 `lookup_score` 由运行器真实执行一次；带 tool_calls 的 assistant 消息由运行器写入，不是模型提出的，事件里这次调用的 `origin` 是 `course_program`。报告里“提到分数”“提到复习日”“写了依据行”三列是关键词初筛，要对照回答原文复核。

`validate_tool_history(messages)` 的名字、签名和行为保持不变，“上下文预算与截取窗口”一课会导入它。

`runtime.py` 实现消息组装、协议检查和报告；`fixtures.py` 仅供离线测试，按本次消息内容拼出确定性回答。课程不提供学生环境的模拟回退。

参考范围见 `docs/architecture/context-state-sources.md`。页面上的流程讲解是教学示意，实际证据请看 request、response、lesson.context 与 lesson.report。
