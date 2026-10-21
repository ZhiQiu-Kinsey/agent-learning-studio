# 关键词检索与 BM25（`keyword-retrieval`）

[English](README.md) · 简体中文

课号按课程表顺序计算，只在网页上显示；文件里提到其他课一律写课程 ID。本课仍是 `planned`：实现、离线测试和中英教学内容已经写好，还没有完成教学验收。

**本课不调用模型。**所有分数都由本地 Python 算出，同样的输入每次结果相同；离线测试和网页运行走的是同一段代码，没有夹具。

## 本课要解决的问题

`document-loading` 把“青石图书馆服务手册”切成了带编号的片段（中文 38 个、英文 36 个）。读者提问时，程序要从中挑出最可能有答案的几段，并说得出为什么是它们排在前面。本课用 BM25 做关键词检索：只看查询和片段共有哪些词，共有的词越稀有、出现次数越多、片段越短，分数越高。

本课要做到三件事：

1. 每条结果都能对应到片段编号（文件名和原文行号）与得分，得分能逐词拆开、手算核对；
2. 在固定的查询集（14 条，六类）上统计命中与漏检，并记下语料版本、查询集版本和参数，后面的课可以在完全相同的条件下复跑对照；
3. 每条漏检给出原因：同义改写为什么找不到，资料里没有答案时 BM25 为什么照样返回结果。

## 文件导览

| 文件 | 内容 |
| --- | --- |
| `runtime.py` | 运行器：三个练习共用 `build_index`（建索引并发 `lesson.index`）；`query_table` 跑整个查询集；`explain` 拆开一条结果的得分；`misses` 分析漏检和无答案查询；报告拼装放在文件末尾的 `_report_*` |
| `bm25.py` | BM25（RAG 核心模块，签名和行为不变，后续课程都导入它）：`tokenize`（英文小写词 + 停用词，中文字二元组 + 停用字）、`BM25Index.search/explain`、`Hit` |
| `query_set.py` | 查询集结构（RAG 核心模块）：`load_queries`、`query_set_version`、`judge`（按片段覆盖的小节判定 `hit`、`complete`、`first_rank`） |
| `stopwords.json` | 中英停用词表；中文分停用词和停用字两张表。代码里不写任何一种语言的词表 |
| `locales/zh_CN.py`、`locales/en.py` | 运行时文本：用资料说法重问的三条查询、报告标签、检查项和回答 |
| `test_lesson.py` | 行为测试：真实建索引与打分、逐项核对公式、参数与 `top_k` 的效果、漏检原因、结构化错误、输入校验、停止、两种运行语言、实验观察点 |
| `content.json`、`content.en.json` | 教学内容与英文译文层 |
| `lesson.json`、`lesson.en.json` | 实现清单与英文译文层 |

共用的语料、查询文字和分块在 `lessons/lesson_document_loading/`（`corpus/`、`corpus/queries.json`、`chunking.py`、`loader.py`）。

## 练习

| 练习 | 做什么 | 主要证据 |
| --- | --- | --- |
| 整个查询集的命中表 | 14 条查询各检索一次，取前 `top_k` 条（默认 5），对照人工标注判定 | 每条一个 `lesson.search`（切词结果、结果片段与逐词贡献、判定）；报告：命中率、完整覆盖率、平均倒数排名、漏检的查询、版本与参数、重建索引复跑是否逐条相同 |
| 拆开一条结果的得分 | 默认拆 `q03` 的第 1 名；可以改 `query_id`、自己写 `query`、指定 `chunk_id` | `lesson.score`：每个查询词的文档频率、逆文档频率（原值与取下限后）、词频、词频部分和贡献，长度与长度归一化系数；报告核对各词贡献之和等于得分，并给出默认参数下的得分作对照 |
| 漏检与无答案查询 | 同义改写的 3 条查询逐条找原因并用资料说法重问；2 条无答案查询看 BM25 返回什么 | 每条漏检一个 `lesson.miss`（原因 `no_shared_terms` 或 `outranked`、人工标注片段共有的词与名次、重问结果）；每条无答案查询一个 `lesson.no_answer`（返回几条、最高分） |

