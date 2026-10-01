# 新增课程与独立定制

普通课程只需要在自己的目录里补充实现、实验、教学内容和测试。导航、源码、模型连接、停止、事件流与回放由平台共用；有不同教学需求的课程可以单独写运行器或前端组件。

## 最短接入流程

`curriculum/catalog.json` 是课号、标题、简介、学习目标、层级、先修和状态的唯一来源。`lessons/lesson_*/lesson.json` 描述实现位置；后端自动发现清单，不再编辑 `server/catalog.py` 加分支。

以下使用仍处于规划中的第 11 课演示命令。课号和目录后缀应按实际课程替换。生成器只接受目录中已有的 `planned` 课，先验证参数、路径和重复清单，再创建文件；不会覆盖已有目录，也不会自动开放课程。

```powershell
# 先预览文件清单，不写文件
.\.venv\Scripts\python.exe scripts/new_lesson.py --id 11 --slug context_budget --dry-run
# 创建使用通用 Agent 循环的课程
.\.venv\Scripts\python.exe scripts/new_lesson.py --id 11 --slug context_budget
# 复杂流程可以改用 --kind custom（同一目录只能创建一次）
```

生成目录包含 `lesson.json`、`content.json`、`README.md`、`__init__.py` 和冒烟测试 `test_lesson.py`。原生课程另有 `main.py`、`tools.py`、`fixtures.py`；定制课程另有 `runtime.py`。示例只验证接入通路，正文与练习明确标记待编写。

1. 根据目录中的学习目标与验收要求实现本课。补齐引言、机制、示例、实验、观察点和自测，保留“概念 → 最小实现 → 运行证据 → 实验 → 自检”的顺序。
2. 运行课程自己的测试，例如 `python -m unittest lessons.lesson_11_context_budget.test_lesson -v`。补充真实 Python 行为、错误处理、输入与停止等测试；冒烟示例通过不代表课程完成。
3. 执行 `python scripts/validate_lessons.py`，检查所有实现清单，包括仍为 `planned` 的作者草稿。校验不调用模型；结构校验通过也不代表教学验收完成。
4. 课程验收通过后，才把 `curriculum/catalog.json` 中的状态改为 `available`，再执行 `python scripts/export_curriculum.py`、完整后端测试并重启服务。
5. 在网页检查导航、导读、源码、实际运行、停止和回放；若新增前端组件，还需构建前端并运行相应浏览器测试。

`planned` 即使有完整实现目录，也不会出现在可执行 API 中；`available` 必须有有效清单。校验错误在开发终端显示课程与本地路径，不能直接把异常堆栈展示给学生。

## 一个实现清单

```json
{
  "schema_version": 1,
  "id": "11",
  "content": "content.json",
  "sources": [
    { "path": "lessons/lesson_11_context_budget/main.py", "language": "python" },
    { "path": "lessons/lesson_11_context_budget/tools.py", "language": "python" },
    { "path": "course/runner.py", "language": "python" }
  ],
  "exercises": [
    { "id": "small-context", "title": "短上下文实验", "question": "本课实际问题" }
  ],
  "runtime": {
    "kind": "native",
    "entrypoint": "main",
    "max_rounds": 3,
    "requires_model": true
  },
  "testing": { "completion_factory": "fixtures:create_completion" }
}
```

`content` 相对于课程目录；`sources.path` 相对于项目根目录，必须落在允许公开的课程与平台源码范围内。不要加入本地密钥或配置。执行入口和测试 factory 只指向同一课内的可信 Python 模块，不从浏览器传入路径或导入地址。不同课程可以使用相同的练习 ID，测试 fixture 按课程隔离。

`main.py` 导出 `SYSTEM_PROMPT`、`TOOLS`、`AVAILABLE_TOOLS` 即可复用原生工具循环。每课可以引用已经存在的无副作用工具；源码清单应展示真实引用的实现。通用循环处理模型请求、工具调用与结果、错误和轮数上限。

确定性 fixture 是课程内的 `create_completion(exercise_id, inputs=None)` 工厂，返回 `completion(body, api_key)`。测试响应可以模拟模型决策，Python 工具必须实际执行；fixture 不作为学生网页的模型替代，也不解释自由输入。需要输入注入的测试练习可设 `offline_only: true`。

## 教学内容与动效复用

`content.json` 的基础结构是 `sections`、`observe`、`quiz`；每道自测有唯一 ID、题目、选项、正确选项与解释。通用导读直接使用这些内容。

可选 `presentation` 描述开场标题、重点命题、概念卡片和分步机制示意，结构参见已有课程的 `content.json`。它由现有 React Bits 组件呈现，不必为文字特效另建一套页面。示意是教学解释，必须与真实运行事件区分；不要把写死的流程图当成模型运行证据。

## 独立运行器

