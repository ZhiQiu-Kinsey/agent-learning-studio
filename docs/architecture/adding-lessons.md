# 新增课程与独立定制

[English](adding-lessons.en.md) · **简体中文**

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

生成目录为 `lessons/lesson_document_loading/`，包含 `lesson.json`、`content.json`、`README.md`、`__init__.py` 和冒烟测试 `test_lesson.py`。原生课程另有 `main.py`、`tools.py`、`fixtures.py`；定制课程另有 `runtime.py`。两类都带 `locales/` 消息目录（`__init__.py`、`zh_CN.py`、`en.py`），清单的 `runtime.locales` 已登记中英两种运行语言，练习问题按语言分别填写（见“多语言运行时”）。示例只验证接入通路，正文与练习明确标记待编写。

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

**实现目录映射规则：** `lessons/*/lesson.json` 的 `id` 必须等于 catalog 中的课程 slug（不能写别名），这是课程与实现之间唯一的映射；目录名只决定 Python 包名，不参与身份判断。最早的十门课沿用 `lesson_NN_<slug 的下划线形式>`（如 `lesson_01_tool_selection` ↔ `tool-selection`），目录名里的数字只是历史编号、不是课号，暂不改名；新课由生成器创建为 `lesson_<slug 的下划线形式>`（如 `lesson_document_loading`），不再带课号前缀。

**接口行为：**

- `GET /api/lessons`、`GET /api/lessons/{id}`、`GET /api/curriculum` 中每课都返回 slug `id`、`number` 与 `aliases`。
- `GET /api/lessons/{id}` 与 `POST /api/runs` 的 `lesson_id` 接受 slug 或别名，内部统一解析为 slug；`run_start` 事件与 `RunContext.lesson_id` 记录的始终是 slug。
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

**多语言：** 术语映射字段 `id`、`zh`、`en`、`first_lesson`、`kind` 只在源文件中维护，译文层不得改动。`curriculum/glossary.<语言>.json` 以术语 `id` 为键提供三项：显示名 `<id>.term`、释义 `<id>.definition`、该语言的别名 `<id>.aliases`（字符串数组，没有别的叫法写 `[]`；源文本是 `en`，英文名改了显示名与别名一起过期）。`GET /api/glossary?lang=en` 返回 `term`、`local_aliases` 与 `definition_locale`；没有译文的条目显示名用 `en`、释义回落中文。英文界面的悬浮卡只显示英文名，回落的中文释义标 `lang="zh-CN"`；英文正文按英文名与别名匹配术语（不分大小写、整词、最长优先、允许复数词尾，连字符等同空格），中文别名仍保留给回落成中文的段落。

## 节奏与读码规范（2026-10-03 起）

