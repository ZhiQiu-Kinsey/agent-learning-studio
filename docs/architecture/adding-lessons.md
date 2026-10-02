# 新增课程与独立定制

普通课程只需要在自己的目录里补充实现、实验、教学内容和测试。导航、源码、模型连接、停止、事件流与回放由平台共用；有不同教学需求的课程可以单独写运行器或前端组件。

## 最短接入流程

`curriculum/catalog.json` 是课程 ID、别名、标题、简介、学习目标、层级、先修和状态的唯一来源；显示课号由它的目录顺序计算（见下一节）。`lessons/lesson_*/lesson.json` 描述实现位置；后端自动发现清单，不再编辑 `server/catalog.py` 加分支。

以下使用仍处于规划中的 `document-loading` 演示命令，按实际课程替换。`--id` 接受课程 slug（或改名前的旧 slug 别名）；`--slug` 可以省略，提供时必须与目录中的 slug 一致（可写成 `document_loading`），只为兼容旧命令保留。生成器只接受目录中已有的 `planned` 课，先验证参数、路径和重复清单，再创建文件；不会覆盖已有目录，也不会自动开放课程。

```powershell
# 先预览文件清单，不写文件
.\.venv\Scripts\python.exe scripts/new_lesson.py --id document-loading --dry-run
# 创建使用通用 Agent 循环的课程
.\.venv\Scripts\python.exe scripts/new_lesson.py --id document-loading
# 复杂流程可以改用 --kind custom（同一目录只能创建一次）
```

生成目录为 `lessons/lesson_document_loading/`，包含 `lesson.json`、`content.json`、`README.md`、`__init__.py` 和冒烟测试 `test_lesson.py`。原生课程另有 `main.py`、`tools.py`、`fixtures.py`；定制课程另有 `runtime.py`。示例只验证接入通路，正文与练习明确标记待编写。

1. 根据目录中的学习目标与验收要求实现本课。补齐引言、机制、示例、实验、观察点和自测，保留“概念 → 最小实现 → 运行证据 → 实验 → 自检”的顺序。
2. 运行课程自己的测试，例如 `python -m unittest lessons.lesson_document_loading.test_lesson -v`。补充真实 Python 行为、错误处理、输入与停止等测试；冒烟示例通过不代表课程完成。各课目录下的 `test_lesson.py` 由 `tests/test_lesson_local_suites.py` 并入完整测试，不需要另外登记。
3. 执行 `python scripts/validate_lessons.py`，检查所有实现清单，包括仍为 `planned` 的作者草稿。校验不调用模型；结构校验通过也不代表教学验收完成。
4. 课程验收通过后，才把 `curriculum/catalog.json` 中的状态改为 `available`，再执行 `python scripts/export_curriculum.py`、完整后端测试并重启服务。
5. 在网页检查导航、导读、源码、实际运行、停止和回放；若新增前端组件，还需构建前端并运行相应浏览器测试。

`planned` 即使有完整实现目录，也不会出现在可执行 API 中；`available` 必须有有效清单。校验错误在开发终端显示课程与本地路径，不能直接把异常堆栈展示给学生。

## 课程 ID、别名与显示课号

| 概念 | 规则 |
| --- | --- |
| 课程 ID（主 ID） | `catalog.json` 中每课的 `id`，稳定的 kebab-case slug，如 `tool-selection`；正则 `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`，不超过 48 字符。接口、事件、链接、前端状态都只用它 |
| 别名 | 每课的 `aliases`：改名前的旧 slug，只用于解析旧请求，接口从不以别名作为返回的 `id`。不接受数字别名：显示课号随目录顺序变化，数字别名会和它混淆（2026-10-03 起删除了全部旧数字别名） |
| 显示课号 | `number`，按 `lessons` 数组顺序从 1 计算，不写进 JSON。插入新课只会改变其后课程的显示课号，不改变任何 ID |
| 目录内引用 | 模块 `lesson_ids`、`prerequisites`、选修 `prerequisites` 一律写 slug；误写别名时校验会提示应改成哪个 slug |

校验（`server/curriculum.py` 的 `index_catalog`，由课程加载、`validate_lessons.py`、`export_curriculum.py` 和 `new_lesson.py` 共用）：

- slug 格式合法且唯一；别名必须是 kebab-case slug（不能是数字），不与任何 slug 或其他别名冲突，也不等于本课 slug。
- 先修引用的课程必须存在，并且排在本课之前（同时排除循环）；选修的先修也必须存在。
- 大类 → 模块 → 课程的遍历顺序必须与 `lessons` 顺序一致，每课只登记在一个模块中，使导航与显示课号不会错位。

**实现目录映射规则：** `lessons/*/lesson.json` 的 `id` 必须等于 catalog 中的课程 slug（不能写别名），这是课程与实现之间唯一的映射；目录名只决定 Python 包名，不参与身份判断。已有第 1–10 课沿用 `lesson_NN_<slug 的下划线形式>`（如 `lesson_01_tool_selection` ↔ `tool-selection`），目录暂不改名；新课由生成器创建为 `lesson_<slug 的下划线形式>`（如 `lesson_document_loading`），不再带课号前缀。