选择 `--kind custom` 后，清单使用 `runtime.kind: custom`、`entrypoint: runtime:run`。自定义课程可以实现分支、图执行、多个阶段或本地算法，再按需要复用通用循环。

```python
from pydantic import Field
from course.execution import LessonInputs, RunContext


class Inputs(LessonInputs):
    label: str = Field(default="样本", min_length=1, max_length=200)


INPUT_MODEL = Inputs


def run(context: RunContext):
    context.check_cancelled()
    context.emit("lesson.step", {"title": "准备样本", "label": context.inputs["label"]})
    return "本地处理完成：" + context.inputs["label"]
```

前端把课程 `input_defaults` 与练习 `inputs` 合并后显示在可编辑 JSON 中。请求未传 `inputs` 时后端使用这份合并预设；显式提交的 `inputs`（包括 `{}`）直接交给该课 `INPUT_MODEL` 校验，不偷偷补入界面里已经删除的参数。模型需要继承 `LessonInputs`，未知字段会被拒绝，省略字段可使用 Pydantic 字段默认值。`context.inputs` 是校验后的字典。没有声明输入模型的课程默认拒绝额外输入。`question`、`exercise_id`、`lesson_id`、`mode` 可从上下文读取；原生课程问题不能为空，定制课程可只使用结构化输入，并自行校验任务所需字段。

上面的纯本地课程应声明 `requires_model: false`，不要求配置密钥，也不伪造模型请求。需要模型的定制课程声明 `requires_model: true`，使用平台方法：

| 方法 | 用途 |
| --- | --- |
| `context.complete(body, round_number=1)` | 使用当前模型连接并记录请求、响应与表示方式 |
| `context.call_tool(name, arguments, available_tools, round_number=1)` | 执行登记的真实工具并记录调用与结果 |
| `context.run_native(module, max_rounds=3)` | 复用原生子流程；其回答记为 `lesson.stage_result`，返回字符串由外层组织最终回答 |
| `context.emit("lesson.step", data)` | 记录课程特有的 JSON 证据；自定义事件使用 `lesson.` 前缀 |
| `context.check_cancelled()` | 在阶段与副作用操作前响应平台停止请求 |

运行器可以是同步或异步函数。返回字符串时平台自动记录最终回答；也可以自行发布 `answer` 后返回 `None`。开始、结束和执行锁由平台管理，课程不能自行伪造生命周期事件。共享服务统一保留模型连接、事件快照、脱敏与回放；不要从课程另建 SSE、绕过连接管理直读密钥，或从回放触发执行。

停止是协作式的：长循环需要插入检查，已发出的网络请求仍受传输超时约束。本地进程中的可信课程代码不是沙箱。接入数据库、持久记忆、检索或框架时，仍需为该能力实现清楚的状态生命周期、适配与测试。第 10 课已提供教学用 SQLite 持久记忆实现，可参考其跨运行读取、版本冲突和过期处理；共享扩展接口本身不提供通用记忆服务。

## 独立页面与可视化

确有不同交互时，可以在 `frontend/src/lesson-extensions/` 为本课写组件，并在 `registry.ts` 使用构建时可信导入登记：

```json
{
  "ui": {
    "lab": "structured-inputs",
    "inspector": "tool-outcomes"
  },
  "input_defaults": { "label": "样本" }
}
```

三个插槽分别是 `guide`、`lab`、`inspector`。`structured-inputs` 是共用结构化输入面板；`tool-outcomes` 展示工具结果；`evidence-board` 展示实际事件中的检查、指标、对照表。没有设置插槽的课程继续用通用页面。固定任务实验可以配置 `ui.question_label` 和 `ui.question_help`，明确问题框是学习者备注，避免学生误以为修改了受控实验条件。

`evidence-board` 消费当前回放位置的 `lesson.report` 事件：`title`、`summary` 为文本，`checks` 为 `{label, passed, detail}` 数组，`metrics` 为 `{label, value}` 数组，可选 `table` 为 `{columns: string[], rows: (string|number|boolean)[][]}`。同一运行可发布初稿、修复、最终等多份报告，界面允许选取并查看原始事件。只有真正执行过的检查才能标记通过，未执行项目应省略或不提供 `passed`。

组件通过 `studio` 使用共享状态，通过 `children` 组合默认页面，并尊重 `active` 暂停离屏动效。专用观察图应使用当前回放位置的事件，不能总展示完整历史的最终状态。未知键、加载或渲染失败会退回默认视图；JSON 不能动态加载任意 URL、脚本或 HTML。新增组件后仍需构建前端，纯内容或 Python 课程更新通常只需重启后端。

## 工具限制

`--root` 用于指向另一份项目或测试根目录，目录必须含 `curriculum/catalog.json`。生成器拒绝无效 slug、未知或已可用课号、重复课程清单和已存在的目标；通过链接跳出项目的目录同样拒绝。写入中断时可能留下新建的部分目录，工具会报告错误并保留文件供检查，不删除或覆盖已有工作。
