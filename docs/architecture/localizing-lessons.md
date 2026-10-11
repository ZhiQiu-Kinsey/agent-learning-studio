# 课程本地化：双语运行时与英文译文

[English](localizing-lessons.en.md) · **简体中文**

一课要同时支持中文和英文，需要两部分：运行时文本（发给模型、写进事件的文字）按运行语言写在 `locales/` 消息目录里；教学内容的英文放在译文层 `content.en.json`、`lesson.en.json`。
机制与约定见 [新增课程](adding-lessons.md) 的“多语言运行时”一节，本文是逐课操作的清单，适用于：

- 只写了中文运行时的新课，要补上英文；
- 改动已有课程的运行时文本（提示词、报告、工具描述）；
- 以后增加别的运行语言时，照同样的步骤做。

现有 24 课都已是中英双语。拿不准时照参考课做：**`chat-request`**（独立运行器）和 **`tool-selection`**（原生运行器）。

## 完成标准

- 每个练习的英文运行里**没有任何中文**：请求体、工具结果、`lesson.*` 报告、回答、`run_start` 都算；
- 中文运行与改造前完全一样；
- 读码页按界面语言显示对应的消息目录。

下面的命令全部通过才算完成：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.<课程目录>.test_lesson -v
.\.venv\Scripts\python.exe -m unittest discover -s tests          # 含 test_runtime_locales、test_lesson_experiments（两种语言）、test_english_text
.\.venv\Scripts\python.exe scripts/validate_lessons.py
.\.venv\Scripts\python.exe scripts/term_report.py --lesson <slug> --full
.\.venv\Scripts\python.exe scripts/migrate_content.py --check
.\.venv\Scripts\python.exe scripts/realign_notes.py --check
.\.venv\Scripts\python.exe scripts/export_curriculum.py --check
.\.venv\Scripts\python.exe scripts/translation_kit.py status --locale en   # 本课：译完，过期 0
.\.venv\Scripts\python.exe scripts/cjk_baseline.py                        # 再加 --check；本课的计数只许下降
```

这一步不需要真实模型。要起服务就用自己的端口（如 8791），不要占用使用者的 8765。保持每个文件原来的换行符（`git ls-files --eol` 可查）。

## 文件布局

```text
lessons/<课程目录>/locales/__init__.py   @dataclass(frozen=True) class Texts：每条消息一个字段
                                         texts_for = catalog(__name__, Texts)   # 来自 course.i18n
