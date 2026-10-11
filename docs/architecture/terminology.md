# 术语与代码名：写法、标注与检查

[English](terminology.en.md) · **简体中文**

课程正文里，读者可能停下来想“这是什么”的词分四类，每类在网页上的样子和作者要做的事不同。
规则由 `server/vocabulary.py` 检查，`validate_lessons` 和 `tests/test_lesson_vocabulary.py` 不通过就不能合入。

## 1. 四类词

| 类别 | 例子 | 网页上 | 作者要做的 |
| --- | --- | --- | --- |
| 课程概念 | 工具调用、上下文预算、任务卡、ReAct | 每页第一次出现处加下划线，悬浮卡给释义；**引入课**是实线渐变，其他课是点线（回顾） | 收进 `curriculum/glossary.json`，`first_lesson` 写最早用到它的可运行课；引入课第一次出现写成“中文（English）”，其他课只写中文 |
| 背景词 | 分词器、消融、基线、夹具、混淆矩阵 | 虚线下划线，悬浮卡标“背景知识” | 收进术语表，`kind` 写 `background`，不设 `first_lesson`；正文只写中文，任何课都不写英文并列 |
| 代码名 | `evidence`、`stop`、`lesson.plan`、`assistant` | 代码样式；作者写了说明的，带点线并可悬停 | 直接写名字，前端按本课登记的源码自动识别；正文要靠读者理解它的含义时，在 `content.json` 的 `code_notes` 写一条说明 |
| 普通词 | 重试、修订、提示词、JSON、HTTP、正则表达式 | 不标注 | 不收录 |

**收录标准。** 一个词进术语表，要满足下面任意一条：

- 它在 Agent / LLM 工程里有特定含义，和日常意思不同或更窄，比如“上下文”“终态”“召回”；
- 它会在两课以上出现，读者需要回顾；
- 它是有编程基础的人也未必懂的机器学习、测试或实验方法用语。

只在一课里出现、正文当场就讲清的词，比如“上下文压缩与探针问题”一课的“探针问题”，不收录。程序员都懂的词也不收录。

**名字要具体。** 中文没有词边界，匹配器会在更长的词里找到短名字，比如“验收器”里的“验收”。所以：

- 术语名和别名不要用常见的单字词或动词。“引用”改为“来源引用”，“产物”改为“A2A 产物”，去掉“压缩”“验收”这类别名。
- 名字确实会出现在意思不同的更长词组里时，在 `not_in` 里列出这个词组。例如“评估”的 `not_in` 写“评估者”，正文里的“评估者”就整个跳过。

## 2. 代码名与代码说明

后端从每课登记的 Python 源码（`lesson.json` 的 `sources`）取出标识符和短字符串字面量（运行时文本 `locales/` 只取标识符和字典键，字符串值是自然语言，不算代码名），再加上平台名字：

- 消息角色；
- JSON 字面量；
- 运行事件名和运行终态。

术语表里已有的名字会被去掉（术语优先），其余的一律放进课程详情的 `code_names`（`server/code_names.py`）。正文里写到这些名字时，前端显示成代码样式，不需要加反引号。

`code_notes` 只给正文**要靠读者理解含义**的名字写说明：

- 每条不超过 60 字，说清它是什么、在本课起什么作用，不复述正文；
- 名字必须真在本课源码里，也必须真在本课正文里出现，否则检查失败；
- 名字已经能说明自己的（`goal`、`add_numbers`），或者只是顺带提到的，不写说明。

```json
"code_notes": [
  {"name": "evidence", "note": "任务卡字段：验收要看哪条工具证据、满足什么条件（工具成功且结果为 42）。"}
]
```

正文里不能出现既不是术语、也不是本课代码名的小写英文词，比如 `tokenizer`、`live`、`regex`：

- 是术语，就收进术语表并写中文；
- 是本课以外的代码，就改写成中文说明；
- 是练习 id（如 `flow-rule`），就改用界面上的中文练习名。

## 3. 写法

- **先讲后用。** 一段最多引入两个新概念。概念卡里出现的新词，要么在术语表里（有悬浮卡），要么在卡片里当场说清。
- **一个东西一个叫法。** 用下表的统一用词；新课出现新的同义叫法时，先补进这张表。
- **英文只在引入课出现一次。** 中英并列太多会显得啰嗦：引入课写一次，其他课靠悬浮卡回顾。

