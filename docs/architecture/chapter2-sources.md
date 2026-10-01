# 第二章来源与取舍

当前课程参考范围于 2026-10-01 调整为三份正式教程。

本记录只覆盖实际打开的本地固定快照文件，不表示读完三份课程资料。课程正文、任务卡与测试数据为本项目原创；参考仓库不是运行依赖。

| 来源与固定 commit | 本次直接阅读 | 对三课的启发与边界 |
| --- | --- | --- |
| `ai-agent-book` `b789c97a8f3de5b405a6f6dfa8289208d679d0b8` | `README.md`、`book/chapter1.md`（Agent/环境、上下文与工具边界）、`book/chapter4.md`（工具职责与参数）、`book/chapter5.md` 开头 Coding 任务示例、`book/chapter7.md` 开头评估与单变量实验 | 将运行终态、执行证据与验收拆开；用固定任务和独立校验器。没有复现其配套实验。 |
| `ai-agents-for-beginners` `25b7985f3b2dc37a84f4a7387ccd3c9f0e5b1595` | `README.md`、`STUDY_GUIDE.md`（连续课程助教案例、能力地图、工具与信任小节） | 第二章沿用“给同一助教逐步增加能力”，每课仍可独立运行；没有引入 Azure 依赖。 |
| `agents-course` `b3946b1d09d29c65736e219d48a8a736a2c52154` | `README.md`、`units/en/unit0/introduction.mdx`、`units/en/unit1/tools.mdx`、`units/en/unit1/agent-steps-and-structure.mdx` | 工具描述影响模型的行动提议，执行仍由程序负责。第 6 课向模型发送真实 tools Schema、观察返回的 tool_calls，不执行该提议。 |

第 4 课使用纯本地故障注入，明确标记为教学场景；第 5、6 课学生运行使用当前真实模型连接。自动化测试的 fixture 仅在测试模式产生确定性响应。第 6 课的工具描述预设观察真实 tool_calls 提议但不执行；每次只比较一对调用，不能从一个样本得出普遍效果结论。