可调输入：`top_k`（1–10）、`k1`（0–3）、`b`（0–1）；“拆开”练习另有 `query_id`、`query`、`chunk_id`。网页问题框是学习者备注，只写进报告，不改变检索。

默认参数下两种语言的命中表都是：有人工标注的 12 条里命中 9 条、完整覆盖 7 条、平均倒数排名 0.75，漏检 `q04`、`q05`、`q06`。中文三条漏检都是一个词也不共有；英文 `q06` 与人工标注片段只共有 `after`，排第 9，把 `top_k` 调到 10 就能命中。

## 实验看什么

- **同一查询集上的关键词检索**（“前 5 条（默认）”对照“只看第 1 条”）：`lesson.index` 里的版本与参数；第一条查询的切词结果与第 1 名；判定里的 `hit`、`complete`、`first_rank`；报告表格、命中率、完整覆盖率（`top_k=1` 时明显下降而命中数不变）；复跑一致的检查。
- **拆开一条结果的得分**（默认、`b=0`、`k1=3` 三组）：逐词表；长度归一化系数（`b=0` 时为 1）；总分；“各词贡献之和等于结果得分”的检查；默认参数下的得分对照。
- **漏检从哪里来**：第一条漏检的原因和共有的词；用资料说法重问后的首个命中名次；无答案查询返回的条数和最高分；报告表格。

预测题：运行“前 5 条（默认）”会发出几条 `lesson.search` 事件（每条查询一条）。

## 运行

离线测试（不需要密钥；本课本来就不调用模型）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_keyword_retrieval.test_lesson -v
.\.venv\Scripts\python.exe -m unittest tests.test_rag_corpus -v   # 共用语料、BM25 与查询集的设计检查
```

课程开放后可以在网页运行，或用脚本运行并打印事件摘要（不产生模型用量）：

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py keyword-retrieval query-table --url http://127.0.0.1:8765
.\.venv\Scripts\python.exe scripts/run_live.py keyword-retrieval misses --url http://127.0.0.1:8765 --locale en
```

## 运行语言

本课支持中文和英文运行。查询文字按语言写在 `corpus/queries.json`，用资料说法重问的三条查询和报告文字写在 `locales/`；查询 id、人工标注锚点、片段编号、事件字段和漏检原因代码各语言相同。中文按字二元组切词，英文按词切分，所以两种语言的词表、平均长度和得分不同，命中表的结论一致。英文运行的事件里没有中文（`test_lesson.py` 检查）。

## 参考与借鉴

- 《深入理解 AI Agent》（bojieli/ai-agent-book，Apache-2.0）第三章“稀疏嵌入：从 TF-IDF 到 BM25”“混合检索”与检索指标一节，以及实验 3-5 `chapter3/sparse-embedding/`（`bm25_engine.py`、`README.md`）：BM25 公式与 RSJ 逆文档频率、`k1=1.5`/`b=0.75` 的起点、逆文档频率取下限、逐词贡献日志、编号整体保留、`recall@k` 实为命中率的脚注、“精确词找得准、同义词读不懂”的对照。
- Hugging Face Agents Course（Apache-2.0）`unit2/llama-index/components.mdx`：加载、索引、存储、查询、评测五个阶段，用固定评测衡量改动。
- Microsoft AI Agents for Beginners（MIT）`05-agentic-rag/README.md`：检索不理想时改写查询再检索、检索过程要可追溯（本课只作为通往 `agentic-rag` 的铺垫）。

只做了改写借鉴，没有复制代码或逐句翻译；中文字二元组切词、按小节锚点的人工标注、漏检原因分类、重问验证和全部实验由本项目编写。
