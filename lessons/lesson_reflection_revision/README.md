# 反思、评审与有上限的修订（`reflection-revision`）

任务固定为“写一条正则匹配学号”：小写 s、连字符、四位数字，第一位不能是 0。测试是 `runtime.py` 里的 9 个固定用例，用 `re.fullmatch` 真实执行；程序只把模型写的字符串当正则编译，不运行模型写的代码。本课需要真实模型连接。

| 预设 | 评审来源 | 上限 |
| --- | --- | --- |
| 模型自评驱动修订 | 模型读需求和正则，输出 pass / revise | 3 |
| 测试结果驱动修订 | 失败用例就是评审意见 | 3 |
| 测试驱动，只允许 1 轮 | 同上 | 1 |

- 每一版正则记为 `lesson.draft`（含上一版），每次评审记为 `lesson.review`（`source` 为 `model` 或 `tests`），测试记为 `lesson.tests`。
- 四种停止原因：评审通过、达到迭代上限、修订后没有变化、评审输出不合格式。
- 循环结束后，最终版本一律用同一组用例检查；累计 `total_tokens` 只累加服务商报告的值，缺失的次数单独写明。

每组只跑一次，不能据此判断自评是否普遍可靠。`fixtures.py` 只服务自动化测试，其中的草稿、自评和用量都是脚本写的。

“自我评估与纠正”的讲法参考 [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners)（MIT）的 09-metacognition 一章，任务、测试、评审格式与停止条件由本项目编写。

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_reflection_revision.test_lesson -v
```