**接口行为：**

- `GET /api/lessons`、`GET /api/lessons/{id}`、`GET /api/curriculum` 中每课都返回 slug `id`、`number` 与 `aliases`。
- `GET /api/lessons/{id}` 与 `POST /api/run` 的 `lesson_id` 接受 slug 或别名，内部统一解析为 slug；`run_start` 事件与 `RunContext.lesson_id` 记录的始终是 slug。
- 无法解析的 ID 返回 404，响应体为 `{"detail": "...", "code": "lesson_not_found"}`；目录中已登记但仍为 `planned` 的课程返回 404 与 `lesson_not_available`。错误信息不回显请求中的原始 ID。
- 前端以 slug 作为 `lessonId`，课号显示使用接口返回的 `number`。来自旧链接、旧导出或本机存储的课程 ID 先经过 `frontend/src/lib/lessonIds.ts` 的 `resolveLessonId` 迁移为 slug（当前 localStorage 中没有保存课程 ID 的键，后续学习进度等新键必须走这一步）。

## 术语表

`curriculum/glossary.json` 是术语的单一来源，`GET /api/glossary` 只读返回，`scripts/validate_lessons.py` 负责校验。每条术语：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | kebab-case，全表唯一；将来内容块用 `term_id` 引用 |
| `zh` | 是 | 中文写法；已直接使用英文的词（Agent、Token、JSON Schema）与 `en` 相同。名字要具体，不用常见单字词或动词 |
| `en` | 是 | 英文原词 |
| `kind` | 否 | `concept`（课程概念，默认）或 `background`（背景词，如分词器、消融，不设 `first_lesson`） |
| `definition` | 是 | 简短中文释义，不超过 160 字符 |
| `aliases` | 否 | 正文中的其他写法，如 `RAG`、`验收器`；中文名与别名在全表唯一 |
| `not_in` | 否 | 含有术语名、但意思不同的更长词组，如“评估”的 `评估者`；正文里这些词组整体不标注 |
| `first_lesson` | 否 | 最早用到该概念的可运行课 slug，不能写别名；课程尚未登记（如提示缓存、沙箱）时省略 |

悬浮卡的标题显示为“中文（English）”，`zh` 与 `en` 相同时只显示一次；接口返回的每条术语附带计算出的 `display` 与 `first_lesson_number`。测试会检查 `first_lesson` 指向的课程目录条目或教学内容中确实出现该术语，避免登记课程中并不存在的知识点。收录标准、四类词（课程概念、背景词、代码名、普通词）的写法与统一用词表见 [术语与代码名](terminology.md)。

**多语言预留（本阶段未实现合并）：** 术语映射字段 `id`、`zh`、`en`、`first_lesson` 只在源文件中维护，译文层不得改动；可译文本字段是 `definition` 与 `aliases`（`server/glossary.py` 的 `TRANSLATABLE_FIELDS`）。将来的 `curriculum/glossary.{locale}.json` 以术语 `id` 为键，只提供这些字段及该语言的显示名 `term`，按 id 覆盖源文件；缺失的条目回退到 zh-CN 源文本。英文界面只显示 `en`，不附中文。

## 一个实现清单

```json
{
  "schema_version": 1,
  "id": "document-loading",
  "content": "content.json",
  "sources": [
    { "path": "lessons/lesson_document_loading/main.py", "language": "python" },
    { "path": "lessons/lesson_document_loading/tools.py", "language": "python" },
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

## 教学内容（content v2）

`content.json` 声明“怎么教”，结构由 `server/content_schema.py` 中的 Pydantic 模型唯一定义。文件开头的 `$schema` 指向 `curriculum/schema/content.v2.schema.json`，编辑器可以据此补全。基本骨架：

```text
{ "$schema": "...", "schema_version": 2, "lesson": "<slug>", "source_language": "zh-CN",
  "capabilities": ["tools", ...],
  "scenes": {
    "understand": { "blocks": [hero, concepts, prose, micro-quiz, walkthrough, flow, predict, ...] },
    "code":       { "blocks": [whats-new, annotated-source, decision] },
    "lab":        { "experiments": [...], "inputs": [...] },
    "check":      { "blocks": [quiz, trace-hunt, checkpoint] } },
  "illustrations": { "<id>": { "events": [...] } } }
