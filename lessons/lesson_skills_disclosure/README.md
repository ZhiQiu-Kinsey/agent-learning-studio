# Skills 与渐进式披露（`skills-disclosure`）

同一个任务，用两种方式把技能（Skill）提供给模型，比较常驻上下文的规模、触发情况和每次请求的提示 Token。本课需要真实模型连接。

| 方式 | 系统提示词 | 工具 | 需要技能时的请求数 |
| --- | --- | --- | --- |
| 全量注入 | 四个技能的描述和正文（约 2000 字符） | 无 | 1 |
| 目录 + 按需加载 | 每个技能一行 name 和 description（约 480 字符） | `load_skill(name)` | 2（提出加载，拿到正文后回答） |

技能文件在 `skills/<name>/SKILL.md`：开头两行 `---` 之间写 `name` 和 `description`，后面是正文。四个技能（`review-cards`、`error-question`、`unit-test-checklist`、`three-sentence-summary`）是本课自己写的教学材料。`load_skill` 只读登记在 `SKILL_NAMES` 里的技能，模型写的名字只拿来查表，不拼进任意路径；名字不在目录里时返回结构化错误。

| 预设 | 方式 | 任务 | review-cards 的描述 |
| --- | --- | --- | --- |
| 整理复习卡：两种方式对照 | 两种都跑 | 整理复习卡（应加载 review-cards） | 精确 |
| 闲聊：两种方式对照 | 两种都跑 | 闲聊（不该加载） | 精确 |
| 整理复习卡：精确 / 模糊描述 | 按需加载 | 整理复习卡 | 精确 / “帮助学习。” |
| 复习提问：精确 / 模糊描述 | 按需加载 | 复习提问（不该加载，容易误触发） | 精确 / “帮助学习。” |

每次请求后发布 `lesson.skill_request`：服务商在 usage 里报告的 `prompt_tokens`（没有报告时为 null，报告里写“未报告”）、这次实际发出的消息里有哪些技能正文、响应提出加载哪些技能。最后的 `lesson.report` 把两种方式并排：每次提示 Token、合计、加载记录、加载判定（正确 / 漏触发 / 误触发 / 加载错技能）和格式初筛。格式初筛只数回答里以“问：”“答：”开头的行，不判断内容对错。

模型会不会加载、加载哪个技能，取决于所用模型和这一次采样，以本次记录为准；“该不该加载”是本课对三个任务的认定。两种都跑时一次运行最多 4 次模型调用，只跑按需加载最多 3 次。`fixtures.py` 只服务自动化测试，其中的漏触发和误触发由脚本写定，响应不带 usage，不代表任何真实模型。

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_skills_disclosure.test_lesson -v
```
