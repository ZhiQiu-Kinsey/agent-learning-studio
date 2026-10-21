# 资料加载与分块（`document-loading`）

[English](README.md) · 简体中文

知识与检索类课程的第一课。模型一次读不下整套资料，检索要以小片段为单位，片段还得能指回原文；资料里写的“指令”只是数据。本课把一套固定的本地手册读成带来源的文档，切成能按行号核对的片段，比较两组分块参数，记录加载异常，并在拼请求时体现信任边界。课程状态仍是 `planned`。

## 语料

“青石图书馆服务手册”（英文 Bluestone Library Handbook）是本项目原创的虚构资料，模型对它没有先验知识。`corpus/zh-CN/` 与 `corpus/en/` 各 10 份 Markdown，同名文件行数相同、小节锚点相同；每份开头的文件头写着 `doc_id`、标题、版本、使用范围，`hours.md` 还写着 `supersedes: hours-2025`。`corpus/problems/<语言>/` 放 5 个问题文件，`corpus/queries.json` 是后面几课共用的 14 条查询（本课用跨段查询 `q09`、`q10` 和 `q03`）。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `loader.py` | 加载：`load_corpus(locale, include_problem_files=False)` 返回 `Document` 列表和 `LoadIssue` 列表；清洗不改行数；`trust` 一律是 `untrusted_data`；`corpus_version` 是全部文档摘要的组合 |
| `chunking.py` | 分块：整节优先、超预算退到行、按行装箱、`overlap_lines` 行重叠；片段 ID 为 `doc_id:起始行-结束行`；`PRESETS` 有 default / narrow 两组，按语言给字符预算 |
| `runtime.py` | 三个练习的运行器：片段目录与原文核对、跨段证据、加载记录、两种资料拼法的对照 |
| `locales/zh_CN.py`、`locales/en.py` | 发给模型和写进事件的全部文字（系统提示词、报告、问题类型说明） |
| `fixtures.py` | 只服务自动化测试的确定性回答 |
| `test_lesson.py` | 行为测试：真实加载与分块、逐片段对回原文、问题文件、标签转义、字符串判定、停止、预算、两种运行语言 |

`loader.py` 与 `chunking.py` 被 keyword-retrieval、embedding-retrieval、hybrid-retrieval、rag-citations、agentic-rag 直接导入，函数签名和行为不能改；`tests/test_rag_corpus.py` 守着语料与分块的设计检查。

## 练习

| 练习 | 调用模型 | 做什么 | 主要证据 |
| --- | --- | --- | --- |
| 两组分块参数：片段目录与跨段查询 | 否 | 同一次运行里用默认参数和窄参数各切一遍，逐个片段按行号对回原文件，检查跨段查询的证据能否落在一个片段里 | 三份 `lesson.report`：语料清单、两份片段目录（片段数、重叠重复的行、固定窗口会切断的行、定位检查）、跨段证据对照 |
| 加载异常：空文档、重复与解析失败 | 否 | 正常语料加问题文件一起加载，每个问题一条事件，核对每个文件都有去向 | 5 个 `lesson.load_issue`（empty、parse_error × 2、unsupported、duplicate），加载记录报告里“悄悄消失的文件”为 0 |
| 信任边界：资料里的伪装指令 | 是，2 次 | 把逾期费用规定和带伪装指令的读者留言交给模型，同一个问题问两次：资料混在指令里 / 资料加标签并声明不可信 | 每轮一条 `lesson.trust_framing` 和 `lesson.trust_result`（`verdict`、`source`），请求体逐字可查，报告并排列出两轮回答 |

确定性数字（离线、真实运行都一样）：中文默认参数 38 个片段、窄参数 82 个；英文 36 / 95。默认参数下两条跨段查询都能在一个片段里找齐证据，窄参数下都不能。

## 实验看什么

- **两组分块参数**：重叠多存的行换来了什么——跨段查询 `q09`（预约研讨室后迟到）在默认参数下落在 `rooms:19-27` 一个片段里；窄参数下答案片段从“签到与释放”的标题开始，过渡句留在前一个片段。本练习不做检索，结论只关于片段目录本身。
- **加载异常**：`notice-board.md` 记了 duplicate 但仍然载入；其余四个问题文件不载入；扫描到的 15 个文件全部有去向。
- **信任边界**：两轮的系统消息有什么不同；模型的实际回答；程序只做字符串判定（是否写出上限“20”、是否出现留言要求的说法），引用留言原文也会命中。回答来源写在报告和 `lesson.trust_result.source` 里。

## 运行

离线测试（确定性夹具，加载、分块和检查都真实执行）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_document_loading.test_lesson -v
```

真实运行：课程开放后在网页实验台运行，或用 `scripts/run_live.py document-loading <练习> --url http://127.0.0.1:8765 [--locale en]`。前两个练习不需要模型配置；“信任边界”会发 2 次模型请求。

## 验证情况

只做了离线验证：夹具给出的两轮回答是固定脚本（混在指令里那一轮照留言回答，加标签那一轮按资料回答），用来检验程序能记录、判定两种结果，不代表任何模型的表现。尚未用真实模型运行“信任边界”，正文也不预设真实模型的回答。

## 参考

分块策略与“片段丢失上下文”参考《深入理解 AI Agent》（bojieli/ai-agent-book，Apache-2.0）第 3 章与配套代码 `chapter3/contextual-retrieval/chunking.py`、`chapter3/retrieval-pipeline/evaluate.py`；来源标记与上下文层防御参考同书第 2 章；Document / Node 与元数据参考 Hugging Face Agents Course（Apache-2.0）`units/en/unit2/llama-index/components.mdx`；上下文感知检索的数字来自 claude-cookbooks（MIT）`capabilities/contextual-embeddings/guide.ipynb`。均为改写借鉴，没有复制代码。