```

- **块与 id**：每个块和条目都有稳定 id，块 id 在整份文档内唯一。块类型与场景无关，场景顺序固定。表现形式只写语义意图（如 `"reveal": "split"`），由前端动效层映射到具体组件。
- **实验**：`experiments` 中每个实验由以下部分组成：
  - `hypothesis`：可检验的假设；
  - `arms`：对照组，用 `exercise` 引用 lesson.json 的练习；
  - `observe`：观察点，带选择器（`event`、`round`、`path`、`span_kind`、`name`）；
  - `guide`：导览动作 `narrate`、`spotlight`、`highlight`、`seek`；
  - `conclusion`：`proves` 写能证明的，`does_not_prove` 写不能证明的。

  选择器的语义由 `server/selectors.py` 和 `frontend/src/content/selector.ts` 共同实现，两边跑同一份共享测试向量。`tests/test_lesson_experiments.py` 会用确定性运行逐个检查观察点和导览目标都能命中；在这次运行中找不到的证据，界面会如实显示“本次运行没有出现这条证据”。
- **预测**：`predict` 只能用能从真实事件计算出的规则（`count_events`），只和学习者自己的运行对照，示意和录制都不算。
- **示意**：`flow` 块引用 `illustrations` 中的合成事件序列。这些事件必须通过 `server/illustrations.py` 的契约：
  - 调用与结果成对；
  - 调用 id 使用示例 id（含 `example`）；
  - 不出现耗时、用量、费用等执行测量值。

  `walkthrough` 是作者写的分步讲解，界面一律标注“教学示意 · 非运行记录”。
- **参数标签**：自定义运行器的 `INPUT_MODEL` 会导出 JSON Schema，前端据此生成参数控件。控件的标签、帮助和选项文字写在 `lab.inputs`，测试保证它与模型字段一一对应。枚举请用 `Literal`，不要用正则 `pattern`。
- **读码块**：`annotated-source` 的路径必须在本课 sources 中，行号必须真实存在。“本课新增”由后端从源码 AST 计算，不要手写。
- **术语与代码名**：课程概念只在引入课（`first_lesson`）第一次出现时写“中文（English）”，其他课只写中文；背景词不写英文并列。正文写到的源码名字自动显示为代码样式，需要解释的在 `content.json` 顶层 `code_notes` 写说明。完整规则与统一用词表见 [术语与代码名](terminology.md)；写完运行 `scripts/term_report.py --lesson <slug> --full`，`validate_lessons` 会拒绝有用词问题的可运行课程。

**版本与迁移**：旧版本内容会在加载时走 `server/content_migrations.py` 的迁移阶梯。写回磁盘并规范格式用 `scripts/migrate_content.py`，加 `--check` 只检查。修改 schema 后，运行 `scripts/export_content_schema.py`，再在 frontend 目录运行 `npm run content:types`；测试会检查三者同步。

**译文层**：在源文件旁放 `content.<语言>.json`，按 id 路径覆盖文本，例如 `hero.headline`、`concepts.<条目>.title`、`inputs.<字段>.label`。事实字段（id、正确答案、代码、选择器、URL 等）不能被覆盖。每条译文记录源文本摘要，源文本改动后这条译文视为过期，回落到源文本。`scripts/validate_lessons.py` 会报告每个译文层的覆盖率。

**随课录制**：真实模型运行后，用 `scripts/export_recording.py --run <run_id> --name <名称>` 原样导出到 `lessons/<目录>/recordings/`。录制只能来自 live 运行，带源码哈希和完整性哈希；源码变化后会提示重新录制。

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
| `context.complete(body, round_number=1, branch=None)` | 使用当前模型连接并记录请求、响应与表示方式；并行发出多个请求时给每个分支一个不同的 `branch`，时间线按它配对请求与响应 |
| `context.call_tool(name, arguments, available_tools, round_number=1)` | 执行登记的真实工具并记录调用与结果 |
| `context.run_native(module, max_rounds=3)` | 复用原生子流程；其回答记为 `lesson.stage_result`，返回字符串由外层组织最终回答 |
| `context.emit("lesson.step", data)` | 记录课程特有的 JSON 证据；自定义事件使用 `lesson.` 前缀 |
| `context.check_cancelled()` | 在阶段与副作用操作前响应平台停止请求 |

运行器可以是同步或异步函数。返回字符串时平台自动记录最终回答；也可以自行发布 `answer` 后返回 `None`。开始、结束和执行锁由平台管理，课程不能自行伪造生命周期事件。共享服务统一保留模型连接、事件快照、脱敏与回放；不要从课程另建 SSE、绕过连接管理直读密钥，或从回放触发执行。

停止是协作式的：长循环需要插入检查，已发出的网络请求仍受传输超时约束。本地进程中的可信课程代码不是沙箱。接入数据库、持久记忆、检索或框架时，仍需为该能力实现清楚的状态生命周期、适配与测试。第 10 课（`persistent-memory`）已提供教学用 SQLite 持久记忆实现，可参考其跨运行读取、版本冲突和过期处理；共享扩展接口本身不提供通用记忆服务。

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

`--root` 用于指向另一份项目或测试根目录，目录必须含 `curriculum/catalog.json`。生成器拒绝无效 slug、与目录不一致的 `--slug`、未知或已可用的课程、重复课程清单（无论清单写的是 slug 还是别名）和已存在的目标；通过链接跳出项目的目录同样拒绝。写入中断时可能留下新建的部分目录，工具会报告错误并保留文件供检查，不删除或覆盖已有工作。
