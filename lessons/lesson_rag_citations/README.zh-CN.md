# RAG 回答与引用（`rag-citations`）

[English](README.md) · 简体中文

本课要解决的问题：检索到的片段交给模型以后，怎样知道回答里的每条结论真的来自这些片段？本课让模型按结构化 JSON 回答，每条结论附上片段 ID 和原文摘录，再由程序逐条核对；答错时，先判断是检索没找到依据，还是模型用错了依据。检索用 `keyword-retrieval`（关键词检索）一课的 BM25（`lessons/lesson_keyword_retrieval/bm25.py`），不用 Embedding：每次运行只有生成请求，证据链短。检索方式不是本课重点，换成 `hybrid-retrieval`（混合检索与重排）一课的混合检索，后面的格式、核对和分类都不用改。资料是共享语料“青石图书馆服务手册”，问题取自共享查询集 `lessons/lesson_document_loading/corpus/queries.json`。

**状态：**`available`。2026-10-21 用 `claude-haiku-5-5` 对每个练习在每种运行语言下各做了一次真实运行，样本各一份（[验证记录](../../docs/verification/live-runs-2026-10-21.md)）。这是对一个模型的带日期记录，不保证其他模型。`unprovided` 检查只在离线夹具运行里出现；真实模型只引用了提供的片段。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `citations.py` | 引用核对（对外接口，`agentic-rag` 也会用）：`GroundedAnswer`（回答结构）、`parse_answer`（JSON 层与字段层）、`check_citation` / `check_answer`（先查存在、再查摘录与数字、按 `supersedes` 判断版本）、`classify`（检索/生成失败分类）、`CATEGORIES` |
| `runtime.py` | 运行器：`search_handbook` 检索 → `judge` 对照人工标注 → 请求模型 → 核对与分类 → 两份 `lesson.report` |
| `locales/zh_CN.py`、`locales/en.py` | 运行时文本：系统提示词、用户消息模板、分类与原因名称、报告文字 |
| `fixtures.py`、`locales/fixture/` | 离线夹具：只服务自动化测试，按请求里的问题和片段 ID 返回脚本写好的 JSON |
| `test_lesson.py` | 行为测试：真实 BM25 检索、引用核对的各个分支、两种运行语言、停止与输入校验 |
| `content.json`、`content.en.json` | 教学内容与英文译文层 |

`citations.py` 的稳定接口：

```python
parse_answer(raw: str) -> tuple[GroundedAnswer | None, list[str]]
check_answer(answer: GroundedAnswer, provided: Sequence[Chunk]) -> AnswerCheck
check_citation(citation: Citation, provided: Mapping[str, Chunk], replaced=None) -> CitationCheck
classify(check: AnswerCheck | None, *, hit: bool | None, complete: bool | None) -> tuple[str, tuple[str, ...]]
```

- `provided` 只放本次请求交给模型的片段：存在性是相对这一次说的，语料里有、这次没提供的片段也算“未提供”。
- `CitationCheck.reason`：`ok`、`not_provided`、`quote_too_short`、`quote_not_found`；`ClaimCheck.unmatched_numbers` 是结论里出现、却不在已找到摘录中的数字。
- `classify` 的 `hit` / `complete` 来自 `query_set.judge`（人工标注）；`None` 表示资料里没有答案。分类代码见 `CATEGORIES`，各语言的名称在 `locales/`。

## 练习

| 练习 | 查询 | 模型请求 | 要看的证据 |
| --- | --- | --- | --- |
| 有证据的问题 | q03 逾期费用每册最高多少？ | 1 | 请求里的 `<sources>`（含那条伪装成指令的读者留言）、`lesson.citation_check` 的引用核对 |
| 资料里没有的问题 | q07 图书馆有停车场吗？ | 1 | 检索仍返回 5 个片段；`insufficient_evidence` 与报告的 `declined` 检查 |
| 版本冲突的问题 | q13 周日几点闭馆？ | 1 | `conflicts` 同时引用 2026 版与 2025 版，`current` 由程序按 `supersedes` 算出 |
| 失败分类三题 | q04、q01、q10 | 3 | 检索未命中、引用了未提供的片段、命中后误用，三类各一 |

参数：`query` 可选查询集里的任一编号（q01–q14）或 `triage`；`top_k`（1–8，默认 5）是每道题交给模型的片段数。中文运行里把冲突题的 `top_k` 改成 3，2026 版的片段一个都进不了请求，分类会变成“检索：依据不全”。

## 实验看什么

1. **有证据、无证据和冲突资料问答**：同一套提示词和核对规则，只换问题。看 `tool_result` 里检索返回了什么、请求里片段怎样和问题分开、每条引用的 `exists` 与 `quote_found`、报告只列这次真正检查过的项。
2. **检索失败还是生成失败**：`lesson.retrieval_judge` 用人工标注判断依据有没有进请求；`lesson.citation_check` 记每条引用的核对与分类；第二份 `lesson.report` 数出检索失败和生成失败各几题。

能证明：这次检索提供了哪些片段、回答引用了哪些、每条引用是否在场、摘录是否逐字可查、数字是否一致，以及失败断在哪一环。不能证明：结论的意思与摘录一致（字符串检查分不出“最多”和“至少”），也不能说明模型或检索的整体水平。

## 怎么运行

离线测试（夹具 + 真实 BM25 检索与核对，不调用模型）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_rag_citations.test_lesson -v
```

真实运行（会产生模型用量）：

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py rag-citations triage --url http://127.0.0.1:8765 --locale en
```

## 诚实说明

- `fixtures.py` 只服务测试。“失败分类三题”里的两个生成错误（编造的片段 ID `borrowing:11-13`、把“5 个开放日”改成“7 个开放日”）由夹具故意写出，响应里的 `x_offline_fixture` 和 `lesson.citation_check` 的 `answer_source: offline_fixture` 都写明了来源；真实模型可能不犯这两种错。
- 夹具不报告用量，报告里的用量显示“未报告”。
- 2026-10-21 的真实模型运行（每个练习每种语言一个样本）改过关于两种生成错误的正文：真实模型可能不犯这两种错，`missing` 过长会记为回答格式不合格。见验证记录。

## 参考

- 深入理解 AI Agent（bojieli/ai-agent-book，Apache-2.0）第 3 章 RAG 基础、检索指标、知识更新与 RAG 的安全边界，第 2 章来源标记。
- Microsoft AI Agents for Beginners（MIT）`05-agentic-rag`；Hugging Face Agents Course（Apache-2.0）`unit3/agentic-rag`。
- claude-cookbooks（MIT）`misc/using_citations.ipynb`、`capabilities/retrieval_augmented_generation/guide.ipynb`、`capabilities/contextual-embeddings/guide.ipynb`。

只改写借鉴思路，没有复制代码或逐句翻译；语料、查询集、核对规则和实验由本项目编写。
