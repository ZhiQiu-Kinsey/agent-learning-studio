# 第 15 课：先规划后执行与重新规划

任务固定为“给学习者 lin 写一份学习周报”，需要查学习进度和每课练习得分。成绩有两个数据源：`primary` 在本课固定失败（课程写死的教学夹具），`backup` 正常。本课需要真实模型连接。

| 预设 | 做法 | 模型请求 |
| --- | --- | --- |
| 静态计划 | 规划器写一次 JSON 计划，执行器照做到底，失败也不改 | 规划 1 + 周报 1 |
| 失败后重新规划 | 某步失败时，把步骤状态和真实错误交回规划器，只替换未执行的步骤；最多修订 2 次 | 规划 1 + 修订次数 + 周报 1 |
| ReAct 基线 | 不写计划，模型每一步看结果再决定 | 每步 1 次 |

- 计划在执行前校验：步骤 id 唯一、工具在登记表里、参数是 JSON 对象；不合格就记 `lesson.plan_error` 并停止。
- 每次步骤状态变化或计划修订都发布 `lesson.plan`（版本、步骤、`reason`、`diff`），界面的计划透镜按回放位置显示。
- 三组用同一个 `verify`：进度和成绩都要来自成功的工具结果，周报要写出真实分数（关键词初筛）。

每组只跑一次，不足以比较策略的可靠性；真实模型第一次可能就选 `backup`，这时不会出现修订。`fixtures.py` 只服务自动化测试。

任务分解、结构化计划和“结果影响后续步骤时迭代规划”的讲法参考 [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners)（MIT）第 07 课，规划器提示词、计划格式、执行器与实验由本项目编写。

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_plan_and_replan.test_lesson -v
```
