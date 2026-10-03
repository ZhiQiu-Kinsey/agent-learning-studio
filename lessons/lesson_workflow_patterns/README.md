# 工作流模式：链式、路由与并行（`workflow-patterns`）

三种由程序决定流程、由模型完成每一步的工作流。本课需要真实模型连接，不使用工具。

| 预设 | 模型请求 | 证据 |
| --- | --- | --- |
| 提示链：三步加检查门 | 最多 3 次 | `lesson.chain_step`：每步输出与检查门结果；不通过就停 |
| 路由：20 张标注工单 | 20 次 | `lesson.route`：标注、预测、原文、是否兜底，兜底时另有 `fallback_reason`；报告给出准确率、混淆矩阵和分错的工单 |
| 三个子任务，串行 | 3 次 | `lesson.parallel`：墙钟时间、各分支开始与结束时间 |
| 三个子任务，并行 | 3 次，同时发出 | 同上；请求和响应带 `branch`，时间线按它配对 |

- 路由只接受 `course`、`account`、`error`、`other` 四个标签，其他输出一律走兜底 `other` 并记下原文。
- 工单标注由课程作者完成，有几张故意模棱两可；20 张不足以代表真实流量。
- 时间由后端 `perf_counter` 测量，受网络和服务商排队影响，一次测量只说明这一次。

`fixtures.py` 只服务自动化测试：路由脚本故意分错两张、对一张输出列表外的标签；复述任务固定停顿 50 毫秒。

三种模式的划分参考 [claude-cookbooks](https://github.com/anthropics/claude-cookbooks)（MIT）`patterns/agents/basic_workflows.ipynb`；那份示例遇到未知标签会出错，本课改为兜底并记录。工单、检查门、计时与实验由本项目编写。

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_workflow_patterns.test_lesson -v
```
