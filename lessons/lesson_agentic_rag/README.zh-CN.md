# Agentic RAG 与有上限的迭代（`agentic-rag`）

[English](README.md) · 简体中文

课程仍为 `planned`：实现、离线测试和中英双语内容已完成，还没有做真实模型验收。

## 本课的问题

静态 RAG 用问题原文检索一次、回答一次。遇到多跳问题（第二跳查什么取决于第一跳查到了什么），第一次检索漏掉的证据就再也找不回来。本课把检索封装成一个有契约的工具 `search_handbook`，让模型自己决定查什么、查几次；运行器负责三件事：

1. **记下每次尝试**：查询、切出的词、返回的片段、新增的片段（`lesson.attempt`）；
2. **发现重复**：词集合相同且 `top_k` 不更大的检索标为 `duplicate_of`，照常计数，下一轮在检索记录里点名（`lesson.harness_injected`）；
3. **到上限如实停下**：检索次数、模型调用数、时间三道上限，每次请求前检查；停止原因写进 `lesson.stop` 和实验报告（`lesson.report`）。

额外检索值不值，用同一题集上的程序检查来判断：引用的片段是否都来自本次检索、是否覆盖人工标注的全部小节，以及实际的模型调用数和服务商报告的 `total_tokens`（没报告写“未报告”）。

资料是共享的虚构语料《青石图书馆服务手册》（`lessons/lesson_document_loading/corpus/`），题目来自共享查询集 `corpus/queries.json`。检索复用 `lessons/lesson_keyword_retrieval/bm25.py` 的 BM25 索引和 `lesson_document_loading/chunking.py` 的默认分块。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `search_tool.py` | 工具定义、`Handbook.search`（参数校验 → 检索上限 → BM25 检索 → 尝试记录）、结构化错误 `InvalidQuery` / `SearchBudgetExhausted`、`cited_in_results`（引用是否来自本次检索） |
| `runtime.py` | 输入模型 `Inputs`；`stop_reason`（三道上限）；`progress_note`（检索记录）；`run_agentic`（有上限的循环）；`run_static`（静态基线）；`_report`（实验报告） |
| `locales/zh_CN.py`、`locales/en.py` | 运行时文本：工具描述、错误、系统提示词、检索记录、停止原因、报告标签 |
| `locales/fixtures/` | 离线测试脚本的查询与回答文字（只服务测试） |
| `fixtures.py` | 离线测试模型：每个练习一套固定的查询和最终回答，用量数字是脚本写的 |
| `test_lesson.py` | 工具契约、重复判断、四个练习、三道上限、引用检查、未报告的用量、模型提出的坏调用与永不停手的模型、轮间取消、正文里手算的检索结果、英文运行无中文、输入校验 |
| `content.json` / `content.en.json` | 教学内容与英文译文层 |

## 练习

| 练习 | 输入 | 离线测试模式下的结果（夹具扮演模型，检索真实执行） |
| --- | --- | --- |
| 静态 RAG：一次检索 + 一次回答 | `mode=static`，q11 | 1 次运行器发起的检索、1 次模型调用，引用只覆盖第一跳 |
| Agentic RAG：拆成子问题，补查第二跳 | q11，最多 4 次检索、5 次模型调用 | 2 次检索、3 次模型调用，两跳都覆盖，停止原因“模型判断证据已够” |
| 无答案问题：在预算内停下 | q07，最多 3 次检索 | 第 2 次检索被标为重复；3 次检索后停下，最后一次请求 `tool_choice=none`，回答资料不足、无引用 |
| 只允许 1 次检索 | q11，`max_searches=1` | 1 次检索、2 次模型调用，证据与静态 RAG 相同，停止原因“检索次数用完” |

可调输入：`mode`、`question_id`（q11、q12 多跳，q04 同义改写，q01 精确编号，q07、q08 无答案）、`max_searches`（1–6）、`max_model_calls`（2–8，最后一次留给最终回答）、`time_budget_s`（5–300 秒，用完不再请求模型）、`top_k`（1–5）。

## 实验看什么

- **多跳问题**：静态 RAG 的检索由运行器发起（`origin: course_program`）；循环里第一次查询是模型写的子问题，第二次带上了第一跳的“三楼”。对照两组的“引用覆盖人工标注”和模型调用数。
- **无答案问题**：空结果也是一次检索；重复检索的 `duplicate_of`、检索记录里的 `repeats`、`lesson.stop` 的原因、最后一次请求的 `tool_choice`。
- **预算只够一次检索**：两组引用检查结果相同，模型调用数不同，这是新增成本没换来收益的例子。

人工标注（`gold_covered`、报告里的覆盖检查）只给学习者看，从不发给模型。引用检查通过不等于回答文字正确，仍要读回答原文。

## 怎么运行

离线测试（确定性夹具 + 真实 BM25 检索，不需要密钥）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_agentic_rag.test_lesson -v
```

真实运行（课程开放后；会产生模型用量）：

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py agentic-rag agentic --url http://127.0.0.1:8765
.\.venv\Scripts\python.exe scripts/run_live.py agentic-rag no-answer --url http://127.0.0.1:8765 --locale en
```

**运行语言：**本课支持中文和英文运行。题目按运行语言从 `queries.json` 取，片段来自对应语言的语料；工具名、参数名、事件名和停止原因代码各语言相同。

## 参考与改写

- 《深入理解 AI Agent》（bojieli/ai-agent-book，Apache-2.0）第三章“智能体化 RAG”与配套 `chapter3/agentic-rag/`：检索做成工具、一次检索与分解检索的离线对照、检索预算与强制最终回答（`campaign.py`）。本课改为每次请求前检查三道上限、尝试记录每轮写回请求、引用由程序核对；代码由本项目编写。
- Microsoft AI Agents for Beginners（MIT）`05-agentic-rag`：迭代循环、在步骤之间保留状态以避免原地打转。
- Hugging Face Agents Course（Apache-2.0）`unit3/agentic-rag`：把检索作为 Agent 的一个工具。
- Mini-SWE-Agent（MIT）`agents/default.py`：每次请求模型之前检查步数、花费与墙钟时间上限。
