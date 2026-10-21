# 混合检索与重排（`hybrid-retrieval`）

[English](README.md) · 简体中文

课号按课程目录顺序计算，只在网页上显示；这里提到其他课一律写课程 ID。本课仍是 `planned`：实现、离线测试和教学内容已经写好，还没有用真实模型验收。

## 本课要解决的问题

`keyword-retrieval` 和 `embedding-retrieval` 各自留下了漏检：关键词检索读不懂同义改写（“滞纳金”找不到“逾期费用”），向量检索可能排不上编号查询（“R-305 有几个座位？”）。本课在同一份资料、同一组 14 条查询上比较三种检索，并处理检索进入真实使用后绕不开的三件事：

1. **合并**：关键词与向量结果按名次合并（倒数排名融合，RRF），不把 BM25 得分和余弦相似度放在一起比较。
2. **重排**：把融合后的前几条候选交给聊天模型重新排序，比较重排前后的命中，记下多出的调用和 Token。
3. **过滤与更新**：按元数据去掉被取代的旧版；资料修改或删除后，找出过期的向量，只重算需要的片段，保证旧片段不再作为当前证据。

本课的三个练习都只检查检索，不生成回答。命中与回答是否正确的区分留到 `rag-citations`。

## 文件导览

| 文件 | 作用 |
| --- | --- |
| `runtime.py` | 运行器：`compare`、`rerank`、`update` 三个流程，以及实验报告（`lesson.report`）的拼装 |
| `retrieval.py` | 三种检索：`embed_texts` 分批请求 Embedding（每批最多 `context.embedding_batch_limit` 条），`build_index`、`keyword_search`、`vector_search`、`hybrid_search`、`run_all` |
| `fusion.py` | `rrf`（按名次合并）与 `apply_filter`（元数据过滤，返回被去掉片段的记录）；签名由 RAG 核心约定，各课共用 |
| `rerank.py` | 重排请求的构造（候选换成 `c1`、`c2` 编号）与回答校验 `parse_order` |
| `index_update.py` | `.runtime/hybrid-retrieval/<语言>/` 下的工作副本、文件改动、指纹、增量更新计划、索引与指纹清单的存取 |
| `locales/zh_CN.py`、`locales/en.py` | 运行时文本：重排的系统提示词、报告标题与标签、判定文字 |
| `fixtures.py`、`fixture_vocab.json` | 只服务自动化测试的确定性 Embedding 与重排回答（见下文） |
| `test_lesson.py` | 行为测试 |
| `content.json`、`content.en.json` | 教学内容（中文源文本与英文译文层） |

共用模块：资料与分块来自 `lesson_document_loading`，BM25 与查询集来自 `lesson_keyword_retrieval`，向量索引来自 `lesson_embedding_retrieval/vector_index.py`。本课只 import，不修改它们。

## 练习

| 练习 | 模型请求（每批 10 条时） | 证据 |
| --- | --- | --- |
| 同一查询集比较三种检索（`compare`） | 6 次 Embedding：片段 4 批 + 查询 2 批 | 关键词、向量、混合各一份报告（各用自己的分数尺度）；只比名次的对照报告；“RRF 逐项计算” |
| 重排：同义改写查询（`rerank-synonym`，q06） | 5 次 Embedding + 1 次聊天请求 | 重排前后前 3 条的判定、候选池是否覆盖人工标注、回答校验、Token 总数、耗时、请求长度 |
| 重排：精确编号查询（`rerank-exact`，q02） | 同上 | 同上 |
| 元数据过滤与索引更新（`update`） | 6 次 Embedding：片段 4 批 + 查询 1 批 + 增量更新 1 批 | 过滤记录；资料变更后旧索引被判过期、失效片段；增量更新计划；重新载入后的五项检查 |

`update` 每次运行先把仓库里的资料复制到 `.runtime/hybrid-retrieval/<语言>/corpus/`，只改这份副本：`fees.md` 的逾期费用 0.5 改成 0.3（版本号改为 2026-10），删除 `hours-2025.md`。仓库里的资料不会被改动。索引存成 `vectors.json`（向量）和 `manifest.json`（资料版本与每个片段的指纹）两个文件，读回时互相校验。

## 怎么运行

离线测试（确定性夹具 + 真实 Python 检索、过滤、文件改动与索引读写）：

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_hybrid_retrieval.test_lesson -v
```

测试把工作目录指到 `.runtime/` 下的临时目录，结束后删除。

真实运行需要所选服务商同时配置了聊天模型和 Embedding 模型（没有 Embedding 模型时平台在开始前拒绝运行，错误码 `embedding_model_missing`）。课程转为 `available` 之后，可以在网页实验台运行，或者：

```powershell
.\.venv\Scripts\python.exe scripts/run_live.py hybrid-retrieval compare --url http://127.0.0.1:8765
.\.venv\Scripts\python.exe scripts/run_live.py hybrid-retrieval update --url http://127.0.0.1:8765 --locale en
```

真实运行会产生模型用量。截至本文，本课**没有做过真实模型验证**。

## 实验看什么

- **三种检索**：先分别打开三份策略报告，看同义改写和编号查询各自的判定；再看对照报告的“关键词命中、向量未命中”和“向量命中、关键词未命中”；最后按“RRF 逐项计算”手算一行。对照报告只比较名次与判定，不比较分数。
- **重排**：先看“候选里已经有全部人工标注的小节”，再比较左右两列带 ★ 的片段名次；成本看 Token 总数（服务商没报告时写“未报告”）、耗时和用户消息字符数。两组都跑，不预设哪一组会变好。
- **过滤与更新**：过滤记录里是被取代的 `hours-2025` 片段；资料变更后，“载入的索引被判定为过期”通过，用旧索引检索出现“来源已删除”“原文已修改”的片段；增量更新只重算 1 个片段；重新载入后五项检查全部通过。

## 测试夹具说明

`fixtures.py` 的 Embedding 不是模型：它按 `fixture_vocab.json` 里人工写的概念词表数词，每个概念一维，同义词落在同一维，编号没有维度，再加一个小常数避免零向量。重排夹具按同一张词表计算查询与候选的重合度来排序。它们只为让自动化测试得到确定的结果，不代表任何真实模型的检索表现；网页上没有夹具入口。

## 运行语言

本课支持中文和英文运行。查询来自共享查询集 `corpus/queries.json` 的对应语言，资料用对应语言的手册；重排系统提示词、报告文字和判定在 `locales/zh_CN.py` 与 `locales/en.py`。策略名（keyword、vector、hybrid）、过滤原因和更新计划的键是代码，各语言相同。

## 参考

- 《深入理解 AI Agent》（bojieli/ai-agent-book，Apache-2.0）第 3 章“混合检索：两全其美的艺术”“知识应该如何更新”，以及 `chapter3/retrieval-pipeline/`（`fusion.py` 的 RRF 与加权融合、重排阶段、按阶段看排名变化）。本课改写借鉴了 RRF 公式与 k=60、双编码器与交叉编码器的对比、失效内容按版本元数据在检索时过滤、索引是可重建派生物的说法；代码由本项目编写。
- Claude Cookbooks（MIT）`capabilities/contextual-embeddings/guide.ipynb`：BM25 + 向量 + RRF 的混合检索、先多取候选再重排、按 Pass@k 测量。本课借鉴了“重排只对少量候选做”和加权 RRF 的对照。
- Hugging Face Agents Course（Apache-2.0）`units/en/unit3/agentic-rag/invitees.mdx`（从 BM25 检索工具起步）与 `units/en/unit2/llama-index/components.mdx`（索引与元数据持久化，避免重复建索引）。