| 统一用词 | 不再使用 |
| --- | --- |
| 工具结果（事件名写 `tool_result`） | 回执、工具回执、tool 回执、收据 |
| 验收器（判断任务是否完成）、验证器（泛指按规则检查的程序） | 校验器、检查器（指程序时） |
| 协议检查（`messages-context` 的 `validate_tool_history`） | 验证器、校验器 |
| 运行器（各课的运行代码）、运行层（概念） | 运行程序、课程程序 |
| 运行器发起的调用（事件字段写 `origin: course_program`，界面显示“运行器调用工具”） | 程序发起、课程程序发起 |
| 未报告（服务商没有报告的用量、缓存命中等数；英文 not reported） | 指这类数时的“未知” |
| 运行语言（一次运行用的语言，写在 `run_start` 的 `locale`）、运行时文本（`locales/` 里的提示词与消息） | 运行时语言、多语言提示词 |
| 白名单（名词）、登记（动词） | 允许列表、登记表 |
| 工具定义（整条定义）、工具描述（description 字段） | 工具说明、接口说明 |
| 调用提议（`tool-proposals` 引入） | 提议行动、行动请求、调用请求 |
| 调用 id（`tool_call_id`） | 调用标识 |
| 消息历史 | 会话历史、对话记录 |
| 轮数上限 | 轮次预算、有限轮数 |
| 提示词、系统提示词 | Prompt、system 提示 |
| 轨迹 | 正文里的 trace |
| 结构化错误 | 结构化观察、结构化失败 |
| 业务规则 | 领域规则 |
| 终态 | 运行生命周期结束 |
| 服务商 | 供应商 |
| 后端（本平台的服务进程） | 服务端 |
| 离线测试模式 | 离线模式、测试模式、offline |
| 真实运行 | live、现场 |
| 故障注入 | 离线注入 |
| Token | token |
| 分词器 | tokenizer |
| 并行 | 并发（只在说执行机制时用） |
| 模型调用数（统计口径） | 模型请求数、请求次数、调用次数 |
| 有上限的（循环） | 有界 |
| 迭代上限（`max_iters`；`reflection-revision` 引入） | 评估循环上限 |
| 评估者（角色）、评审（动作、事件、停止原因） | 评估循环、评估通过、评委 |
| 评审模型（`prompt-experiments` 引入，写“评审模型（LLM-as-a-Judge）”） | 评委、LLM 评审 |
| 推理模型（先生成推理内容、再给出回答的模型；背景词，只写中文，第一次出现可在括号里加一句中文解释，不写英文） | 先推理的模型、先推理再回答的模型、思考模型 |
| 人工标注 | 正文里的“标注”“gold” |
| 实验报告（实验台的报告面板） | 证据板 |
| 编码 Agent（Claude Code、Cursor 这类工具；背景词，不加英文括注） | 编程助手、编码助手 |
| 学习者备注 | 问题栏 |

“评审”和“评估者”的分界：

- “评审”指动作、事件和停止原因（评审意见、评审通过这类说法），也指 `reflection-revision` 里的评审模型；
- “评估者”只是 `orchestrator-evaluator` 里的角色名，与生成者相对；
- 单独的“评估”是术语表里的课程概念，由 `evaluation-sets` 一课引入（见 `curriculum/glossary.json` 的 `evaluation`），之前的课不用它指别的东西。

“未报告”和“未知”的分界：

- 服务商没有在响应里报告的数（用量、缓存命中、推理 Token）写“未报告”，英文 not reported：这个数可能存在，只是这次没给，也不能用本地估算或 0 冒充；
- “未知”只用于程序确实无法知道的值，英文 unknown；
- `validate_lessons` 与 `tests/test_lesson_vocabulary.py` 用 `server/vocabulary.py` 的 `UNREPORTED` 检查可运行课程的正文（各场景的全部可读文字）和 `code_notes` 说明，拒绝两种写法：
  - “用量”“Token”“命中”“命中数”“缓存命中”后面隔最多 4 个字（中间没有。；，、或换行）出现“未知”，如“用量未知”“Token 数未知”“缓存命中数仍未知”；
  - “未知”或“未知的”后面紧跟“用量”“Token 数”“命中数”，如“未知用量”“未知的用量”“未知命中数”。
- 这条正则只覆盖上面的说法；“记为未知”这类换了说法的句子，以及课程目录、术语表、导学里的文字，要靠作者自己检查。英文写法的对应检查见第 5 节。