lessons/<课程目录>/locales/zh_CN.py      TEXTS = Texts(...)   # 源语言，逐字保留现在的中文
lessons/<课程目录>/locales/en.py         TEXTS = Texts(...)   # 英文
lessons/<课程目录>/locales/<部分>/...    被别的课导入的模块单独一个目录（见 tool-selection 的 locales/tools/）
lessons/<课程目录>/locales/<数据>/zh_CN.md、en.md   运行时读取的分语言数据文件（用 course.i18n.localized_file 读）
lessons/<课程目录>/README.md             英文，链接到 README.zh-CN.md
lessons/<课程目录>/README.zh-CN.md       中文，链接到 README.md
```

消息目录的模块文档字符串用英文（`"""<slug> runtime text: English."""`）。

## 清单

1. **盘点。** 列出所有会进入模型或事件的字符串：系统提示词、工具描述（含参数描述）、工具报错、预设问题与输入、报告的标题/摘要/标签/取值/表头、任务卡、提醒、`lesson.*` 标题、程序拼出的回答、抛进运行的错误（最终进了 `error` 事件或工具结果的 `ValueError("…")`）。用 `scripts/cjk_baseline.py`，再在 `runtime.py`、`tools.py`、`store.py`、`fixtures.py` 里搜中文，就能找全。
2. **建消息目录。** 字段名说明消息是什么（`report_title`、`label_prompt_tokens`、`not_a_number`），不按位置起名。模板用命名占位符：`"Round {round} of {limit}"` 配 `.format(round=…, limit=…)`，不要用 `+` 拼句子。值可以是 `str`、`tuple[str, ...]` 或 `dict[str, str]`（如代码 → 含义）。中文与现在的字面量逐字节相同，中文运行才不会变。
3. **改代码。** 在 `run` 开头取 `t = texts_for(context.locale)`，之后用 `t.<字段>`。不要在导入时计算和语言有关的模块常量（`DEFAULT_QUESTION = "…"` 改成在 `run` 里用 `t.default_question`）。把 `t`（或 `locale`）显式传给辅助函数，不用全局变量，也不用上下文变量。
   - **原生课：** `main.py` 导出 `setup(locale) -> AgentSetup(system_prompt, tools, available_tools)`；`main(locale=None)` 用 `cli_locale()` 读语言，再调 `run_cli(setup(locale), title=t.cli_title, examples=t.cli_examples, max_tool_rounds=…, locale=locale)`。`run_native` 只认 `setup`。
   - **工具：** `tool_definitions(locale)` 生成 JSON Schema 列表（工具名和参数名是代码，各语言相同；描述来自消息目录）。会报错的工具把消息目录作为**仅限位置的第一个参数**：`def divide(t, /, a, b)`，由 `available_tools(locale)` 用 `functools.partial(divide, texts_for(locale))` 绑定。模型的参数总是按名字传，换不掉 `t`；多传的参数仍是 `TypeError`。
   - **发送工具的独立运行器**导出或导入 `tool_definitions(locale)`，读码页才能把证据链接挂到工具函数上（`tool-proposals` 从 `tools.py` 导入）。
   - **平台方法：** `context.call_tool`、`context.execute_proposal`、`context.submit_call`、`context.run_native` 已经把 `context.locale` 传给 `course/`。直接调用 `course.runner.execute_tool` 时，要自己传 `locale`。
4. **`lesson.json`。** 在 `runtime` 里加 `"locales": ["zh-CN", "en"]`。每个自然语言的 `question`、`inputs` 值和 `input_defaults` 值改成 `{"zh-CN": "…", "en": "…"}`；数字、布尔和代码取值保持标量（双语课里含中文的普通字符串会被拒绝）。把消息目录文件加进 `sources`，放在带批注的代码文件之后、`fixtures.py` 之前（读码页按这个顺序打开文件，手机端测试会点第二个文件），并写 `"locale"`（`zh_CN.py` → `"zh-CN"`，`en.py` → `"en"`）；登记了哪个 `locales/` 目录，就要登记它的每种运行语言；`Texts` 所在的 `__init__.py` 可以不登记（参考课都没登记）。练习标题仍在 `lesson.en.json` 里翻译。
5. **`INPUT_MODEL`。** 不设中文默认值：自然语言字段不写默认值（由 `input_defaults` 按语言给出），或用与语言无关的值。`Literal` 选项写代码（`"mon"`，不写 `"周一"`），选项文字写在 `content.json` 的 `lab.inputs[].options`，走译文层。`test_runtime_locales` 会检查英文课的输入 Schema 里有没有中文。
6. **测试夹具。** 写成 `create_completion(exercise_id, inputs=None, locale="zh-CN")`，确定性回答按语言分开（在 `fixtures.py` 里写 `{"zh-CN": …, "en": …}`，夹具数据不进学习者看到的消息目录）。开头标记用 `server.offline.offline_marker(locale)`，工具结果汇总用 `result_answer(results, locale)`。工具照常真实执行。
7. **课程测试（`test_lesson.py`）。** 保留所有中文断言；文字不同的地方，再按 `locale="en"` 加同样的检查。构造上下文时写 `RunContext(..., locale=locale)`。断言用消息目录里的值（`texts_for("en").report_title`），不要重抄长字符串。课程代码里的文档字符串和注释用英文。
8. **注释与文档字符串。** 课程的 Python 文件和 `course/` 用英文；`server/`、`scripts/`、`tests/` 仍用中文。说明为什么，不复述代码。
9. **中文正文（`content.json`）。**
   - 引用运行时文本时，与中文消息目录逐字一致。
   - 改了名的代码名（`TOOLS` → `tool_definitions`，`SYSTEM_PROMPT` → 消息目录里的 `t.system_prompt`）要同步改正文、`code_notes`（≤ 60 字，名字必须在本课源码里）和概念卡的 `token`。
   - 分步讲解里的 `code` 片段是事实字段（不走译文层），写成与语言无关的形式（`"content": "……"`，注释用英文）。
   - 重新对准读码批注：`python scripts/realign_notes.py <课程目录>`。锚点消失的块它会拒绝处理，要手工改（新的 `line` 与 `anchor`）。再用眼睛核对块的 `start`/`end`：块的第一行被改写时，realign 可能把 `start` 移进上一个函数。
   - 要逐行讲解提示词，在 `locales/zh_CN.py` 上写 `annotated-source` 块（只写在源语言文件上，写明 `start`/`end`，块内每一行都在 `TEXTS` 的某个字段里）。英文目录里被覆盖的字段必须**行数相同**（两种语言都一句一行），平台按“哪个字段的第几行”把块换算到 `en.py`。这类块同样要满足批注密度。
   - 服务商没有报告的用量写“未报告”，“未知”只给确实无法知道的值（校验会拒绝“用量未知”这类写法，见 [术语与代码名](terminology.md)）。
10. **英文译文层（`content.en.json`）。**
    - 导出待译条目：`translation_kit.py export lesson:<slug> --locale en -o todo.json`；写好英文后先 `apply … --check`，再 `apply`。
    - 引用**英文**运行时文本的原文（`"not reported"`、英文系统提示词），不要再写旧的 `"中文" ("gloss")` 形式；`validate_lessons` 会拒绝这种写法。
    - 以代码名为键的路径（`code_notes.<名字>.note`）在名字改了以后也会变：先从 `content.en.json` **删掉旧键**，否则整份译文层被拒绝，这课会整课回落到中文。
    - 按下文“英文写法”写。
11. **README。** 英文 `README.md` 与中文 `README.zh-CN.md`，互相链接（`English · [简体中文](README.zh-CN.md)`）。说明运行语言；原生课写上 `--locale en`。
12. **基线。** 运行 `python scripts/cjk_baseline.py` 收紧 `tests/baselines/python-cjk.json`（只许下降；`locales/zh_CN.py` 与 `test_*.py` 豁免）。

## 踩过的坑

- **操作系统会本地化的值。** 中文 Windows 上 `datetime.tzname()` 返回“中国标准时间”。优先用与语言无关的数据（`tool-selection` 现在返回 `"UTC+08:00"` 这样的偏移）。无中文测试会抓到这类泄漏：改数据，不要用 mock 绕过。
- **共用模块。** `lesson_07_messages_context/runtime.py` 被 `context-budget` 和 `context-compaction` 导入；`lesson_10_persistent_memory` 的 `store.py` 被 `memory-lifecycle` 导入；`lesson_01_tool_selection/tools.py` 被 `tool-proposals` 和 `dependent-calls` 导入。给共用模块单独的消息目录（`locales/<部分>/`）和 `locale` 参数，并让每个导入它的课保持通过（这些课的 `sources` 要为自己的每种运行语言登记共用目录的文件）。
- **夹具导入运行器常量**（`prompt-experiments`、`orchestrator-evaluator`、`workflow-patterns`、`context-compaction`）：改为导入消息目录，或把 `locale` 传进去。
- **改了 `code_notes` 的名字**会让译文层的键悄悄失效（见第 10 步）。
- **`tests/test_code_reading.py`** 对部分课断言“本课新增”。消息目录字段以 `t.<字段>` 参与比较（按中文目录比较，两种语言结论一致），要有意识地更新预期。
- **观察点选择器**不能依赖文字取值：`test_lesson_experiments` 会在两种语言下跑每个实验组。
- **测试里拿报告标签当键：** 把标签映射回消息目录字段（见 `lessons/lesson_chat_request/test_lesson.py` 的 `metrics()`），一条断言就能覆盖两种语言。
- **工具内部抛出的报错**会变成模型读到的工具结果：它们是运行时文本，不是给开发者看的错误。
- **Markdown 数据文件**（`prompt-caching` 的手册、`skills-disclosure` 的 `SKILL.md`）会发给模型：放到 `locales/<名字>/zh_CN.md` 与 `en.md`，两份都登记 `locale`，用 `localized_file(directory, context.locale, ".md")` 读取。

## 不要做

- 翻译工具名、参数名、事件类型、JSON 键、`lesson.*` 事件名或 `Literal` 代码。
- 把夹具回答放进 `locales/`。
- 改变中文运行发出的内容。唯一的例外是把随操作系统或机器变化的文字换成与语言无关的数据，并在 PR 里说明。
- 在同一个改动里顺手改 `server/`、`course/` 或前端；需要平台改动时，单独提出来。

## 英文写法

面向学 Agent 原理的程序员：直白、技术化的英文（美式拼写），短句，先说结论。

- 按意思翻译，不按中文语序。不写营销词（powerful、seamless、delve、crucial、it's worth noting、in summary）。
- 原文的诚实区分一个都不能丢：“流程结束”（the run finished）、“请求成功”（the request succeeded）、“工具执行”（the tool executed）和“任务验收通过”（the task passed acceptance）各不相同；“未报告”是 not reported，“未知”是 unknown。不弱化也不加强原文的说法。
- 标题和短的界面标签用句首大写（sentence case），不用每词大写。全角标点换成英文标点。“第 2 轮”写 round 2，“第 3 行”写 line 3；课程引用保持 `{{lesson:<slug>}}`。
- 必须原样保留：`{{…}}` 占位符、每一段反引号里的代码、代码名、事件类型、字段名、文件名、JSON 键、模型与服务商名称，以及源文本里本来就是英文的标签（如 `"01 / REQUEST"`）。`translation_kit.py apply` 会拒绝占位符或行内代码不一致的译文。
- 课程术语用 `curriculum/glossary.json` 里的 `en` 名称，全文一致。中文引入课写“中文（English）”的地方，英文只写一次，正文里小写（专有名词和缩写除外）。英文里不写中英并列。
- 同一个练习、实验或实验组的标题，在一份文件里只用一种译法；练习标题以 `lesson.en.json` 为准。
- 英文文本里不能有中文。确需保留的（如参考书中文书名、讲分词时的中文例子）登记到 `server/vocabulary.py` 的 `ENGLISH_CJK_ALLOWED`，写明理由；规则见 [术语与代码名](terminology.md) 第 5 节。

界面上的固定叫法，英文必须与界面一致：

| 中文 | 英文 |
| --- | --- |
| 理解 / 读码 / 实验 / 自检 / 回顾（场景） | Understand / Code / Lab / Check / Review |
| 开始之前 | Before you start |
| 课程地图 / 完整课程表 | Curriculum map / Full syllabus |
| 实验台 / 运行观察台 | lab bench / run console |
| 运行记录 / 回放 | run record / replay |
| 舞台 / 胶片 / 时间线 | stage / film strip / timeline |
| 工具卡片 | tool card |
| 观察点 / 导览 | observation point / guided tour |
| 对照组、实验组 | arm（如 arm A） |
| 假设 / 预测 | hypothesis / prediction |
| 微型自测 | quick check |
| 实验报告 | lab report |
| 本课新增 | New in this lesson |
| 教学示意 · 非运行记录 | Illustration · not a run record |
| 深入一点 | Deep dive |
| 练习 / 实验 / 预设 | exercise / experiment / preset |
| 服务商 / 用量 | provider / usage |
| 标准化请求/响应 | SDK-standardized request/response |
| 原生 HTTP | raw HTTP |
| 百炼 | Bailian |
| 验收 | acceptance check / acceptance |
| 平台代码 / 课程代码 | platform code / lesson code |
| 测试夹具 | test fixture |
| 已实现 / 计划中 | available / planned |

拿不准的译法不要默默猜，在 PR 描述里列出来请审读的人看。