依据：16 门课的节奏与读码审计（见 [课程实施计划第 8 节](curriculum-plan-2026-10.md#8-第二轮节奏读码与课程表细化2026-10-03)）。新课与改课都按下面的规则写；能自动检查的已经接进 `validate_lessons` 与测试。

### 节奏

- **一课只学一件事。** 本课引入的课程概念（术语表里 `first_lesson` 是本课的 concept 条目）不超过 5 个；要讲第 6 个，先考虑拆课或挪到前后课。
- **一段最多引入两个新概念**，每节配一个具体例子（真实字段名、真实数字）。概念卡 3–4 张，只放本课最核心的几件事。
- **先跑一次。** `predict` 块放在第一道微测之前：学习者读完两三节就能去实验台跑第一次，而不是读完全部理解场景。
- **实验不超过 3 个**，每个实验的对照组不超过 5 个；每个实验都写清 `proves` 与 `does_not_prove`。
- **不调用模型的课**在课程简介和正文第一节写明“本课不调用模型”。
- **提到其他课写 `{{lesson:<slug>}}`**，后端换成“第 N 课”。显示课号随课程表插入新课而变化，正文、README、运行时字符串都不写死课号（测试会检查课程文本）。

### 读码

| 规则 | 怎么做 | 检查 |
| --- | --- | --- |
| 先读课程代码 | `lesson.json` 的 `sources` 把本课文件放前面；平台文件（`course/`）只在本课确实要讲它时列出 | 前端标出“平台”“测试夹具” |
| 每个读码块不超过约 40 行，每课最多 3 个块 | 一个块只讲一个职责；超长函数拆块或把与本课无关的行放进 `folds`；没放进读码块的代码仍可在文件视图里展开阅读 | 块数由 `tests/test_code_reading.py` 检查，行数人工把握 |
| 批注带锚点 | `notes[].anchor` 写该行必须包含的一段原文；源码移动后跑 `scripts/realign_notes.py` | `validate_lessons` |
| 批注密度 | 展示范围内每 8 个非空、未折叠行至少 1 条，连续无批注不超过 12 行；优先写函数签名、循环开头、停止条件 | `validate_lessons`、`tests/test_code_note_density.py`（旧块在只减不增的基线里） |
| 平台代码折叠 | 事件发布、计时、报告拼装等与教学点无关的行，用 `folds: [{id, start, end, label}]` 收起，label 说清折叠了什么（如“平台：发布报告事件”） | 折叠内不能有批注 |
| 行内注释 | `lessons/` 与 `course/` 的注释和文档字符串写英文（中文讲解放在读码批注里，批注有中英两份）；写“为什么”而不是复述代码；主循环按步骤编号（`# 1.`、`# 2.`） | 人工；文档字符串计入硬编码中文基线 |
| 本课新增 | 由后端从 `lessons/` 下的课程文件计算，不含平台与测试夹具 | 自动 |

运行器写法：把“记录证据”放在边界上。模型请求统一走 `context.complete`，模型提出的调用走 `context.execute_proposal`，运行器自己发起的调用走 `context.call_tool`；课程循环里只留本课要讲的步骤。报告事件（`lesson.report`）的组装放进一个 `_report(...)` 函数，读码块不展示它，或用 `folds` 收起。

### 验证

- 离线：课程测试、全部后端测试、`validate_lessons`、`migrate_content.py --check`；改了前端再跑构建、vitest、i18n 与相关 Playwright。
- 真实模型：每个练习至少真实运行一次（`POST /api/runs`，`mode: live`），核对事件、报告和正文的说法一致；结果写进执行记录。正文不预设真实运行的结果，只写能从事件检查的判断方法。

## 一个实现清单

```json
{
  "schema_version": 1,
  "id": "document-loading",
  "content": "content.json",
  "sources": [
    { "path": "lessons/lesson_document_loading/main.py", "language": "python" },
    { "path": "lessons/lesson_document_loading/tools.py", "language": "python" },
    { "path": "lessons/lesson_document_loading/locales/zh_CN.py", "language": "python", "locale": "zh-CN" },
    { "path": "lessons/lesson_document_loading/locales/en.py", "language": "python", "locale": "en" },
    { "path": "course/runner.py", "language": "python" }
  ],
  "exercises": [
    { "id": "small-context", "title": "短上下文实验",
      "question": { "zh-CN": "本课实际问题", "en": "The real question of this lesson" } }
  ],
  "runtime": {
    "kind": "native",
    "entrypoint": "main",
    "max_rounds": 3,
    "requires_model": true,
    "locales": ["zh-CN", "en"]
  },
  "testing": { "completion_factory": "fixtures:create_completion" }
}
```

`content` 相对于课程目录；`sources.path` 相对于项目根目录，必须落在允许公开的课程与平台源码范围内。不要加入本地密钥或配置。执行入口和测试 factory 只指向同一课内的可信 Python 模块，不从浏览器传入路径或导入地址。不同课程可以使用相同的练习 ID，测试 fixture 按课程隔离。

`main.py` 导出 `setup(locale)`，返回 `course.runner.AgentSetup(system_prompt, tools, available_tools)`，即可复用原生工具循环；它按运行语言给出系统提示词与工具定义（见下文“多语言运行时”）。每课可以引用已经存在的无副作用工具；源码清单应展示真实引用的实现。通用循环处理模型请求、工具调用与结果、错误和轮数上限。

确定性 fixture 是课程内的 `create_completion(exercise_id, inputs=None, locale="zh-CN")` 工厂，返回 `completion(body, api_key)`；支持多种运行语言的课按 `locale` 给出该语言的确定性回答。测试响应可以模拟模型决策，Python 工具必须实际执行；fixture 不作为学生网页的模型替代，也不解释自由输入。需要输入注入的测试练习可设 `offline_only: true`（网页不能真实运行它）。要让学习者在网页上亲手检验失败路径，优先改成本地练习：在 custom 运行器里让运行器构造有问题的调用（`context.submit_call`），并给这个练习声明 `requires_model: false`，例如 `fail-safely` 的两组故障注入。

用到 Embedding 请求的课再声明 `"testing": {"embedding_factory": "fixtures:create_embedding"}`：`create_embedding(exercise_id, inputs=None, locale="zh-CN")` 返回 `embedding(body, api_key)`，按 OpenAI 格式返回 `{"data": [{"index": i, "embedding": [...]}], "model": ..., "usage": ...}`，向量条数与 `body["input"]` 相同。确定性测试向量（例如按人工概念词表构造的小维度向量）只服务测试，在夹具注释里写明怎么构造。只发 Embedding 请求、不调聊天模型的课可以只声明 `embedding_factory`。声明了它的课，调用模型的练习默认都要 Embedding：真实模式下所选服务商没有 Embedding 模型时，平台在开始前拒绝运行（错误码 `embedding_model_missing`，前端翻译并引导去模型设置），不悄悄换模型；不发 Embedding 请求的练习写 `requires_embedding: false`，不调用模型的练习（`requires_model: false`）不需要写。

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
- **深入一层（`deep-dive`）**：放主线之外的背景、机制和手算例子，字段是 `title`、可选的 `summary`（折叠时显示的一句话）和 `paragraphs`（Markdown）。
  - 网页上默认折叠，主线不依赖它：不看也能完成本课，也不要把本课的核心概念只放在这里。
  - 它不是“节”，不计入“每连续三段讲解内至少有一个微型自测”的节奏；`summary` 与 `paragraphs` 里的术语、代码名和用词照常检查。
  - 理解页按作者排的位置渲染；前置导学的章节里，`deep-dive` 与 `flow`、`micro-quiz`、`misconception` 一样，跟在前一节后面。
- **实验**：`experiments` 中每个实验由以下部分组成：
  - `hypothesis`：可检验的假设；
  - `arms`：对照组，用 `exercise` 引用 lesson.json 的练习；
  - `observe`：观察点，带选择器（条件 `event`、`round`、`path`、`span_kind`、`name`，可加 `nth`）；
  - `guide`：导览，每步 `{ "text", "observe"?, "stage"? }`：一小段讲解（一两句），加上这段话要看的地方。`observe` 引用观察点，界面在学习者自己的运行里跳到证据并用遮罩框住（JSON 字段精确到行）；`stage` 写这一步讲的是哪个舞台角色（`user`、`runtime`、`model`、`tool`、`memory`），没有 `observe` 时框住该节点；两者都不填的一步居中显示，只用于开场。每个观察点都要讲到，每步的话不重复。观察点选择器匹配的是第一个符合的事件，路径只要存在就算命中（值为 null 也算）：同类事件有多个时用 `round` 或只在目标事件上出现的字段钉住，实在没有可钉的字段（如同一轮的第二个 `tool_call`）再写 `nth`，按运行顺序取第几个命中（从 1 数），否则导览会框到别的事件。`nth` 依赖事件顺序，真实运行的顺序和次数可能与确定性运行不同，能用字段钉住时优先用字段。指向报告里的某一条指标或检查时，给这一条加稳定的 `id`，路径写 `data.metrics[id=<id>]`（取数组里第一个 `id` 等于它的对象），不写 `data.metrics[5]` 这样的位置：报告增删条目时位置会变；
  - `conclusion`：`proves` 写能证明的，`does_not_prove` 写不能证明的。

  选择器的语义由 `server/selectors.py` 和 `frontend/src/content/selector.ts` 共同实现，两边跑同一份共享测试向量。`tests/test_lesson_experiments.py` 会用确定性运行逐个检查观察点和导览目标都能命中；在这次运行中找不到的证据，界面会如实显示“本次运行没有出现这条证据”。
- **预测**：`predict` 只能用能从真实事件计算出的规则（`count_events`），只和学习者自己的运行对照，示意和录制都不算。实验有多组时用 `arm` 写明预测的是哪一组，题目里用“”点名的也必须是这一组；网页只拿这一组练习的运行判定，屏幕上是别的练习的运行时显示“先运行这个练习”。
- **示意**：`flow` 块引用 `illustrations` 中的合成事件序列。这些事件必须通过 `server/illustrations.py` 的契约：
  - 调用与结果成对；
  - 调用 id 使用示例 id（含 `example`）；
  - 不出现耗时、用量、费用等执行测量值。

  `walkthrough` 是作者写的分步讲解，界面一律标注“教学示意 · 非运行记录”。
- **参数标签**：自定义运行器的 `INPUT_MODEL` 会导出 JSON Schema，前端据此生成参数控件。控件的标签、帮助和选项文字写在 `lab.inputs`，测试保证它与模型字段一一对应。枚举请用 `Literal`，不要用正则 `pattern`。
- **读码块**：`annotated-source` 的路径必须在本课 sources 中，行号必须真实存在。“本课新增”由后端从源码 AST 计算，不要手写。
- **术语与代码名**：课程概念只在引入课（`first_lesson`）第一次出现时写“中文（English）”，其他课只写中文；背景词不写英文并列。正文写到的源码名字自动显示为代码样式，需要解释的在 `content.json` 顶层 `code_notes` 写说明。完整规则与统一用词表见 [术语与代码名](terminology.md)；写完运行 `scripts/term_report.py --lesson <slug> --full`，`validate_lessons` 会拒绝有用词问题的可运行课程。

**版本与迁移**：旧版本内容会在加载时走 `server/content_migrations.py` 的迁移阶梯。写回磁盘并规范格式用 `scripts/migrate_content.py`，加 `--check` 只检查。修改 schema 后，运行 `scripts/export_content_schema.py`，再在 frontend 目录运行 `npm run content:types`；测试会检查三者同步。

**译文层（多语言）**：源语言是 zh-CN，其他语言是源文件旁的译文层，格式统一为 `{"schema_version": 1, "locale": "en", "texts": {路径: {"text": 译文, "source": 源文本摘要}}}`。网页按界面语言请求 `?lang=<语言>`，逐条合并：缺失或过期（源文本改了、摘要对不上）的条目回落到源文本，文件损坏或写了不可译路径时整份回落。

| 源文件 | 译文层 | 可译路径（以 id 为键） | 规则 |
| --- | --- | --- | --- |
| `lessons/*/content.json` | `content.<语言>.json` | `hero.headline`、`concepts.<条目>.title`、`inputs.<字段>.label` 等 | `server/content_overlay.py` |
| `curriculum/onboarding.json` | `onboarding.<语言>.json` | 同上，前面带章节 id | 同上 |
| `curriculum/catalog.json` | `catalog.<语言>.json` | `category.<id>.title`、`module.<id>.description`、`lesson.<slug>.title/summary/objectives.<n>/topics.<n>/acceptance.<n>/experiments.<n>.steps.<m>`、规划课的 `sections.<n>.gist`、`elective.<id>.*`、`source.<id>.role/adaptation`、`principles.<n>`、`title` | `server/data_overlay.py` |
| `curriculum/glossary.json` | `glossary.<语言>.json` | `<术语 id>.term/definition/aliases` | 同上 |
| `lessons/*/lesson.json` | `lesson.<语言>.json` | `subtitle`、`exercises.<练习 id>.title`、`ui.question_label`、`ui.question_help` | 同上 |

事实字段不能被覆盖：id、slug、状态、先修、课时、难度、正确答案、代码、选择器、URL，以及练习的 `question` 与预设输入（它们原样发给模型，属于运行事实）；源码、系统提示词和运行事件同理不经过译文层。运行时的文字按运行语言写在 `lesson.json` 与 `locales/` 消息目录里，见下文“多语言运行时”。课程级别与难度是固定取值，接口附带 `level_code`、`difficulty_code`，界面按代码翻译。译文里的 `{{lesson:<slug>}}` 按目标语言写成 “Lesson N”，没翻译的文本仍写“第 N 课”。

翻译用 `scripts/translation_kit.py`，目标写 `lesson:<slug>`、`onboarding`、`catalog`、`glossary`、`manifest:<slug>`：

```powershell
.\.venv\Scripts\python.exe scripts/translation_kit.py status --locale en                       # 各目标覆盖率与过期条数
.\.venv\Scripts\python.exe scripts/translation_kit.py export catalog --locale en -o todo.json  # 只导出缺失或过期的条目；--all 导出全部
.\.venv\Scripts\python.exe scripts/translation_kit.py apply catalog --locale en -i done.json --check   # 只校验
.\.venv\Scripts\python.exe scripts/translation_kit.py apply catalog --locale en -i done.json   # 合并写回，自动记源文本摘要
```

`apply` 拒绝不可译路径，以及占位符（`{{...}}`）或行内代码（反引号）与源文本不一致的译文。英文译文的术语一律用术语表的 `en` 名，标题只首字母大写，代码名、事件名与字段名原样保留。`scripts/validate_lessons.py` 报告每份译文层的覆盖率，结构错误直接失败。

**随课录制**：真实模型运行后，用 `scripts/export_recording.py --run <run_id> --name <名称>` 原样导出到 `lessons/<目录>/recordings/`。录制只能来自 live 运行，带源码哈希和完整性哈希；源码变化后会提示重新录制。

## 多语言运行时

界面和课程正文按界面语言显示（上一节的译文层）；运行时同样分语言：英文界面运行练习时，程序发给模型和写进事件的文字都是英文——系统提示词、工具描述、工具错误、练习问题与预设输入、`lesson.*` 报告的标签与取值、程序写出的回答、`course/` 平台消息。中文界面的运行与以前完全一样。语言是运行的一部分：创建运行时确定，记在 `run_start` 里，回放按记录原样显示。

### 运行语言怎么定

1. 前端创建运行时带上界面语言：`POST /api/runs` 的 `locale`。
2. 后端按本课 `lesson.json` 的 `runtime.locales`（没写时只有 `["zh-CN"]`）解析出运行语言，规则在 `course/i18n.py` 的 `resolve_locale`：完全相同的语言优先；其次是同一语言的其他地区写法（`en-US` → `en`，`zh-TW` → `zh-CN`）；都没有时用源语言 `zh-CN`。格式不合法的语言代码返回 422。
3. `RunContext.locale` 是解析后的语言；`run_start.data.locale` 记录它，回落时另记 `requested_locale`；运行存储的 `runs.locale` 与 `GET /api/runs` 也带上它（加入这一列之前的旧运行记为 `zh-CN`）。录制元数据（版本 2）带 `locale`，必须与 `run_start` 一致、且在本课 `runtime.locales` 里。
4. `GET /api/lessons/{id}?lang=` 与 `/code?lang=` 按同一规则返回 `runtime_locale`：练习问题、预设输入、系统提示词、工具定义和运行时文本文件都是这种语言。本课还不支持界面语言时，英文界面看到的是中文问题与中文源码，实验台写明“本课的运行器暂时只有中文版”；屏幕上的运行和界面语言不同时，回答区写明“这是一次中文运行”。

### 消息目录（`locales/`）

运行时文本写在类型化的消息目录里，每种语言一份 Python 文件：

```text
lessons/<目录>/locales/__init__.py   Texts：frozen dataclass，一个字段一条消息；texts_for = catalog(__name__, Texts)
lessons/<目录>/locales/zh_CN.py      TEXTS = Texts(...)   源语言
lessons/<目录>/locales/en.py         TEXTS = Texts(...)
```

- 代码里 `t = texts_for(context.locale)`，用 `t.system_prompt`、`t.report_title`。带变量的消息用具名占位符 `t.unknown_tool.format(name=name)`，不拼接字符串（各语言语序不同）。
- 字段可以是字符串、字符串元组或 `{键: 字符串}` 字典。`Texts` 少一个字段在导入时就报错；`tests/test_runtime_locales.py` 再逐个叶子比较两种语言的结构、类型和占位符，并检查英文目录里没有中文。
- 被多课共用的模块有自己的目录，例如 `lessons/lesson_01_tool_selection/locales/tools/` 只放 `tools.py` 的工具描述与错误；各课自己的系统提示词放在本课的 `locales/`。
- 平台消息（未知工具、参数不是对象、轮数用完、停止、模型调用超限、百炼连接错误、命令行提示）在 `course/locales/`。只给开发者看的编程错误直接写英文，不进目录。
- `texts_for` 对平台支持、但这个包没有对应文件的语言回落到源语言，所以只支持中文的课在英文请求下照常运行；不是运行语言的字符串（如 `fr`）是编程错误。

**为什么不用 gettext、Babel 或 Fluent：**提示词很长、有结构，学习者要逐字读到真正发出去的那一段。消息目录就是普通 Python 数据，读码页显示的文件就是运行时用的文本；gettext 用一段源语言原文作消息 id，中文读者读代码时只能看到英文 id（或反过来），也看不到另一种语言的完整提示词。我们需要的复数、日期格式化在运行时文本里几乎用不到，类型化的 dataclass 加一个通用测试就能保证各语言字段齐全、占位符一致。

### 清单与预设

- `runtime.locales`：本课的运行语言，必须含源语言 `zh-CN`，都在平台的 `RUNTIME_LOCALES` 里。
- 练习的 `question`，以及 `inputs`、`input_defaults` 里的自然语言值，按语言写成 `{"zh-CN": "…", "en": "…"}`；数字、布尔和代码取值（如 `Literal` 选项）照常写标量。支持多种运行语言的课里，含中文的标量会被拒绝。对象只用来表示“按语言分别填写”，键必须恰好是本课的运行语言。
- `INPUT_MODEL` 的自然语言字段不设中文默认值（不写默认值，由 `input_defaults` 按语言给出），否则英文界面的参数表单会露出中文，显式提交 `{}` 时英文运行也会带上中文。
- 输入控件的标签、帮助和选项文字仍写在 `content.json` 的 `lab.inputs`，走译文层。
- 加载后 `spec["exercises"]` 与 `spec["input_defaults"]` 是源语言那份，各语言的预设在 `spec["presets"][locale]`；后端用 `server/catalog.py` 的 `run_locale`、`lesson_presets` 取用。

### 原生课与独立运行器

- 原生课的 `main.py` 导出 `setup(locale) -> AgentSetup`：系统提示词来自本课目录，工具定义由 `tool_definitions(locale)` 生成（工具名和参数名是代码，各语言相同，只翻译描述），白名单由 `available_tools(locale)` 生成。工具函数需要报错文字时，把消息目录作为**仅限位置参数**放在最前面（`def add_numbers(t, /, a, b)`），用 `functools.partial` 绑定；模型的参数总是按名字传，换不掉它，多传的参数仍是 `TypeError`。
- 独立运行器在 `run(context)` 开头取 `t = texts_for(context.locale)`，报告、任务卡、提醒、程序写出的回答都用 `t`。
- `course/` 的函数带 `locale` 参数：`execute_tool(call, tools, locale)`、`run_agent(..., locale=)`、`send_bailian(..., locale=)`、`SDKCompletion(profile, locale)`；`RunContext` 自动传入。
- 命令行：`main(locale=None)` 用 `course.i18n.cli_locale()` 读 `--locale en`；根目录的 `main.py --locale en` 也一样。

### 读码页

- `sources` 里语言文件写 `locale`（文件名必须是 `zh_CN.py`、`en.py`），同一个目录要登记本课的每种运行语言；`__init__.py` 这类不分语言的文件不写。接口只返回运行语言那一份，角色是 `texts`（界面标“运行时文本”）。
- “本课新增”也比较运行时文本：`TEXTS` 的每个字段记为 `t.<字段>`，按源语言那份比较，提示词改了就显示为变化，各语言结论一致。
- 运行时文本也可以做读码块（讲提示词逐句写法的课需要）：块写在源语言文件上，写明 `start`、`end`，起止行、批注和折叠都落在字段里；块覆盖的字段在每种语言里行数相同（英文逐行对应中文，校验会检查）。英文界面里平台按“哪个字段的第几行”把块换算到 `en.py`，批注文字走译文层。读码块覆盖的运行时文本也计入批注密度。

### 测试夹具与检查

- fixture 写成 `create_completion(exercise_id, inputs=None, locale="zh-CN")`，确定性回答按 `locale` 分语言；开头的标记用 `server/offline.py` 的 `offline_marker(locale)`（英文是 `[Offline script answer] `），`result_answer(results, locale)` 同理。
- `tests/test_runtime_locales.py`：每课 × 每个练习 × 本课每种运行语言都离线跑通；英文运行的全部事件（请求体、工具结果、报告、回答、`run_start`）里没有中文；中文运行仍是中文；消息目录逐字段对应；英文课的输入 Schema 没有中文；语言回落与 `?lang=` 接口。
- `tests/test_lesson_experiments.py` 在每种运行语言下检查观察点与导览命中：选择器只能看事件结构，不能依赖某种语言的文字。
- `scripts/cjk_baseline.py --check`（`tests/test_python_cjk_baseline.py`）：`course/` 与 `lessons/` 的 Python 文件里含中文的字符串字面量（含文档字符串）只许减少；`locales/zh_CN.py` 和测试文件豁免。
- 正文与运行时文本保持一致：中文正文引用中文目录里的原文，英文译文层引用英文目录里的原文（不再写“中文原文加英文注释”）。读码批注在源码移动后用 `realign_notes.py` 重新对准，中英两份批注都要复核。

逐课改造的步骤清单、常见的坑和英文写法见 [课程本地化](localizing-lessons.md)。

## 独立运行器

选择 `--kind custom` 后，清单使用 `runtime.kind: custom`、`entrypoint: runtime:run`。自定义课程可以实现分支、图执行、多个阶段或本地算法，再按需要复用通用循环。

```python
from pydantic import Field
from course.execution import LessonInputs, RunContext
from lessons.lesson_document_loading.locales import texts_for


class Inputs(LessonInputs):
    # No default: lesson.json supplies the preset in the run's language.
    label: str = Field(min_length=1, max_length=200)


INPUT_MODEL = Inputs


def run(context: RunContext):
    t = texts_for(context.locale)
    context.check_cancelled()
    context.emit("lesson.step", {"title": t.step_title, "label": context.inputs["label"]})
    return t.done.format(label=context.inputs["label"])
```

前端把课程 `input_defaults` 与练习 `inputs` 合并后显示在可编辑 JSON 中。请求未传 `inputs` 时后端使用这份合并预设；显式提交的 `inputs`（包括 `{}`）直接交给该课 `INPUT_MODEL` 校验，不偷偷补入界面里已经删除的参数。模型需要继承 `LessonInputs`，未知字段会被拒绝，省略字段可使用 Pydantic 字段默认值。`context.inputs` 是校验后的字典。没有声明输入模型的课程默认拒绝额外输入。`question`、`exercise_id`、`lesson_id`、`mode` 可从上下文读取；原生课程问题不能为空，定制课程可只使用结构化输入，并自行校验任务所需字段。

上面的纯本地课程应声明 `requires_model: false`，不要求配置密钥，也不伪造模型请求。custom 课程里的单个练习也可以在 `exercises` 里声明 `requires_model: false`：这个练习不连接模型（`context.completion` 为空），界面按本地运行显示；其余练习沿用课程的声明。需要模型的定制课程声明 `requires_model: true`，使用平台方法：

| 方法 | 用途 |
| --- | --- |
| `context.complete(body, round_number=1, branch=None)` | 使用当前模型连接并记录请求、响应与表示方式；并行发出多个请求时给每个分支一个不同的 `branch`，时间线按它配对请求与响应 |
| `context.execute_proposal(tool_call, available_tools)` | 执行模型提出的一次调用：记录调用提议与工具结果，用同一个调用 id 配对。服务商漏发或发空调用 id 时，平台补一个本次运行内确定的 `synthesized_call_<轮次>_<序号>`，写回调用本身（课程放回历史的助手消息与工具消息因此用同一个 id，下一轮请求格式正确），`tool_call` 事件标 `id_synthesized: true`；记录的 `response` 保持服务商原样。不拒绝这类调用，是因为模型确实提出了它，拒绝会藏起真实的提议。事件挂在最近一次 `complete` 的轮次上，不分分支：目前没有课程在并行分支里执行调用提议，要这样做先给它加上显式的轮次与分支参数 |
| `context.call_tool(name, arguments, available_tools, round_number=1)` | 由运行器（不是模型）发起一次登记过的工具调用，并记录调用与结果 |
| `context.submit_call(name, raw_arguments, available_tools, round_number=1)` | 运行器原样提交一条调用（名字可以未登记，参数是原样的 JSON 字符串、可以是坏的），走与模型提议相同的检查；用于演示拒绝路径，事件标为运行器发起（`origin: course_program`，界面显示“运行器调用工具”） |
| `context.embed(texts, round_number=1, *, branch=None, dimensions=None)` | 发一次 Embedding 请求，返回 OpenAI 格式的响应。`request` / `response` 事件带 `endpoint: "embeddings"`，请求体与响应体如实记录（含完整向量），计入 `max_rounds` 预算。一次最多 `context.embedding_batch_limit` 条非空文本（百炼 10），课程自己分批，让每一批都是学习者看得到的请求；`context.embedding_model` 是这次运行的 Embedding 模型。格式见 [事件信封 v2](event-envelope-v2.md) 的“Embedding 请求” |
| `context.run_native(module, max_rounds=3)` | 复用原生子流程；其回答记为 `lesson.stage_result`，返回字符串由外层组织最终回答 |
| `context.emit("lesson.step", data)` | 记录课程特有的 JSON 证据；自定义事件使用 `lesson.` 前缀 |
| `context.check_cancelled()` | 在阶段与副作用操作前响应平台停止请求 |
| `context.locale` | 这次运行的语言（`zh-CN`、`en`）；课程代码用 `texts_for(context.locale)` 取运行时文本 |

运行器可以是同步或异步函数。返回字符串时平台自动记录最终回答；也可以自行发布 `answer` 后返回 `None`。开始、结束和执行锁由平台管理，课程不能自行伪造生命周期事件。共享服务统一保留模型连接、事件快照、脱敏与回放；不要从课程另建 SSE、绕过连接管理直读密钥，或从回放触发执行。

停止是协作式的：长循环需要插入检查，已发出的网络请求仍受传输超时约束。本地进程中的可信课程代码不是沙箱。接入数据库、持久记忆、检索或框架时，仍需为该能力实现清楚的状态生命周期、适配与测试。`lessons/lesson_10_persistent_memory/store.py` 提供教学用 SQLite 持久记忆实现（`persistent-memory` 讲保存、重开与召回，`memory-lifecycle` 讲版本冲突、过期与范围），可参考；共享扩展接口本身不提供通用记忆服务。框架课（LangChain、LangGraph）用 `course/frameworks.py` 的 `RunContextChatModel`、`execute_tool_calls` 和 `stream_graph`，模型调用、工具调用和图的每一步都经 `RunContext` 记录，框架输入单独记为 `lesson.framework_input`，协议课（MCP、A2A）用 `course/protocols.py` 启动本地服务进程并在停止时回收；两者都见 [架构说明](platform.md) 的“框架适配层与‘框架输入’标注”。

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

`evidence-board` 消费当前回放位置的 `lesson.report` 事件：`title`、`summary` 为文本，`checks` 为 `{label, passed, detail}` 数组，`metrics` 为 `{label, value}` 数组（两者都可带稳定的 `id`，供观察点按 `[id=…]` 选取），可选 `table` 为 `{columns: string[], rows: (string|number|boolean)[][]}`。同一运行可发布初稿、修复、最终等多份报告，界面允许选取并查看原始事件。只有真正执行过的检查才能标记通过，未执行项目应省略或不提供 `passed`。

指标和表格单元格按值的形状显示（`frontend/src/lesson-extensions/shared/reportValue.ts`）：数字用大号指标字体；短文本用正文字体；超过 32 字（单元格 160 字）或带换行的文本单独占一行，默认折叠成四行；对象和内容是 JSON 对象的字符串（如服务商用量）显示成键值列表，嵌套键用点号连接。值本身不改写，原始记录里仍是原样。

组件通过 `studio` 使用共享状态，通过 `children` 组合默认页面，并尊重 `active` 暂停离屏动效。专用观察图应使用当前回放位置的事件，不能总展示完整历史的最终状态。未知键、加载或渲染失败会退回默认视图；JSON 不能动态加载任意 URL、脚本或 HTML。新增组件后仍需构建前端，纯内容或 Python 课程更新通常只需重启后端。

## 工具限制

`--root` 用于指向另一份项目或测试根目录，目录必须含 `curriculum/catalog.json`。生成器拒绝无效 slug、与目录不一致的 `--slug`、未知或已可用的课程、重复课程清单（无论清单写的是 slug 还是别名）和已存在的目标；通过链接跳出项目的目录同样拒绝。写入中断时可能留下新建的部分目录，工具会报告错误并保留文件供检查，不删除或覆盖已有工作。