单课内部的叫法也要固定。例如：

- `context-budget`：截取窗口；`context-compaction`：规则压缩、清理旧工具结果、摘要压缩、探针问题；
- `persistent-memory`：召回（命名空间已是课程概念，`persistent-memory` 引入，字段名写 `namespace`）；`memory-lifecycle`：范围（`scope`）、乐观并发控制、过时写入；
- `todo-planning`：运行层**插入**的消息；
- `plan-and-replan`：失败后重新规划（策略）、修订计划（动作）。

## 4. 作者流程（新课和改课都适用）

1. 写正文前，先查术语表和上面的统一用词表。
2. 写完运行 `.\.venv\Scripts\python.exe scripts/term_report.py --lesson <slug> --full`，看三样东西：
   - 本课引入、回顾、背景三类术语各有哪些；
   - 哪些代码名带了说明；
   - 还有哪些问题。
3. **通读正文，找中文术语。** 机器只能检查已收录的词，没收录的中文术语靠人工发现：
   - 逐段问自己：一个只学过前面几课的读者，会不会卡在这个词上？
   - 会卡住的，按第 1 节的标准决定是收进术语表还是当场讲清。
4. 运行 `validate_lessons` 和 `tests/test_lesson_vocabulary.py`，问题必须为零。

## 5. 英文文本的检查

上面的规则只看中文源文本。英文文字另有三条检查，由 `server/vocabulary.py` 的 `english_problems` 实现，`validate_lessons` 与 `tests/test_english_text.py` 不通过就不能合入。检查范围：

- 译文层：各课 `content.en.json`、`lesson.en.json`，`curriculum/` 下的 `catalog.en.json`、`glossary.en.json`、`onboarding.en.json`（逐条检查 `texts` 里的译文，过期条目也查）；
- 英文运行时文本：`lessons/*/locales/**/en.py`、`en.md` 与 `course/locales/en.py`（整份文件）；
- 英文界面文案：`frontend/src/i18n/locales/en/*.json`。

三条规则：

1. **不含中文。** 英文文字里不能有汉字、中文标点和全角字符。确需保留的写进 `ENGLISH_CJK_ALLOWED`，每条是“文件、文本路径、精确子串、理由”，文件和路径可以写 `*`。子串先从文字里去掉，剩下的不能再有中文；白名单里用不上的条目也会报出来，要删掉（`validate_lessons` 查写明文件的条目，`*` 条目由 `tests/test_english_text.py` 检查）。现有条目：
   - 任意文件：`(深入理解 AI Agent)`，参考书的中文原书名，括在英文书名后面，读者凭它找到原书；
   - `curriculum/onboarding.en.json` 的 `how-llm-works.tokens.paragraphs.1`：分词示例“函数式编程”和它切出的三段；
   - `lessons/lesson_reflection_revision/content.en.json` 的 `section-4.paragraphs.2`：`` `s-1０４２` ``，说明 Python 正则的数字类也匹配全角数字。
2. **没报告的数写 not reported。** 与第 3 节的 `UNREPORTED` 对应（`EN_UNREPORTED`），不区分大小写，拒绝两种写法：
   - usage、token count、cache hit、hit count，或 prompt / completion / reasoning / cached / input / output tokens 后面只隔系动词或 as、still 这类词（中间没有标点），可带冒号、括号或引号，接着是 unknown，如 “usage unknown”“cache hits: unknown”“prompt tokens (unknown)”；
   - unknown 后面紧跟上面这些名词，如 “unknown usage”“unknown token count”。
   单独的 tokens 不算（分词器里的 “unknown tokens” 是另一回事）。课程目录里只检查可运行课程的条目（`lesson.<slug>.*`）；规划中课程的条目和来源说明是计划文字，和中文一样暂不检查。
3. **不写“中文原文加英文注释”。** 运行时改成双语以前，英文译文只能引用中文原文，写成 `"未报告" ("not reported")`。现在英文运行发的就是英文，英文文字要直接引用英文运行时文本（`"not reported"`）。引号里含中文、后面紧跟括号和引号的写法一律拒绝，白名单不豁免。

英文文本的其他写法（句首大写、术语用术语表的 `en` 名称、界面固定叫法）见 [课程本地化](localizing-lessons.md) 的“英文写法”。
